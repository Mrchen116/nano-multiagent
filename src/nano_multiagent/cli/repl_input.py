"""Compatibility alias exposing canonical apps-level REPL input helpers."""

import sys

from nano_multiagent.apps.coding_cli.input import repl_input as _repl_input

sys.modules[__name__] = _repl_input
