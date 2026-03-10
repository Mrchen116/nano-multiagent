from fastapi.testclient import TestClient

from nano_multiagent.observability.logger import capture_logs
from nano_multiagent.platform.http_api.app import create_app


REQUIRED = {"session_id", "turn_id", "tool_call_id", "trace_id"}


def test_api_error_log_contains_trace_and_correlation_fields() -> None:
    client = TestClient(create_app(auth_token="test-token"))

    with capture_logs() as records:
        response = client.get(
            "/v1/sessions",
            headers={
                "Authorization": "Bearer wrong-token",
                "X-Request-Id": "req-observ-contract",
            },
        )

    assert response.status_code == 401
    api_errors = [item for item in records if item["message"] == "api_error"]
    assert api_errors
    fields = api_errors[0]["fields"]
    assert REQUIRED.issubset(fields.keys())
    assert fields["trace_id"] == "req-observ-contract"
