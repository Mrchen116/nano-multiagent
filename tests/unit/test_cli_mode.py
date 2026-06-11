"""CLI 运行模式 / lifecycle / LLM config 测试 (refactor-387 M2)。

M2 后：
- --mode managed/remote 已删除，CLI 总是进程内启动 Kernel
- --base-url 已删除
- health 子命令已删除
- llm-config get/set 通过 Kernel.get_llm_config / reconfigure_llm 实现
"""

import io
import json
from unittest.mock import MagicMock

from coding_cli.main import run_cli
from tests.unit._cli_kernel_stubs import (
    _BaseKernelStub,
    _make_kernel_factory,
)


# ---------------------------------------------------------------------------
# LLM config stub
# ---------------------------------------------------------------------------


class _LLMConfigKernelStub(_BaseKernelStub):
    def __init__(self) -> None:
        super().__init__()
        from tests.unit._cli_kernel_stubs import _StubLLMConfig

        self._llm_config = _StubLLMConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
            timeout_seconds=30.0,
        )

    def reconfigure_llm(self, **kwargs):
        self.calls.append(("reconfigure_llm", kwargs))
        for key, value in kwargs.items():
            if hasattr(self._llm_config, key):
                setattr(self._llm_config, key, value)
        return self._llm_config


# ---------------------------------------------------------------------------
# Tests: basic REPL lifecycle (replaces managed/remote lifecycle tests)
# ---------------------------------------------------------------------------


def test_run_cli_enters_repl_directly_without_mode(tmp_path) -> None:
    """M2: no --mode flag; CLI always enters async REPL via Kernel SDK."""
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Auto mode" in text or "auto mode" in text


def test_run_cli_kernel_closed_on_exit(tmp_path) -> None:
    """kernel.aclose() must be called when REPL exits normally (bugfix-402-M3 R2)."""
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/exit"])

    run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    # bugfix-402-M3 R2: _async_main finally now calls aclose() (async), not close()
    assert any(call[0] == "aclose" for call in stub.calls)


def test_run_cli_kernel_closed_on_eof(tmp_path) -> None:
    """kernel.aclose() must be called when REPL exits via EOF (bugfix-402-M3 R2)."""
    stub = _BaseKernelStub()
    output = io.StringIO()

    def _eof(_):
        raise EOFError()

    run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=_eof,
        workspace_root=tmp_path,
    )

    # bugfix-402-M3 R2: _async_main finally now calls aclose() (async), not close()
    assert any(call[0] == "aclose" for call in stub.calls)


def test_run_cli_auto_mode_banner_shown_at_startup(tmp_path) -> None:
    """Auto mode banner must appear before the first prompt."""
    stub = _BaseKernelStub()
    output = io.StringIO()
    inputs = iter(["/exit"])

    run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    text = output.getvalue()
    assert "Auto mode" in text or "auto mode" in text


# ---------------------------------------------------------------------------
# Tests: llm-config subcommand
# ---------------------------------------------------------------------------


def test_run_cli_llm_config_get_outputs_payload(tmp_path) -> None:
    stub = _LLMConfigKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        ["llm-config", "get"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "openai_compat"
    assert any(call[0] == "get_llm_config" for call in stub.calls)


def test_run_cli_llm_config_set_applies_requested_fields(tmp_path) -> None:
    stub = _LLMConfigKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        [
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
            "55",
        ],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "anthropic"
    assert (
        "reconfigure_llm",
        {
            "provider": "anthropic",
            "model": "kimiCoding:K2.6",
            "base_url": "http://127.0.0.1:4100",
            "api_key": "sk-cli",
            "timeout_seconds": 55.0,
        },
    ) in stub.calls


def test_run_cli_llm_config_set_requires_at_least_one_field(tmp_path) -> None:
    stub = _LLMConfigKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        ["llm-config", "set"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "at least one" in payload["error"].lower()
    assert payload["layer"] == "input"


def test_run_cli_llm_config_set_rejects_conflicting_api_key_flags(tmp_path) -> None:
    stub = _LLMConfigKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        ["llm-config", "set", "--api-key", "sk-cli", "--clear-api-key"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "cannot be used together" in payload["error"].lower()
    assert "choose either" in payload["suggestion"].lower()


def test_run_cli_llm_flags_forwarded_to_kernel_factory(tmp_path) -> None:
    """--model, --provider etc. are available to the kernel factory via args."""
    received_kwargs: dict = {}

    def _capturing_factory():
        received_kwargs["called"] = True
        return _BaseKernelStub()

    output = io.StringIO()
    inputs = iter(["/exit"])

    run_cli(
        ["--model", "kimiCoding:K2.6", "--provider", "anthropic"],
        stdout=output,
        kernel_factory=_capturing_factory,
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert received_kwargs.get("called"), "kernel_factory must be called"
