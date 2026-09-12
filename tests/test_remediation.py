from __future__ import annotations

import time
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, repository
from app.repository import Repository


def carry_on() -> dict:
    return {"name": "Remediation carry-on", "internal_dimensions_mm": {"width": 550, "height": 350, "depth": 230}, "empty_weight_g": 2500, "baggage_limit_g": 10000, "clearance_mm": 8, "display_length_unit": "mm", "display_weight_unit": "g"}


def test_migrations_and_openapi_cover_durable_contract() -> None:
    with TestClient(app) as client:
        assert repository.schema_version() >= 3
        schema = client.get("/openapi.json").json()
        for path in ("/api/suitcases/{suitcase_id}", "/api/trips/{trip_id}/plan-jobs", "/api/plan-jobs/{job_id}", "/api/plans/{plan_id}/replan-jobs"):
            assert path in schema["paths"]


def test_old_database_fixture_migrates_forward() -> None:
    with tempfile.TemporaryDirectory(prefix="packright-old-db-", ignore_cleanup_errors=True) as directory:
        old_path = Path(directory) / "old.sqlite3"
        with sqlite3.connect(old_path) as connection:
            connection.execute("CREATE TABLE items (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("PRAGMA user_version = 1")
        old_repository = Repository(old_path)
        old_repository.initialize()
        assert old_repository.schema_version() >= 3
        with old_repository.connect() as connection:
            assert connection.execute("SELECT 1 FROM schema_migrations WHERE version=3").fetchone() is not None


def test_plan_job_replay_and_body_conflict() -> None:
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()[0]
        trip = client.post("/api/trips", json={"name": "Async plan", "suitcase": carry_on(), "selected_item_ids": [stock["id"]]}).json()["trip"]
        key = "plan-job-test"
        first = client.post(f"/api/trips/{trip['id']}/plan-jobs", json={"seed": 41}, headers={"X-Idempotency-Key": key})
        replay = client.post(f"/api/trips/{trip['id']}/plan-jobs", json={"seed": 41}, headers={"X-Idempotency-Key": key})
        conflict = client.post(f"/api/trips/{trip['id']}/plan-jobs", json={"seed": 42}, headers={"X-Idempotency-Key": key})
        assert first.status_code == replay.status_code == 202
        assert first.json()["id"] == replay.json()["id"]
        assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "idempotency_conflict"
        job_id = first.json()["id"]
        for _ in range(50):
            status = client.get(f"/api/plan-jobs/{job_id}").json()
            if status["status"] == "completed":
                assert status["plan_id"]
                break
            time.sleep(.02)
        else:
            raise AssertionError("plan job did not complete")


def test_trip_creation_keeps_every_selected_library_item() -> None:
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()[:3]
        response = client.post("/api/trips", json={"name": "Three-item judge trip", "suitcase": carry_on(), "selected_item_ids": [item["id"] for item in stock]})
        assert response.status_code == 201
        trip = response.json()["trip"]
        assert [entry["item_id"] for entry in trip["items"]] == [item["id"] for item in stock]
        assert all(len(entry["instances"]) == 1 for entry in trip["items"])


def test_demo_prepare_is_repeatable_and_reset_is_namespace_only() -> None:
    with TestClient(app) as client:
        stock = client.get("/api/library?kind=stock").json()[0]
        personal = client.post("/api/trips", json={"name": "Personal", "suitcase": carry_on(), "selected_item_ids": [stock["id"]]}).json()["trip"]["id"]
        prepared = client.post("/api/operations/demo/prepare")
        repeat = client.post("/api/operations/demo/prepare")
        assert prepared.status_code == repeat.status_code == 200
        assert prepared.json()["trip_id"] == repeat.json()["trip_id"]
        reset = client.post("/api/operations/demo/reset")
        assert reset.status_code == 200 and reset.json()["removed_records"] > 0
        assert client.get(f"/api/trips/{personal}").status_code == 200
        assert client.get(f"/api/trips/{prepared.json()['trip_id']}").status_code == 404


def test_custom_lifecycle_archive_and_restore_is_explicit() -> None:
    with TestClient(app) as client:
        draft = client.post("/api/items", json={"weight_g": 100, "priority_stars": 3, "display_weight_unit": "g"}).json()
        assert client.delete(f"/api/items/{draft['id']}").status_code == 200
        archived = client.get("/api/library?kind=custom&lifecycle=archived").json()
        assert archived and archived[0]["id"] == draft["id"] and archived[0]["lifecycle"] == "archived"
        assert client.post(f"/api/items/{draft['id']}/restore").status_code == 200
        assert client.get("/api/library?kind=custom&lifecycle=draft").json()[0]["id"] == draft["id"]
