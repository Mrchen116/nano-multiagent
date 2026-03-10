import io

import httpx

from nano_multiagent.apps.coding_cli.main import run_cli
from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.platform.http_api.app import create_app


class _RetryThenSuccessRuntime:
    def __init__(self, *, fail_times: int) -> None:
        self._fail_times = fail_times
        self._calls = 0

    def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None) -> TurnResult:  # noqa: ANN001
        del parts
        del stream
        del run_id
        self._calls += 1
        if self._calls <= self._fail_times:
            raise ModelError(f"upstream flaky #{self._calls}", retryable=True)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cli_retry_integration",
            messages=(Message(message_id="msg_cli_retry_integration", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


def test_cli_repl_http_chain_surfaces_retry_progress_events(monkeypatch) -> None:
    monkeypatch.setattr(
        "nano_multiagent.runs.registry._wait_with_cancel",
        lambda _event, _seconds: False,
    )
    app = create_app(runtime=_RetryThenSuccessRuntime(fail_times=2), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.platform.sdk.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "State: completed | stop=completed | run=" in text
    assert "Progress: retrying (attempt 2, next 1.0s, last error model_error: upstream flaky #2)" in text
    assert "Assistant:" in text
    assert "ok" in text
