"""Compatibility alias exposing canonical apps-level turn usage module."""

import sys

from nano_multiagent.apps.coding_cli.render import turn_usage as _turn_usage

sys.modules[__name__] = _turn_usage
