from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from .config import Settings
from .repository import Repository
from .schemas import BoundsMm, DimensionsMm, Geometry, Matrix3, Orientation, ORIENTATION_MATRICES


class GeometryError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def extract_geometry(item_id: UUID, repository: Repository, settings: Settings, scale_correction: float = 1.0) -> Geometry:
    asset = repository.get_latest_asset(item_id)
    if asset is None or asset.stage.value != "ingested":
        raise GeometryError("asset_not_ready", "A validated GLB asset is required before geometry extraction.")
    asset_path = settings.runtime_dir / asset.storage_path
    output = settings.runtime_dir / "tmp" / f"{uuid4()}.geometry.json"
    command = [
        sys.executable, str(Path(__file__).with_name("geometry_worker.py")), str(asset_path), str(output),
        str(settings.limits.parser_memory_limit_mb), str(scale_correction),
    ]
    try:
        try:
            completed = subprocess.run(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=settings.limits.processing_timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired:
            raise GeometryError("geometry_timeout", "Geometry extraction exceeded the configured time limit.") from None
        if not output.exists():
            raise GeometryError("geometry_failed", "Geometry extraction failed safely.")
        result = json.loads(output.read_text(encoding="utf-8"))
        if completed.returncode != 0 or not result.get("ok"):
            code = result.get("code", "geometry_failed")
            messages = {
                "empty_geometry": "The model contains no usable geometry.",
                "nonfinite_geometry": "The model contains nonfinite vertices.",
                "degenerate_geometry": "The model is planar or degenerate and needs correction.",
                "bounds_failure": "The canonical bounds could not conservatively contain the model.",
                "geometry_failed": "Geometry extraction failed safely.",
            }
            raise GeometryError(code, messages.get(code, messages["geometry_failed"]))
    finally:
        output.unlink(missing_ok=True)

    dimensions = result["canonical_dimensions_mm"]
    clearance = result["clearance_mm"]
    geometry = Geometry(
        version=repository.next_geometry_version(item_id), asset_id=asset.id,
        aabb_mm=BoundsMm(minimum=tuple(result["aabb_min_mm"]), maximum=tuple(result["aabb_max_mm"])),
        canonical_dimensions_mm=DimensionsMm(width=dimensions[0], height=dimensions[1], depth=dimensions[2]),
        geometric_center_mm=tuple(result["geometric_center_mm"]),
        source_to_canonical=tuple(result["source_to_canonical"]),
        canonical_to_source=tuple(result["canonical_to_source"]),
        box_volume_mm3=result["box_volume_mm3"], mesh_volume_mm3=result["mesh_volume_mm3"],
        fill_ratio=result["fill_ratio"],
        clearance_mm=DimensionsMm(width=clearance[0], height=clearance[1], depth=clearance[2]),
        preview_camera_distance_mm=result["preview_camera_distance_mm"], scale_correction=scale_correction,
        requires_scale_confirmation=result["requires_scale_confirmation"], mesh_watertight=result["mesh_watertight"],
        orientations=tuple(
            Orientation(id=identifier, matrix=Matrix3(values=matrix))
            for identifier, matrix in ORIENTATION_MATRICES.items()
        ),
        warnings=tuple(result["warnings"]),
    )
    repository.save_geometry(item_id, geometry)
    return geometry
