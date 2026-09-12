from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
GLB = ROOT / "assets" / "demo" / "glb" / "known_box_300x200x100.glb"


def png(nonblank: bool = True) -> bytes:
    image = Image.new("RGB", (512, 512), "#ebe8df")
    if nonblank:
        ImageDraw.Draw(image).rectangle((120, 170, 392, 342), fill="#367759")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def prepared_item(client: TestClient) -> tuple[str, dict]:
    item = client.post("/api/items", json={"weight_g": 100, "priority_stars": 3, "display_weight_unit": "g"}).json()
    uploaded = client.post(f"/api/items/{item['id']}/asset", content=GLB.read_bytes(), headers={"X-Upload-Filename": "box.glb"})
    assert uploaded.status_code == 200
    geometry = client.post(f"/api/items/{item['id']}/process").json()
    return item["id"], geometry


def test_four_nonblank_views_and_thumbnail_are_cached_and_readable() -> None:
    with TestClient(app) as client:
        item_id, geometry = prepared_item(client)
        records = []
        for view in ("front", "side", "top", "three_quarter"):
            response = client.post(
                f"/api/items/{item_id}/previews?view={view}&geometry_version={geometry['version']}&renderer_version=test-r1",
                content=png(), headers={"Content-Type": "image/png"},
            )
            assert response.status_code == 200, response.text
            records.append(response.json())
        repeated = client.post(
            f"/api/items/{item_id}/previews?view=front&geometry_version={geometry['version']}&renderer_version=test-r1",
            content=png(), headers={"Content-Type": "image/png"},
        )
        listed = client.get(f"/api/items/{item_id}/previews?geometry_version={geometry['version']}").json()
        image_response = client.get(f"/api/previews/{records[0]['id']}")
        status = client.get(f"/api/items/{item_id}/status").json()
    assert repeated.json()["id"] == records[0]["id"]
    assert {record["view"] for record in listed} == {"front", "side", "top", "three_quarter", "thumbnail"}
    assert image_response.status_code == 200 and len(image_response.content) > 1000
    assert status["progress_stage"] == "enrichment"


def test_blank_and_stale_previews_are_rejected() -> None:
    with TestClient(app) as client:
        item_id, geometry = prepared_item(client)
        blank = client.post(
            f"/api/items/{item_id}/previews?view=front&geometry_version={geometry['version']}&renderer_version=test-r1",
            content=png(False), headers={"Content-Type": "image/png"},
        )
        stale = client.post(
            f"/api/items/{item_id}/previews?view=front&geometry_version=999&renderer_version=test-r1",
            content=png(), headers={"Content-Type": "image/png"},
        )
    assert blank.status_code == 422 and blank.json()["detail"]["code"] == "blank_preview"
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_geometry"
