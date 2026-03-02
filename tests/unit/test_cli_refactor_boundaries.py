from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli import context_budget
from nano_multiagent.cli import error_presenter
from nano_multiagent.cli import repl_commands
from nano_multiagent.cli import repl_events


def test_commands_does_not_expose_repl_input_bridge_symbols() -> None:
    assert not hasattr(cli_commands, "_build_repl_input_reader")
    assert not hasattr(cli_commands, "_read_interactive_line")


<<<<<<< HEAD
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
