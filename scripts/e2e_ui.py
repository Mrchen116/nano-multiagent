"""Build only stale E2E browser assets, keeping successful build provenance local."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess


FRONTEND = "src/IM/frontend"
VIEWER = "packages/dsh-trajectory-viewer"
CONTRACTS = "packages/product-contracts"
TRAJECTORY = "packages/trajectory-ui"


def _inputs(repo: Path, packages: list[str], *, libraries: bool = True) -> list[Path]:
    paths = [
        repo / name
        for name in (
            "scripts/e2e_ui.py",
            "package.json",
            "pnpm-lock.yaml",
            "pnpm-workspace.yaml",
            "tsconfig.base.json",
            ".npmrc",
            "node_modules/.modules.yaml",
            "node_modules/.pnpm/lock.yaml",
        )
    ]
    for package in packages:
        directory = repo / package
        paths.extend(directory / name for name in ("src", "public"))
        if libraries and package in (CONTRACTS, TRAJECTORY):
            # These are the actual package exports consumed by the UI builds.
            paths.append(directory / "lib")
        paths.extend(
            path
            for path in directory.iterdir()
            if path.is_file()
            and (
                path.suffix
                in (".json", ".js", ".mjs", ".ts", ".css", ".html", ".yaml", ".yml")
                or path.name.startswith(".env")
                or path.name in ("LICENSE", ".npmrc")
            )
        )
        if package == FRONTEND:
            paths.append(directory / "node_modules/.package-lock.json")
    return paths


def _digest(repo: Path, paths: list[Path], context: dict) -> str:
    digest = hashlib.sha256(json.dumps(context, sort_keys=True).encode())
    for path in sorted(set(paths)):
        files = (
            sorted(item for item in path.rglob("*") if item.is_file())
            if path.is_dir()
            else [path]
        )
        for file in files:
            digest.update(file.relative_to(repo).as_posix().encode() + b"\0")
            digest.update(
                hashlib.sha256(file.read_bytes()).digest()
                if file.is_file()
                else b"missing"
            )
    return digest.hexdigest()


def _build(repo: Path, package: str, env: dict[str, str]) -> None:
    command = ["npm", "--prefix"] if package == FRONTEND else ["pnpm", "--dir"]
    subprocess.run(
        [*command, str(repo / package), "run", "build"], cwd=repo, env=env, check=True
    )


def prepare_ui(repo: Path) -> None:
    """Prepare the same-origin frontend and trajectory viewer for E2E startup.

    Args:
        repo: Checkout containing the build scripts, installed dependencies and UI sources.

    Raises:
        subprocess.CalledProcessError: A required build fails; startup must stop.
        RuntimeError: A build lacks its entrypoint or its inputs changed during the build.
    """
    env = {**os.environ, "VITE_IM_API_BASE_URL": ""}
    context = {
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "env": {
            key: value
            for key, value in env.items()
            if (key.startswith("VITE_") and key != "VITE_IM_PROXY_TARGET")
            or key in ("NODE_ENV", "NODE_OPTIONS", "BROWSERSLIST", "BROWSERSLIST_ENV")
        },
    }
    cache = repo / ".cache/e2e-ui"
    cache.mkdir(parents=True, exist_ok=True)
    # Different runtime roots can share a checkout; never publish overlapping builds.
    with (cache / "build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        contracts_built = False
        for name, package, dependencies in (
            ("frontend", FRONTEND, [CONTRACTS]),
            ("trajectory", VIEWER, [CONTRACTS, TRAJECTORY]),
        ):
            packages = [package, *dependencies]
            stamp = cache / f"{name}.json"
            dist = repo / package / "dist"
            current = {
                "inputs": _digest(repo, _inputs(repo, packages), context),
                "outputs": _digest(repo, [dist], {}),
            }
            try:
                previous = json.loads(stamp.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                previous = None
            if previous == current and (dist / "index.html").is_file():
                print(f"E2E UI: reuse {name}", flush=True)
                continue
            print(
                f"E2E UI: build {name} (inputs or assets changed; or no verified build)",
                flush=True,
            )
            # A failed/partial rebuild must never keep a previous success marker.
            stamp.unlink(missing_ok=True)
            sources = _digest(repo, _inputs(repo, packages, libraries=False), context)
            if not contracts_built:
                _build(repo, CONTRACTS, env)
                contracts_built = True
            if package == VIEWER:
                _build(repo, TRAJECTORY, env)
            _build(repo, package, env)
            if not (dist / "index.html").is_file():
                raise RuntimeError(f"{name} build did not produce dist/index.html")
            if sources != _digest(
                repo, _inputs(repo, packages, libraries=False), context
            ):
                raise RuntimeError(
                    f"{name} inputs changed during build; run startup again"
                )
            stamp.write_text(
                json.dumps(
                    {
                        "inputs": _digest(repo, _inputs(repo, packages), context),
                        "outputs": _digest(repo, [dist], {}),
                    }
                )
            )


if __name__ == "__main__":
    prepare_ui(Path(__file__).resolve().parents[1])
