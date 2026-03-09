"""CLI public entrypoints for parser construction and process execution."""


def build_parser(*args, **kwargs):
    from nano_multiagent.apps.coding_cli.commands import build_parser as _build_parser

    return _build_parser(*args, **kwargs)



def run_cli(*args, **kwargs):
    from nano_multiagent.apps.coding_cli.commands import run_cli as _run_cli

    return _run_cli(*args, **kwargs)


__all__ = ["build_parser", "run_cli"]
