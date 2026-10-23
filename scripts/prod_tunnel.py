#!/usr/bin/env python3
"""Supervise and verify the Mini's Cloudflare QUIC path through its local TUN."""

from __future__ import annotations

import argparse
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
CLASH_CONFIG = (
    HOME_DIR
    / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
    / "clash-verge.yaml"
)
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


def _clash_get(path: str) -> dict:
    """Read local routing metadata without exposing controller credentials."""
    config = yaml.safe_load(CLASH_CONFIG.read_text())
    # Both production versions expose a local Unix socket; no public controller.
    transport = httpx.HTTPTransport(uds=config["external-controller-unix"])
    with httpx.Client(transport=transport, trust_env=False, timeout=3) as client:
        return client.get("http://localhost" + path).raise_for_status().json()


def _check_path() -> str:
    config = yaml.safe_load(TUNNEL_CONFIG.read_text())
    if (
        config.get("protocol") != "quic"
        or str(config.get("edge-ip-version")) != "6"
        or config.get("metrics") != "127.0.0.1:20241"
    ):
        raise RuntimeError("Tunnel must use QUIC/IPv6 and the managed metrics endpoint")
    tun = _clash_get("/configs")["tun"]
    interface = tun.get("device", "")
    if not tun.get("enable") or not interface.startswith("utun"):
        raise RuntimeError("Production proxy TUN is unavailable")
    for address in EDGE_ADDRESSES:
        route = subprocess.check_output(
            ["/sbin/route", "-n", "get", "-inet6", address], text=True
        )
        routed = re.search(r"interface:\s*(\S+)", route)
        if routed is None or routed[1] != interface:
            raise RuntimeError("Tunnel IPv6 destination must use the proxy TUN")
    return interface


def _ready() -> bool:
    try:
        return (
            httpx.get(METRICS + "/ready", trust_env=False, timeout=3).status_code == 200
        )
    except httpx.HTTPError:
        return False


def _snapshot() -> dict:
    interface = _check_path()
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
    sockets = subprocess.check_output(
        ["lsof", "-nP", "-a", "-p", str(pid), "-i6UDP", "-Fn"], text=True
    )
    if len(re.findall(r"^n.*$", sockets, re.MULTILINE)) != 4:
        raise RuntimeError("Production child must have four IPv6 QUIC sockets")
    if not _ready():
        raise RuntimeError("Tunnel /ready is not 200")
    metrics = (
        httpx.get(METRICS + "/metrics", trust_env=False, timeout=3)
        .raise_for_status()
        .text
    )
    if "cloudflared_tunnel_ha_connections 4\n" not in metrics:
        raise RuntimeError("Tunnel does not have four HA connections")
    for direction in ["sent", "receive"]:
        values = re.findall(
            rf"^quic_client_{direction}_bytes\{{[^\n]+\}} (\S+)$", metrics, re.MULTILINE
        )
        if len(values) != 4 or any(float(value) <= 0 for value in values):
            raise RuntimeError(
                "Four production QUIC connections must have bidirectional traffic"
            )
    closed = re.search(r"^quic_client_closed_connections (\S+)$", metrics, re.MULTILINE)
    if closed is None:
        raise RuntimeError("Tunnel QUIC connection counter is missing")
    connections = _clash_get("/connections")["connections"]
    proxied = [
        connection
        for connection in connections
        if connection["metadata"].get("network") == "udp"
        and str(connection["metadata"].get("destinationPort")) == "7844"
        and connection["metadata"].get("process") == "cloudflared"
    ]
    if len(proxied) != 4 or any(
        not connection.get("chains")
        or "DIRECT" in connection["chains"]
        or connection.get("upload", 0) <= 0
        or connection.get("download", 0) <= 0
        for connection in proxied
    ):
        raise RuntimeError("Four Tunnel QUIC connections must carry traffic via proxy")
    # The actual proxy chains prove QUIC's egress. The independent HTTPS request
    # proves the business path using the Gateway's persisted configuration.
    public = public_probe()
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": pid,
        "ipv6_quic_ha": 4,
        "interface": interface,
        "quic_egress": "configured_proxy",
        "proxy_chains": [connection["chains"] for connection in proxied],
        "closed_connections": int(float(closed[1])),
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
                    print("Waiting for verified proxy TUN/IPv6 path", flush=True)
                waiting = True
                if child is not None:
                    print(
                        "Proxy TUN unavailable; stopping Tunnel until it recovers",
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
        help="Check proxy TUN path before starting Tunnel",
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
                _check_path()
                print("Verified QUIC/IPv6 proxy TUN path")
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
                identity = (snapshot["pid"], snapshot["closed_connections"])
                if baseline is None:
                    baseline = identity
                elif identity != baseline:
                    raise RuntimeError(
                        "Tunnel restarted or lost a QUIC connection during sampling"
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
