"""Generate small, deterministic GLB fixtures without third-party packages."""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "demo" / "glb"


def padded(data: bytes, byte: bytes) -> bytes:
    return data + byte * ((-len(data)) % 4)


def make_glb(path: Path, nodes: list[dict], dimensions_m: tuple[float, float, float]) -> None:
    width, height, depth = dimensions_m
    vertices = [
        (x, y, z)
        for x in (-width / 2, width / 2)
        for y in (-height / 2, height / 2)
        for z in (-depth / 2, depth / 2)
    ]
    indices = [0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1,
               2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3]
    positions = b"".join(struct.pack("<3f", *vertex) for vertex in vertices)
    triangles = b"".join(struct.pack("<H", index) for index in indices)
    binary = padded(positions + triangles, b"\x00")
    document = {
        "asset": {"version": "2.0", "generator": "PackRight fixture generator"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "target": 34962},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(triangles), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
             "min": [-width / 2, -height / 2, -depth / 2], "max": [width / 2, height / 2, depth / 2]},
            {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR",
             "min": [0], "max": [7]},
        ],
    }
    json_chunk = padded(json.dumps(document, separators=(",", ":"), sort_keys=True).encode(), b" ")
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    glb = struct.pack("<4sII", b"glTF", 2, total_length)
    glb += struct.pack("<I4s", len(json_chunk), b"JSON") + json_chunk
    glb += struct.pack("<I4s", len(binary), b"BIN\x00") + binary
    path.write_bytes(glb)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "known_box_300x200x100.glb": ([{"mesh": 0, "name": "generated-demo-box"}], (0.3, 0.2, 0.1)),
        "nested_translation.glb": ([{"children": [1], "translation": [1, 2, 3]}, {"mesh": 0, "translation": [0.25, 0, 0]}], (0.3, 0.2, 0.1)),
        "nested_scale.glb": ([{"children": [1], "scale": [2, 1, 1]}, {"mesh": 0, "scale": [1, 0.5, 1]}], (0.3, 0.2, 0.1)),
        "nested_rotation.glb": ([{"children": [1], "rotation": [0, 0, 0.70710678, 0.70710678]}, {"mesh": 0}], (0.3, 0.2, 0.1)),
        "nested_matrix.glb": ([{"children": [1], "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0.4, 0.2, -0.1, 1]}, {"mesh": 0}], (0.3, 0.2, 0.1)),
        "repeated_instance.glb": ([{"children": [1, 2]}, {"mesh": 0, "translation": [-0.3, 0, 0]}, {"mesh": 0, "translation": [0.3, 0, 0]}], (0.2, 0.1, 0.05)),
    }
    for filename, (nodes, dimensions) in fixtures.items():
        make_glb(OUT / filename, nodes, dimensions)

    (OUT / "bad_magic.glb").write_bytes(b"NOT_A_GLB")
    (OUT / "truncated.glb").write_bytes(struct.pack("<4sII", b"glTF", 2, 2048))
    bad_json = padded(b"{ definitely not json", b" ")
    length = 12 + 8 + len(bad_json)
    (OUT / "invalid_json.glb").write_bytes(
        struct.pack("<4sII", b"glTF", 2, length) + struct.pack("<I4s", len(bad_json), b"JSON") + bad_json
    )
    manifest = {
        "generated": True,
        "source_units": "meters",
        "fixtures": {name: {"base_dimensions_m": dims} for name, (_, dims) in fixtures.items()},
        "malformed": ["bad_magic.glb", "truncated.glb", "invalid_json.glb"],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

