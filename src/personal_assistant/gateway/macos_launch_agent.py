"""Own the concrete macOS LaunchAgent used to supervise one Gateway config."""

from __future__ import annotations

import hashlib
import math
import os
import plistlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

_LABEL_PREFIX = "io.github.mrchen116.nano-multiagent.gateway"
_DEFAULT_GATEWAY_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_UNLOAD_POLL_ATTEMPTS = 50
_UNLOAD_POLL_SECONDS = 0.1


def launch_agent_label(config_path: str | Path) -> str:
    """Return the stable LaunchAgent label for one resolved Gateway config."""
    resolved = str(Path(config_path).expanduser().resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return f"{_LABEL_PREFIX}.{digest}"


def plist_path_for_config(config_path: str | Path) -> Path:
    """Return the persistent user LaunchAgent plist path for one config."""
    return _launch_agents_directory() / f"{launch_agent_label(config_path)}.plist"


def is_loaded(*, config_path: str | Path) -> bool:
    """Return whether this config's job exists in the current GUI domain."""
    return _job_is_loaded(_identity(config_path))


def apply_and_start(
    *,
    config_path: str | Path,
    log_path: str | Path,
    shutdown_grace_seconds: float,
    auto_bind: bool = False,
    im_service_url_override: str | None = None,
) -> None:
    """Persist and bootstrap the LaunchAgent definition for one Gateway config.

    Args:
        config_path: Gateway YAML path used as the service identity and child input.
        log_path: File receiving child stdout and stderr.
        shutdown_grace_seconds: Existing Gateway grace period mapped to ExitTimeOut.
        auto_bind: Explicit one-launch binding control for the current login session.
        im_service_url_override: Explicit one-launch IM URL for the current login session.

    Raises:
        RuntimeError: When the GUI domain, unload, or bootstrap operation fails.
        OSError: When the persistent or temporary plist cannot be written or removed.

    Side Effects:
        Replaces the persistent plist, unloads any current definition, and bootstraps
        the new definition in the current user's GUI domain.
    """
    resolved_config = Path(config_path).expanduser().resolve()
    resolved_log = Path(log_path).expanduser().resolve()
    stable_path = plist_path_for_config(resolved_config)
    stable_payload = _plist_payload(
        config_path=resolved_config,
        log_path=resolved_log,
        shutdown_grace_seconds=shutdown_grace_seconds,
    )
    _write_plist(stable_path, stable_payload)
    stop_current_login(config_path=resolved_config)

    transient = auto_bind or bool(
        isinstance(im_service_url_override, str) and im_service_url_override.strip()
    )
    bootstrap_path = stable_path
    temporary_path: Path | None = None
    if transient:
        temporary_path = stable_path.with_name(
            f".{stable_path.stem}.{uuid4().hex}.bootstrap.plist"
        )
        transient_payload = _plist_payload(
            config_path=resolved_config,
            log_path=resolved_log,
            shutdown_grace_seconds=shutdown_grace_seconds,
            auto_bind=auto_bind,
            im_service_url_override=im_service_url_override,
        )
        _write_plist(temporary_path, transient_payload)
        bootstrap_path = temporary_path

    identity = _identity(resolved_config)
    try:
        result = _run_launchctl(
            ["/bin/launchctl", "bootstrap", identity.domain_target, str(bootstrap_path)]
        )
        _require_success(result, action="bootstrap Gateway LaunchAgent")
        if not _job_is_loaded(identity):
            raise RuntimeError(
                f"Gateway LaunchAgent {identity.label} was not loaded after bootstrap"
            )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def stop_current_login(*, config_path: str | Path) -> bool:
    """Boot out this config's current GUI-domain job while preserving its plist.

    Args:
        config_path: Gateway YAML path used to derive the stable service identity.

    Returns:
        ``True`` when a loaded job was booted out; ``False`` when it was not loaded.

    Raises:
        RuntimeError: When job state cannot be determined or bootout fails.

    Side Effects:
        Stops a loaded LaunchAgent in the current login session. The persistent plist
        remains available for the next login.
    """
    identity = _identity(config_path)
    if not _job_is_loaded(identity):
        return False
    result = _run_launchctl(
        ["/bin/launchctl", "bootout", "--wait", identity.service_target]
    )
    _require_success(result, action="boot out Gateway LaunchAgent")
    for attempt in range(_UNLOAD_POLL_ATTEMPTS):
        if not _job_is_loaded(identity):
            return True
        if attempt + 1 < _UNLOAD_POLL_ATTEMPTS:
            time.sleep(_UNLOAD_POLL_SECONDS)
    raise RuntimeError(
        f"Gateway LaunchAgent {identity.label} remained loaded after bootout"
    )


def permanently_remove(*, config_path: str | Path) -> bool:
    """Stop the current job and remove this config's persistent LaunchAgent plist.

    Args:
        config_path: Gateway YAML path used to derive the stable service identity.

    Returns:
        ``True`` when a loaded job was booted out; ``False`` when none was loaded.

    Raises:
        RuntimeError: When job state cannot be determined or bootout fails.
        OSError: When the persistent plist cannot be removed.

    Side Effects:
        Stops the current GUI-domain job before deleting its persistent definition.
    """
    stopped = stop_current_login(config_path=config_path)
    plist_path_for_config(config_path).unlink(missing_ok=True)
    return stopped


class _LaunchAgentIdentity:
    def __init__(self, *, label: str, uid: int) -> None:
        self.label = label
        self.domain_target = f"gui/{uid}"
        self.service_target = f"{self.domain_target}/{label}"


def _identity(config_path: str | Path) -> _LaunchAgentIdentity:
    return _LaunchAgentIdentity(label=launch_agent_label(config_path), uid=os.getuid())


def _job_is_loaded(identity: _LaunchAgentIdentity) -> bool:
    domain = _run_launchctl(["/bin/launchctl", "print", identity.domain_target])
    _require_success(domain, action="inspect current macOS GUI domain")
    result = _run_launchctl(["/bin/launchctl", "print", identity.service_target])
    if result.returncode == 0:
        return True
    diagnostic = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 113 and "Could not find service" in diagnostic:
        return False
    _require_success(result, action="inspect Gateway LaunchAgent")
    raise AssertionError("unreachable")


def _plist_payload(
    *,
    config_path: Path,
    log_path: Path,
    shutdown_grace_seconds: float,
    auto_bind: bool = False,
    im_service_url_override: str | None = None,
) -> dict[str, Any]:
    source_root = _source_root().resolve()
    python = _python_executable().absolute()
    arguments = [
        str(python),
        "-m",
        "personal_assistant.main",
        "--config",
        str(config_path),
        "--foreground",
    ]
    if auto_bind:
        arguments.append("--auto-bind")
    if isinstance(im_service_url_override, str) and im_service_url_override.strip():
        arguments.extend(["--im-service-url", im_service_url_override.strip()])
    return {
        "Label": launch_agent_label(config_path),
        "Program": str(python),
        "ProgramArguments": arguments,
        "WorkingDirectory": str(source_root.parent),
        "EnvironmentVariables": {
            "PATH": _DEFAULT_GATEWAY_PATH,
            "PYTHONPATH": str(source_root),
        },
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "KeepAlive": True,
        "ExitTimeOut": max(1, math.ceil(shutdown_grace_seconds)),
    }


def _write_plist(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path: Path | None = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            plistlib.dump(payload, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _require_success(result: subprocess.CompletedProcess[str], *, action: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
    raise RuntimeError(f"{action} failed: {detail}")


def _run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _launch_agents_directory() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _python_executable() -> Path:
    return Path(sys.executable)


def _source_root() -> Path:
    return Path(__file__).resolve().parents[2]
