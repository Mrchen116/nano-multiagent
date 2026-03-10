"""Compatibility alias exposing canonical apps-level error presenter module."""

import sys

from nano_multiagent.apps.coding_cli.render import error_presenter as _error_presenter

sys.modules[__name__] = _error_presenter
