"""Static defaults for the personal_assistant product package."""

from pathlib import Path

CONFIG_NAMESPACE = "nanoassistant"
GLOBAL_CONFIG_HOME = Path("~/.nanoassistant")
WORKSPACE_CONFIG_DIRNAME = ".nanoassistant"
SESSION_DB_FILENAME = "sessions.sqlite3"
COMPAT_SKILL_ROOTS: list[Path] = [Path("~/.claude/skills"), Path("~/.codex/skills")]
MEMORY_LAYOUT = {"kind": "personal_memory"}
HEARTBEAT_LAYOUT = {"transport": "assistant_presence"}
CAPABILITIES = {"im": True, "heartbeat": True, "memory": True}

__all__ = [
    "CONFIG_NAMESPACE",
    "GLOBAL_CONFIG_HOME",
    "WORKSPACE_CONFIG_DIRNAME",
    "SESSION_DB_FILENAME",
    "COMPAT_SKILL_ROOTS",
    "MEMORY_LAYOUT",
    "HEARTBEAT_LAYOUT",
    "CAPABILITIES",
]
