import json
import struct
from pathlib import Path


def test_generated_glbs_have_consistent_headers() -> None:
    fixture_dir = Path(__file__).resolve().parents[1] / "assets" / "demo" / "glb"
    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["fixtures"]) == 6
    for filename in manifest["fixtures"]:
        payload = (fixture_dir / filename).read_bytes()
        magic, version, declared_length = struct.unpack("<4sII", payload[:12])
        assert magic == b"glTF"
        assert version == 2
        assert declared_length == len(payload)

