"""R6 tests: ``python -m IM.cli init_admin`` seeds a first user reachable via /auth/login."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def test_init_admin_cli_creates_user_loginable_via_http(tmp_path: Path) -> None:
    """init_admin --username --password --display-name should produce a user that can log in."""
    db_path = tmp_path / "im.db"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "IM.cli",
            "init_admin",
            "--username",
            "root",
            "--password",
            "rootpassword",
            "--display-name",
            "Root",
            "--db-path",
            str(db_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"

    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        login = client.post(
            "/im/v1/auth/login",
            json={"username": "root", "password": "rootpassword"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["user"]["username"] == "root"


def test_init_admin_cli_rejects_duplicate(tmp_path: Path) -> None:
    """Running init_admin twice with the same username should error out with non-zero exit."""
    db_path = tmp_path / "im.db"
    cmd = [
        sys.executable,
        "-m",
        "IM.cli",
        "init_admin",
        "--username",
        "root",
        "--password",
        "rootpassword",
        "--display-name",
        "Root",
        "--db-path",
        str(db_path),
    ]
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src"), "PATH": "/usr/bin:/bin"}
    first = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    second = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    assert first.returncode == 0, first.stderr
    assert second.returncode != 0
    assert "already exists" in (second.stderr + second.stdout)
