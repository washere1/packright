from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx


class GeminiError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class GeminiProvider:
    endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"

    def __init__(self, api_key: str, model_id: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.model_id = model_id
        self.client = client

    def generate(
        self, prompt: str, schema: dict[str, Any], images: list[tuple[Path, str]], timeout_seconds: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        inputs: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path, mime_type in images:
            inputs.append({
                "type": "image", "mime_type": mime_type,
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            })
        body = {
            "model": self.model_id,
            "input": inputs,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
            "store": False,
            "generation_config": {"temperature": 0.1},
        }
        headers = {
            "x-goog-api-key": self.api_key,
            "Api-Revision": "2026-05-20",
            "Content-Type": "application/json",
        }
        try:
            if self.client is not None:
                response = self.client.post(self.endpoint, headers=headers, json=body, timeout=timeout_seconds)
            else:
                with httpx.Client(timeout=timeout_seconds) as client:
                    response = client.post(self.endpoint, headers=headers, json=body)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise GeminiError("model_timeout") from None
        except httpx.HTTPError:
            raise GeminiError("provider_error") from None
        try:
            payload = response.json()
            text = self._extract_text(payload)
            return json.loads(text), payload
        except (ValueError, TypeError, KeyError):
            raise GeminiError("invalid_output") from None

    @classmethod
    def _extract_text(cls, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text
        for output in payload.get("outputs", []):
            if isinstance(output, dict) and output.get("type") == "text" and isinstance(output.get("text"), str):
                return output["text"]
        for step in payload.get("steps", []):
            if not isinstance(step, dict):
                continue
            for content in step.get("content", step.get("outputs", [])):
                if isinstance(content, dict) and content.get("type") == "text" and isinstance(content.get("text"), str):
                    return content["text"]
        raise KeyError("No text output")
