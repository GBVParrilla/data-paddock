"""Thin wrapper around the Anthropic SDK for narrative generation.

- Credentials come from the environment, never parameters or logs. Either:
  * ANTHROPIC_API_KEY (local dev), or
  * Workload Identity Federation (no stored secret): ANTHROPIC_FEDERATION_RULE_ID +
    ANTHROPIC_ORGANIZATION_ID (+ ANTHROPIC_SERVICE_ACCOUNT_ID / ANTHROPIC_WORKSPACE_ID).
    Inside GitHub Actions the identity token is fetched fresh from the runner for every
    exchange; elsewhere the SDK reads ANTHROPIC_IDENTITY_TOKEN_FILE / ANTHROPIC_IDENTITY_TOKEN.
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
import requests
from anthropic import WorkloadIdentityCredentials
from anthropic.lib.credentials import WorkloadIdentityError

from ..config import FALLBACK_MODELS, NARRATIVE_EFFORT, NARRATIVE_MAX_TOKENS, NARRATIVE_MODEL, PROMPT_VERSION

log = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


class NarrativeGenerationError(RuntimeError):
    pass


class NarrativeStopError(NarrativeGenerationError):
    """Every further call would fail the same way (credentials, credit balance) - stop the run."""


class NarrativeAuthError(NarrativeStopError):
    """Credentials are missing or rejected."""


# Audience the federation rule matches on (its `match.audience`).
OIDC_AUDIENCE = os.environ.get("F1_OIDC_AUDIENCE", "https://api.anthropic.com")


def _github_actions_identity_token() -> str:
    """A fresh GitHub Actions OIDC token. They live ~5 minutes and are single-use (jti),
    so the SDK calls this on every exchange instead of re-reading a cached file."""
    resp = requests.get(
        os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
        params={"audience": OIDC_AUDIENCE},
        headers={"Authorization": f"Bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["value"]


def _federation_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_FEDERATION_RULE_ID") and os.environ.get("ANTHROPIC_ORGANIZATION_ID"))


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is not None:
        return _client
    if os.environ.get("ANTHROPIC_API_KEY"):
        _client = anthropic.Anthropic(max_retries=3, timeout=600.0)  # key resolved from env by the SDK
    elif _federation_configured() and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"):
        _client = anthropic.Anthropic(
            credentials=WorkloadIdentityCredentials(
                identity_token_provider=_github_actions_identity_token,
                federation_rule_id=os.environ["ANTHROPIC_FEDERATION_RULE_ID"],
                organization_id=os.environ["ANTHROPIC_ORGANIZATION_ID"],
                service_account_id=os.environ.get("ANTHROPIC_SERVICE_ACCOUNT_ID") or None,
                workspace_id=os.environ.get("ANTHROPIC_WORKSPACE_ID") or None,
            ),
            max_retries=3,
            timeout=600.0,
        )
    elif _federation_configured():
        _client = anthropic.Anthropic(max_retries=3, timeout=600.0)  # SDK reads the identity token env vars
    else:
        raise NarrativeAuthError(
            "No Claude credentials: set ANTHROPIC_API_KEY (e.g. in .env, see .env.example) "
            "or the Workload Identity Federation variables (see README)."
        )
    return _client


def stable_hash(payload: Any) -> str:
    """Deterministic hash of the structured input + prompt version + model."""
    blob = json.dumps({"v": PROMPT_VERSION, "model": NARRATIVE_MODEL, "input": payload}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def generate_json(system: str, user: str, schema: dict[str, Any], *, effort: str | None = None) -> tuple[dict[str, Any], str]:
    """One structured-output call. Returns (parsed JSON, model that served it)."""
    client = _get_client()
    fallback: dict[str, Any] = {}
    if NARRATIVE_MODEL in FALLBACK_MODELS:  # re-run a refused request on another model, server-side
        fallback = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        response = client.beta.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=NARRATIVE_MAX_TOKENS,
            # the system prompt (rules + worked examples) is the same for every story of a kind: cached,
            # later calls read it at about a tenth of the input price (Haiku 5.5 caches from 512 tokens)
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort or NARRATIVE_EFFORT, "format": {"type": "json_schema", "schema": schema}},
            **fallback,
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise NarrativeAuthError(f"Anthropic API rejected the credentials ({exc.status_code})") from exc
    except anthropic.CredentialsError as exc:
        raise NarrativeAuthError(f"Could not get Claude credentials: {exc}") from exc
    except WorkloadIdentityError as exc:
        if exc.status_code in (400, 401, 403):
            # the exchange was refused: the Console's Workload identity -> authentication history says why
            raise NarrativeAuthError(f"Workload identity token exchange was refused: {exc}") from exc
        raise NarrativeGenerationError(f"Workload identity token exchange failed: {exc}") from exc
    except requests.RequestException as exc:
        raise NarrativeGenerationError(f"Could not fetch the GitHub Actions identity token: {exc}") from exc
    except anthropic.RateLimitError as exc:
        raise NarrativeGenerationError("Anthropic API rate limit hit; try again shortly") from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code == 400 and "credit balance" in str(exc.message).lower():
            raise NarrativeStopError("Anthropic credit balance is too low - add credits in the Console (Plans & Billing)") from exc
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
    log.info("narrative call: model=%s in=%s cache_read=%s cache_write=%s out=%s", response.model, getattr(usage, "input_tokens", "?"),
             getattr(usage, "cache_read_input_tokens", "?"), getattr(usage, "cache_creation_input_tokens", "?"), getattr(usage, "output_tokens", "?"))
    return data, response.model
