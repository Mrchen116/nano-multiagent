"""Compatibility alias exposing canonical apps-level context budget helpers."""

import sys

from nano_multiagent.apps.coding_cli.render import context_budget as _context_budget

sys.modules[__name__] = _context_budget
