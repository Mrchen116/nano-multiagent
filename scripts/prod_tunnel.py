#!/usr/bin/env python3
"""Supervise and verify the Mini's configured Cloudflare IPv6 transport."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import httpx
import yaml

HOME_DIR = Path.home()
TUNNEL_CONFIG = HOME_DIR / ".cloudflared/nano-im-public.yml"
CHILD_PID = HOME_DIR / ".nanoassistant/public-tunnel-child.pid"
EDGE_ADDRESSES = ["2606:4700:a0::1", "2606:4700:a8::1"]
INTERFACE = "en0"
METRICS = "http://127.0.0.1:20241"
PUBLIC_URL = "https://im.nanoim.win/"
RECOVERY_SECONDS = 30
POLL_SECONDS = 5
PROXY_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


def configure_business_proxy(config_path: Path) -> None:
    """Use the service's persisted proxy policy instead of the caller's shell."""
    config = yaml.safe_load(config_path.read_text())
    environment = config.get("gateway", {}).get("environment", {})
    if not (environment.get("https_proxy") or environment.get("HTTPS_PROXY")):
        raise RuntimeError("Public business probe requires a configured HTTPS proxy")
    for name in PROXY_VARIABLES:
        os.environ.pop(name, None)
        if name in environment:
            os.environ[name] = environment[name]


def public_probe(*, direct_diagnostic: bool = False) -> dict:
    """Read the complete HTTPS response without confusing egress with Tunnel health."""
    route = "direct_diagnostic" if direct_diagnostic else "configured_proxy"
    try:
        public = httpx.get(PUBLIC_URL, trust_env=not direct_diagnostic, timeout=10)
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Public HTTPS via {route} failed: {type(exc).__name__}"
        ) from exc
    if public.status_code != 200 or not public.content:
        raise RuntimeError(
            f"Public HTTPS via {route} returned {public.status_code}, "
            f"{len(public.content)} bytes"
        )
    return {"https": 200, "bytes": len(public.content), "public_egress": route}


def _check_path() -> str:
    config = yaml.safe_load(TUNNEL_CONFIG.read_text())
    protocol = config.get("protocol")
    if (
        protocol not in {"quic", "http2"}
        or str(config.get("edge-ip-version")) != "6"
        or config.get("metrics") != "127.0.0.1:20241"
    ):
        raise RuntimeError(
            "Tunnel must use explicit QUIC or HTTP2 over IPv6 and managed metrics"
        )
    for address in EDGE_ADDRESSES:
        route = subprocess.check_output(
            ["/sbin/route", "-n", "get", "-inet6", address], text=True
        )
        interface = re.search(r"interface:\s*(\S+)", route)
        if interface is None or interface[1] != INTERFACE:
            raise RuntimeError("Tunnel IPv6 destination must use Mini's en0 route")
    return protocol


def _ready() -> bool:
    try:
        return (
            httpx.get(METRICS + "/ready", trust_env=False, timeout=3).status_code == 200
        )
    except httpx.HTTPError:
        return False


def _snapshot() -> dict:
    protocol = _check_path()
    pid = int(CHILD_PID.read_text())
    command = subprocess.check_output(
        ["ps", "-p", str(pid), "-o", "comm="], text=True
    ).strip()
    if Path(command).name != "cloudflared":
        raise RuntimeError("Recorded child PID is not cloudflared")
    listeners = subprocess.check_output(
        ["lsof", "-nP", "-a", "-p", str(pid), "-iTCP:20241", "-sTCP:LISTEN", "-Fn"],
        text=True,
    )
    if "n127.0.0.1:20241\n" not in listeners:
        raise RuntimeError("Production child does not own the metrics listener")
    socket_args = ["-i6UDP"] if protocol == "quic" else ["-i6TCP", "-sTCP:ESTABLISHED"]
    sockets = subprocess.check_output(
        ["lsof", "-nP", "-a", "-p", str(pid), *socket_args, "-Fn"], text=True
    )
    endpoints = re.findall(r"^n.*$", sockets, re.MULTILINE)
    if protocol == "http2":
        endpoints = [
            endpoint for endpoint in endpoints if re.search(r"->.*:7844$", endpoint)
        ]
    if len(endpoints) != 4:
        raise RuntimeError(
            f"Production child must have four IPv6 {protocol.upper()} edge sockets"
        )
    if not _ready():
        raise RuntimeError("Tunnel /ready is not 200")
    metrics = (
        httpx.get(METRICS + "/metrics", trust_env=False, timeout=3)
        .raise_for_status()
        .text
    )
    if "cloudflared_tunnel_ha_connections 4\n" not in metrics:
        raise RuntimeError("Tunnel does not have four HA connections")
    closed_count = None
    if protocol == "quic":
        for direction in ["sent", "receive"]:
            values = re.findall(
                rf"^quic_client_{direction}_bytes\{{[^\n]+\}} (\S+)$",
                metrics,
                re.MULTILINE,
            )
            if len(values) != 4 or any(float(value) <= 0 for value in values):
                raise RuntimeError(
                    "Four production QUIC connections must have bidirectional traffic"
                )
        closed = re.search(
            r"^quic_client_closed_connections (\S+)$", metrics, re.MULTILINE
        )
        if closed is None:
            raise RuntimeError("Tunnel QUIC connection counter is missing")
        closed_count = int(float(closed[1]))
    # TCP endpoints detect HTTP2 reconnections even if all four are healthy again
    # between samples. QUIC additionally retains its transport close counter.
    signature = hashlib.sha256("\n".join(sorted(endpoints)).encode()).hexdigest()
    public = public_probe()
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": pid,
        "protocol": protocol,
        "ha_connections": 4,
        "edge_ip_version": "6",
        "interface": INTERFACE,
        "closed_connections": closed_count,
        "connection_signature": signature,
        **public,
    }


def _stop(child: subprocess.Popen) -> None:
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def _supervise() -> None:
    stopping = False

    def stop_requested(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_requested)
    signal.signal(signal.SIGINT, stop_requested)
    child = None
    unhealthy_since = None
    waiting = False
    try:
        while not stopping:
            try:
                _check_path()
                path_ok = True
            except (
                OSError,
                ValueError,
                KeyError,
                RuntimeError,
                httpx.HTTPError,
                subprocess.SubprocessError,
            ):
                path_ok = False
            if child is not None and child.poll() is not None:
                print("Tunnel child exited; restarting after path check", flush=True)
                child = None
                unhealthy_since = None
            if not path_ok:
                if not waiting:
                    print("Waiting for verified QUIC/IPv6 path", flush=True)
                waiting = True
                if child is not None:
                    print(
                        "IPv6 path unavailable; stopping Tunnel until the route recovers",
                        flush=True,
                    )
                    _stop(child)
                    child = None
                unhealthy_since = None
            elif child is None:
                waiting = False
                child = subprocess.Popen(
                    [
                        "/opt/homebrew/bin/cloudflared",
                        "tunnel",
                        "--config",
                        str(TUNNEL_CONFIG),
                        "--no-autoupdate",
                        "run",
                        "nano-im-public",
                    ]
                )
                CHILD_PID.write_text(str(child.pid))
                CHILD_PID.chmod(0o600)
                unhealthy_since = time.monotonic()
                print(f"Tunnel child started pid={child.pid}", flush=True)
            elif _ready():
                unhealthy_since = None
            else:
                now = time.monotonic()
                if unhealthy_since is None:
                    unhealthy_since = now
                if now - unhealthy_since >= RECOVERY_SECONDS:
                    print(
                        "Tunnel /ready failed for 30s; restarting unhealthy child",
                        flush=True,
                    )
                    _stop(child)
                    child = None
                    unhealthy_since = None
            time.sleep(POLL_SECONDS)
    finally:
        if child is not None:
            _stop(child)
        CHILD_PID.unlink(missing_ok=True)


def main() -> int:
    """Run the production path check or managed Tunnel supervisor."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument(
        "--ready",
        action="store_true",
        help="Check configured transport and IPv6 path before starting Tunnel",
    )
    parser.add_argument(
        "--seconds", type=int, default=0, help="Require continuous healthy samples"
    )
    parser.add_argument(
        "--gateway-config",
        type=Path,
        default=HOME_DIR / ".nanoassistant/config.yaml",
        help="Read the persisted business proxy policy from this Gateway config",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Check only public HTTPS through the business egress (also on Air)",
    )
    parser.add_argument(
        "--direct-diagnostic",
        action="store_true",
        help="With --public-only, diagnose direct HTTPS separately from acceptance",
    )
    args = parser.parse_args()
    if args.direct_diagnostic and not args.public_only:
        parser.error("--direct-diagnostic requires --public-only")
    if args.supervise:
        _supervise()
        return 0
    deadline = time.monotonic() + args.seconds
    baseline = None
    try:
        if not args.ready and not args.direct_diagnostic:
            configure_business_proxy(args.gateway_config)
        while True:
            if args.ready:
                protocol = _check_path()
                print(f"Verified {protocol.upper()}/IPv6 en0 path")
            elif args.public_only:
                print(
                    json.dumps(
                        {
                            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            **public_probe(direct_diagnostic=args.direct_diagnostic),
                        }
                    ),
                    flush=True,
                )
            else:
                snapshot = _snapshot()
                identity = (
                    snapshot["pid"],
                    snapshot["connection_signature"],
                    snapshot["closed_connections"],
                )
                if baseline is None:
                    baseline = identity
                elif identity != baseline:
                    raise RuntimeError(
                        "Tunnel restarted or changed an edge connection during sampling"
                    )
                print(json.dumps(snapshot, ensure_ascii=False), flush=True)
            if time.monotonic() >= deadline:
                return 0
            time.sleep(min(10, max(0, deadline - time.monotonic())))
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        httpx.HTTPError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
