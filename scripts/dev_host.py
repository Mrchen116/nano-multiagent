#!/usr/bin/env python3
"""Read local development capabilities and guard isolated E2E entrypoints."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"expected an absolute path: {value}")
    return path.resolve()


def _load() -> tuple[Path, dict]:
    default = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = _path(
        os.environ.get(
            "NANO_DEV_HOST_CONFIG", str(default / "nano-multiagent/dev-host.json")
        )
    )
    if not path.exists() and "NANO_DEV_HOST_CONFIG" not in os.environ:
        return path, {}
    config = json.loads(path.read_text())
    if not isinstance(config, dict):
        raise ValueError("dev-host config must be a JSON object")
    fields = {
        "host",
        "e2e_config",
        "protected_paths",
        "feishu_e2e",
        "llm_logs",
        "reference_root",
    }
    if unknown := config.keys() - fields:
        raise ValueError(f"unknown dev-host fields: {', '.join(sorted(unknown))}")
    for key in ("host", "e2e_config", "llm_logs", "reference_root"):
        if key in config and (not isinstance(config[key], str) or not config[key]):
            raise ValueError(f"{key} must be a nonempty string")
    if "feishu_e2e" in config and not isinstance(config["feishu_e2e"], bool):
        raise ValueError("feishu_e2e must be a boolean")
    paths = config.get("protected_paths", [])
    if not isinstance(paths, list) or any(
        not isinstance(p, str) or not p for p in paths
    ):
        raise ValueError("protected_paths must be an array of absolute paths")
    for value in paths + [
        config[k] for k in ("e2e_config", "llm_logs", "reference_root") if k in config
    ]:
        _path(value)
    return path, config


def _guard(config: dict, repo: Path, runtime: Path, profile: str) -> None:
    for candidate in (repo.resolve(), runtime.resolve()):
        for parent in (candidate, *candidate.parents):
            if (parent / ".nano-production").exists():
                raise ValueError(
                    f"refusing production path: {candidate} (marker in {parent})"
                )
        for value in config.get("protected_paths", []):
            protected = _path(value)
            if candidate.is_relative_to(protected) or protected.is_relative_to(
                candidate
            ):
                raise ValueError(
                    f"refusing production path: {candidate} overlaps {protected}"
                )
    if profile == "feishu" and config.get("feishu_e2e") is False:
        raise ValueError(
            "Feishu E2E is disabled on this host; hand off this commit to Air"
        )


def _e2e_config(config: dict, repo: Path) -> Path:
    path = (
        _path(config["e2e_config"])
        if "e2e_config" in config
        else repo.resolve() / "config/e2e/gateway.yaml"
    )
    if not path.is_file():
        raise ValueError(f"E2E config not found: {path}")
    return path


def _check(path: Path, config: dict, repo: Path) -> int:
    commands = {}
    for name in ("git", "node", "pnpm", "python3", "curl"):
        executable = shutil.which(name)
        version = None
        if executable:
            result = subprocess.run(
                [executable, "--version"], capture_output=True, text=True, timeout=10
            )
            version = result.stdout.splitlines()[0] if result.stdout else None
        commands[name] = {"path": executable, "version": version}
    resources = {
        key: {"path": str(_path(config[key])), "exists": _path(config[key]).is_dir()}
        for key in ("llm_logs", "reference_root")
        if key in config
    }
    protected = [
        {"path": str(_path(p)), "exists": _path(p).is_dir()}
        for p in config.get("protected_paths", [])
    ]
    print(
        json.dumps(
            {
                "config": str(path),
                "configured": path.exists(),
                "host": config.get("host"),
                "e2e_config": str(_e2e_config(config, repo)),
                "feishu_e2e": config.get("feishu_e2e"),
                "protected_paths": protected,
                "resources": resources,
                "commands": commands,
                "note": "Paths and command versions only; compare package.json engines. This does not verify a running stack or model response.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return int(
        any(not c["path"] for c in commands.values())
        or any(not p["exists"] for p in protected)
    )


def main() -> int:
    """Run read-only host checks, configuration selection or E2E protection.

    Returns:
        Zero on success; one for invalid configuration or a refused operation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "guard", "e2e-config"))
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--runtime", type=Path)
    parser.add_argument(
        "--profile", choices=("default", "daily", "feishu"), default="default"
    )
    args = parser.parse_args()
    try:
        path, config = _load()
        if args.command == "guard":
            if args.runtime is None:
                parser.error("guard requires --runtime")
            _guard(config, args.repo, args.runtime, args.profile)
        elif args.command == "e2e-config":
            print(_e2e_config(config, args.repo))
        else:
            return _check(path, config, args.repo)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"dev-host: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
