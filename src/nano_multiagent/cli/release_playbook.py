"""Compatibility shim for the canonical apps-level CLI release playbook."""

import sys

from nano_multiagent.apps.coding_cli.release_playbook import build_release_playbook_report, main

__all__ = ["build_release_playbook_report", "main"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
