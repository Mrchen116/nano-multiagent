"""Compatibility alias exposing canonical apps-level REPL runtime helpers."""

import sys

from nano_multiagent.apps.coding_cli.runtime import repl_runtime as _repl_runtime

sys.modules[__name__] = _repl_runtime
