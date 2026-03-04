import io
import json

from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli import context_budget
from nano_multiagent.cli import error_presenter
from nano_multiagent.cli import repl_commands
from nano_multiagent.cli import repl_events
from nano_multiagent.cli import repl_input
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


def test_commands_delegates_async_event_consumption_to_module() -> None:
    assert cli_commands._supports_async_repl_events is repl_events.supports_async_repl_events
    assert cli_commands._send_message_with_async_events is repl_events.send_message_with_async_events
    assert cli_commands._consume_async_run_events is repl_events.consume_async_run_events
    assert cli_commands._print_event_preview is repl_events.print_event_preview
    assert cli_commands._merge_text_delta is repl_events.merge_text_delta


def test_commands_delegates_context_budget_snapshot_to_module() -> None:
    assert cli_commands._print_context_budget_snapshot is context_budget.print_context_budget_snapshot
    assert cli_commands._context_budget_prefix is context_budget.context_budget_prefix
    assert cli_commands._extract_context_budget_metrics is context_budget.extract_context_budget_metrics
    assert cli_commands._context_budget_hint_for_ratio is context_budget.context_budget_hint_for_ratio


def test_commands_delegates_error_layer_and_suggestion_mapping_to_module() -> None:
    assert cli_commands._error_layer_for_exception is error_presenter.error_layer_for_exception
    assert cli_commands._suggestion_for_exception is error_presenter.suggestion_for_exception


def test_run_repl_passes_supported_commands_to_input_reader(monkeypatch) -> None:
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


def test_cli_release_observability_maps_guardrail_reason_to_actionable_hints() -> None:
    from nano_multiagent.cli.release_observability import build_guardrail_hints

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


def test_cli_release_observability_builds_summary_lines_from_perf_metrics() -> None:
    from nano_multiagent.cli.release_observability import summarize_perf_metrics

    metrics = {
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

    lines = summarize_perf_metrics(metrics)

    assert lines == [
        "perf: stable=True reason=ok batches=3",
        "perf: polled=120 consumed=96 preview=12 filtered=18 dedupe=6",
        "perf: throughput=0.8 redraw_ratio=0.125 sample_ready=True",
    ]
    assert json.dumps(lines, ensure_ascii=False)
