"""Console script module for launching CLI through HTTP API boundary."""

from nano_multiagent.cli.commands import build_parser, run_cli


if __name__ == "__main__":
    raise SystemExit(run_cli())
