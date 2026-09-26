"""Thin wrapper around the Anthropic SDK for narrative generation.

- The API key is read from the environment by the SDK at call time
  (ANTHROPIC_API_KEY). It is never accepted as a parameter or logged.
- Model string lives in config.NARRATIVE_MODEL.
- Server-side refusal fallback is enabled by default (fallbacks="default").
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import anthropic

from ..config import NARRATIVE_EFFORT, NARRATIVE_MAX_TOKENS, NARRATIVE_MODEL, PROMPT_VERSION

log = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


class NarrativeGenerationError(RuntimeError):
    pass


def _get_client() -> anthropic.Anthropic:
    global _client
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise NarrativeGenerationError("ANTHROPIC_API_KEY is not set. Put it in .env (see .env.example).")
    if _client is None:
        _client = anthropic.Anthropic(max_retries=3, timeout=600.0)  # key resolved from env by the SDK
    return _client


def stable_hash(payload: Any) -> str:
    """Deterministic hash of the structured input + prompt version + model."""
    blob = json.dumps({"v": PROMPT_VERSION, "model": NARRATIVE_MODEL, "input": payload}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def generate_json(system: str, user: str, schema: dict[str, Any], *, effort: str | None = None) -> tuple[dict[str, Any], str]:
    """One structured-output call. Returns (parsed JSON, model that served it)."""
    client = _get_client()
    try:
        response = client.beta.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=NARRATIVE_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort or NARRATIVE_EFFORT, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise NarrativeGenerationError("Anthropic API rejected the API key") from exc
    except anthropic.RateLimitError as exc:
        raise NarrativeGenerationError("Anthropic API rate limit hit; try again shortly") from exc
    except anthropic.APIStatusError as exc:
        raise NarrativeGenerationError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise NarrativeGenerationError("Could not reach the Anthropic API") from exc

    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise NarrativeGenerationError(f"Model declined to generate (category={getattr(details, 'category', None)})")
    if response.stop_reason == "max_tokens":
        raise NarrativeGenerationError("Narrative output was truncated (max_tokens); increase NARRATIVE_MAX_TOKENS")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise NarrativeGenerationError("No text block in model response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NarrativeGenerationError("Model response was not valid JSON") from exc
    usage = response.usage
    log.info("narrative call: model=%s in=%s out=%s", response.model, getattr(usage, "input_tokens", "?"), getattr(usage, "output_tokens", "?"))
    return data, response.model
