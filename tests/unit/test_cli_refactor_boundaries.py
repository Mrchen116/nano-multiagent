from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli import repl_input
from nano_multiagent.cli import repl_commands


def test_commands_delegates_repl_input_engine_to_module() -> None:
    assert cli_commands._build_repl_input_reader is repl_input.build_repl_input_reader
    assert cli_commands._read_interactive_line is repl_input.read_interactive_line


def test_commands_delegates_repl_command_routing_to_module() -> None:
    assert cli_commands._handle_repl_command is repl_commands.handle_repl_command
    assert cli_commands.supported_repl_commands() == repl_commands.REPL_COMMANDS
