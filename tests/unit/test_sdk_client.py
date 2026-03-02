import json

import httpx

from nano_multiagent.sdk.client import ServerClient, ServerClientConfig


def test_server_client_config_from_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("NANO_MULTIAGENT_API_BASE_URL", "http://127.0.0.1:9123")
    monkeypatch.setenv("NANO_MULTIAGENT_API_TOKEN", "token-from-env")
    monkeypatch.setenv("NANO_MULTIAGENT_REQUEST_ID", "req-env")

    config = ServerClientConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9123"
    assert config.token == "token-from-env"
    assert config.request_id == "req-env"


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
