"""Own Gateway background process lifecycle and process identity safety."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
from personal_assistant.config.local_store import (
    LocalConfig,
    default_local_config_path,
    load_gateway_runtime_config,
    load_local_config,
)
from personal_assistant.gateway import runtime
from personal_assistant.gateway.im_bootstrap import GatewayStartupError

_log = logging.getLogger("personal_assistant.gateway.process_lifecycle")
ProcessLike = subprocess.Popen[Any]
BackgroundProcessFactory = Callable[[list[str], Path], ProcessLike]
StartWaiter = Callable[[ProcessLike, LocalConfig, float], None]
SignalHandlerInstaller = Callable[[], Callable[[], None]]


def install_builtin_skills_for_gateway() -> None:
    """Synchronize packaged skills without preventing Gateway startup.

    The installation belongs to the foreground process because it writes the
    user-global skill root. A background launcher only creates that process.
    """
    try:
        synchronized_builtin_skills = install_builtin_skills()
        if synchronized_builtin_skills:
            synchronized_names = ", ".join(sorted(synchronized_builtin_skills))
            _log.info(
                "synchronized built-in personal assistant skills: %s",
                synchronized_names,
            )
    except Exception:  # noqa: BLE001
        _log.warning(
            "failed to synchronize built-in personal assistant skills", exc_info=True
        )


@dataclass(frozen=True, slots=True)
class RuntimeFactories:
    """Collect replaceable construction hooks used by the gateway entry.

    Args:
        load_config: Function used to load YAML config into `LocalConfig`.
        build_runtime: Factory that creates the runtime orchestrator from config.
        install_signal_handlers: Optional hook that installs OS signal handlers before run.
    """

    load_config: Callable[[str | Path], LocalConfig] = load_local_config
    build_runtime: Callable[[LocalConfig], runtime.GatewayRuntimeLike] | None = None
    install_signal_handlers: SignalHandlerInstaller | None = None


@dataclass(frozen=True, slots=True)
class BackgroundLaunchResult:
    """Describe the operator-facing result of a successful background launch.

    Args:
        pid: Process id of the detached foreground child now hosting the gateway runtime.
        log_path: File receiving the detached child stdout/stderr stream.
        im_service_url: Optional IM service URL configured for this gateway.
    """

    pid: int
    log_path: Path
    im_service_url: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayRuntimeState:
    """Persist the operator-facing metadata needed to locate one background gateway.

    Args:
        pid: Background gateway process id launched for this config.
        config_path: Absolute config path used for that process.
        log_path: Log file receiving the detached process output.
        process_start: OS process birth identity. ``None`` identifies legacy state.
    """

    pid: int
    config_path: str
    log_path: str
    process_start: str | None = None


def _read_log_last_error(
    log_path: Path, *, offset: int = 0, lines: int = 20
) -> str | None:
    """Return the last non-empty line written after *offset* bytes, or None if unreadable."""
    try:
        with log_path.open("rb") as f:
            f.seek(offset)
            chunk = f.read().decode("utf-8", errors="replace")
        tail = [l for l in chunk.splitlines()[-lines:] if l.strip()]
        return tail[-1] if tail else None
    except Exception:  # noqa: BLE001
        return None


def run_gateway(
    *,
    config_path: str | Path,
    factories: RuntimeFactories | Mapping[str, Any] | None = None,
    im_service_url_override: str | None = None,
) -> int:
    """Load config, build runtime, and execute the gateway entry flow.

    Args:
        config_path: YAML config file passed by the operator.
        factories: Optional factory overrides used by tests.

    Returns:
        Process exit code. `0` means the managed startup/shutdown sequence succeeded.
    """

    resolved_factories = _coerce_factories(factories)
    config = load_gateway_runtime_config(
        config_path,
        load_config=resolved_factories.load_config,
        im_service_url_override=im_service_url_override,
    )
    # This foreground process owns persistent packaged-skill installation; detached
    # launchers only spawn this entry and must not duplicate the filesystem effect.
    install_builtin_skills_for_gateway()
    # refactor-406-M2: model registry init is build_kernel's responsibility (决策 5):
    # build_runtime → build_pa_kernel → build_kernel inits the registry from config.llm.
    builder = resolved_factories.build_runtime or _default_build_runtime
    runtime = builder(config)
    restore_signal_handlers = (
        resolved_factories.install_signal_handlers
        or _install_default_signal_handlers(runtime)
    )
    restore = restore_signal_handlers()
    pid = os.getpid()
    process_start = _process_start_identity(pid)
    if process_start is None:
        raise RuntimeError(f"cannot read process birth identity for gateway pid={pid}")
    state = GatewayRuntimeState(
        pid=pid,
        process_start=process_start,
        config_path=str(config.source_path.resolve()),
        log_path=str(_default_gateway_log_path(config)),
    )
    _write_gateway_state(config, state)
    try:
        return runtime.run_forever()
    finally:
        restore()
        _remove_gateway_state(_gateway_state_path(config), expected=state)


def launch_gateway_in_background(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_start: StartWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Start the gateway in a detached child and confirm its PID is live.

    Args:
        config_path: Operator-provided config path forwarded to the detached child.
        load_config: Config loader used to resolve lifecycle timing before spawning.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_start: Optional PID/start confirmation waiter override used by tests.

    Returns:
        Detached process metadata once the child writes its PID and remains alive.

    Raises:
        RuntimeError: When the detached child exits or never confirms startup.
    """
    with _gateway_lifecycle_lock(config_path):
        return _launch_gateway_in_background_unlocked(
            config_path=config_path,
            load_config=load_config,
            spawn_process=spawn_process,
            wait_for_start=wait_for_start,
            im_service_url_override=im_service_url_override,
        )


def _launch_gateway_in_background_unlocked(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig],
    spawn_process: BackgroundProcessFactory | None,
    wait_for_start: StartWaiter | None,
    im_service_url_override: str | None,
) -> BackgroundLaunchResult:
    """Execute one background launch while the caller holds its lifecycle lock."""

    config = load_gateway_runtime_config(
        config_path,
        load_config=load_config,
        im_service_url_override=im_service_url_override,
    )
    state_path = _gateway_state_path(config)
    existing_state = _read_gateway_state(state_path)
    if existing_state is not None:
        _assert_gateway_state_static(config, existing_state)
        signal_state = (
            _upgrade_legacy_gateway_state(config, existing_state.pid, existing_state)
            if existing_state.process_start is None
            else existing_state
        )
        if signal_state is not None and _gateway_process_matches(signal_state):
            raise GatewayStartupError(
                summary=f"gateway is already running (pid={existing_state.pid})",
                next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
            )
        _remove_gateway_state(state_path, expected=existing_state)
    else:
        legacy_pid = _read_legacy_gateway_pid(config)
        if legacy_pid is not None:
            legacy_state = _upgrade_legacy_gateway_state(config, legacy_pid, None)
            if legacy_state is not None and _gateway_process_matches(legacy_state):
                raise GatewayStartupError(
                    summary=f"gateway is already running (pid={legacy_pid})",
                    next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
                )
            _remove_legacy_gateway_pid(config, expected_pid=legacy_pid)

    log_path = _default_gateway_log_path(config)
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    argv = _background_gateway_argv(
        config.source_path, im_service_url_override=im_service_url_override
    )
    launcher = spawn_process or _spawn_background_gateway_process
    start_waiter = wait_for_start or _wait_for_gateway_start
    process = launcher(argv, log_path)
    try:
        start_waiter(process, config, config.gateway.startup_timeout_seconds)
    except Exception as exc:
        _stop_background_process(
            process, timeout_seconds=config.gateway.shutdown_grace_seconds
        )
        hint = _read_log_last_error(log_path, offset=log_offset)
        summary = hint if hint else str(exc)
        raise GatewayStartupError(
            summary=summary,
            next_step=f"Check the log for details: tail -20 {log_path}",
        ) from exc
    result = BackgroundLaunchResult(
        pid=process.pid,
        log_path=log_path,
        im_service_url=config.im_service.url if config.im_service is not None else None,
    )
    published_state = _read_gateway_state(state_path)
    if published_state is None:
        _stop_background_process(
            process, timeout_seconds=config.gateway.shutdown_grace_seconds
        )
        raise GatewayStartupError(
            summary="gateway child did not publish lifecycle state",
            next_step=f"Check the log for details: tail -20 {log_path}",
        )
    _assert_gateway_state_static(config, published_state, expected_pid=process.pid)
    return result


def stop_gateway(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
) -> str:
    """Stop the background gateway associated with one config path.

    Args:
        config_path: Operator-provided config path used to resolve the runtime state file.
        load_config: Config loader used to derive the state file and shutdown timing.

    Returns:
        One operator-facing status line describing stop success, not-running, or stale state.

    Side Effects:
        Sends SIGTERM and possibly SIGKILL to the background gateway process and removes stale state.
    """
    with _gateway_lifecycle_lock(config_path):
        return _stop_gateway_unlocked(config_path=config_path, load_config=load_config)


def restart_gateway(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_start: StartWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Stop and start one Gateway as a single serialized lifecycle operation.

    Args:
        config_path: Operator-provided config path identifying the lifecycle owner.
        load_config: Config loader shared by the stop and start phases.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_start: Optional process-start confirmation override used by tests.
        im_service_url_override: Optional IM service URL forwarded to the new process.

    Returns:
        Metadata for the replacement background Gateway.

    Side Effects:
        Stops the owned Gateway, then launches its replacement while holding one lock.
    """
    with _gateway_lifecycle_lock(config_path):
        _stop_gateway_unlocked(config_path=config_path, load_config=load_config)
        return _launch_gateway_in_background_unlocked(
            config_path=config_path,
            load_config=load_config,
            spawn_process=spawn_process,
            wait_for_start=wait_for_start,
            im_service_url_override=im_service_url_override,
        )


def _stop_gateway_unlocked(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig],
) -> str:
    """Stop one Gateway while the caller holds its lifecycle lock."""

    config = load_config(config_path)
    state_path = _gateway_state_path(config)
    state = _read_gateway_state(state_path)
    if state is None:
        pid = _read_legacy_gateway_pid(config)
        if pid is None:
            return f"NOT RUNNING config={config.source_path.name} state={state_path}"
        success_target = f"pid_file={_legacy_gateway_pid_path(config)}"
        state_to_remove = None
    else:
        pid = state.pid
        _assert_gateway_state_static(config, state)
        success_target = f"state={state_path}"
        state_to_remove = state_path

    if state is None or state.process_start is None:
        signal_state = _upgrade_legacy_gateway_state(config, pid, state)
        if signal_state is None:
            _remove_legacy_gateway_pid(config, expected_pid=pid)
            if state_to_remove is not None:
                _remove_gateway_state(state_to_remove, expected=state)
            return f"STALE pid={pid} {success_target}"
    else:
        signal_state = state
    if not _gateway_process_matches(signal_state):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STALE pid={pid} {success_target}"

    if not _signal_gateway_process(signal_state, signal.SIGTERM):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target}"
    if _wait_for_gateway_exit(config, signal_state):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target}"
    if not _signal_gateway_process(signal_state, signal.SIGKILL):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target} forced=true"
    if not _wait_for_gateway_exit(config, signal_state):
        raise RuntimeError(
            f"gateway pid={pid} did not exit after SIGKILL; lifecycle state retained"
        )
    _clear_gateway_lifecycle(config, state_to_remove, signal_state)
    return f"STOPPED pid={pid} {success_target} forced=true"


def _wait_for_gateway_exit(config: LocalConfig, state: GatewayRuntimeState) -> bool:
    """Wait one shutdown grace interval for the original process instance to exit."""
    deadline = time.monotonic() + config.gateway.shutdown_grace_seconds
    while _gateway_process_matches(state):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(config.gateway.poll_interval_seconds, remaining))
    return True


def _clear_gateway_lifecycle(
    config: LocalConfig,
    state_path: Path | None,
    completed: GatewayRuntimeState,
) -> None:
    """Clear only lifecycle evidence that still names the completed instance."""
    if state_path is not None:
        _remove_gateway_state(state_path, expected=completed)
    _remove_legacy_gateway_pid(config, expected_pid=completed.pid)


def _coerce_factories(
    factories: RuntimeFactories | Mapping[str, Any] | None,
) -> RuntimeFactories:
    if factories is None:
        return RuntimeFactories()
    if isinstance(factories, RuntimeFactories):
        return factories
    load_config = factories.get("load_config", load_local_config)
    build_runtime_factory = factories.get("build_runtime")
    install_signal_handlers = factories.get("install_signal_handlers")
    return RuntimeFactories(
        load_config=load_config,
        build_runtime=build_runtime_factory,
        install_signal_handlers=install_signal_handlers,
    )


def _default_gateway_log_path(config: LocalConfig) -> Path:
    return config.source_path.parent / "gateway.log"


def _legacy_gateway_pid_path(config: LocalConfig) -> Path:
    """Return the pre-refactor PID file path used only during live migration.

    Returns:
        Path to ``gateway.pid`` inside the config's runtime directory.
    """
    return config.source_path.parent / "gateway.pid"


@contextmanager
def _gateway_lifecycle_lock(config_path: str | Path) -> Iterator[None]:
    """Serialize lifecycle operations for one resolved config across processes."""
    resolved = Path(config_path).expanduser().resolve()
    lock_path = resolved.parent / f".{resolved.name}.gateway-lifecycle.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _remove_legacy_gateway_pid(
    config: LocalConfig, *, expected_pid: int | None = None
) -> None:
    """Remove a legacy ``gateway.pid`` only while it names the expected process.

    Side Effects:
        Deletes the PID file; silently succeeds if the file is already gone.
    """
    if expected_pid is not None and _read_legacy_gateway_pid(config) != expected_pid:
        return
    with suppress(FileNotFoundError):
        _legacy_gateway_pid_path(config).unlink()


def _read_legacy_gateway_pid(config: LocalConfig) -> int | None:
    """Read a pre-refactor ``gateway.pid``, or ``None`` if absent/invalid.

    Returns:
        Integer PID when the file exists and contains a parseable integer; ``None`` otherwise.
    """
    pid_path = _legacy_gateway_pid_path(config)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _process_start_identity(pid: int) -> str | None:
    """Read the OS process birth identity for one PID without signalling it."""
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return None
    return " ".join(value.split())


def _process_command(pid: int) -> str | None:
    """Read the full live command for one PID without signalling it."""
    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
    )
    command = result.stdout.strip()
    return command if result.returncode == 0 and command else None


def _process_cwd(pid: int) -> Path | None:
    """Return the live process working directory when the OS exposes it."""
    proc_cwd = Path(f"/proc/{pid}/cwd")
    try:
        return proc_cwd.resolve(strict=True)
    except (FileNotFoundError, OSError):
        pass
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return Path(line[1:]).resolve()
    return None


def _legacy_gateway_command_matches(
    command: str, *, pid: int, config: LocalConfig
) -> bool:
    """Validate one legacy Gateway command by argv semantics, not formatting."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if (
        not any(
            argv[index : index + 2] == ["-m", "personal_assistant.main"]
            for index in range(max(0, len(argv) - 1))
        )
        or "--foreground" not in argv
    ):
        return False

    raw_config: str | None = None
    for index, value in enumerate(argv):
        if value == "--config" and index + 1 < len(argv):
            raw_config = argv[index + 1]
            break
        if value.startswith("--config="):
            raw_config = value.split("=", 1)[1]
            break
    if raw_config is None:
        candidate = default_local_config_path()
    else:
        candidate = Path(raw_config).expanduser()
        if not candidate.is_absolute():
            cwd = _process_cwd(pid)
            if cwd is None:
                return False
            candidate = cwd / candidate
    return candidate.resolve() == config.source_path.resolve()


def _upgrade_legacy_gateway_state(
    config: LocalConfig,
    pid: int,
    state: GatewayRuntimeState | None,
) -> GatewayRuntimeState | None:
    """Adopt a legacy PID only after its live command proves Gateway ownership."""
    before = _process_start_identity(pid)
    if before is None:
        return None
    command = _process_command(pid)
    after = _process_start_identity(pid)
    if after is None:
        return None
    if before != after:
        raise RuntimeError("legacy Gateway process changed; evidence retained")
    config_path = str(config.source_path.resolve())
    if command is None or not _legacy_gateway_command_matches(
        command, pid=pid, config=config
    ):
        raise RuntimeError("legacy Gateway ownership mismatch; evidence retained")
    upgraded = (
        replace(state, process_start=after)
        if state is not None
        else GatewayRuntimeState(
            pid=pid,
            process_start=after,
            config_path=config_path,
            log_path=str(_default_gateway_log_path(config)),
        )
    )
    if state is not None:
        _write_gateway_state(config, upgraded)
    _log.warning(
        "adopted legacy Gateway lifecycle evidence after live command verification"
    )
    return upgraded


def _assert_gateway_state_static(
    config: LocalConfig,
    state: GatewayRuntimeState,
    *,
    expected_pid: int | None = None,
) -> None:
    """Reject state that does not claim the selected PID and resolved config."""
    if (expected_pid is not None and state.pid != expected_pid) or Path(
        state.config_path
    ).resolve() != config.source_path.resolve():
        raise RuntimeError("gateway state does not match process and config")


def _gateway_process_matches(state: GatewayRuntimeState) -> bool:
    """Return whether the PID still names the original process birth."""
    return (
        state.process_start is not None
        and _process_start_identity(state.pid) == state.process_start
    )


def _signal_gateway_process(state: GatewayRuntimeState, sig: int) -> bool:
    """Signal the original Gateway instance after rechecking its PID birth."""
    if not _gateway_process_matches(state):
        return False
    try:
        pgid = os.getpgid(state.pid)
    except ProcessLookupError:
        return False
    if not _gateway_process_matches(state):
        return False
    try:
        if pgid == state.pid:
            os.killpg(pgid, sig)
        else:
            # Foreground launches do not own their shell's process group.
            os.kill(state.pid, sig)
    except ProcessLookupError:
        return False
    return True


def _gateway_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / ".gateway-state.json"


def _write_gateway_state(config: LocalConfig, state: GatewayRuntimeState) -> None:
    """Atomically publish the single lifecycle state document."""
    path = _gateway_state_path(config)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path: Path | None = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(asdict(state), stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if fd >= 0:
            os.close(fd)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _read_gateway_state(state_path: Path) -> GatewayRuntimeState | None:
    if not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return GatewayRuntimeState(
        pid=int(payload["pid"]),
        config_path=str(payload["config_path"]),
        log_path=str(payload["log_path"]),
        process_start=(
            str(payload["process_start"]).strip()
            if payload.get("process_start") is not None
            else None
        ),
    )


def _remove_gateway_state(
    state_path: Path, *, expected: GatewayRuntimeState | None = None
) -> None:
    if expected is not None and _read_gateway_state(state_path) != expected:
        return
    with suppress(FileNotFoundError):
        state_path.unlink()


def _background_gateway_argv(
    config_path: Path, *, im_service_url_override: str | None = None
) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "personal_assistant.main",
        "--config",
        str(config_path),
    ]
    if isinstance(im_service_url_override, str) and im_service_url_override.strip():
        argv.extend(["--im-service-url", im_service_url_override.strip()])
    argv.append("--foreground")
    return argv


def _spawn_background_gateway_process(argv: list[str], log_path: Path) -> ProcessLike:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        return subprocess.Popen(
            argv,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )


def _wait_for_gateway_start(
    process: ProcessLike, config: LocalConfig, timeout_seconds: float
) -> None:
    """Wait for the background Gateway child to publish complete lifecycle state.

    This is a process-start confirmation, not a runtime/channel readiness signal.
    ``run_gateway`` writes one atomic state document before entering ``run_forever``.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"gateway exited before startup confirmation with return code {return_code}"
            )
        state = _read_gateway_state(_gateway_state_path(config))
        if state is not None and state.process_start is not None:
            _assert_gateway_state_static(config, state, expected_pid=process.pid)
            if not _gateway_process_matches(state):
                raise RuntimeError(
                    "gateway exited before process identity confirmation"
                )
            return
        time.sleep(config.gateway.poll_interval_seconds or 0.2)
    raise RuntimeError(
        "timed out waiting for gateway startup confirmation "
        "(lifecycle state never appeared)"
    )


def _stop_background_process(process: ProcessLike, *, timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    # Gateway owns the session created by start_new_session=True. Terminating the
    # process group also reaps channel/tool descendants owned by that Gateway.
    _kill_process_tree(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=timeout_seconds)
    except (TimeoutError, subprocess.TimeoutExpired):
        process.kill()
        _kill_process_tree(process.pid, signal.SIGKILL)
        with suppress(TimeoutError, subprocess.TimeoutExpired):
            process.wait(timeout=timeout_seconds)


def _kill_process_tree(pid: int, sig: int) -> None:
    """Send ``sig`` to the entire process group led by ``pid``; falls back to single pid.

    Gateway 后台启动时 ``start_new_session=True``，其 channel/tool 后代进程位于同一 pgid。
    killpg 一次性回收 Gateway 拥有的整棵进程树。
    pgid 拿不到(进程刚消失)时静默吞掉,让上层走 wait 路径决定下一步。
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return


def _install_default_signal_handlers(
    gateway_runtime: runtime.GatewayRuntimeLike,
) -> SignalHandlerInstaller:
    def _installer() -> Callable[[], None]:
        if not isinstance(gateway_runtime, runtime.GatewayRuntime):
            return lambda: None
        if threading.current_thread() is not threading.main_thread():
            return lambda: None

        previous: dict[signal.Signals, Any] = {}

        def _handler(_signum: int, _frame: Any) -> None:
            gateway_runtime.request_shutdown()

        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, _handler)

        def _restore() -> None:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

        return _restore

    return _installer


def _default_build_runtime(config: LocalConfig) -> runtime.GatewayRuntimeLike:
    """Defer composition import until lifecycle execution to avoid import cycles."""
    from personal_assistant.gateway.composition import compose_gateway

    return compose_gateway(config)
