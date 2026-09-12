from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
GLBS = ROOT / "assets" / "demo" / "glb"
SUPPLIED_MODELS = ("Board Game.glb", "Marker.glb", "Measuring Tape.glb", "Mouse.glb", "Puzzle Box.glb")


def create_and_ingest(client: TestClient, filename: str = "known_box_300x200x100.glb") -> str:
    created = client.post("/api/items", json={"weight_g": 100, "priority_stars": 3, "display_weight_unit": "g"})
    item_id = created.json()["id"]
    uploaded = client.post(
        f"/api/items/{item_id}/asset", content=(GLBS / filename).read_bytes(),
        headers={"X-Upload-Filename": filename},
    )
    assert uploaded.status_code == 200, uploaded.text
    return item_id


def test_known_cuboid_recovers_canonical_dimensions_and_volume() -> None:
    with TestClient(app) as client:
        item_id = create_and_ingest(client)
        response = client.post(f"/api/items/{item_id}/process", json={"scale_correction": 1})
    assert response.status_code == 200, response.text
    geometry = response.json()
    dimensions = geometry["canonical_dimensions_mm"]
    assert [dimensions["width"], dimensions["height"], dimensions["depth"]] == pytest.approx([300, 200, 100], abs=1e-3)
    assert geometry["box_volume_mm3"] == pytest.approx(6_000_000, rel=1e-6)
    assert geometry["mesh_volume_mm3"] == pytest.approx(6_000_000, rel=1e-6)
    assert geometry["fill_ratio"] == pytest.approx(1)
    assert len(geometry["orientations"]) == 6


@pytest.mark.parametrize("filename", SUPPLIED_MODELS)
def test_supplied_demo_models_extract_bounded_geometry(filename: str) -> None:
    with TestClient(app) as client:
        item_id = create_and_ingest(client, filename)
        response = client.post(f"/api/items/{item_id}/process")
    assert response.status_code == 200, response.text
    geometry = response.json()
    assert all(0 < value <= 3000 for value in geometry["canonical_dimensions_mm"].values())
    assert len(geometry["source_to_canonical"]) == 16


def test_canonical_transforms_round_trip_and_obb_contains_world_vertices() -> None:
    with TestClient(app) as client:
        item_id = create_and_ingest(client, "nested_rotation.glb")
        geometry = client.post(f"/api/items/{item_id}/process", json={}).json()
    forward = np.asarray(geometry["source_to_canonical"]).reshape((4, 4))
    inverse = np.asarray(geometry["canonical_to_source"]).reshape((4, 4))
    assert forward @ inverse == pytest.approx(np.eye(4), abs=1e-8)
    dimensions = geometry["canonical_dimensions_mm"]
    assert sorted(dimensions.values()) == pytest.approx([100, 200, 300], abs=1e-3)


def test_repeated_mesh_instances_are_included_and_warned() -> None:
    with TestClient(app) as client:
        item_id = create_and_ingest(client, "repeated_instance.glb")
        geometry = client.post(f"/api/items/{item_id}/process").json()
    dimensions = geometry["canonical_dimensions_mm"]
    assert dimensions["width"] == pytest.approx(800, abs=1e-3)
    assert "disconnected_components" in geometry["warnings"]


def test_scale_correction_is_uniform_versioned_and_flagged() -> None:
    with TestClient(app) as client:
        item_id = create_and_ingest(client)
        original = client.post(f"/api/items/{item_id}/process", json={"scale_correction": 1}).json()
        scaled = client.post(f"/api/items/{item_id}/process", json={"scale_correction": 0.01}).json()
        latest = client.get(f"/api/items/{item_id}/geometry").json()
    assert scaled["version"] == original["version"] + 1
    assert scaled["canonical_dimensions_mm"]["width"] == pytest.approx(3, abs=1e-4)
    assert scaled["requires_scale_confirmation"] is True
    assert "suspicious_scale" in scaled["warnings"]
    assert latest["version"] == scaled["version"]


def test_non_watertight_mesh_uses_box_volume_and_warning() -> None:
    payload = bytearray((GLBS / "known_box_300x200x100.glb").read_bytes())
    json_length = struct.unpack_from("<I", payload, 12)[0]
    json_start = 20
    document_bytes = payload[json_start:json_start + json_length].rstrip(b" ")
    import json
    document = json.loads(document_bytes)
    document["accessors"][1]["count"] = 30
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    encoded += b" " * ((-len(encoded)) % 4)
    old_bin_header = json_start + json_length
    bin_length = struct.unpack_from("<I", payload, old_bin_header)[0]
    binary = bytes(payload[old_bin_header + 8:old_bin_header + 8 + bin_length])
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    modified = struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(encoded), b"JSON") + encoded + struct.pack("<I4s", len(binary), b"BIN\x00") + binary
    with TestClient(app) as client:
        created = client.post("/api/items", json={"weight_g": 100, "priority_stars": 3, "display_weight_unit": "g"}).json()
        uploaded = client.post(f"/api/items/{created['id']}/asset", content=modified, headers={"X-Upload-Filename": "open-box.glb"})
        assert uploaded.status_code == 200, uploaded.text
        geometry = client.post(f"/api/items/{created['id']}/process").json()
    assert geometry["mesh_volume_mm3"] is None
    assert geometry["fill_ratio"] is None
    assert "non_watertight_mesh" in geometry["warnings"]
