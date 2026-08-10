from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from evals.spec_design_alignment.experiments.feat_532_spec_memory import runner


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def confined_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    boundary = tmp_path / "pilot-workspace"
    workspace = boundary / "roles/role-01"
    runtime = tmp_path / "runtime/role-01"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir(parents=True)
    runtime.mkdir(parents=True)
    artifacts.mkdir()
    (boundary / ".role-context-canary").write_text("parent-canary\n", encoding="utf-8")
    (runtime / "codex-home").mkdir()
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(runtime / "home"),
        "CODEX_HOME": str(runtime / "codex-home"),
        "TMPDIR": str(runtime / "tmp"),
    }
    return boundary, workspace, runtime, artifacts, environment


@pytest.mark.parametrize("workspace_write", [False, True])
def test_read_allowlist_blocks_unrelated_host_and_auth_canaries(
    tmp_path: Path, workspace_write: bool
) -> None:
    boundary, workspace, runtime, artifacts, environment = confined_fixture(tmp_path)
    private_canary = Path("/private/tmp") / f"feat-532-{tmp_path.name}.txt"
    volume_target = Path("/private/tmp") / f"feat-532-volume-{tmp_path.name}.txt"
    volume_style_canary = Path("/Volumes/Macintosh HD/private/tmp") / volume_target.name
    private_canary.write_text("PRIVATE-TMP-SENTINEL\n", encoding="utf-8")
    volume_target.write_text("VOLUME-STYLE-SENTINEL\n", encoding="utf-8")
    auth = runtime / "codex-home/auth.json"
    auth.write_text("AUTH-SENTINEL\n", encoding="utf-8")
    actual = artifacts / "actual.json"
    try:
        result = runner.run_confined_subprocess(
            manifest_id="role-01",
            command=[
                "/bin/sh",
                "-c",
                'for path do /bin/cat "$path"; done',
                "role-probe",
                str(private_canary),
                str(volume_style_canary),
                str(auth),
            ],
            workspace=workspace,
            workspace_boundary=boundary,
            artifacts=artifacts,
            runtime_root=runtime,
            host_home=Path.home(),
            environment=environment,
            envelope="",
            actual_path=actual,
            workspace_write=workspace_write,
        )
    finally:
        private_canary.unlink(missing_ok=True)
        volume_target.unlink(missing_ok=True)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "PRIVATE-TMP-SENTINEL" not in output
    assert "VOLUME-STYLE-SENTINEL" not in output
    assert "AUTH-SENTINEL" not in output
    attestation = load_json(actual)
    assert attestation["os_sandbox"]["unrelated_read_blocked"] is True
    assert attestation["os_sandbox"]["credential_read_blocked"] is True


@pytest.mark.parametrize("workspace_write", [False, True])
def test_nested_codex_is_denied_auth_and_execution(
    tmp_path: Path, workspace_write: bool
) -> None:
    boundary, workspace, runtime, artifacts, environment = confined_fixture(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    nested_codex = fake_bin / "codex"
    marker = tmp_path / "nested-codex-ran"
    nested_codex.write_text(
        f"#!/bin/sh\ntouch '{marker}'\ncat \"$CODEX_HOME/auth.json\"\n",
        encoding="utf-8",
    )
    nested_codex.chmod(0o755)
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    (runtime / "codex-home/auth.json").write_text(
        "NESTED-AUTH-SENTINEL\n", encoding="utf-8"
    )

    result = runner.run_confined_subprocess(
        manifest_id="role-01",
        command=[
            "/bin/sh",
            "-c",
            'codex; "$1"',
            "role-probe",
            str(nested_codex),
        ],
        workspace=workspace,
        workspace_boundary=boundary,
        artifacts=artifacts,
        runtime_root=runtime,
        host_home=Path.home(),
        environment=environment,
        envelope="",
        actual_path=artifacts / "actual.json",
        workspace_write=workspace_write,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "NESTED-AUTH-SENTINEL" not in output
    assert not marker.exists()


def test_runner_git_ignores_untrusted_execution_configuration(tmp_path: Path) -> None:
    repository = tmp_path / "candidate"
    repository.mkdir()
    (repository / "README.md").write_text("# Candidate\n", encoding="utf-8")
    runner.rewrite_as_parentless_repository(repository)
    runner.relocate_candidate_git_metadata(repository)
    marker = tmp_path / "git-control-plane-executed"
    executable = tmp_path / "malicious.sh"
    executable.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    executable.chmod(0o755)
    subprocess.run(
        ["git", "config", "core.fsmonitor", str(executable)],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "diff.evil.command", str(executable)],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "filter.evil.clean", str(executable)],
        cwd=repository,
        check=True,
    )
    (repository / ".gitattributes").write_text(
        "README.md diff=evil\n", encoding="utf-8"
    )
    (repository / "README.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(runner.PilotError, match="unsafe executable Git configuration"):
        runner.run_git(repository, "status", "--porcelain=v1", "--untracked-files=all")

    assert not marker.exists()


def test_runner_git_rejects_executable_hook_without_running(tmp_path: Path) -> None:
    repository = tmp_path / "candidate"
    repository.mkdir()
    (repository / "README.md").write_text("# Candidate\n", encoding="utf-8")
    runner.rewrite_as_parentless_repository(repository)
    runner.relocate_candidate_git_metadata(repository)
    marker = tmp_path / "hook-ran"
    hook = repository / runner.CANDIDATE_GIT_METADATA / "hooks/post-index-change"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)

    with pytest.raises(runner.PilotError, match="unsafe executable Git hook"):
        runner.run_git(repository, "status", "--porcelain")
    assert not marker.exists()
