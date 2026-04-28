import json

import httpx

from agent.platform.sdk.client import ServerClient, ServerClientConfig, _should_trust_env
from agent.platform.sdk.client import ServerClient as PlatformServerClient
from agent.platform.sdk.client import ServerClientConfig as PlatformServerClientConfig
from agent.platform.sdk.client import ServerClient as LegacySDKServerClient
from agent.platform.sdk.client import ServerClientConfig as LegacySDKServerClientConfig


def test_server_client_config_from_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("NANO_MULTIAGENT_API_BASE_URL", "http://127.0.0.1:9123")
    monkeypatch.setenv("NANO_MULTIAGENT_API_TOKEN", "token-from-env")
    monkeypatch.setenv("NANO_MULTIAGENT_REQUEST_ID", "req-env")

    config = ServerClientConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9123"
    assert config.token == "token-from-env"
    assert config.request_id == "req-env"


def test_sdk_client_module_keeps_backward_compatible_aliases() -> None:
    assert PlatformServerClient is ServerClient
    assert PlatformServerClientConfig is ServerClientConfig
    assert LegacySDKServerClient is PlatformServerClient
    assert LegacySDKServerClientConfig is PlatformServerClientConfig


def test_submit_message_posts_http_payload_with_auth_and_request_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["request_id"] = request.headers.get("X-Request-Id")
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={"run_id": "run_1", "anchor_sequence": 5, "injected": False, "status": "queued"},
        )

    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(handler)) as client:
        payload = client.submit_message(session_id="sess_1", text="hello")

    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/sessions/sess_1/messages"
    assert seen["auth"] == "Bearer secret"
    assert seen["request_id"] == "req-fixed"
    assert seen["payload"] == {
        "parts": [{"type": "text", "text": "hello"}],
        "priority": "next",
    }
    assert payload["run_id"] == "run_1"
    assert payload["anchor_sequence"] == 5


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
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path.endswith("/tools"):
            return httpx.Response(
                status_code=200,
                json={"session_id": "sess_2", "tools": [{"name": "read", "description": "Read", "input_schema": {}}]},
            )
        if request.url.path.endswith("/context-budget"):
            return httpx.Response(
                status_code=200,
                json={
                    "session_id": "sess_2",
                    "used_tokens": 120,
                    "max_tokens": 200,
                    "remaining_tokens": 80,
                    "usage_ratio": 0.6,
                },
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
        budget_payload = client.get_context_budget(session_id="sess_2")
        assert budget_payload["session_id"] == "sess_2"
        assert budget_payload["usage_ratio"] == 0.6

    assert requests == [
        ("GET", "/v1/sessions/sess_2/tools"),
        ("POST", "/v1/sessions/sess_2:compact"),
        ("GET", "/v1/sessions/sess_2/context-budget"),
    ]


def test_llm_config_get_and_set_use_config_endpoint_contract() -> None:
    requests: list[tuple[str, str, object | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload: object | None = None
        if request.content:
            payload = json.loads(request.content.decode("utf-8"))
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(
                status_code=200,
                json={
                    "provider": "openai_compat",
                    "model": "codex_oauth:gpt-5.4",
                    "base_url": "http://127.0.0.1:4000",
                    "api_key_configured": False,
                    "timeout_seconds": 30.0,
                },
            )
        return httpx.Response(
            status_code=200,
            json={
                "provider": "anthropic",
                "model": "moonshotAnthropic:kimi-k2.5",
                "base_url": "http://127.0.0.1:4100",
                "api_key_configured": True,
                "timeout_seconds": 55.0,
            },
        )

    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(handler)) as client:
        got = client.get_llm_config()
        updated = client.set_llm_config(
            provider="anthropic",
            model="moonshotAnthropic:kimi-k2.5",
            base_url="http://127.0.0.1:4100",
            api_key="sk-cli",
            timeout_seconds=55.0,
        )

    assert got["provider"] == "openai_compat"
    assert updated["provider"] == "anthropic"
    assert requests == [
        ("GET", "/v1/llm-config", None),
        (
            "PATCH",
            "/v1/llm-config",
            {
                "provider": "anthropic",
                "model": "moonshotAnthropic:kimi-k2.5",
                "base_url": "http://127.0.0.1:4100",
                "api_key": "sk-cli",
                "timeout_seconds": 55.0,
            },
        ),
    ]


def test_set_llm_config_requires_at_least_one_field() -> None:
    config = ServerClientConfig(base_url="http://test.local", token="secret", request_id="req-fixed")
    with ServerClient(config=config, transport=httpx.MockTransport(lambda request: httpx.Response(status_code=200, json={}))) as client:
        try:
            client.set_llm_config()
        except ValueError as exc:
            assert "at least one field" in str(exc).lower()
        else:  # pragma: no cover - explicit failure branch
            raise AssertionError("expected ValueError")


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


def test_incremental_sse_parser_emits_event() -> None:
    from agent.platform.sdk.client import _IncrementalSseParser

    parser = _IncrementalSseParser()
    chunk = b'id: 42\nevent: run_status\ndata: {"status":"running"}\n\n'
    events = parser.feed(chunk)
    assert len(events) == 1
    assert events[0]["event"] == "run_status"
    assert events[0]["_id"] == 42
    assert events[0]["status"] == "running"


def test_incremental_sse_parser_across_chunks() -> None:
    from agent.platform.sdk.client import _IncrementalSseParser

    parser = _IncrementalSseParser()
    events = parser.feed(b'id: 1\nevent: a\ndata: {"x":1}\n\n')
    assert len(events) == 1
    events = parser.feed(b'id: 2\nevent: b\ndata: {"x":2}\n\n')
    assert len(events) == 1
    assert events[0]["event"] == "b"
    assert events[0]["_id"] == 2


def test_incremental_sse_parser_skips_comments_and_empty() -> None:
    from agent.platform.sdk.client import _IncrementalSseParser

    parser = _IncrementalSseParser()
    chunk = b':comment\n\nid: 3\nevent: ok\ndata: {"y":true}\n\n'
    events = parser.feed(chunk)
    assert len(events) == 1
    assert events[0]["event"] == "ok"
    assert events[0]["_id"] == 3
