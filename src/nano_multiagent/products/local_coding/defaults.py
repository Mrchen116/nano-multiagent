"""Static defaults for the local_coding product package."""

from pathlib import Path

CONFIG_NAMESPACE = "nanocode"
GLOBAL_CONFIG_HOME = Path("~/.nanocode")
WORKSPACE_CONFIG_DIRNAME = ".nanocode"
SESSION_DB_FILENAME = "sessions.sqlite3"
COMPAT_SKILL_ROOTS = [Path("~/.codex/skills")]
MEMORY_LAYOUT = {"kind": "workspace_scoped"}
HEARTBEAT_LAYOUT = {"transport": "runtime_events"}

__all__ = [
    "CONFIG_NAMESPACE",
    "GLOBAL_CONFIG_HOME",
    "WORKSPACE_CONFIG_DIRNAME",
    "SESSION_DB_FILENAME",
    "COMPAT_SKILL_ROOTS",
    "MEMORY_LAYOUT",
    "HEARTBEAT_LAYOUT",
]
