from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from .config import PROJECT_ROOT, Settings
from .providers.gemini import GeminiError, GeminiProvider
from .repository import Repository
from .schemas import (
    AccessClass, Compressibility, ConfidenceScores, EnrichmentResult, EnrichmentSuggestion,
    Fragility, Handling, ItemStage, OrientationId, PreviewView, ProgressStage, StackClass,
)

PROMPT_VERSION = "packright-enrichment-v1"
REQUIRED_VIEWS = {PreviewView.FRONT, PreviewView.SIDE, PreviewView.TOP, PreviewView.THREE_QUARTER}


def neutral_suggestion() -> EnrichmentSuggestion:
    confidence = ConfidenceScores(
        name=0, category=0, fragility=0, compressibility=0, stack_class=0, orientations=0, access=0,
    )
    return EnrichmentSuggestion(
        name="Unnamed item", category="other", fragility=Fragility.MEDIUM,
        compressibility=Compressibility.NONE, stack_class=StackClass.NEUTRAL,
        can_support_weight=False, liquid_risk=False,
        allowed_orientations=tuple(OrientationId), access=AccessClass.NORMAL,
        short_reason="Neutral handling metadata is in use until the item is reviewed.",
        needs_confirmation=("name", "handling"), confidence=confidence,
    )


def normalize_candidate(raw: dict[str, Any], legal_geometry_orientations: set[str]) -> EnrichmentSuggestion:
    candidate = dict(raw)
    orientations = candidate.get("allowed_orientations")
    if isinstance(orientations, list):
        candidate["allowed_orientations"] = list(dict.fromkeys(
            value for value in orientations if isinstance(value, str) and value in legal_geometry_orientations
        ))
    confidence = candidate.get("confidence")
    if isinstance(confidence, dict):
        normalized_confidence = {}
        for key, value in confidence.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                normalized_confidence[key] = value
            else:
                normalized_confidence[key] = min(1.0, max(0.0, float(value)))
        candidate["confidence"] = normalized_confidence
    return EnrichmentSuggestion.model_validate(candidate)


def enrich_item(
    item_id: UUID, repository: Repository, settings: Settings, provider: GeminiProvider | None = None,
) -> EnrichmentResult:
    item = repository.get_item(item_id)
    asset = repository.get_latest_asset(item_id)
    geometry = repository.get_latest_geometry(item_id)
    if item is None or asset is None or geometry is None:
        raise ValueError("item, asset, and geometry are required")
    previews = repository.list_previews(item_id, geometry.version)
    views = {preview.view for preview in previews}
    usable_previews = [preview for preview in previews if preview.view in REQUIRED_VIEWS]
    preview_signature = ",".join(sorted(str(preview.id) for preview in usable_previews))
    cache_material = "|".join((
        asset.sha256, str(geometry.version), preview_signature, PROMPT_VERSION, settings.gemini_model,
        asset.original_filename, "live" if settings.gemini_configured else "fallback",
    ))
    cache_key = hashlib.sha256(cache_material.encode("utf-8")).hexdigest()
    cached = repository.get_cached_enrichment(cache_key)
    if cached:
        _apply_result(item_id, cached, repository)
        return cached

    fallback_reason: str | None = None
    suggestion: EnrichmentSuggestion | None = None
    raw_response: dict[str, Any] | None = None
    if not settings.gemini_configured:
        fallback_reason = "missing_credentials"
    elif not REQUIRED_VIEWS.issubset(views):
        fallback_reason = "missing_previews"
    else:
        schema = json.loads((PROJECT_ROOT / "config" / "enrichment-schema.json").read_text(encoding="utf-8"))
        system_prompt = (PROJECT_ROOT / "config" / "enrichment-prompt.txt").read_text(encoding="utf-8")
        dimensions = geometry.canonical_dimensions_mm
        context = {
            "filename_data": asset.original_filename,
            "canonical_dimensions_mm": [dimensions.width, dimensions.height, dimensions.depth],
            "canonical_axes": {"x": "width", "y": "height", "z": "depth"},
            "fill_ratio": geometry.fill_ratio,
            "geometry_orientations": [orientation.id.value for orientation in geometry.orientations],
        }
        prompt = system_prompt + "\nItem geometry data:\n" + json.dumps(context, separators=(",", ":"))
        images = [(settings.runtime_dir / preview.storage_path, preview.mime_type) for preview in usable_previews]
        active_provider = provider or GeminiProvider(settings.gemini_api_key, settings.gemini_model)
        deadline = time.monotonic() + settings.limits.model_timeout_seconds
        last_error = "invalid_output"
        for _ in range(2):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last_error = "model_timeout"
                break
            run_id = uuid4()
            try:
                candidate, raw_response = active_provider.generate(prompt, schema, images, remaining)
                suggestion = normalize_candidate(candidate, {orientation.id.value for orientation in geometry.orientations})
                repository.save_model_run(
                    run_id, item_id, "gemini", settings.gemini_model, PROMPT_VERSION,
                    "valid", None, cache_key, raw_response,
                )
                break
            except (GeminiError, ValidationError) as error:
                last_error = error.code if isinstance(error, GeminiError) else "invalid_output"
                repository.save_model_run(
                    run_id, item_id, "gemini", settings.gemini_model, PROMPT_VERSION,
                    "invalid", last_error, cache_key, raw_response,
                )
        if suggestion is None:
            fallback_reason = last_error

    if suggestion is None:
        suggestion = neutral_suggestion()
    result = EnrichmentResult(
        suggestion=suggestion,
        provider="neutral_fallback" if fallback_reason else "gemini",
        model_id=settings.gemini_model, prompt_version=PROMPT_VERSION,
        fallback_reason=fallback_reason,
    )
    repository.save_enrichment(cache_key, item_id, result)
    if fallback_reason:
        repository.save_model_run(
            uuid4(), item_id, result.provider, settings.gemini_model, PROMPT_VERSION,
            "fallback", fallback_reason, cache_key, None,
        )
    _apply_result(item_id, result, repository)
    return result


def _apply_result(item_id: UUID, result: EnrichmentResult, repository: Repository) -> None:
    item = repository.get_item(item_id)
    if item is None:
        return
    suggestion = result.suggestion
    handling = Handling(
        version=1, category=suggestion.category, fragility=suggestion.fragility,
        compressibility=suggestion.compressibility, stack_class=suggestion.stack_class,
        can_support_weight=suggestion.can_support_weight, liquid_risk=suggestion.liquid_risk,
        legal_orientations=suggestion.allowed_orientations, access=suggestion.access,
        confidence=suggestion.confidence,
        provenance="neutral_fallback" if result.fallback_reason else "gemini_suggested",
        short_reason=suggestion.short_reason, needs_confirmation=suggestion.needs_confirmation,
    )
    updated = item.model_copy(update={
        "name": suggestion.name, "handling": handling, "stage": ItemStage.AWAITING_REVIEW,
        "progress_stage": ProgressStage.COMPLETE, "error_code": None,
    })
    repository.save_item(updated)
