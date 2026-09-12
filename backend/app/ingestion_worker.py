from __future__ import annotations

import ctypes
import json
import os
import sys
from pathlib import Path


_job_handle = None


def apply_resource_limit(memory_mb: int) -> None:
    global _job_handle
    memory_bytes = memory_mb * 1024 * 1024
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        return

    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class BASIC_LIMITS(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
        ]

    class EXTENDED_LIMITS(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMITS), ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    limits = EXTENDED_LIMITS()
    limits.BasicLimitInformation.LimitFlags = 0x00000100 | 0x00002000
    limits.ProcessMemoryLimit = memory_bytes
    if not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    if not kernel32.AssignProcessToJobObject(handle, kernel32.GetCurrentProcess()):
        error = ctypes.get_last_error()
        if error != 5:
            raise OSError(error, "AssignProcessToJobObject failed")
    _job_handle = handle


def inspect_scene(path: Path, max_vertices: int, max_faces: int) -> dict:
    import numpy as np
    import trimesh

    loaded = trimesh.load(path, file_type="glb", force="scene", process=False)
    scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
    nodes = list(scene.graph.nodes_geometry)
    if not nodes:
        return {"ok": False, "code": "empty_geometry"}

    minima = []
    maxima = []
    vertices_total = 0
    faces_total = 0
    instances = 0
    for node_name in nodes:
        transform, geometry_name = scene.graph[node_name]
        transform = np.asarray(transform, dtype=np.float64)
        if transform.shape != (4, 4) or not np.isfinite(transform).all():
            return {"ok": False, "code": "nonfinite_transform"}
        mesh = scene.geometry.get(geometry_name)
        if mesh is None or not hasattr(mesh, "vertices"):
            continue
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0:
            continue
        if not np.isfinite(vertices).all():
            return {"ok": False, "code": "nonfinite_transform"}
        if faces.size and (not np.issubdtype(faces.dtype, np.integer) or faces.min() < 0 or faces.max() >= len(vertices)):
            return {"ok": False, "code": "invalid_indices"}
        vertices_total += len(vertices)
        faces_total += len(faces)
        instances += 1
        if vertices_total > max_vertices or faces_total > max_faces:
            return {"ok": False, "code": "unreasonable_geometry"}
        world = trimesh.transform_points(vertices, transform)
        if not np.isfinite(world).all():
            return {"ok": False, "code": "nonfinite_transform"}
        minima.append(world.min(axis=0))
        maxima.append(world.max(axis=0))
    if not minima:
        return {"ok": False, "code": "empty_geometry"}
    return {
        "ok": True,
        "bounds_min_m": np.vstack(minima).min(axis=0).tolist(),
        "bounds_max_m": np.vstack(maxima).max(axis=0).tolist(),
        "vertex_count": vertices_total,
        "face_count": faces_total,
        "mesh_instance_count": instances,
    }


def main() -> int:
    path, output, memory_mb, max_vertices, max_faces = sys.argv[1:]
    try:
        apply_resource_limit(int(memory_mb))
        result = inspect_scene(Path(path), int(max_vertices), int(max_faces))
    except BaseException:
        result = {"ok": False, "code": "processing_failed"}
    Path(output).write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
