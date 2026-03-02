import inspect

from nano_multiagent.cli import main as cli_main
from nano_multiagent.sdk import client as sdk_client


def test_cli_keeps_http_only_boundary() -> None:
    cli_source = inspect.getsource(cli_main)
    sdk_source = inspect.getsource(sdk_client)

    assert "agent.runtime" not in cli_source
    assert "agent.runtime" not in sdk_source
    assert "ServerClient" in cli_source


def test_cli_exposes_minimal_http_commands() -> None:
    parser = cli_main.build_parser()
    subparsers = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]
    assert subparsers
    names = set(subparsers[0].choices.keys())
    assert {"health", "create-session", "send-message"}.issubset(names)
