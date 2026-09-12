from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import subprocess

from app.config import get_settings
from app.ingestion import IngestionError, _run_worker, validate_glb_structure
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
GLBS = ROOT / "assets" / "demo" / "glb"


def draft(client: TestClient) -> str:
    response = client.post("/api/items", json={"weight_g": 100, "priority_stars": 3, "display_weight_unit": "g"})
    assert response.status_code == 201
    return response.json()["id"]


def upload(client: TestClient, item_id: str, filename: str, payload: bytes):
    return client.post(
        f"/api/items/{item_id}/asset", content=payload,
        headers={"Content-Type": "application/octet-stream", "X-Upload-Filename": filename},
    )


def make_json_only_glb(document: dict) -> bytes:
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8")
    encoded += b" " * ((-len(encoded)) % 4)
    length = 12 + 8 + len(encoded)
    return struct.pack("<4sII", b"glTF", 2, length) + struct.pack("<I4s", len(encoded), b"JSON") + encoded


def read_document_and_binary(payload: bytes) -> tuple[dict, bytes]:
    json_length = struct.unpack_from("<I", payload, 12)[0]
    document = json.loads(payload[20:20 + json_length].rstrip(b" \x00"))
    binary_header = 20 + json_length
    binary_length = struct.unpack_from("<I", payload, binary_header)[0]
    return document, payload[binary_header + 8:binary_header + 8 + binary_length]


def rebuild_glb(document: dict, binary: bytes) -> bytes:
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8")
    encoded += b" " * ((-len(encoded)) % 4)
    binary += b"\x00" * ((-len(binary)) % 4)
    length = 12 + 8 + len(encoded) + 8 + len(binary)
    return (
        struct.pack("<4sII", b"glTF", 2, length)
        + struct.pack("<I4s", len(encoded), b"JSON") + encoded
        + struct.pack("<I4s", len(binary), b"BIN\x00") + binary
    )


@pytest.mark.parametrize(
    ("filename", "expected_min", "expected_max", "instances"),
    [
        ("nested_translation.glb", (1.1, 1.9, 2.95), (1.4, 2.1, 3.05), 1),
        ("nested_scale.glb", (-0.3, -0.05, -0.05), (0.3, 0.05, 0.05), 1),
        ("nested_rotation.glb", (-0.1, -0.15, -0.05), (0.1, 0.15, 0.05), 1),
        ("nested_matrix.glb", (0.25, 0.1, -0.15), (0.55, 0.3, -0.05), 1),
        ("repeated_instance.glb", (-0.4, -0.05, -0.025), (0.4, 0.05, 0.025), 2),
    ],
)
def test_nested_transforms_and_repeated_instances_have_world_bounds(
    filename: str, expected_min: tuple[float, ...], expected_max: tuple[float, ...], instances: int,
) -> None:
    with TestClient(app) as client:
        response = upload(client, draft(client), filename, (GLBS / filename).read_bytes())
    assert response.status_code == 200, response.text
    assert response.json()["bounds"]["minimum_m"] == pytest.approx(expected_min, abs=1e-6)
    assert response.json()["bounds"]["maximum_m"] == pytest.approx(expected_max, abs=1e-6)
    assert response.json()["mesh_instance_count"] == instances


@pytest.mark.parametrize("filename", ["bad_magic.glb", "truncated.glb", "invalid_json.glb"])
def test_malformed_assets_fail_without_artifacts(filename: str) -> None:
    temporary = get_settings().runtime_dir / "tmp"
    before = set(temporary.glob("*.part"))
    with TestClient(app) as client:
        item_id = draft(client)
        response = upload(client, item_id, filename, (GLBS / filename).read_bytes())
        status = client.get(f"/api/items/{item_id}/status").json()
        asset = client.get(f"/api/items/{item_id}/asset")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_glb"
    assert status["stage"] == "failed"
    assert status["error_code"] == "invalid_glb"
    assert asset.status_code == 404
    assert set(temporary.glob("*.part")) == before


def test_external_references_are_rejected() -> None:
    payload = make_json_only_glb({
        "asset": {"version": "2.0"}, "buffers": [{"byteLength": 4, "uri": "https://example.test/mesh.bin"}],
        "scenes": [{"nodes": []}], "scene": 0,
    })
    with TestClient(app) as client:
        item_id = draft(client)
        response = upload(client, item_id, "external.glb", payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "external_reference"


def test_nonfinite_transform_is_rejected_with_specific_code() -> None:
    document, binary = read_document_and_binary((GLBS / "known_box_300x200x100.glb").read_bytes())
    document["nodes"][0]["translation"] = [float("inf"), 0, 0]
    with TestClient(app) as client:
        response = upload(client, draft(client), "nonfinite.glb", rebuild_glb(document, binary))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "nonfinite_transform"


def test_invalid_mesh_index_is_rejected_before_parser() -> None:
    document, binary = read_document_and_binary((GLBS / "known_box_300x200x100.glb").read_bytes())
    index_view = document["bufferViews"][document["accessors"][1]["bufferView"]]
    corrupted = bytearray(binary)
    struct.pack_into("<H", corrupted, index_view.get("byteOffset", 0), 999)
    with TestClient(app) as client:
        response = upload(client, draft(client), "invalid-indices.glb", rebuild_glb(document, bytes(corrupted)))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_indices"


def test_empty_scene_fails_and_does_not_create_original_asset() -> None:
    document, binary = read_document_and_binary((GLBS / "known_box_300x200x100.glb").read_bytes())
    document["nodes"] = []
    document["scenes"] = [{"nodes": []}]
    with TestClient(app) as client:
        item_id = draft(client)
        response = upload(client, item_id, "empty.glb", rebuild_glb(document, binary))
        asset = client.get(f"/api/items/{item_id}/asset").json()
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_geometry"
    assert asset["stage"] == "failed"
    assert not (get_settings().runtime_dir / asset["storage_path"]).exists()


def test_oversized_content_length_is_rejected_before_asset_creation() -> None:
    with TestClient(app) as client:
        item_id = draft(client)
        response = client.post(
            f"/api/items/{item_id}/asset", content=b"x",
            headers={"X-Upload-Filename": "large.glb", "Content-Length": str(50 * 1024 * 1024 + 1)},
        )
        asset = client.get(f"/api/items/{item_id}/asset")
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "too_large"
    assert asset.status_code == 404


def test_resource_bounds_reject_excess_decoded_geometry() -> None:
    settings = get_settings()
    constrained = settings.model_copy(update={"limits": settings.limits.model_copy(update={"max_decoded_vertices": 1})})
    with pytest.raises(IngestionError, match="exceeds configured limits") as raised:
        _run_worker(GLBS / "known_box_300x200x100.glb", constrained)
    assert raised.value.code == "unreasonable_geometry"


def test_worker_timeout_has_recoverable_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="worker", timeout=0.01)

    monkeypatch.setattr("app.ingestion.subprocess.run", timeout)
    with pytest.raises(IngestionError) as raised:
        _run_worker(GLBS / "known_box_300x200x100.glb", get_settings())
    assert raised.value.code == "processing_timeout"


def test_original_is_saved_atomically_under_generated_path() -> None:
    source = GLBS / "known_box_300x200x100.glb"
    with TestClient(app) as client:
        item_id = draft(client)
        response = upload(client, item_id, "../../user-name.glb", source.read_bytes())
        asset = client.get(f"/api/items/{item_id}/asset").json()
    assert response.status_code == 200
    stored = get_settings().runtime_dir / asset["storage_path"]
    assert stored.name == "model.glb"
    assert stored.read_bytes() == source.read_bytes()
    assert "user-name" not in asset["storage_path"]
