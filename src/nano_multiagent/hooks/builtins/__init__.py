"""Compatibility alias for platform-owned built-in hook modules."""

import sys

from nano_multiagent.platform.hooks import builtins as _platform_builtins

sys.modules[__name__] = _platform_builtins
