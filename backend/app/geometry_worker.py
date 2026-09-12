from __future__ import annotations

import json
import sys
from pathlib import Path

from ingestion_worker import apply_resource_limit


def extract(path: Path, scale_correction: float) -> dict:
    import numpy as np
    import trimesh

    loaded = trimesh.load(path, file_type="glb", force="scene", process=False)
    scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
    world_meshes = []
    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        mesh = scene.geometry.get(geometry_name)
        if mesh is None or not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
            continue
        transformed = mesh.copy()
        transformed.apply_transform(transform)
        world_meshes.append(transformed)
    if not world_meshes:
        return {"ok": False, "code": "empty_geometry"}

    combined = trimesh.util.concatenate(world_meshes)
    vertices = np.asarray(combined.vertices, dtype=np.float64)
    if not np.isfinite(vertices).all():
        return {"ok": False, "code": "nonfinite_geometry"}
    try:
        to_origin, raw_extents = trimesh.bounds.oriented_bounds(combined, angle_digits=1, ordered=True)
    except BaseException:
        return {"ok": False, "code": "degenerate_geometry"}
    raw_extents = np.asarray(raw_extents, dtype=np.float64)
    if not np.isfinite(raw_extents).all() or np.any(raw_extents <= 1e-9):
        return {"ok": False, "code": "degenerate_geometry"}

    order = np.argsort(raw_extents)[::-1]
    permutation = np.zeros((3, 3))
    permutation[np.arange(3), order] = 1.0
    if np.linalg.det(permutation) < 0:
        permutation[0] *= -1.0
    axis_transform = np.eye(4)
    axis_transform[:3, :3] = permutation
    to_canonical_m = axis_transform @ to_origin
    extents_m = raw_extents[order]
    converted = np.eye(4)
    converted[:3, :3] *= 1000.0 * scale_correction
    source_to_canonical = converted @ to_canonical_m
    canonical_to_source = np.linalg.inv(source_to_canonical)
    center_m = np.linalg.inv(to_canonical_m)[:3, 3]

    aabb = np.asarray(combined.bounds) * 1000.0 * scale_correction
    extents_mm = extents_m * 1000.0 * scale_correction
    transformed_vertices_mm = trimesh.transform_points(vertices, source_to_canonical)
    if np.any(np.abs(transformed_vertices_mm) - extents_mm / 2.0 > 1e-4):
        return {"ok": False, "code": "bounds_failure"}

    watertight = bool(combined.is_watertight)
    mesh_volume = abs(float(combined.volume)) * (1000.0 * scale_correction) ** 3 if watertight else None
    box_volume = float(np.prod(extents_mm))
    fill_ratio = min(1.0, mesh_volume / box_volume) if mesh_volume is not None and box_volume > 0 else None
    warnings = []
    if not watertight:
        warnings.append("non_watertight_mesh")
    if len(world_meshes) > 1 or combined.body_count > 1:
        warnings.append("disconnected_components")
    if len(combined.faces) > 200_000:
        warnings.append("high_polygon_count")
    plausible = float(extents_mm.max()) <= 2000 and float(extents_mm.max()) >= 10
    if not plausible:
        warnings.append("suspicious_scale")
    clearance = np.maximum(4.0, extents_mm * 0.02)
    camera_distance = float(extents_mm.max() / (2.0 * np.tan(np.radians(35.0) / 2.0)) * 1.25)
    return {
        "ok": True,
        "aabb_min_mm": aabb[0].tolist(), "aabb_max_mm": aabb[1].tolist(),
        "canonical_dimensions_mm": extents_mm.tolist(),
        "geometric_center_mm": (center_m * 1000.0 * scale_correction).tolist(),
        "source_to_canonical": source_to_canonical.reshape(-1).tolist(),
        "canonical_to_source": canonical_to_source.reshape(-1).tolist(),
        "box_volume_mm3": box_volume, "mesh_volume_mm3": mesh_volume, "fill_ratio": fill_ratio,
        "clearance_mm": clearance.tolist(), "preview_camera_distance_mm": camera_distance,
        "requires_scale_confirmation": not plausible, "mesh_watertight": watertight,
        "warnings": warnings,
    }


def main() -> int:
    path, output, memory_mb, scale = sys.argv[1:]
    try:
        apply_resource_limit(int(memory_mb))
        result = extract(Path(path), float(scale))
    except BaseException:
        result = {"ok": False, "code": "geometry_failed"}
    Path(output).write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
