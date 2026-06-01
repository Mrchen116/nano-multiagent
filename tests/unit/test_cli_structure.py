"""CLI 架构 / 模块位置校验。

验证 CLI 内部模块的命名空间和事件管道契约，
不依赖任何运行时服务或 stub 客户端。
"""

from coding_cli import commands as cli_commands
from coding_cli.main import run_cli


def test_cli_commands_surface_matches_app_commands_module() -> None:
    import coding_cli.commands as app_commands

    assert cli_commands.build_parser is app_commands.build_parser
    assert cli_commands.run_cli is app_commands.run_cli
    assert run_cli is app_commands.run_cli


def test_cli_internal_modules_live_under_apps_coding_cli_subpackages() -> None:
    from coding_cli.events import repl_events as layered_events
    from coding_cli.input import repl_commands as layered_repl_commands
    from coding_cli.input import repl_input as layered_repl_input
    from coding_cli.render import context_budget as layered_context_budget
    from coding_cli.render import error_presenter as layered_error_presenter
    from coding_cli.render import repl_render as layered_repl_render
    from coding_cli.render import turn_usage as layered_turn_usage
    from coding_cli.runtime import repl_runtime as layered_repl_runtime

    assert (
        layered_events._event_preview_line.__module__ == "coding_cli.events.repl_events"
    )
    assert (
        layered_repl_input.emit_external_text.__module__
        == "coding_cli.input.repl_input"
    )
    assert layered_repl_commands.REPL_COMMANDS
    assert (
        layered_repl_render.print_repl_turn_summary.__module__
        == "coding_cli.render.repl_render"
    )
    assert (
        layered_repl_runtime.ReplRunQueue.__module__
        == "coding_cli.runtime.repl_runtime"
    )
    assert (
        layered_context_budget.print_context_budget_snapshot.__module__
        == "coding_cli.render.context_budget"
    )
    assert (
        layered_error_presenter.error_layer_for_exception.__module__
        == "coding_cli.render.error_presenter"
    )
    assert (
        layered_turn_usage.extract_turn_usage_metrics.__module__
        == "coding_cli.render.turn_usage"
    )


def test_cli_event_pipeline_layer_exposes_normalize_dedupe_and_view_model() -> None:
    from coding_cli.events import event_pipeline

    assert hasattr(event_pipeline, "NormalizedSessionEvent")
    assert hasattr(event_pipeline, "EventDedupeWindow")
    assert hasattr(event_pipeline, "normalize_session_event")
    assert hasattr(event_pipeline, "consume_event_for_run")
    assert hasattr(event_pipeline, "build_repl_view_model")


def test_cli_render_phase_machine_transitions_and_guards() -> None:
    from coding_cli.events.event_pipeline import ReplRenderPhase
    from coding_cli.events.event_pipeline import ReplRenderPhaseMachine

    machine = ReplRenderPhaseMachine()
    assert machine.phase is ReplRenderPhase.STREAMING
    assert machine.can_emit_preview() is True

    machine.begin_finalizing()
    assert machine.phase is ReplRenderPhase.FINALIZING
    assert machine.can_emit_preview() is False

    machine.mark_finalized()
    assert machine.phase is ReplRenderPhase.FINALIZED
    assert machine.can_emit_preview() is False


def test_cli_render_phase_machine_filters_previewed_tool_lines_from_final_summary() -> (
    None
):
    from coding_cli.events.event_pipeline import ReplRenderPhaseMachine

    machine = ReplRenderPhaseMachine()
    preview_identity = "run_target|bash|call_1|start"
    assert machine.should_emit_tool_preview(preview_identity) is True
    machine.record_tool_preview(
        preview_identity=preview_identity, preview_line_identity="bash start args=ping"
    )
    assert machine.should_emit_tool_preview(preview_identity) is False

    machine.begin_finalizing()
    filtered = machine.filter_summary_tool_updates(
        ["bash start args=ping", "bash exit code=0 status=completed duration=10ms"],
        line_identity_resolver=lambda line: line.strip(),
    )
    assert filtered == ["bash exit code=0 status=completed duration=10ms"]
