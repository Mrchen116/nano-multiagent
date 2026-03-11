from personal_assistant.client.kernel_api_client import KernelApiClient


EXPECTED_METHODS = {
    "health",
    "create_session",
    "send_message_async",
    "stream_session_events",
    "get_run",
    "cancel_run",
}


def test_kernel_api_client_exposes_gateway_http_subset() -> None:
    for method_name in EXPECTED_METHODS:
        assert hasattr(KernelApiClient, method_name)
