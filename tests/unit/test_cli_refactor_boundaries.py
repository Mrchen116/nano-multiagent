import io
import json
import subprocess

from nano_multiagent.apps.coding_cli.events import repl_events
from nano_multiagent.apps.coding_cli.input import repl_commands, repl_input
from nano_multiagent.apps.coding_cli.render import context_budget, error_presenter
from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli.main import run_cli


class _ExitOnlyStubClient:
    def __enter__(self) -> "_ExitOnlyStubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb



def test_commands_does_not_expose_repl_input_bridge_symbols() -> None:
    assert not hasattr(cli_commands, "_build_repl_input_reader")
    assert not hasattr(cli_commands, "_read_interactive_line")



def test_commands_does_not_expose_repl_command_bridge_symbols() -> None:
    assert not hasattr(cli_commands, "_handle_repl_command")
    assert not hasattr(cli_commands, "supported_repl_commands")



def test_repl_command_catalog_remains_stable() -> None:
    assert repl_commands.REPL_COMMANDS == ("/help", "/new", "/use", "/session", "/tools", "/compact", "/history", "/exit")



def test_commands_delegates_async_event_consumption_to_apps_module() -> None:
    assert cli_commands._supports_async_repl_events is repl_events.supports_async_repl_events
    assert cli_commands._send_message_with_async_events is repl_events.send_message_with_async_events
    assert cli_commands._consume_async_run_events is repl_events.consume_async_run_events
    assert cli_commands._print_event_preview is repl_events.print_event_preview
    assert cli_commands._merge_text_delta is repl_events.merge_text_delta



def test_commands_delegates_context_budget_snapshot_to_apps_module() -> None:
    assert cli_commands._print_context_budget_snapshot is context_budget.print_context_budget_snapshot
    assert cli_commands._context_budget_prefix is context_budget.context_budget_prefix
    assert cli_commands._extract_context_budget_metrics is context_budget.extract_context_budget_metrics
    assert cli_commands._context_budget_hint_for_ratio is context_budget.context_budget_hint_for_ratio



def test_commands_delegates_error_layer_and_suggestion_mapping_to_apps_module() -> None:
    assert cli_commands._error_layer_for_exception is error_presenter.error_layer_for_exception
    assert cli_commands._suggestion_for_exception is error_presenter.suggestion_for_exception



def test_run_repl_passes_supported_commands_to_apps_input_reader(monkeypatch) -> None:
    captured: dict[str, tuple[str, ...]] = {}

    def _fake_build_reader(*, out, input_fn, repl_input_reader_factory, command_suggestions):
        del out, input_fn, repl_input_reader_factory
        captured["command_suggestions"] = tuple(command_suggestions)
        return lambda prompt, history: "/exit"

    monkeypatch.setattr(repl_input, "build_repl_input_reader", _fake_build_reader)
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: _ExitOnlyStubClient(),
    )

    assert exit_code == 0
    assert captured["command_suggestions"] == repl_commands.REPL_COMMANDS



def test_cli_release_observability_is_thin_compat_shim() -> None:
    from nano_multiagent.apps.coding_cli.release_observability import build_guardrail_hints as apps_build_guardrail_hints
    from nano_multiagent.apps.coding_cli.release_observability import summarize_perf_metrics as apps_summarize_perf_metrics
    from nano_multiagent.cli.release_observability import build_guardrail_hints, summarize_perf_metrics

    assert build_guardrail_hints is apps_build_guardrail_hints
    assert summarize_perf_metrics is apps_summarize_perf_metrics

    hints = build_guardrail_hints(
        {
            "stable": False,
            "guardrail_reason": "throughput, redraw_ratio, sample_size",
            "throughput_ok": False,
            "redraw_ratio_ok": False,
            "sample_ready": False,
        }
    )
    assert hints == [
        "throughput: 检查 run_id 过滤或去重策略是否过严。",
        "redraw_ratio: 检查 preview 发射是否超过关键节点集合。",
        "sample_size: 当前样本不足，继续采样后再判定稳定性。",
    ]

    lines = summarize_perf_metrics(
        {
            "batches": 3,
            "polled_events": 120,
            "consumed_events": 96,
            "preview_emitted": 12,
            "run_filtered": 18,
            "dedupe_dropped": 6,
            "throughput_ratio": 0.8,
            "redraw_ratio": 0.125,
            "sample_ready": True,
            "throughput_ok": True,
            "redraw_ratio_ok": True,
            "stable": True,
            "guardrail_reason": "ok",
        }
    )
    assert lines == [
        "perf: stable=True reason=ok batches=3",
        "perf: polled=120 consumed=96 preview=12 filtered=18 dedupe=6",
        "perf: throughput=0.8 redraw_ratio=0.125 sample_ready=True",
    ]
    assert json.dumps(lines, ensure_ascii=False)



def test_cli_release_playbook_is_thin_compat_shim() -> None:
    from nano_multiagent.apps.coding_cli.release_playbook import build_release_playbook_report as apps_build_release_playbook_report
    from nano_multiagent.cli.release_playbook import build_release_playbook_report

    assert build_release_playbook_report is apps_build_release_playbook_report

    report = build_release_playbook_report(base_url="http://127.0.0.1:8003", token="test-token", execute=False)
    assert report["execute"] is False
    acceptance_steps = report["acceptance_steps"]
    rollback_steps = report["rollback_steps"]
    assert isinstance(acceptance_steps, list) and len(acceptance_steps) >= 2
    assert isinstance(rollback_steps, list) and len(rollback_steps) >= 2
    assert acceptance_steps[0]["name"] == "cli_gate_tests"
    assert "pytest -q tests/unit/test_cli_main.py" in acceptance_steps[0]["command"]
    assert rollback_steps[0]["name"] == "rollback_main_to_previous_commit"



def test_cli_release_playbook_execute_runs_steps_and_collects_status() -> None:
    from nano_multiagent.cli.release_playbook import build_release_playbook_report

    calls: list[str] = []

    def _fake_runner(command: str) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "pytest -q" in command:
            return subprocess.CompletedProcess(command, 0, stdout="gate ok", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = build_release_playbook_report(
        base_url="http://127.0.0.1:8003",
        token="test-token",
        execute=True,
        runner=_fake_runner,
    )

    assert report["execute"] is True
    assert report["status"] == "passed"
    execution = report["execution"]
    assert isinstance(execution, list) and len(execution) >= 2
    assert all(item["returncode"] == 0 for item in execution)
    assert any("pytest -q tests/unit/test_cli_main.py" in cmd for cmd in calls)
