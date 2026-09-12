from __future__ import annotations

from itertools import combinations
import os
from pathlib import Path
from statistics import median
from time import monotonic
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repository import Repository
from app.schemas import (
    DimensionsMm, HandlingEdit, ItemInstance, LibraryItem, PackingPlan, PlanState, Suitcase, Trip,
    TripItem, TripSnapshot,
)
from app.selection import UTILITY, expand_snapshot, heaviest_first_baseline, lowest_star_first_baseline, select_candidates
from app.solver import solve_snapshot
from app.suitcases import SuitcaseBoundaryRequest, normalize_suitcase
from app.validation import validate_plan


def handling(*, support: bool = True, stack: str = "base", orientations=("xyz", "xzy", "yxz", "yzx", "zxy", "zyx"), access="normal") -> HandlingEdit:
    return HandlingEdit(category="test", fragility="low", compressibility="none", stack_class=stack,
                        can_support_weight=support, liquid_risk=False, legal_orientations=orientations, access=access)


def snapshot(specs, suitcase_dims=(300, 220, 180), allowance=5000) -> TripSnapshot:
    records = []; entries = []
    for index, spec in enumerate(specs):
        item_id = uuid4(); dims, weight, stars, mandatory = spec[:4]
        item_handling = spec[4] if len(spec) > 4 else handling()
        records.append(LibraryItem(id=item_id, kind="stock", name=f"Item {index}", category="test",
            dimensions_mm={"width": dims[0], "height": dims[1], "depth": dims[2]}, weight_g=weight,
            priority_stars=stars, handling=item_handling, ready=True, example_values=True))
        instance = ItemInstance(item_id=item_id, copy_number=1, priority_stars=stars, must_pack=mandatory)
        entries.append(TripItem(item_id=item_id, instances=(instance,)))
    suitcase = Suitcase(name="Test case", internal_dimensions_mm={"width": suitcase_dims[0], "height": suitcase_dims[1], "depth": suitcase_dims[2]},
                        empty_weight_g=1000, baggage_limit_g=1000 + allowance, clearance_mm=0,
                        display_length_unit="mm", display_weight_unit="g")
    trip = Trip(name="Fixed scenario", suitcase=suitcase, items=tuple(entries))
    return TripSnapshot(trip_id=trip.id, version=1, trip=trip, item_snapshots=tuple(records))


def test_metric_and_imperial_boundaries_are_equivalent_and_crud_persists() -> None:
    metric = SuitcaseBoundaryRequest(name="Metric", width=55, height=35, depth=23, length_unit="cm", empty_weight=2.5, baggage_limit=10, weight_unit="kg", clearance_mm=8)
    imperial = SuitcaseBoundaryRequest(name="Imperial", width=550 / 25.4, height=350 / 25.4, depth=230 / 25.4, length_unit="in", empty_weight=2500 / 453.59237, baggage_limit=10000 / 453.59237, weight_unit="lb", clearance_mm=8)
    first, second = normalize_suitcase(metric), normalize_suitcase(imperial)
    assert list(first.internal_dimensions_mm.model_dump().values()) == pytest.approx(list(second.internal_dimensions_mm.model_dump().values()))
    assert first.empty_weight_g == pytest.approx(second.empty_weight_g)
    with TestClient(app) as client:
        created = client.post("/api/suitcases", json=metric.model_dump(mode="json"))
        listed = client.get("/api/suitcases")
        updated_payload = metric.model_copy(update={"name": "Updated"})
        updated = client.patch(f"/api/suitcases/{created.json()['id']}", json=updated_payload.model_dump(mode="json"))
        deleted = client.delete(f"/api/suitcases/{created.json()['id']}")
    assert created.status_code == 201 and any(value["id"] == created.json()["id"] for value in listed.json())
    assert updated.json()["name"] == "Updated" and deleted.json()["deleted"] is True


@pytest.mark.parametrize("case", range(8))
def test_exact_selection_matches_independent_bruteforce(case: int) -> None:
    specs = [((45 + index * 3, 35, 25), 180 + ((index * 83 + case * 17) % 320), 1 + ((index + case) % 5), index == 0)
             for index in range(7)]
    snap = snapshot(specs, allowance=1200 + case * 40)
    result = select_candidates(snap, monotonic() + 2)
    instances = expand_snapshot(snap); mandatory = {item.instance_id for item in instances if item.must_pack}
    limit = snap.trip.suitcase.baggage_limit_g - snap.trip.suitcase.empty_weight_g
    brute = max((subset for size in range(len(instances) + 1) for subset in combinations(instances, size)
                 if mandatory.issubset({item.instance_id for item in subset}) and sum(item.weight_g for item in subset) <= limit),
                key=lambda subset: (sum(item.utility for item in subset), len(subset), tuple(sorted(str(item.instance_id) for item in subset))))
    assert sum(item.utility for item in result.candidates[0]) == sum(item.utility for item in brute)
    assert result.mode == "exact" and result.heuristic is False


def test_mandatory_rejections_and_priority_change_exclusion() -> None:
    oversize = snapshot([((400, 20, 20), 100, 5, True)], suitcase_dims=(200, 200, 200))
    with pytest.raises(Exception, match="mandatory item"):
        select_candidates(oversize, monotonic() + 1)
    low = snapshot([((100, 50, 50), 600, 1, False), ((100, 50, 50), 600, 5, False)], allowance=600)
    low_result = select_candidates(low, monotonic() + 1)
    assert low_result.candidates[0][0].priority_stars == 5
    changed_specs = [((100, 50, 50), 600, 5, False), ((100, 50, 50), 600, 1, False)]
    changed_snapshot = snapshot(changed_specs, allowance=600)
    changed = select_candidates(changed_snapshot, monotonic() + 1)
    assert changed.candidates[0][0].priority_stars == 5
    assert changed.candidates[0][0].item_id == changed_snapshot.item_snapshots[0].id


def test_near_limit_selection_is_labeled_heuristic_and_baselines_keep_mandatory() -> None:
    snap = snapshot([((30, 30, 30), 100 + index * 10, 1 + index % 5, index == 0) for index in range(24)], allowance=1300)
    result = select_candidates(snap, monotonic() + 1)
    limit = snap.trip.suitcase.baggage_limit_g - snap.trip.suitcase.empty_weight_g
    lowest = lowest_star_first_baseline(result.all_instances, limit)
    heaviest = heaviest_first_baseline(result.all_instances, limit)
    mandatory = result.all_instances[0].instance_id
    assert result.mode == "bounded_beam" and result.heuristic is True
    assert mandatory in lowest and mandatory in heaviest


def test_union_support_layout_is_independently_approved() -> None:
    specs = [
        ((96, 40, 96), 300, 3, True, handling(support=True, stack="base")),
        ((96, 40, 96), 300, 3, True, handling(support=True, stack="base")),
        ((196, 40, 96), 100, 3, True, handling(support=False, stack="top_only")),
    ]
    snap = snapshot(specs, suitcase_dims=(210, 100, 110), allowance=1000)
    repository = Repository(Path(os.environ["PACKRIGHT_RUNTIME_DIR"]) / f"support-{uuid4()}.sqlite3"); repository.initialize()
    repository.save_trip(snap.trip); repository.save_trip_snapshot(snap)
    plan = solve_snapshot(snap, repository, 1.5)
    assert plan.state == PlanState.FEASIBLE and plan.validation and plan.validation.valid
    elevated = [placement for placement in plan.placements if placement.position_mm[1] > 0]
    assert elevated and all(placement.support_ratio >= .8 for placement in elevated)


def test_reducing_suitcase_dimension_changes_fixed_scenario_feasibility() -> None:
    wide = snapshot([((140, 80, 80), 200, 3, True), ((140, 80, 80), 200, 3, True)], suitcase_dims=(300, 100, 100))
    narrow_trip = wide.trip.model_copy(update={"id": uuid4(), "suitcase": wide.trip.suitcase.model_copy(update={"internal_dimensions_mm": DimensionsMm(width=250, height=100, depth=100)})})
    narrow = wide.model_copy(update={"id": uuid4(), "trip_id": narrow_trip.id, "trip": narrow_trip})
    repository = Repository(Path(os.environ["PACKRIGHT_RUNTIME_DIR"]) / f"packing-{uuid4()}.sqlite3"); repository.initialize()
    repository.save_trip(wide.trip); repository.save_trip_snapshot(wide)
    first = solve_snapshot(wide, repository, 1.0)
    repository.save_trip(narrow.trip); repository.save_trip_snapshot(narrow)
    second = solve_snapshot(narrow, repository, 1.0)
    assert first.state == PlanState.FEASIBLE and first.validation and first.validation.valid
    assert second.state in (PlanState.INFEASIBLE, PlanState.SEARCH_EXHAUSTED)


SCENARIOS = [
    ([((60, 50, 40), 200, 3, False)] * count, (320, 220, 180), 5000) for count in range(1, 7)
] + [
    ([((100, 70, 45), 300, 5, True), ((80, 60, 40), 200, 2, False)], (220, 160, 120), 1000),
    ([((180, 60, 40), 250, 4, True, handling(orientations=("xyz",)))], (190, 80, 60), 500),
    ([((80, 40, 80), 200, 3, False, handling(support=False, stack="top_only")), ((80, 40, 80), 200, 3, False)], (100, 100, 180), 1000),
    ([((95, 30, 70), 250, 3, False)] * 4, (210, 100, 160), 1500),
    ([((70, 35, 70), 120, 3, False, handling(access="quick"))] * 5, (240, 120, 160), 1500),
    ([((40, 40, 40), 100, 1, False)] * 8, (180, 100, 180), 1000),
    ([((120, 45, 90), 500, 5, True), ((100, 45, 90), 450, 4, True)], (240, 100, 110), 1200),
    ([((130, 80, 60), 400, 2, False), ((130, 80, 60), 400, 5, False)], (150, 100, 80), 400),
    ([((55, 55, 55), 150, 3, False)] * 6, (190, 130, 130), 1200),
    ([((75, 30, 100), 180, 4, False, handling(orientations=("xzy", "xyz")))] * 3, (240, 120, 120), 1000),
    ([((90, 40, 60), 210, 3, True)] * 4, (200, 100, 140), 1000),
    ([((65, 45, 65), 170, 2, False)] * 7, (220, 150, 150), 1400),
    ([((50, 50, 100), 200, 3, False)] * 4, (220, 120, 120), 1000),
    ([((85, 35, 85), 190, 5, False)] * 5, (280, 100, 190), 1200),
]


def test_twenty_fixed_scenarios_are_bounded_and_truthful() -> None:
    runtimes = []
    for index, (specs, dimensions, allowance) in enumerate(SCENARIOS):
        snap = snapshot(specs, dimensions, allowance)
        repository = Repository(Path(os.environ["PACKRIGHT_RUNTIME_DIR"]) / f"scenario-{uuid4()}.sqlite3"); repository.initialize()
        repository.save_trip(snap.trip); repository.save_trip_snapshot(snap)
        plan = solve_snapshot(snap, repository, 2.75)
        runtimes.append(plan.runtime_ms)
        assert plan.runtime_ms < 3000
        assert plan.state in (PlanState.FEASIBLE, PlanState.INFEASIBLE, PlanState.SEARCH_EXHAUSTED)
        if plan.state == PlanState.FEASIBLE:
            assert plan.validation is not None and plan.validation.valid
            mandatory = {instance.id for entry in snap.trip.items for instance in entry.instances if instance.must_pack}
            assert mandatory.issubset({placement.instance_id for placement in plan.placements})
        else:
            assert plan.state != PlanState.FEASIBLE
    assert len(SCENARIOS) == 20
    assert median(runtimes) < 2750 and max(runtimes) < 3000


def test_plan_api_snapshots_solves_validates_and_reloads() -> None:
    suitcase_payload = {"name": "Solver case", "internal_dimensions_mm": {"width": 550, "height": 350, "depth": 230},
                        "empty_weight_g": 2500, "baggage_limit_g": 10000, "clearance_mm": 8,
                        "display_length_unit": "mm", "display_weight_unit": "g"}
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()
        trip = client.post("/api/trips", json={"name": "API solve", "suitcase": suitcase_payload}).json()["trip"]
        for item in stock[:6]:
            client.post(f"/api/trips/{trip['id']}/items", json={"item_id": item["id"], "quantity": 1, "priority_stars": item["priority_stars"], "must_pack": item["name"] == "Book"})
        created = client.post(f"/api/trips/{trip['id']}/plans", json={"seed": 11}, headers={"X-Idempotency-Key": "plan-once"})
        replay = client.post(f"/api/trips/{trip['id']}/plans", json={"seed": 11}, headers={"X-Idempotency-Key": "plan-once"})
        loaded = client.get(f"/api/plans/{created.json()['id']}")
        explanation = client.get(f"/api/plans/{created.json()['id']}/instructions")
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["state"] in ("feasible", "search_exhausted", "infeasible")
    if plan["state"] == "feasible": assert plan["validation"]["valid"] is True
    assert plan["runtime_ms"] < 3000 and loaded.json() == plan
    assert replay.status_code == 201 and replay.json() == plan
    assert explanation.status_code == 200
    assert len(explanation.json()["instructions"]) == len(plan["instructions"])


def test_independent_validator_rejects_corrupted_collision_and_dimensions() -> None:
    snap = snapshot([((80, 60, 40), 100, 3, True), ((80, 60, 40), 100, 3, False)], suitcase_dims=(220, 120, 120))
    repository = Repository(Path(os.environ["PACKRIGHT_RUNTIME_DIR"]) / f"corruption-{uuid4()}.sqlite3"); repository.initialize()
    repository.save_trip(snap.trip); repository.save_trip_snapshot(snap)
    plan = solve_snapshot(snap, repository, 1.0)
    assert plan.state == PlanState.FEASIBLE
    first, second = plan.placements[:2]
    collision = plan.model_copy(update={"placements": (first.model_copy(update={"position_mm": second.position_mm}), second)})
    wrong_dims = plan.model_copy(update={"placements": (first.model_copy(update={"dimensions_mm": DimensionsMm(width=1, height=1, depth=1)}), *plan.placements[1:])})
    assert "collision" in {violation.code for violation in validate_plan(collision, snap).violations}
    assert "wrong_dimensions" in {violation.code for violation in validate_plan(wrong_dims, snap).violations}


def test_preflight_respects_legal_orientation_and_item_padding() -> None:
    suitcase_payload = {"name": "Flat case", "internal_dimensions_mm": {"width": 300, "height": 100, "depth": 100},
                        "empty_weight_g": 1000, "baggage_limit_g": 5000, "clearance_mm": 0,
                        "display_length_unit": "mm", "display_weight_unit": "g"}
    with TestClient(app) as client:
        bottle = next(item for item in client.get("/api/library?kind=stock").json() if item["name"] == "Water bottle")
        trip = client.post("/api/trips", json={"name": "Orientation warning", "suitcase": suitcase_payload}).json()["trip"]
        summary = client.post(f"/api/trips/{trip['id']}/items", json={"item_id": bottle["id"], "quantity": 1, "priority_stars": 3, "must_pack": False}).json()
    assert f"oversize:{bottle['id']}" in summary["warnings"]


def test_demo_reset_is_scoped_and_processing_status_is_retryable_surface() -> None:
    suitcase_payload = {"name": "Personal case", "internal_dimensions_mm": {"width": 550, "height": 350, "depth": 230}, "empty_weight_g": 2500, "baggage_limit_g": 10000, "clearance_mm": 8, "display_length_unit": "mm", "display_weight_unit": "g"}
    with TestClient(app) as client:
        personal = client.post("/api/trips", json={"name": "Personal", "suitcase": suitcase_payload}).json()["trip"]["id"]
        seeded = client.post("/api/operations/demo/seed")
        assert seeded.status_code == 200
        demo_id = seeded.json()["trip_id"]
        status = client.get("/api/processing/status")
        reset = client.post("/api/operations/demo/reset")
        personal_loaded = client.get(f"/api/trips/{personal}")
        demo_loaded = client.get(f"/api/trips/{demo_id}")
    assert status.status_code == 200 and isinstance(status.json(), list)
    assert reset.status_code == 200 and reset.json()["removed_records"] >= 1
    assert personal_loaded.status_code == 200 and demo_loaded.status_code == 404
