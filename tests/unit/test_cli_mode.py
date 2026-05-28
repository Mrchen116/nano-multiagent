"""CLI 运行模式 / lifecycle / LLM config 测试。

覆盖 managed / remote / auto 模式选择逻辑、managed server start/stop 生命周期、
llm-config get/set 子命令、超时配置和 LLM 启动参数透传。
"""

import io
import json

from coding_cli.main import run_cli


# ---------------------------------------------------------------------------
# Stub clients
# ---------------------------------------------------------------------------

class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        return {"healthy": True}

    def create_session(self, *, title: str | None = None, **kwargs: object) -> dict[str, str]:
        self.calls.append(("create_session", {"title": title or ""}))
        return {"session_id": "sess_cli"}

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        self._last_text = text
        return {"run_id": "run-1", "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        text = getattr(self, "_last_text", "hello repl")
        yield {"event": "assistant_message", "run_id": "run-1", "content": f"echo:{text}"}
        yield {"event": "run_status", "run_id": "run-1", "status": "completed", "stop_reason": "stop", "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "used_tokens": 64,
            "max_tokens": 200,
            "remaining_tokens": 136,
            "usage_ratio": 0.32,
        }

    def get_llm_config(self) -> dict[str, object]:
        self.calls.append(("get_llm_config", None))
        return {
            "provider": "openai_compat",
            "model": "codex_oauth:gpt-5.5",
            "base_url": "http://127.0.0.1:4000",
            "api_key_configured": False,
            "timeout_seconds": 30.0,
        }

    def set_llm_config(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "set_llm_config",
                {
                    "provider": provider,
                    "model": model,
                    "base_url": base_url,
                    "api_key": api_key,
                    "timeout_seconds": timeout_seconds,
                    "clear_api_key": clear_api_key,
                },
            )
        )
        resolved_api_key = None if clear_api_key else api_key
        return {
            "provider": provider or "openai_compat",
            "model": model or "codex_oauth:gpt-5.5",
            "base_url": base_url or "http://127.0.0.1:4000",
            "api_key_configured": bool(resolved_api_key),
            "timeout_seconds": timeout_seconds or 30.0,
        }


class _ConnectionRefusedOnHealthStubClient(_StubClient):
    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        raise ConnectionRefusedError(61, "Connection refused")


# ---------------------------------------------------------------------------
# Managed server spy — 记录 lifecycle 事件和配置绑定
# ---------------------------------------------------------------------------

class _ManagedServerSpy:
    def __init__(self, *, fail_on_start: Exception | None = None) -> None:
        self.fail_on_start = fail_on_start
        self.events: list[str] = []
        self.config_base_url: str | None = None
        self.config_token: str | None = None
        self.llm_provider: str | None = None
        self.llm_model: str | None = None
        self.llm_base_url: str | None = None
        self.llm_api_key: str | None = None
        self.llm_timeout_seconds: float | None = None

    def bind(self, config: object) -> "_ManagedServerSpy":
        self.config_base_url = getattr(config, "base_url", None)
        self.config_token = getattr(config, "token", None)
        self.llm_provider = getattr(config, "llm_provider", None)
        self.llm_model = getattr(config, "llm_model", None)
        self.llm_base_url = getattr(config, "llm_base_url", None)
        self.llm_api_key = getattr(config, "llm_api_key", None)
        self.llm_timeout_seconds = getattr(config, "llm_timeout_seconds", None)
        return self

    def start(self) -> None:
        self.events.append("start")
        if self.fail_on_start is not None:
            raise self.fail_on_start

    def stop(self) -> None:
        self.events.append("stop")


# ---------------------------------------------------------------------------
# Tests: managed / remote / auto mode lifecycle
# ---------------------------------------------------------------------------

def test_run_cli_managed_mode_starts_and_stops_local_server() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8111",
            "health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert manager.config_base_url == "http://127.0.0.1:8111"
    assert manager.events == ["start", "stop"]


def test_run_cli_without_mode_defaults_repl_to_managed_lifecycle() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/exit"])
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert manager.config_base_url == "http://127.0.0.1:8000"
    assert manager.events == ["start", "stop"]
    # feat-333-M3/R2: REPL now prints an auto mode startup banner before the
    # session loop; the /exit command does not suppress the banner.
    text = output.getvalue()
    assert "Auto mode" in text or "auto mode" in text, (
        f"Expected auto mode banner in REPL output, got: {text!r}"
    )


def test_run_cli_without_mode_defaults_command_path_to_managed_when_base_url_is_omitted() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        ["health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert manager.config_base_url == "http://127.0.0.1:8000"
    assert manager.events == ["start", "stop"]


def test_run_cli_without_mode_uses_remote_mode_when_base_url_is_supplied() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8116", "health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not start")),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}


def test_run_cli_explicit_remote_mode_overrides_managed_default() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8112", "health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not start")),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}


def test_run_cli_without_mode_ignores_api_base_url_env_for_repl_default(monkeypatch) -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/exit"])
    manager = _ManagedServerSpy()
    monkeypatch.setenv("NANO_MULTIAGENT_API_BASE_URL", "http://remote.example:8123")

    exit_code = run_cli(
        [],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert manager.config_base_url == "http://127.0.0.1:8000"
    assert manager.events == ["start", "stop"]
    # feat-333-M3/R2: REPL now prints an auto mode startup banner before the
    # session loop; the env var override does not affect the banner content.
    text = output.getvalue()
    assert "Auto mode" in text or "auto mode" in text, (
        f"Expected auto mode banner in REPL output, got: {text!r}"
    )


def test_run_cli_without_mode_ignores_api_base_url_env_for_command_default(monkeypatch) -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()
    monkeypatch.setenv("NANO_MULTIAGENT_API_BASE_URL", "http://remote.example:8123")

    exit_code = run_cli(
        ["health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert manager.config_base_url == "http://127.0.0.1:8000"
    assert manager.events == ["start", "stop"]


def test_run_cli_remote_mode_does_not_start_local_server() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8112",
            "health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not start")),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}


def test_run_cli_managed_mode_start_failure_surfaces_actionable_suggestion() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy(fail_on_start=RuntimeError("port 8000 already in use"))

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8000",
            "health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "port 8000 already in use" in payload["error"]
    assert "remote" in payload["suggestion"].lower()


def test_run_cli_remote_mode_requires_base_url_with_actionable_error() -> None:
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "health"],
        stdout=output,
        client_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not build client")),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "remote mode requires --base-url" in payload["error"]
    assert payload["layer"] == "input"
    assert "--base-url" in payload["suggestion"]


def test_run_cli_remote_mode_connection_failure_suggestion_mentions_remote_api() -> None:
    stub = _ConnectionRefusedOnHealthStubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8222",
            "health"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "connection refused" in payload["error"].lower()
    assert payload["layer"] == "network"
    assert "remote api" in payload["suggestion"].lower()


def test_run_cli_managed_mode_uses_higher_default_timeout_when_not_configured() -> None:
    observed: dict[str, float] = {}

    class _TimeoutCaptureClient(_StubClient):
        def __init__(self, timeout_seconds: float) -> None:
            super().__init__()
            observed["timeout_seconds"] = timeout_seconds

    output = io.StringIO()
    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://127.0.0.1:8113", "health"],
        stdout=output,
        client_factory=lambda config: _TimeoutCaptureClient(config.timeout_seconds),
        managed_server_factory=lambda _: _ManagedServerSpy(),
    )

    assert exit_code == 0
    assert observed["timeout_seconds"] == 120.0


def test_run_cli_respects_explicit_api_timeout_seconds() -> None:
    observed: dict[str, float] = {}

    class _TimeoutCaptureClient(_StubClient):
        def __init__(self, timeout_seconds: float) -> None:
            super().__init__()
            observed["timeout_seconds"] = timeout_seconds

    output = io.StringIO()
    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8114",
            "--api-timeout-seconds",
            "45",
            "health"],
        stdout=output,
        client_factory=lambda config: _TimeoutCaptureClient(config.timeout_seconds),
        managed_server_factory=lambda _: _ManagedServerSpy(),
    )

    assert exit_code == 0
    assert observed["timeout_seconds"] == 45.0


# ---------------------------------------------------------------------------
# Tests: llm-config subcommand
# ---------------------------------------------------------------------------

def test_run_cli_llm_config_get_outputs_payload() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8000", "llm-config", "get"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "openai_compat"
    assert stub.calls == [("get_llm_config", None)]


def test_run_cli_llm_config_set_applies_requested_fields() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8000",
            "llm-config",
            "set",
            "--provider",
            "anthropic",
            "--model",
            "kimiCoding:K2.6",
            "--base-url",
            "http://127.0.0.1:4100",
            "--api-key",
            "sk-cli",
            "--timeout-seconds",
            "55"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "anthropic"
    assert stub.calls == [
        (
            "set_llm_config",
            {
                "provider": "anthropic",
                "model": "kimiCoding:K2.6",
                "base_url": "http://127.0.0.1:4100",
                "api_key": "sk-cli",
                "timeout_seconds": 55.0,
                "clear_api_key": False,
            },
        )
    ]


def test_run_cli_llm_config_set_requires_at_least_one_field() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8000", "llm-config", "set"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "at least one" in payload["error"].lower()
    assert payload["layer"] == "input"
    assert "llm-config set" in payload["suggestion"]


def test_run_cli_llm_config_set_rejects_conflicting_api_key_flags() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8000",
            "llm-config",
            "set",
            "--api-key",
            "sk-cli",
            "--clear-api-key"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "cannot be used together" in payload["error"].lower()
    assert "choose either" in payload["suggestion"].lower()


def test_run_cli_managed_mode_forwards_llm_startup_options_to_managed_server() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8115",
            "--provider",
            "anthropic",
            "--model",
            "kimiCoding:K2.6",
            "--llm-base-url",
            "http://127.0.0.1:4100",
            "--api-key",
            "sk-managed",
            "--timeout-seconds",
            "75",
            "health"],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert manager.config_base_url == "http://127.0.0.1:8115"
    assert manager.llm_provider == "anthropic"
    assert manager.llm_model == "kimiCoding:K2.6"
    assert manager.llm_base_url == "http://127.0.0.1:4100"
    assert manager.llm_api_key == "sk-managed"
    assert manager.llm_timeout_seconds == 75.0
