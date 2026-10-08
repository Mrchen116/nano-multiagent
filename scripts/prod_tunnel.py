#!/usr/bin/env python3
"""Supervise and verify the Mini's production Cloudflare proxy path."""

from __future__ import annotations

import argparse
import json
import re
import signal
import subprocess
import time
from pathlib import Path

import httpx
import yaml

HOME_DIR = Path.home()
CLASH_DIR = (
    HOME_DIR / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
)
TUNNEL_CONFIG = HOME_DIR / ".cloudflared/nano-im-public.yml"
CHILD_PID = HOME_DIR / ".nanoassistant/public-tunnel-child.pid"
NODE = "🇯🇵 日本Z03 | IEPL"
NETWORKS = ["198.41.192.0/24", "198.41.200.0/24"]
METRICS = "http://127.0.0.1:20241"
PUBLIC_URL = "https://im.nanoim.win/"
RECOVERY_SECONDS = 30
POLL_SECONDS = 5


def _proxy_client() -> httpx.Client:
    config = yaml.safe_load((CLASH_DIR / "clash-verge.yaml").read_text())
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=config["external-controller-unix"]),
        base_url="http://localhost",
        headers={"Authorization": "Bearer " + config["secret"]},
        timeout=3,
    )


def _check_path(client: httpx.Client) -> None:
    config = yaml.safe_load(TUNNEL_CONFIG.read_text())
    if config.get("protocol") != "quic" or str(config.get("edge-ip-version")) != "4":
        raise RuntimeError(
            "Tunnel must use QUIC and IPv4 through the verified proxy path"
        )
    runtime = client.get("/configs").raise_for_status().json()
    if runtime["mode"] != "rule":
        raise RuntimeError(
            "Clash must use rule mode; Direct/Global bypass the fixed path"
        )
    tun = runtime["tun"]
    if (
        not tun["enable"]
        or not tun["auto-route"]
        or sorted(tun.get("route-address", [])) != sorted(NETWORKS)
    ):
        raise RuntimeError(
            "Clash must route only the two Tunnel IPv4 networks through TUN"
        )
    rules = client.get("/rules").raise_for_status().json()["rules"]
    if len(rules) < len(NETWORKS):
        raise RuntimeError("Fixed Tunnel rules are missing")
    for index, network in enumerate(NETWORKS):
        rule = rules[index]
        if (
            rule["type"] != "IPCIDR"
            or rule["payload"] != network
            or rule["proxy"] != NODE
        ):
            raise RuntimeError("Tunnel network must use the fixed Z03 proxy")
        route = subprocess.check_output(
            ["/sbin/route", "-n", "get", network.split("/")[0]], text=True
        )
        interface = re.search(r"interface:\s*(\S+)", route)
        if interface is None or interface[1] != tun["device"]:
            raise RuntimeError("Tunnel destination bypasses the expected TUN interface")


def _ready() -> bool:
    try:
        return (
            httpx.get(METRICS + "/ready", trust_env=False, timeout=3).status_code == 200
        )
    except httpx.HTTPError:
        return False


def _snapshot(client: httpx.Client) -> dict:
    _check_path(client)
    if not _ready():
        raise RuntimeError("Tunnel /ready is not 200")
    pid = int(CHILD_PID.read_text())
    command = subprocess.check_output(
        ["ps", "-p", str(pid), "-o", "comm="], text=True
    ).strip()
    if Path(command).name != "cloudflared":
        raise RuntimeError("Recorded child PID is not cloudflared")
    sockets = subprocess.check_output(
        ["lsof", "-nP", "-a", "-p", str(pid), "-iUDP", "-Fn"], text=True
    )
    ports = set(re.findall(r"^n[^\n]*?:(\d+)(?:->|$)", sockets, re.MULTILINE))
    connections = client.get("/connections").raise_for_status().json()["connections"]
    flows = [
        c
        for c in connections
        if c["metadata"].get("network") == "udp"
        and str(c["metadata"].get("destinationPort")) == "7844"
        and str(c["metadata"].get("sourcePort")) in ports
    ]
    if len(flows) != 4 or any(
        c["chains"] != [NODE] or not c["download"] for c in flows
    ):
        raise RuntimeError(
            "Production PID must have four bidirectional QUIC flows through fixed Z03"
        )
    metrics = (
        httpx.get(METRICS + "/metrics", trust_env=False, timeout=3)
        .raise_for_status()
        .text
    )
    if "cloudflared_tunnel_ha_connections 4\n" not in metrics:
        raise RuntimeError("Tunnel does not have four HA connections")
    public = httpx.get(PUBLIC_URL, trust_env=False, timeout=10)
    if public.status_code != 200:
        raise RuntimeError(f"Public HTTPS returned {public.status_code}")
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": pid,
        "flows": 4,
        "proxy": NODE,
        "https": 200,
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
                with _proxy_client() as client:
                    _check_path(client)
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
                    print("Waiting for verified fixed proxy path", flush=True)
                waiting = True
                if child is not None:
                    print(
                        "Proxy path unavailable; stopping Tunnel to prevent direct fallback",
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
        "--ready", action="store_true", help="Check proxy path before starting Tunnel"
    )
    parser.add_argument(
        "--seconds", type=int, default=0, help="Require continuous healthy samples"
    )
    args = parser.parse_args()
    if args.supervise:
        _supervise()
        return 0
    deadline = time.monotonic() + args.seconds
    try:
        with _proxy_client() as client:
            while True:
                if args.ready:
                    _check_path(client)
                    print("Verified fixed Z03 TUN path")
                else:
                    print(json.dumps(_snapshot(client), ensure_ascii=False), flush=True)
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
