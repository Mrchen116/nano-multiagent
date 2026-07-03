"""Bootstrap helpers for starting and stopping configured channels."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Callable

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry

DEFAULT_BUILTIN_SKILL_TARGET_ROOT = Path("~/.nanoassistant/skills")


def _copy_resource_tree(source: resources.abc.Traversable, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            _copy_resource_tree(item, target)
            continue
        if target.exists():
            continue
        target.write_bytes(item.read_bytes())


def install_builtin_skills(
    *, target_root: Path | None = None, package_name: str = "personal_assistant"
) -> tuple[str, ...]:
    """Install missing PA builtin skills from packaged resources.

    Args:
        target_root: Runtime skill root. Defaults to ``~/.nanoassistant/skills``.
        package_name: Package that owns the ``builtin_skills`` resource directory.

    Returns:
        Skill names copied during this call.

    Side Effects:
        Copies each packaged ``builtin_skills/<name>/`` directory into the runtime
        skill root when ``<target_root>/<name>/SKILL.md`` is missing. Existing user
        skill files are never overwritten.
    """

    resolved_target = (
        target_root if target_root is not None else DEFAULT_BUILTIN_SKILL_TARGET_ROOT
    ).expanduser()
    source_root = resources.files(package_name).joinpath("builtin_skills")
    if not source_root.is_dir():
        return ()

    installed: list[str] = []
    for skill_resource in sorted(source_root.iterdir(), key=lambda item: item.name):
        if not skill_resource.is_dir():
            continue
        if not skill_resource.joinpath("SKILL.md").is_file():
            continue
        skill_name = skill_resource.name
        destination = resolved_target / skill_name
        if (destination / "SKILL.md").exists():
            continue
        _copy_resource_tree(skill_resource, destination)
        installed.append(skill_name)
    return tuple(installed)


def start_channels(
    registry: ChannelRegistry, on_inbound: Callable[[InboundMessage], None]
) -> tuple[str, ...]:
    """Start all registered channel adapters.

    Args:
        registry: Registry containing configured channel adapters.
        on_inbound: Shared gateway callback invoked by every adapter.

    Returns:
        Names of adapters started in registry order.

    Side Effects:
        Calls ``start()`` on each registered channel adapter.
    """

    started: list[str] = []
    for channel in registry.list():
        channel.start(on_inbound)
        started.append(channel.name)
    return tuple(started)


def stop_channels(registry: ChannelRegistry) -> tuple[str, ...]:
    """Stop all registered channel adapters in reverse startup order."""

    stopped: list[str] = []
    for channel in reversed(registry.list()):
        channel.stop()
        stopped.append(channel.name)
    return tuple(stopped)
