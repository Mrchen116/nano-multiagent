"""Protect production paths before E2E entrypoints can mutate local state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("entrypoint", ["e2e-up.sh", "e2e-down.sh"])
@pytest.mark.parametrize("protection", ["configured", "symlink", "marker", "ancestor"])
def test_e2e_refuses_production_before_touching_state(
    tmp_path: Path, entrypoint: str, protection: str
) -> None:
    """Both lifecycle commands must leave protected runtime files intact."""
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    protected = runtime / "production" if protection == "ancestor" else runtime
    protected.mkdir(exist_ok=True)
    host = tmp_path / "host.json"
    host.write_text(json.dumps({"protected_paths": [str(protected)]}))
    if protection == "marker":
        host.write_text("{}")
        (runtime / ".nano-production").touch()
    target = runtime
    if protection == "symlink":
        target = tmp_path / "alias"
        target.symlink_to(runtime, target_is_directory=True)
    sentinel = runtime / (
        ".e2e-ports.env" if entrypoint == "e2e-up.sh" else ".gateway.pid"
    )
    sentinel.write_text("keep this production state")
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("[")
    args = [str(ROOT / "scripts" / entrypoint), "--wt", str(target)]
    if entrypoint == "e2e-up.sh":
        args += ["--main-config", str(invalid_yaml)]
    result = subprocess.run(
        args,
        env={**os.environ, "NANO_DEV_HOST_CONFIG": str(host)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "production" in result.stderr.lower()
    assert sentinel.read_text() == "keep this production state"
    assert not (runtime / ".gateway-config.yaml").exists()


def test_disabled_feishu_refuses_before_reading_credentials(tmp_path: Path) -> None:
    """A Mini profile cannot acquire the Air Bot or remove previous state."""
    host = tmp_path / "host.json"
    host.write_text(json.dumps({"feishu_e2e": False}))
    sentinel = tmp_path / ".e2e-ports.env"
    sentinel.write_text("keep")
    result = subprocess.run(
        [str(ROOT / "scripts/e2e-up.sh"), "--wt", str(tmp_path), "--feishu"],
        env={**os.environ, "NANO_DEV_HOST_CONFIG": str(host)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "disabled" in result.stderr.lower()
    assert sentinel.read_text() == "keep"


def test_host_config_selects_local_source_and_rejects_missing_explicit_config(
    tmp_path: Path,
) -> None:
    """Local paths override the default without silently ignoring config mistakes."""
    source = tmp_path / "gateway.yaml"
    source.write_text("llm: {}")
    host = tmp_path / "host.json"
    host.write_text(json.dumps({"e2e_config": str(source)}))
    command = [
        sys.executable,
        str(ROOT / "scripts/dev_host.py"),
        "e2e-config",
        "--repo",
        str(ROOT),
    ]
    env = {**os.environ, "NANO_DEV_HOST_CONFIG": str(host)}
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(source)
    host.unlink()
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert str(host) in result.stderr


@pytest.mark.parametrize("content", ['{"feishu_e2e": "false"}', "[]", "{"])
def test_invalid_host_config_cannot_silently_enable_e2e(
    tmp_path: Path, content: str
) -> None:
    """Malformed policy must fail closed before a lifecycle command writes files."""
    host = tmp_path / "host.json"
    host.write_text(content)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/dev_host.py"),
            "guard",
            "--repo",
            str(ROOT),
            "--runtime",
            str(tmp_path),
        ],
        env={**os.environ, "NANO_DEV_HOST_CONFIG": str(host)},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "dev-host" in result.stderr
