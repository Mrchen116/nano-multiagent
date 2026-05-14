"""AutoModeConfig: auto mode permission classifier configuration.

Global and workspace two-level loading (workspace overrides global).
Default: auto enabled, dangerously_skip_permissions disabled.

Config file location follows product config directory convention:
  - Coding CLI: ~/.nanocode/config.yaml > <workspace>/.nanocode/config.yaml
  - Personal Assistant: ~/.nanoassistant/config.yaml > <workspace>/.nanoassistant/config.yaml
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml


@dataclass(frozen=True)
class AutoModeConfig:
    """Auto mode permission classifier configuration.

    All fields are optional; missing fields fall back to safe defaults.
    Designed to be loaded from config.yaml auto_mode section.
    """

    enabled: bool = True
    dangerously_skip_permissions: bool = False
    always_allow_tools: tuple[str, ...] = ()
    deny_limit: int = 3
    ask_timeout_sec: int = 600
    unattended_fallback: Literal["deny", "allow"] = "deny"
    allow: tuple[str, ...] = ()
    soft_deny: tuple[str, ...] = ()
    environment: tuple[str, ...] = ()


def load_auto_mode_config(
    *,
    global_config_dir: Path | None,
    workspace_config_dir: Path | None,
) -> AutoModeConfig:
    """Load AutoModeConfig from global and workspace config.yaml files.

    Workspace values override global. Fields not present in workspace
    are inherited from global. Fields absent in both use dataclass defaults.

    Args:
        global_config_dir: Path to global config directory (e.g. ~/.nanocode/).
        workspace_config_dir: Path to workspace config directory, or None.

    Returns:
        Merged AutoModeConfig with workspace > global > default precedence.
    """
    global_raw = _read_auto_mode_section(global_config_dir)
    workspace_raw = _read_auto_mode_section(workspace_config_dir)

    # Workspace overrides global field-by-field
    merged = dict(global_raw)
    merged.update(workspace_raw)

    return _parse_auto_mode_config(merged)


def _read_auto_mode_section(config_dir: Path | None) -> dict[str, Any]:
    """Read the auto_mode section from config.yaml in config_dir."""
    if config_dir is None:
        return {}
    config_file = config_dir / "config.yaml"
    if not config_file.is_file():
        return {}
    try:
        raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except Exception:
        # Corrupted config → log warning (don't crash), use empty
        return {}
    if not isinstance(raw, Mapping):
        return {}
    section = raw.get("auto_mode")
    if not isinstance(section, Mapping):
        return {}
    return dict(section)


def _parse_auto_mode_config(raw: dict[str, Any]) -> AutoModeConfig:
    """Parse a flat dict (from merged config sections) into AutoModeConfig."""
    defaults = AutoModeConfig()

    enabled = _coerce_bool(raw.get("enabled"), defaults.enabled)
    dangerously_skip = _coerce_bool(raw.get("dangerously_skip_permissions"), defaults.dangerously_skip_permissions)
    always_allow_tools = _coerce_str_tuple(raw.get("always_allow_tools"), defaults.always_allow_tools)
    deny_limit = _coerce_int(raw.get("deny_limit"), defaults.deny_limit)
    ask_timeout_sec = _coerce_int(raw.get("ask_timeout_sec"), defaults.ask_timeout_sec)
    unattended_fallback = _coerce_literal(
        raw.get("unattended_fallback"), ("deny", "allow"), defaults.unattended_fallback
    )
    allow = _coerce_str_tuple(raw.get("allow"), defaults.allow)
    soft_deny = _coerce_str_tuple(raw.get("soft_deny"), defaults.soft_deny)
    environment = _coerce_str_tuple(raw.get("environment"), defaults.environment)

    return AutoModeConfig(
        enabled=enabled,
        dangerously_skip_permissions=dangerously_skip,
        always_allow_tools=always_allow_tools,
        deny_limit=deny_limit,
        ask_timeout_sec=ask_timeout_sec,
        unattended_fallback=unattended_fallback,
        allow=allow,
        soft_deny=soft_deny,
        environment=environment,
    )


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default


def _coerce_str_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return default
    return tuple(str(v) for v in value if isinstance(v, str))


def _coerce_literal(value: Any, allowed: tuple[str, ...], default: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return default
