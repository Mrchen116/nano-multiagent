from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.llm.factory import LLMFactoryConfig
from nano_multiagent.platform.http_api.app import create_app
from nano_multiagent.platform.http_api.routes.global_routes import build_capabilities_payload
from nano_multiagent.platform.tools.base import ToolContext
from nano_multiagent.platform.tools.registry import ToolRegistry


class _AlphaTool:
    name = "alpha"
    description = "alpha"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def run(self, args, ctx):  # pragma: no cover - helper stub
        del args, ctx
        return {"ok": True}


class _ZetaTool:
    name = "zeta"
    description = "zeta"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def run(self, args, ctx):  # pragma: no cover - helper stub
        del args, ctx
        return {"ok": True}


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_build_capabilities_payload_reflects_active_llm_and_sorted_tools() -> None:
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(_ZetaTool())
    registry.register(_AlphaTool())

    payload = build_capabilities_payload(
        tool_registry=registry,
        llm_config=LLMFactoryConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            base_url="http://127.0.0.1:4000",
        ),
    )

    assert payload["llm"]["active_provider"] == "anthropic"
    assert payload["llm"]["active_model"] == "claude-3-5-sonnet-20241022"
    assert [item["name"] for item in payload["tools"]] == ["alpha", "zeta"]

    providers = {item["provider"]: item for item in payload["llm"]["providers"]}
    assert "openai_compat" in providers
    assert "anthropic" in providers
    assert providers["openai_compat"]["default_model"] == "codexOAuth:gpt-5.2-codex"


def test_llm_config_patch_updates_runtime_and_capabilities() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    initial = client.get("/v1/llm-config", headers=_auth_headers("req-llm-config-get"))
    assert initial.status_code == 200
    assert initial.json()["provider"] == "openai_compat"

    patched = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-patch"),
        json={
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "base_url": "http://127.0.0.1:5000",
            "timeout_seconds": 15.0,
        },
    )
    assert patched.status_code == 200
    payload = patched.json()
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "claude-3-5-sonnet-20241022"
    assert payload["base_url"] == "http://127.0.0.1:5000"
    assert payload["timeout_seconds"] == 15.0

    capabilities = client.get("/v1/capabilities", headers=_auth_headers("req-capabilities-after-patch"))
    assert capabilities.status_code == 200
    assert capabilities.json()["llm"]["active_provider"] == "anthropic"
    assert capabilities.json()["llm"]["active_model"] == "claude-3-5-sonnet-20241022"


def test_llm_config_patch_rejects_empty_payload() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.patch("/v1/llm-config", headers=_auth_headers("req-llm-config-empty"), json={})

    assert response.status_code == 400
    payload = response.json()["error"]
    assert payload["code"] == "invalid_request"
    assert payload["retryable"] is False


def test_llm_config_patch_supports_setting_and_clearing_api_key() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    set_response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-set-key"),
        json={"api_key": "secret-key"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["api_key"] == "secret-key"

    clear_by_null_response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-clear-key-null"),
        json={"api_key": None},
    )
    assert clear_by_null_response.status_code == 200
    assert clear_by_null_response.json()["api_key"] is None

    set_again_response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-set-key-again"),
        json={"api_key": "secret-key-again"},
    )
    assert set_again_response.status_code == 200
    assert set_again_response.json()["api_key"] == "secret-key-again"

    clear_by_flag_response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-clear-key-flag"),
        json={"clear_api_key": True},
    )
    assert clear_by_flag_response.status_code == 200
    assert clear_by_flag_response.json()["api_key"] is None


def test_llm_config_patch_maps_invalid_provider_to_invalid_request() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-invalid-provider"),
        json={"provider": "unknown-provider"},
    )

    assert response.status_code == 400
    payload = response.json()["error"]
    assert payload["code"] == "invalid_request"
    assert "unsupported llm provider" in payload["message"]


def test_llm_config_patch_maps_model_error_to_model_error_response() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    runtime = client.app.state.agent_runtime

    def _raise_model_error(**kwargs: object) -> None:
        del kwargs
        raise ModelError("upstream timeout", retryable=True)

    runtime.reconfigure_llm = _raise_model_error  # type: ignore[method-assign]

    response = client.patch(
        "/v1/llm-config",
        headers=_auth_headers("req-llm-config-model-error"),
        json={"provider": "anthropic"},
    )

    assert response.status_code == 502
    payload = response.json()["error"]
    assert payload["code"] == "model_error"
    assert payload["message"] == "upstream timeout"
    assert payload["retryable"] is True
