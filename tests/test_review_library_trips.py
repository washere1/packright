from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from test_previews import prepared_item


def handling_from(item: dict, **changes) -> dict:
    handling = item["handling"]
    value = {key: handling[key] for key in (
        "category", "fragility", "compressibility", "stack_class", "can_support_weight",
        "liquid_risk", "legal_orientations", "access",
    )}
    value.update(changes)
    return value


def ready_uploaded_item(client: TestClient, scale: float = 1) -> tuple[str, dict]:
    item_id, _ = prepared_item(client)
    if scale != 1:
        client.post(f"/api/items/{item_id}/process", json={"scale_correction": scale})
    client.post(f"/api/items/{item_id}/enrich")
    item = client.get(f"/api/items/{item_id}").json()
    payload = {"name": "Packed box", "weight_g": 125, "priority_stars": 4,
               "handling": handling_from(item), "acknowledge_scale": scale != 1}
    confirmed = client.post(f"/api/items/{item_id}/confirm", json=payload)
    assert confirmed.status_code == 200, confirmed.text
    return item_id, confirmed.json()


def suitcase(limit: float = 10_000) -> dict:
    return {"name": "Carry-on", "internal_dimensions_mm": {"width": 550, "height": 350, "depth": 230},
            "empty_weight_g": 2500, "baggage_limit_g": limit, "clearance_mm": 8,
            "display_length_unit": "mm", "display_weight_unit": "g"}


def test_review_confirmation_versions_generated_and_user_values_separately() -> None:
    with TestClient(app) as client:
        item_id, first = ready_uploaded_item(client)
        review = client.get(f"/api/items/{item_id}/review").json()
        item = review["item"]
        second_payload = {"name": "Corrected box", "weight_g": 130, "priority_stars": 5,
                          "handling": handling_from(item, category="games"), "acknowledge_scale": False}
        second = client.post(f"/api/items/{item_id}/confirm", json=second_payload)
        saved = client.get(f"/api/items/{item_id}").json()
    assert first["generated_handling"]["provenance"] == "neutral_fallback"
    assert second.json()["version"] == 2
    assert second.json()["generated_handling"]["category"] == "other"
    assert second.json()["confirmed_handling"]["category"] == "games"
    assert saved["stage"] == "ready" and saved["name"] == "Corrected box"


def test_scale_acknowledgement_and_handling_consistency_are_required() -> None:
    with TestClient(app) as client:
        item_id, _ = prepared_item(client)
        client.post(f"/api/items/{item_id}/process", json={"scale_correction": .01})
        client.post(f"/api/items/{item_id}/enrich")
        item = client.get(f"/api/items/{item_id}").json()
        payload = {"name": "Tiny box", "weight_g": 100, "priority_stars": 3,
                   "handling": handling_from(item), "acknowledge_scale": False}
        missing_ack = client.post(f"/api/items/{item_id}/confirm", json=payload)
        payload["acknowledge_scale"] = True
        payload["handling"] = handling_from(item, stack_class="top_only", can_support_weight=True)
        inconsistent = client.post(f"/api/items/{item_id}/confirm", json=payload)
        review = client.get(f"/api/items/{item_id}/review").json()
    assert missing_ack.status_code == 422 and missing_ack.json()["detail"]["code"] == "scale_acknowledgement_required"
    assert inconsistent.status_code == 422
    assert "suspicious_scale" in review["questions"]


def test_stock_catalog_search_clone_and_custom_persistence() -> None:
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()
        search = client.get("/api/library?kind=stock&search=charger&category=electronics").json()
        source = next(item for item in stock if item["name"] == "Laptop")
        clone = client.post(f"/api/stock/{source['id']}/clone").json()
        client.patch(f"/api/items/{clone['id']}", json={"name": "Work laptop", "priority_stars": 5})
        custom = client.get("/api/library?kind=custom&search=work").json()
        stock_after = client.get("/api/library?kind=stock&search=Laptop").json()
    assert len(stock) == 12 and all(item["example_values"] for item in stock)
    assert {item["name"] for item in search} == {"Laptop charger", "Phone charger"}
    assert custom[0]["name"] == "Work laptop" and custom[0]["priority_stars"] == 5
    assert any(item["name"] == "Laptop" for item in stock_after)


def test_incomplete_draft_cannot_enter_trip_and_links_back_to_review() -> None:
    with TestClient(app) as client:
        draft = client.post("/api/items", json={"weight_g": 100, "priority_stars": 2, "display_weight_unit": "g"}).json()
        library = client.get("/api/library?kind=custom").json()
        trip = client.post("/api/trips", json={"name": "Draft test", "suitcase": suitcase()}).json()["trip"]
        added = client.post(f"/api/trips/{trip['id']}/items", json={"item_id": draft["id"], "quantity": 1, "priority_stars": 2, "must_pack": False})
    record = next(item for item in library if item["id"] == draft["id"])
    assert record["ready"] is False and record["review_route"].endswith(draft["id"])
    assert added.status_code == 409 and added.json()["detail"]["code"] == "item_not_ready"


def test_six_mixed_items_quantities_overrides_and_snapshot_are_stable() -> None:
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()
        clone = client.post(f"/api/stock/{stock[0]['id']}/clone").json()
        selected = [clone["id"], *[item["id"] for item in stock[1:6]]]
        trip = client.post("/api/trips", json={"name": "Six items", "suitcase": suitcase()}).json()["trip"]
        summary = None
        for item_id in selected:
            summary = client.post(f"/api/trips/{trip['id']}/items", json={"item_id": item_id, "quantity": 1, "priority_stars": 3, "must_pack": item_id == selected[0]}).json()
        initial_id = summary["trip"]["items"][0]["instances"][0]["id"]
        low_utility = summary["total_utility"]
        changed = client.post(f"/api/trips/{trip['id']}/items", json={"item_id": selected[0], "quantity": 2, "priority_stars": 5, "must_pack": True}).json()
        matching = next(entry for entry in changed["trip"]["items"] if entry["item_id"] == selected[0])
        snapshot = client.post(f"/api/trips/{trip['id']}/snapshot").json()
        client.patch(f"/api/items/{clone['id']}", json={"weight_g": 9999})
        reloaded_snapshot = client.get(f"/api/trips/{trip['id']}/snapshots").json()[0]
        reloaded_trip = client.get(f"/api/trips/{trip['id']}").json()
    assert len(changed["trip"]["items"]) == 6 and len(matching["instances"]) == 2
    assert matching["instances"][0]["id"] == initial_id
    assert all(instance["must_pack"] and instance["priority_stars"] == 5 for instance in matching["instances"])
    assert changed["total_utility"] > low_utility
    assert snapshot["item_snapshots"][0]["weight_g"] == reloaded_snapshot["item_snapshots"][0]["weight_g"]
    assert reloaded_trip["requested_item_weight_g"] > changed["requested_item_weight_g"]


def test_instance_limit_and_preflight_weight_warning_are_clear() -> None:
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()
        trip = client.post("/api/trips", json={"name": "Limits", "suitcase": suitcase(2600)}).json()["trip"]
        overweight = client.post(f"/api/trips/{trip['id']}/items", json={"item_id": stock[0]["id"], "quantity": 1, "priority_stars": 3, "must_pack": True}).json()
        too_many = client.post(f"/api/trips/{trip['id']}/items", json={"item_id": stock[1]["id"], "quantity": 24, "priority_stars": 3, "must_pack": False})
    assert "requested_items_overweight" in overweight["warnings"]
    assert too_many.status_code == 409 and too_many.json()["detail"]["code"] == "instance_limit"
