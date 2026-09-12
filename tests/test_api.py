import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_safe_config() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": "packright-api", "api_version": "0.1.0"}

        config = client.get("/api/config")
        assert config.status_code == 200
        body = config.json()
        assert body["limits"]["max_upload_bytes"] == 50 * 1024 * 1024
        assert body["limits"]["solver_budget_seconds"] < 3
        assert body["capabilities"]["neutral_enrichment_fallback"] is True
        assert "key" not in config.text.lower()


def test_runtime_directories_created() -> None:
    with TestClient(app):
        from app.config import get_settings
        runtime = get_settings().runtime_dir
        assert all((runtime / name).is_dir() for name in ("assets", "previews", "tmp"))


def create_draft(client: TestClient, weight_g: float = 100, priority: int = 3) -> str:
    response = client.post("/api/items", json={
        "weight_g": weight_g,
        "priority_stars": priority,
        "display_weight_unit": "g",
    })
    assert response.status_code == 201
    assert response.json()["stage"] == "draft"
    return response.json()["id"]


def test_reference_glbs_complete_durable_ingestion() -> None:
    root = Path(__file__).resolve().parents[1]
    reference = json.loads((root / "assets" / "demo" / "scan-weights.json").read_text(encoding="utf-8"))
    with TestClient(app) as client:
        for row in reference["items"]:
            item_id = create_draft(client, row["weight_g"])
            payload = (root / "assets" / "demo" / "glb" / row["model"]).read_bytes()
            response = client.post(
                f"/api/items/{item_id}/asset",
                content=payload,
                headers={"Content-Type": "application/octet-stream", "X-Upload-Filename": row["model"]},
            )
            assert response.status_code == 200
            assert response.json()["stage"] == "processing"
            assert response.json()["received_bytes"] == len(payload)
            asset = client.get(f"/api/items/{item_id}/asset")
            assert asset.status_code == 200
            assert asset.json()["stage"] == "ingested"
            assert asset.json()["storage_path"].endswith("/model.glb")
            assert row["model"] not in asset.json()["storage_path"]


def test_duplicate_upload_warns_but_is_accepted() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = (root / "assets" / "demo" / "glb" / "known_box_300x200x100.glb").read_bytes()
    with TestClient(app) as client:
        first_id = create_draft(client)
        second_id = create_draft(client)
        first = client.post(f"/api/items/{first_id}/asset", content=payload, headers={"X-Upload-Filename": "box.glb"})
        second = client.post(f"/api/items/{second_id}/asset", content=payload, headers={"X-Upload-Filename": "box-copy.glb"})
        assert first.status_code == second.status_code == 200
        assert first.json()["warnings"] == []
        assert "matches an earlier upload" in second.json()["warnings"][0]


def test_bad_upload_returns_actionable_error_and_draft_can_retry() -> None:
    root = Path(__file__).resolve().parents[1]
    with TestClient(app) as client:
        item_id = create_draft(client, 94, 4)
        bad = client.post(f"/api/items/{item_id}/asset", content=b"not glb", headers={"X-Upload-Filename": "Mouse.glb"})
        assert bad.status_code == 422
        assert bad.json()["detail"]["code"] == "invalid_glb"

        payload = (root / "assets" / "demo" / "glb" / "Mouse.glb").read_bytes()
        retry = client.post(f"/api/items/{item_id}/asset", content=payload, headers={"X-Upload-Filename": "Mouse.glb"})
        assert retry.status_code == 200
        assert retry.json()["stage"] == "processing"
