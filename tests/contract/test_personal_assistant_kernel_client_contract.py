from personal_assistant.client.kernel_api_client import KernelApiClient


EXPECTED_METHODS = {
    "health",
    "create_session",
    "get_session",
    "append_message",
    "submit_message",
    "stream_session",
    "get_run",
    "cancel_run",
    "interrupt_session",
    "submit_permission_decision",
}


def test_kernel_api_client_exposes_gateway_http_subset() -> None:
    for method_name in EXPECTED_METHODS:
        assert hasattr(KernelApiClient, method_name), (
            f"KernelApiClient is missing expected method: {method_name}"
        )
