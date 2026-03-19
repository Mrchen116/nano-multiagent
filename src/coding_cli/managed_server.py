"""Managed-mode local API process lifecycle helpers for CLI."""

import errno
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


class ManagedServerError(RuntimeError):
    """Managed-mode startup/runtime error with optional user suggestion."""

    def __init__(self, message: str, *, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.suggestion = suggestion


@dataclass(frozen=True, slots=True)
class ManagedServerConfig:
    """Managed local API process settings derived from CLI options."""

    base_url: str
    token: str | None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float | None = None
    startup_timeout_seconds: float = 10.0
    poll_interval_seconds: float = 0.1


class ManagedServerProcess:
    """Start/stop local API process for CLI managed mode."""

    def __init__(
        self,
        *,
        config: ManagedServerConfig,
        popen_factory: Callable[..., subprocess.Popen[str]] | None = None,
        health_probe: Callable[[str], bool] | None = None,
        time_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._config = config
        self._popen_factory = popen_factory or _default_popen
        self._health_probe = health_probe or _default_health_probe
        self._time_fn = time_fn or time.monotonic
        self._sleep_fn = sleep_fn or time.sleep
        self._process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        """Start local API process and wait until health endpoint is reachable."""
        if self._process is not None and self._process.poll() is None:
            return

        host, port = _parse_local_host_port(self._config.base_url)
        if _is_port_in_use(host, port):
            raise ManagedServerError(
                f"managed mode cannot start local API: port {port} already in use on {host}.",
                suggestion="free the port, choose another local --base-url, or switch to --mode remote.",
            )

        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "coding_cli.kernel_app:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ]
        env = os.environ.copy()
        if self._config.token:
            env["NANO_MULTIAGENT_API_TOKEN"] = self._config.token
        if self._config.llm_provider:
            env["NANO_MULTIAGENT_LLM_PROVIDER"] = self._config.llm_provider
        if self._config.llm_model:
            env["NANO_MULTIAGENT_LLM_MODEL"] = self._config.llm_model
        if self._config.llm_base_url:
            env["NANO_MULTIAGENT_LLM_BASE_URL"] = self._config.llm_base_url
        if self._config.llm_api_key:
            env["NANO_MULTIAGENT_LLM_API_KEY"] = self._config.llm_api_key
        if self._config.llm_timeout_seconds is not None:
            env["NANO_MULTIAGENT_LLM_TIMEOUT_SECONDS"] = str(self._config.llm_timeout_seconds)

        try:
            self._process = self._popen_factory(command, env=env)
        except OSError as exc:
            raise ManagedServerError(
                f"failed to start managed API process: {exc}",
                suggestion="check local python/uvicorn installation, then retry or switch to --mode remote.",
            ) from exc

        try:
            self._wait_until_ready()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        """Stop managed API process with terminate-then-kill fallback."""
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def _wait_until_ready(self) -> None:
        deadline = self._time_fn() + self._config.startup_timeout_seconds
        while self._time_fn() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                details = _read_process_stderr(process)
                suffix = f" stderr={details}" if details else ""
                raise ManagedServerError(
                    f"managed API process exited before becoming healthy.{suffix}",
                    suggestion="check local API logs, token/env configuration, and retry.",
                )
            if self._health_probe(self._config.base_url):
                return
            self._sleep_fn(self._config.poll_interval_seconds)
        raise ManagedServerError(
            f"managed API startup timed out after {self._config.startup_timeout_seconds:.1f}s.",
            suggestion="check whether the selected local port is reachable, then retry or switch to --mode remote.",
        )


def _default_popen(command: list[str], *, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _default_health_probe(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/v1/health"
    try:
        response = httpx.get(url, timeout=0.25, trust_env=False)
    except Exception:
        return False
    return response.status_code == 200


def _parse_local_host_port(base_url: str) -> tuple[str, int]:
    """Validate managed-mode base URL and extract host/port."""
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise ManagedServerError(
            "managed mode requires an http:// local --base-url.",
            suggestion="use --base-url like http://127.0.0.1:8000, or switch to --mode remote.",
        )
    host = (parsed.hostname or "").strip().lower()
    if host not in _LOCAL_HOSTS:
        raise ManagedServerError(
            "managed mode requires a local --base-url host (127.0.0.1/localhost/::1/0.0.0.0).",
            suggestion="for non-local API endpoints use --mode remote --base-url <url>.",
        )
    if parsed.path not in ("", "/"):
        raise ManagedServerError(
            "managed mode requires a root --base-url without path segments.",
            suggestion="remove the path from --base-url (example: http://127.0.0.1:8000).",
        )
    port = parsed.port if parsed.port is not None else 8000
    return host, port


def _read_process_stderr(process: subprocess.Popen[str]) -> str:
    stream = process.stderr
    if stream is None:
        return ""
    try:
        value = stream.read()
    except Exception:
        return ""
    return value.strip()


def _is_port_in_use(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return False
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            return True
        raise ManagedServerError(
            f"managed mode failed to bind {host}:{port}: {exc}",
            suggestion="choose another local --base-url port or switch to --mode remote.",
        ) from exc
    finally:
        sock.close()
