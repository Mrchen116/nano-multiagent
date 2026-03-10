"""Compatibility alias exposing canonical apps-level REPL render module."""

import sys

from nano_multiagent.apps.coding_cli.render import repl_render as _repl_render

sys.modules[__name__] = _repl_render
