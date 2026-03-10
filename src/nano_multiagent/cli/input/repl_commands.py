"""Compatibility alias exposing canonical apps-level REPL command module."""

import sys

from nano_multiagent.apps.coding_cli.input import repl_commands as _repl_commands

sys.modules[__name__] = _repl_commands
