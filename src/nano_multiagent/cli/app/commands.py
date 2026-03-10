"""Compatibility alias exposing canonical apps-level CLI commands module."""

import sys

from nano_multiagent.apps.coding_cli import commands as _app_commands

sys.modules[__name__] = _app_commands
