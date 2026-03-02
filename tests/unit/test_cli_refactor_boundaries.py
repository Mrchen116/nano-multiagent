from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli import repl_input


def test_commands_delegates_repl_input_engine_to_module() -> None:
    assert cli_commands._build_repl_input_reader is repl_input.build_repl_input_reader
    assert cli_commands._read_interactive_line is repl_input.read_interactive_line
