"""Compatibility alias exposing canonical platform session service module."""

import sys

from nano_multiagent.platform.persistence.session import service as _service

sys.modules[__name__] = _service
