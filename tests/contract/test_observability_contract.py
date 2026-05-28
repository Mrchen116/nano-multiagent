from fastapi.testclient import TestClient

from agent.core.observability.logger import capture_logs
from agent.platform.http_api.app import create_app


REQUIRED = {"session_id", "turn_id", "tool_call_id", "trace_id"}


def test_api_error_log_contains_trace_and_correlation_fields() -> None:
    # PATCH /v1/llm-config with empty body triggers APIError(invalid_request),
    # which exercises the api_error log path with trace/correlation fields.
    # (Auth is disabled; the 401 path is no longer reachable without auth enforcement.)
    client = TestClient(create_app())

    with capture_logs() as records:
        response = client.patch(
            "/v1/llm-config",
            headers={"X-Request-Id": "req-observ-contract"},
            json={},
        )

    assert response.status_code == 400
    api_errors = [item for item in records if item["message"] == "api_error"]
    assert api_errors
    fields = api_errors[0]["fields"]
    assert REQUIRED.issubset(fields.keys())
    assert fields["trace_id"] == "req-observ-contract"
