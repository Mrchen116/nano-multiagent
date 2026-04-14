"""Executable release acceptance and rollback playbook for CLI delivery."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from typing import Callable


_CLI_GATE_TEST_COMMAND = (
    "PYTHONPATH=src pytest -q "
    "tests/unit/test_cli_main.py "
    "tests/unit/test_cli_refactor_boundaries.py "
    "tests/integration/test_cli_http_flow_integration.py "
    "tests/contract/test_cli_http_only_contract.py "
    "tests/contract/test_cli_error_contract.py"
)
_PYTHON_EXECUTABLE = shlex.quote(sys.executable)


def build_release_playbook_report(
    *,
    base_url: str,
    execute: bool,
    runner: Callable[[str], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, object]:
    """Build release playbook and optionally execute acceptance steps."""
    acceptance_steps = _build_acceptance_steps(base_url=base_url)
    rollback_steps = _build_rollback_steps()
    report: dict[str, object] = {
        "execute": execute,
        "acceptance_steps": acceptance_steps,
        "rollback_steps": rollback_steps,
        "status": "pending",
        "execution": [],
    }
    if not execute:
        return report

    resolved_runner = runner or _default_runner
    execution: list[dict[str, object]] = []
    status = "passed"
    for step in acceptance_steps:
        command = str(step["command"])
        result = resolved_runner(command)
        execution.append(
            {
                "name": step["name"],
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != 0:
            status = "failed"
            break
    report["execution"] = execution
    report["status"] = status
    return report


def _build_acceptance_steps(*, base_url: str) -> list[dict[str, str]]:
    return [
        {
            "name": "cli_gate_tests",
            "command": _CLI_GATE_TEST_COMMAND,
            "description": "Run required CLI unit/integration/contract gates.",
        },
        {
            "name": "managed_smoke_ping",
            "command": (
                "printf '/new\\nping\\n/exit\\n' | "
                f"PYTHONPATH=src {_PYTHON_EXECUTABLE} -m coding_cli.main "
                f"--mode managed --base-url {base_url}"
            ),
            "description": "Smoke managed mode with one short conversation turn.",
        },
    ]


def _build_rollback_steps() -> list[dict[str, str]]:
    return [
        {
            "name": "rollback_main_to_previous_commit",
            "command": "git checkout main && git revert <merge_commit_sha>",
            "description": "Rollback merged main commit by revert for safe history.",
        },
        {
            "name": "rollback_milestone_branch",
            "command": "git checkout milestone/M54 && git reset --hard <stable_c3_sha>",
            "description": "Rollback milestone branch to last stable C3 checkpoint.",
        },
        {
            "name": "revalidate_after_rollback",
            "command": _CLI_GATE_TEST_COMMAND,
            "description": "Re-run CLI gates after rollback.",
        },
    ]


def _default_runner(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, shell=True, check=False, capture_output=True, text=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nano-multiagent-cli-release-playbook",
        description="Render or execute CLI release acceptance/rollback playbook.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run release playbook command line entrypoint."""
    args = _build_parser().parse_args(argv)
    report = build_release_playbook_report(
        base_url=args.base_url,
        execute=bool(args.execute),
    )
    print(json.dumps(report, ensure_ascii=False))
    if args.execute and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
