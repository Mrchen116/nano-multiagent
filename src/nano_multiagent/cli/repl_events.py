"""Compatibility alias exposing canonical apps-level REPL event helpers."""

import sys

from nano_multiagent.apps.coding_cli.events import repl_events as _repl_events

sys.modules[__name__] = _repl_events
