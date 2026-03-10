"""Shared tool output limits aligned with upstream coding-agent defaults.

Source of truth (upstream):
- /Users/czj/Repos/opencode-hub/pi-mono/packages/coding-agent/src/core/tools/truncate.ts
  - DEFAULT_MAX_LINES = 2000
  - DEFAULT_MAX_BYTES = 50 * 1024
"""

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024
DEFAULT_MAX_KILOBYTES = DEFAULT_MAX_BYTES // 1024
