import json

import httpx

from nano_multiagent.cli.http_client import ServerClient, ServerClientConfig, _should_trust_env
from nano_multiagent.sdk.client import ServerClient as SDKServerClient
from nano_multiagent.sdk.client import ServerClientConfig as SDKServerClientConfig


def test_server_client_config_from_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("NANO_MULTIAGENT_API_BASE_URL", "http://127.0.0.1:9123")
    monkeypatch.setenv("NANO_MULTIAGENT_API_TOKEN", "token-from-env")
    monkeypatch.setenv("NANO_MULTIAGENT_REQUEST_ID", "req-env")

    config = ServerClientConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9123"
    assert config.token == "token-from-env"
    assert config.request_id == "req-env"


def test_sdk_client_module_keeps_backward_compatible_aliases() -> None:
    assert SDKServerClient is ServerClient
    assert SDKServerClientConfig is ServerClientConfig


def test_send_message_posts_http_payload_with_auth_and_request_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["request_id"] = request.headers.get("X-Request-Id")
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "session_id": "sess_1",
                "turn_id": "turn_1",
                "message": {"message_id": "msg_1", "role": "assistant", "content": "ok"},
                "completed": True,
                "stop_reason": "stop",
            },
        )

    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(handler)) as client:
        payload = client.send_message(session_id="sess_1", text="hello")

    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/sessions/sess_1/messages"
    assert seen["auth"] == "Bearer secret"
    assert seen["request_id"] == "req-fixed"
    assert seen["payload"] == {
        "parts": [{"type": "text", "text": "hello"}],
        "stream": False,
    }
    assert payload["message"]["content"] == "ok"


def test_session_tools_and_compact_call_session_scoped_endpoints() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        if request.url.path.endswith("/tools"):
            return httpx.Response(
                status_code=200,
                json={"session_id": "sess_2", "tools": [{"name": "read", "description": "Read", "input_schema": {}}]},
            )
        return httpx.Response(
            status_code=200,
            json={"session_id": "sess_2", "compacted": False, "result": None},
        )

    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(handler)) as client:
        tools_payload = client.list_session_tools(session_id="sess_2")
        assert tools_payload["session_id"] == "sess_2"
        assert tools_payload["tools"][0]["name"] == "read"
        compact_payload = client.compact_session(session_id="sess_2")
        assert compact_payload["session_id"] == "sess_2"
        assert compact_payload["compacted"] is False

    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/sessions/sess_2:compact"


def test_server_client_bypasses_env_proxy_for_local_base_url() -> None:
    assert _should_trust_env("http://127.0.0.1:8000") is False
    assert _should_trust_env("http://localhost:8000") is False


def test_server_client_keeps_env_proxy_for_remote_base_url() -> None:
    assert _should_trust_env("https://api.example.com") is True


def test_get_llm_config_calls_v1_llm_config_endpoint() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(
            status_code=200,
            json={
                "provider": "openai",
                "model": "gpt-5",
                "base_url": "https://api.example.com/v1",
                "api_key": None,
                "timeout_seconds": 30.0,
            },
        )

    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(handler)) as client:
        payload = client.get_llm_config()

    assert seen["method"] == "GET"
    assert seen["path"] == "/v1/llm-config"
    assert seen["auth"] == "Bearer secret"
    assert payload["model"] == "gpt-5"


def test_patch_llm_config_calls_v1_llm_config_endpoint() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "provider": "openai",
                "model": "gpt-5-mini",
                "base_url": "https://api.example.com/v1",
                "api_key": None,
                "timeout_seconds": 45.0,
            },
        )

    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(handler)) as client:
        payload = client.patch_llm_config({"model": "gpt-5-mini", "timeout_seconds": 45.0})

    assert seen["method"] == "PATCH"
    assert seen["path"] == "/v1/llm-config"
    assert seen["payload"] == {"model": "gpt-5-mini", "timeout_seconds": 45.0}
    assert payload["model"] == "gpt-5-mini"
