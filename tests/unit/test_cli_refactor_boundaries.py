from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli import context_budget
from nano_multiagent.cli import repl_input
from nano_multiagent.cli import repl_commands
from nano_multiagent.cli import repl_events


def test_commands_delegates_repl_input_engine_to_module() -> None:
    assert cli_commands._build_repl_input_reader is repl_input.build_repl_input_reader
    assert cli_commands._read_interactive_line is repl_input.read_interactive_line


def test_commands_delegates_repl_command_routing_to_module() -> None:
    assert cli_commands._handle_repl_command is repl_commands.handle_repl_command
    assert cli_commands.supported_repl_commands() == repl_commands.REPL_COMMANDS


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
