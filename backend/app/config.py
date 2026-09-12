from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    max_upload_bytes: int = Field(gt=0)
    max_item_weight_g: float = Field(gt=0)
    max_dimension_mm: float = Field(gt=0)
    max_trip_instances: int = Field(gt=0)
    processing_timeout_seconds: float = Field(gt=0)
    parser_memory_limit_mb: int = Field(ge=128, le=4096)
    max_glb_json_bytes: int = Field(gt=0)
    max_scene_nodes: int = Field(gt=0)
    max_decoded_vertices: int = Field(gt=0)
    max_decoded_faces: int = Field(gt=0)
    max_preview_bytes: int = Field(gt=0)
    max_preview_dimension_px: int = Field(ge=256, le=4096)
    model_timeout_seconds: float = Field(gt=0)
    solver_budget_seconds: float = Field(gt=0, lt=3)
    max_suitcase_clearance_mm: float = Field(ge=0)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str
    port: int
    dev_origin: str
    runtime_dir: Path
    limits: Limits
    gemini_configured: bool
    gemini_api_key: str
    gemini_model: str


@lru_cache
def get_settings() -> Settings:
    raw = json.loads((PROJECT_ROOT / "config" / "limits.json").read_text(encoding="utf-8"))
    overrides = {
        "max_upload_bytes": int(os.getenv("PACKRIGHT_MAX_UPLOAD_BYTES", raw["max_upload_bytes"])),
        "max_trip_instances": int(os.getenv("PACKRIGHT_MAX_TRIP_INSTANCES", raw["max_trip_instances"])),
        "processing_timeout_seconds": float(os.getenv("PACKRIGHT_PROCESSING_TIMEOUT_SECONDS", raw["processing_timeout_seconds"])),
        "parser_memory_limit_mb": int(os.getenv("PACKRIGHT_PARSER_MEMORY_LIMIT_MB", raw["parser_memory_limit_mb"])),
        "model_timeout_seconds": float(os.getenv("PACKRIGHT_MODEL_TIMEOUT_SECONDS", raw["model_timeout_seconds"])),
        "solver_budget_seconds": float(os.getenv("PACKRIGHT_SOLVER_BUDGET_SECONDS", raw["solver_budget_seconds"])),
    }
    limits = Limits.model_validate({**raw, **overrides})
    runtime_value = os.getenv("PACKRIGHT_RUNTIME_DIR", "runtime-data")
    runtime_dir = Path(runtime_value)
    if not runtime_dir.is_absolute():
        runtime_dir = PROJECT_ROOT / runtime_dir
    return Settings(
        host=os.getenv("PACKRIGHT_HOST", "127.0.0.1"),
        port=int(os.getenv("PACKRIGHT_PORT", "8000")),
        dev_origin=os.getenv("PACKRIGHT_DEV_ORIGIN", "http://127.0.0.1:5173"),
        runtime_dir=runtime_dir,
        limits=limits,
        gemini_configured=bool(os.getenv("GEMINI_API_KEY", "").strip()),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    )
