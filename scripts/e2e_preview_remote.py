"""Mini-side worktree preview lifecycle. Invoked over SSH by e2e-preview.py."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import httpx


def _run(*args: str | Path, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, stdout=sys.stderr)


def _build(root: Path, instance: Path, commit: str) -> Path:
    source = Path(tempfile.mkdtemp(prefix="checkout-", dir=instance))
    try:
        _run("git", "init", "-q", cwd=source)
        _run(
            "git",
            "fetch",
            "-q",
            "--depth=1",
            "--no-tags",
            root / "source.git",
            commit,
            cwd=source,
        )
        _run("git", "checkout", "-q", "--detach", "FETCH_HEAD", cwd=source)
        _run("pnpm", "install", "--frozen-lockfile", cwd=source)
        _run("npm", "--prefix", "src/IM/frontend", "ci", cwd=source)
        _run("pnpm", "build", cwd=source)
        # Build both UIs before stopping the current stack. e2e-up checks these assets again.
        _run(sys.executable, "scripts/e2e_ui.py", cwd=source)
        return source
    except BaseException:
        shutil.rmtree(source)
        raise


def _claim_host(root: Path, instance: Path) -> str:
    hosts = (root / "hosts").read_text().splitlines()
    for host in hosts:
        if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}", host):
            raise ValueError(f"Invalid preview hostname in {root / 'hosts'}")
        try:
            (root / "leases" / host).symlink_to(instance)
        except FileExistsError:
            continue
        return host
    raise RuntimeError(
        "Preview host pool is full. Stop a preview or add a dedicated hostname."
    )


def _lease(root: Path, instance: Path) -> Path | None:
    for entry in (root / "leases").iterdir():
        try:
            if entry.readlink() == instance:
                return entry
        except FileNotFoundError:
            continue  # Another instance released its lease.
    return None


def _handoff(runtime: Path) -> tuple[int, str]:
    env = dict(
        line.removeprefix("export ").split("=", 1)
        for line in (runtime / ".e2e-ports.env").read_text().splitlines()
        if line.startswith("export ")
    )
    port = int(env["IM_PORT"])
    if not 0 < port <= 65535 or not env["NODE_ID"]:
        raise ValueError("Invalid E2E port or node identity")
    return port, env["NODE_ID"]


def _route(root: Path, name: str, host: str, port: int) -> None:
    routes = root / "routes"
    content = (
        f'[http.routers.{name}]\nrule = "Host(`{host}`)"\nservice = "{name}"\n'
        f'[[http.services.{name}.loadBalancer.servers]]\nurl = "http://127.0.0.1:{port}"\n'
    )
    with tempfile.NamedTemporaryFile(
        mode="w", dir=routes, suffix=".tmp", delete=False
    ) as pending:
        pending.write(content)
    os.replace(pending.name, routes / f"{name}.toml")


def _password(runtime: Path) -> str:
    path = runtime / ".e2e-preview-password"
    if path.stat().st_mode & 0o077:
        raise RuntimeError(
            f"Restrict {path} to its owner before accessing the password"
        )
    return path.read_text().strip()


def _verify(url: str, password: str, node_id: str, *, wait: int = 40) -> None:
    headers = {"Origin": url, "X-IM-Session": "browser"}
    deadline = time.monotonic() + wait
    with httpx.Client(base_url=url, headers=headers, timeout=5) as client:
        while True:
            try:
                response = client.post(
                    "/im/v1/auth/login", json={"username": "nano", "password": password}
                )
                response.raise_for_status()
                session = response.json()
                nodes = client.get(
                    "/im/v1/nodes",
                    headers={"Authorization": "Bearer " + session["access_token"]},
                )
                nodes.raise_for_status()
                client.post("/im/v1/auth/logout", json={}).raise_for_status()
                if not any(
                    node["node_id"] == node_id
                    and node["status"] == "online"
                    and node["owner_id"] == session["user"]["owner_id"]
                    for node in nodes.json()
                ):
                    raise RuntimeError(f"Expected online node {node_id} missing")
                return
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Public verification failed at {url}: {error}"
                    ) from error
                time.sleep(2)


def _active(instance: Path) -> Path | None:
    active = instance / "active"
    if not active.is_symlink():
        return None
    checkout = active.resolve(strict=True)
    if checkout.parent != instance or not checkout.name.startswith("checkout-"):
        raise RuntimeError(f"Refusing to manage a checkout outside {instance}")
    return checkout


def _stop(instance: Path, checkout: Path | None) -> None:
    if checkout:
        _run(
            checkout / "scripts/e2e-down.sh", "--wt", instance / "runtime", cwd=checkout
        )


def _remove(root: Path, instance: Path) -> None:
    (root / "routes" / f"{instance.name}.toml").unlink(missing_ok=True)
    _stop(instance, _active(instance))
    lease = _lease(root, instance)
    if lease:
        lease.unlink()
    shutil.rmtree(instance)


def _operate(root: Path, action: str, instance: Path, commit: str | None) -> None:
    route = root / "routes" / f"{instance.name}.toml"
    runtime = instance / "runtime"
    active = instance / "active"
    if instance.is_symlink() or runtime.is_symlink():
        raise RuntimeError("Refusing a symlinked instance or runtime directory")
    if action == "up":
        if instance.exists():
            raise RuntimeError("Preview already exists. Use status, update, or down.")
        instance.mkdir(mode=0o700)
    elif not instance.is_dir():
        if action in {"down", "status"}:
            print(json.dumps({"instance": instance.name, "status": "absent"}))
            return
        raise RuntimeError("Preview does not exist. Run up first.")

    if action == "down":
        _remove(root, instance)
        print(json.dumps({"instance": instance.name, "status": "removed"}))
        return
    if action == "password":
        print(_password(runtime))
        return
    try:
        if action == "up":
            host = _claim_host(root, instance)
            runtime.mkdir()
        else:
            lease = _lease(root, instance)
            if not lease:
                raise RuntimeError("Incomplete initialization. Run down and then up.")
            host = lease.name
        url = "https://" + host
        if action in {"up", "update"}:
            assert commit
            if action == "update" and not (runtime / ".e2e-ports.env").is_file():
                raise RuntimeError(
                    "Missing initial E2E handoff. Inspect the instance before recovery."
                )
            candidate = _build(root, instance, commit)
            try:
                route.unlink(missing_ok=True)
                previous = _active(instance)
                _stop(instance, previous)
                # Keep a pointer to the scripts owning any partially started processes.
                next_active = instance / "next-active"
                next_active.unlink(missing_ok=True)
                next_active.symlink_to(candidate.name)
                os.replace(next_active, active)
            except BaseException:
                shutil.rmtree(candidate)
                raise
            if previous:
                shutil.rmtree(previous)
            args = ["--wt", runtime, "--preview-url", url]
            if action == "update":
                args.append("--resume")
            _run(candidate / "scripts/e2e-up.sh", *args, cwd=candidate)
            port, node_id = _handoff(runtime)
            _route(root, instance.name, host, port)
            try:
                _verify(url, _password(runtime), node_id)
            except BaseException:
                route.unlink(missing_ok=True)
                raise
        else:
            if not route.exists():
                raise RuntimeError(
                    "Preview has no public route. Run update to recover or down to remove."
                )
            _, node_id = _handoff(runtime)
            _verify(url, _password(runtime), node_id, wait=4)
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=active, text=True
            ).strip()
        print(
            json.dumps(
                {
                    "instance": instance.name,
                    "status": "ready",
                    "commit": commit,
                    "url": url,
                    "node_id": node_id,
                }
            )
        )
    except BaseException:
        if action == "up":
            _remove(root, instance)
        raise


def main(args: list[str]) -> None:
    """Serialize one Air worktree's operation on the Mini.

    Args:
        args: Action, worktree identity, and commit for up or update.
    """
    action, name, *version = args
    if action not in {"up", "update", "down", "password", "status"} or not re.fullmatch(
        r"pv-[0-9a-f]{20}", name
    ):
        raise ValueError("Invalid action or instance")
    if action in {"up", "update"}:
        if len(version) != 1 or not re.fullmatch(r"[0-9a-f]{40}", version[0]):
            raise ValueError("Expected a full Git commit ID")
    elif version:
        raise ValueError("Unexpected revision")
    os.umask(0o077)
    root = Path.home() / ".local/share/nano-preview"
    for name_dir in ("locks", "leases", "instances"):
        (root / name_dir).mkdir(mode=0o700, exist_ok=True)
    with (root / "locks" / name).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _operate(root, action, root / "instances" / name, next(iter(version), None))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        sys.exit(f"preview: {error}")
