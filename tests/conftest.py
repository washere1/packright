from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="packright-tests-")
os.environ["PACKRIGHT_RUNTIME_DIR"] = _TEST_RUNTIME.name
