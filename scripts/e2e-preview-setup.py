#!/usr/bin/env python3
"""Install the shared macOS test ingress and register its preview hostnames."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path.home() / ".local/share/nano-preview"
NAME = "nano-worktree-preview"
LISTEN = "127.0.0.1:18471"
METRICS = "127.0.0.1:18472"


def write(path: Path, data: bytes) -> None:
    """Publish one private configuration file atomically."""
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(data)
    os.replace(f.name, path)


def service(name: str, args: list[str]) -> None:
    """Start this user's preview LaunchAgent and retain existing connections on reruns."""
    label = f"io.github.mrchen116.nano-preview.{name}"
    domain = f"gui/{os.getuid()}"
    directory = Path.home() / "Library/LaunchAgents"
    directory.mkdir(exist_ok=True, parents=True)
    plist = directory / f"{label}.plist"
    config = plistlib.dumps(
        dict(
            Label=label,
            ProgramArguments=args,
            RunAtLoad=True,
            KeepAlive=True,
            StandardOutPath=str(ROOT / f"{name}.log"),
            StandardErrorPath=str(ROOT / f"{name}.log"),
        )
    )
    loaded = (
        subprocess.run(
            ["launchctl", "print", f"{domain}/{label}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    if loaded:
        if not plist.exists() or plist.read_bytes() != config:
            raise SystemExit(
                f"Preview agent {label} is already running with another configuration"
            )
        return
    write(plist, config)
    subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)


def setup(args: argparse.Namespace) -> None:
    """Prepare the dedicated tunnel, proxy, source store, and DNS pool on the IM host."""
    cf, proxy = shutil.which("cloudflared"), shutil.which("traefik")
    if not cf or not proxy:
        raise SystemExit(
            "cloudflared and traefik must be installed on the preview host"
        )
    for executable in ("node", "pnpm", "npm", "git", "python", "python3"):
        if not shutil.which(executable):
            raise SystemExit(f"missing {executable} in the preview build PATH")
    subprocess.run(["python", "-c", "import httpx, yaml"], check=True)
    subprocess.run(["python3", "-c", "import yaml"], check=True)
    subprocess.run(
        [
            "python3",
            str(args.repo / "scripts/dev_host.py"),
            "guard",
            "--repo",
            str(args.repo),
            "--runtime",
            str(ROOT),
        ],
        check=True,
    )

    routes = ROOT / "routes"
    routes.mkdir(exist_ok=True)
    source = ROOT / "source.git"
    if not source.exists():
        subprocess.run(
            ["git", "clone", "--bare", "--local", str(args.repo), str(source)],
            check=True,
        )
    write(
        ROOT / "env", ("export PATH=" + shlex.quote(os.environ["PATH"]) + "\n").encode()
    )

    cred = ROOT / "tunnel.json"
    if not cred.exists():
        subprocess.run(
            [cf, "tunnel", "create", "--credentials-file", str(cred), NAME], check=True
        )
    tunnel_id = json.loads(cred.read_text())["TunnelID"]
    conf = ROOT / "tunnel.yml"
    config = dict(
        tunnel=tunnel_id,
        protocol="http2",
        **{"credentials-file": str(cred)},
        metrics=METRICS,
        ingress=[{"service": "http://" + LISTEN}],
    )
    write(conf, json.dumps(config).encode())
    service(
        "router",
        [
            proxy,
            "--global.checknewversion=false",
            "--entrypoints.preview.address=" + LISTEN,
            "--providers.file.directory=" + str(routes),
            "--providers.file.watch=true",
            "--providers.providersThrottleDuration=100ms",
        ],
    )
    service(
        "tunnel",
        [cf, "tunnel", "--no-autoupdate", "--config", str(conf), "run", tunnel_id],
    )
    for _ in range(50):
        try:
            with urllib.request.urlopen(
                "http://" + METRICS + "/ready", timeout=2
            ) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        time.sleep(1)
    else:
        raise SystemExit(f"Preview tunnel is not ready; inspect {ROOT}/tunnel.log")
    pool = ROOT / "hosts"
    hosts = pool.read_text().splitlines() if pool.exists() else []
    for host in args.hostnames:
        if host not in hosts:
            subprocess.run([cf, "tunnel", "route", "dns", tunnel_id, host], check=True)
            hosts.append(host)
            write(pool, ("\n".join(hosts) + "\n").encode())
    print("Preview domain pool:", ", ".join(hosts))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="development checkout used to seed the Git object store",
    )
    parser.add_argument(
        "hostnames", nargs="+", help="dedicated test hosts covered by edge TLS"
    )
    args = parser.parse_args()
    args.repo = args.repo.resolve()
    if any(
        not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}", host)
        for host in args.hostnames
    ):
        parser.error("expected lowercase DNS hostnames")
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (ROOT / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        setup(args)


if __name__ == "__main__":
    main()
