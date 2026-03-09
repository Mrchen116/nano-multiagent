"""Compatibility alias for platform-owned built-in tool helpers."""

import sys

from nano_multiagent.platform.tools import builtins as _platform_builtins

sys.modules[__name__] = _platform_builtins
