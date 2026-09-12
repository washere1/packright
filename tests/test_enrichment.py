from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.enrichment import enrich_item, normalize_candidate
from app.main import app, repository, settings
from app.providers.gemini import GeminiError
from test_previews import png, prepared_item


def candidate(**updates):
    value = {
        "name": "Travel mouse", "category": "electronics", "fragility": "medium",
        "compressibility": "none", "stack_class": "neutral", "can_support_weight": False,
        "liquid_risk": False, "allowed_orientations": ["xyz", "xzy"], "access": "normal",
        "short_reason": "A compact electronic accessory that should avoid heavy loads.",
        "needs_confirmation": [],
        "confidence": {"name": .9, "category": .8, "fragility": .7, "compressibility": .9,
                       "stack_class": .6, "orientations": .5, "access": .7},
    }
    value.update(updates)
    return value


class FakeProvider:
    def __init__(self, responses): self.responses, self.calls = list(responses), 0
    def generate(self, prompt, schema, images, timeout_seconds):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception): raise response
        return response, {"output_text": "mocked"}


@pytest.mark.parametrize("raw,valid", [
    (candidate(), True),
    (candidate(allowed_orientations=["xyz", "xyz", "bad", "zyx"]), True),
    (candidate(confidence={"name": 4, "category": -2, "fragility": .7, "compressibility": .9, "stack_class": .6, "orientations": .5, "access": .7}), True),
    (candidate(fragility="glass"), False),
    (candidate(compressibility=True), False),
    (candidate(stack_class="top_only", can_support_weight=True), False),
    (candidate(allowed_orientations=[]), False),
    (candidate(access="immediate"), False),
    (candidate(short_reason="x" * 241), False),
    (candidate(confidence={"name": "certain"}), False),
])
def test_ten_varied_model_responses_validate_or_are_explicitly_rejected(raw, valid) -> None:
    try:
        normalized = normalize_candidate(raw, {"xyz", "xzy", "yxz", "yzx", "zxy", "zyx"})
    except ValidationError:
        assert not valid
    else:
        assert valid
        assert normalized.allowed_orientations
        assert len(normalized.allowed_orientations) == len(set(normalized.allowed_orientations))
        assert all(0 <= value <= 1 for value in normalized.confidence.model_dump().values())


def test_missing_credentials_uses_neutral_fallback_and_preserves_user_inputs() -> None:
    with TestClient(app) as client:
        item_id, _ = prepared_item(client)
        before = client.get(f"/api/items/{item_id}/status").json()
        response = client.post(f"/api/items/{item_id}/enrich")
        after = client.get(f"/api/items/{item_id}/status").json()
    assert response.status_code == 200
    assert response.json()["fallback_reason"] == "missing_credentials"
    assert response.json()["provider"] == "neutral_fallback"
    assert (after["weight_g"], after["priority_stars"]) == (before["weight_g"], before["priority_stars"])


def test_invalid_output_retries_once_then_falls_back() -> None:
    configured = settings.model_copy(update={"gemini_configured": True, "gemini_api_key": "test"})
    provider = FakeProvider([candidate(fragility="invalid"), candidate(access="invalid")])
    with TestClient(app) as client:
        item_id, geometry = prepared_item(client)
        for view in ("front", "side", "top", "three_quarter"):
            client.post(f"/api/items/{item_id}/previews?view={view}&geometry_version={geometry['version']}&renderer_version=enrichment-test", content=png(), headers={"Content-Type": "image/png"})
        result = enrich_item(item_id, repository, configured, provider)
    assert provider.calls == 2
    assert result.fallback_reason == "invalid_output"
    assert result.suggestion.name == "Unnamed item"


def test_valid_second_response_and_cache_are_used_without_changing_priority() -> None:
    configured = settings.model_copy(update={"gemini_configured": True, "gemini_api_key": "test", "gemini_model": "mock-model"})
    provider = FakeProvider([GeminiError("invalid_output"), candidate(allowed_orientations=["xyz", "xyz"], confidence={"name": 2, "category": -.5, "fragility": .7, "compressibility": .9, "stack_class": .6, "orientations": .5, "access": .7})])
    with TestClient(app) as client:
        item_id, geometry = prepared_item(client)
        for view in ("front", "side", "top", "three_quarter"):
            client.post(f"/api/items/{item_id}/previews?view={view}&geometry_version={geometry['version']}&renderer_version=enrichment-cache", content=png(), headers={"Content-Type": "image/png"})
        first = enrich_item(item_id, repository, configured, provider)
        second = enrich_item(item_id, repository, configured, provider)
        item = client.get(f"/api/items/{item_id}/status").json()
    assert provider.calls == 2
    assert first.fallback_reason is None and first.suggestion.allowed_orientations == ("xyz",)
    assert first.suggestion.confidence.name == 1 and first.suggestion.confidence.category == 0
    assert second.cached is True
    assert item["weight_g"] == 100 and item["priority_stars"] == 3
