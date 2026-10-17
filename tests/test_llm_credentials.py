import pytest
from anthropic import WorkloadIdentityCredentials

from f1tracker.narratives import llm

WIF_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
            "ANTHROPIC_SERVICE_ACCOUNT_ID", "ANTHROPIC_WORKSPACE_ID", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in WIF_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(llm, "_client", None)


def test_no_credentials_is_an_auth_error():
    with pytest.raises(llm.NarrativeAuthError):
        llm._get_client()


def test_github_actions_uses_workload_identity(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_x")
    monkeypatch.setenv("ANTHROPIC_ORGANIZATION_ID", "org")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "")  # unset repo variable arrives as ""
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://runner.example/token?api-version=2.0")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "req-token")
    client = llm._get_client()
    assert isinstance(client.credentials, WorkloadIdentityCredentials)
    assert client.api_key is None


def test_github_identity_token_is_fetched_fresh_with_audience(monkeypatch):
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://runner.example/token?api-version=2.0")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "req-token")
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"value": f"jwt-{len(calls)}"}

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers))
        return Resp()

    monkeypatch.setattr(llm.requests, "get", fake_get)
    assert llm._github_actions_identity_token() == "jwt-1"
    assert llm._github_actions_identity_token() == "jwt-2"  # never cached: GitHub tokens are single-use
    assert calls[0][1] == {"audience": "https://api.anthropic.com"}
    assert calls[0][2] == {"Authorization": "Bearer req-token"}


def test_api_key_still_works_locally(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert llm._get_client().api_key == "sk-ant-test"


class _Resp:
    stop_reason = "end_turn"
    model = "m"
    usage = None
    content = [type("B", (), {"type": "text", "text": '{"a": "b"}'})()]


def _capture_create(monkeypatch, model):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(llm, "NARRATIVE_MODEL", model)
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return _Resp()

    monkeypatch.setattr(llm._get_client().beta.messages, "create", create)
    llm.generate_json("sys", "user", {"type": "object"})
    return sent


def test_haiku_requests_have_no_fallbacks(monkeypatch):
    sent = _capture_create(monkeypatch, "claude-haiku-5-5")
    assert "fallbacks" not in sent and "betas" not in sent
    assert sent["output_config"]["format"]["type"] == "json_schema"


def test_fallback_models_keep_server_side_fallback(monkeypatch):
    sent = _capture_create(monkeypatch, "claude-sonnet-5-5")
    assert sent["fallbacks"] == "default" and sent["betas"] == ["server-side-fallback-2026-07-01"]


def test_low_credit_balance_stops_the_run(monkeypatch):
    import anthropic
    import httpx2

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    body = {"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low to access the Anthropic API."}}

    def create(**kwargs):
        raise anthropic.BadRequestError("Your credit balance is too low to access the Anthropic API.", response=httpx2.Response(400, request=req, json=body), body=body)

    monkeypatch.setattr(llm._get_client().beta.messages, "create", create)
    with pytest.raises(llm.NarrativeStopError):
        llm.generate_json("sys", "user", {"type": "object"})
