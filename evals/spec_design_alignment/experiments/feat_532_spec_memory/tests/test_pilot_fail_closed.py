from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest

from evals.spec_design_alignment.experiments.feat_532_spec_memory import runner


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def initialize_repository(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    runner.rewrite_as_parentless_repository(root)


@pytest.mark.parametrize("workspace_write", [False, True])
def test_role_filesystem_confinement_blocks_parent_canary(
    tmp_path: Path, workspace_write: bool
) -> None:
    boundary = tmp_path / "pilot-workspace"
    workspace = boundary / "roles/role-01"
    runtime = tmp_path / "runtime/role-01"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir(parents=True)
    runtime.mkdir(parents=True)
    artifacts.mkdir()
    canary = boundary / ".role-context-canary"
    canary.write_text("must-not-be-readable\n", encoding="utf-8")
    visible = workspace / "visible.txt"
    visible.write_text("allowed\n", encoding="utf-8")
    actual = artifacts / "actual.json"

    result = runner.run_confined_subprocess(
        manifest_id="role-01",
        command=["/bin/sh", "-c", 'cat "$1"', "role-probe", str(canary)],
        workspace=workspace,
        workspace_boundary=boundary,
        artifacts=artifacts,
        runtime_root=runtime,
        host_home=Path.home(),
        environment={
            "PATH": os.environ["PATH"],
            "HOME": str(runtime / "home"),
            "CODEX_HOME": str(runtime / "codex-home"),
            "TMPDIR": str(runtime / "tmp"),
        },
        envelope="",
        actual_path=actual,
        workspace_write=workspace_write,
    )

    assert result.returncode != 0
    attestation = load_json(actual)
    runner.validate_schema(
        actual,
        runner.EXPERIMENT_ROOT / "schemas/role-context-attestation.schema.json",
    )
    assert attestation["os_sandbox"]["mechanism"] == "macos_sandbox_exec_seatbelt"
    assert attestation["os_sandbox"]["canary_read_blocked"] is True
    assert attestation["tools"]["shell"] is True
    assert attestation["tools"]["workspace_write"] is workspace_write
    assert attestation["readable_roots"] == [
        "role_runtime",
        "system_runtime",
        "workspace",
    ]


def test_gate1_rejects_ignored_scratch_and_symlinks(tmp_path: Path) -> None:
    repository = tmp_path / "candidate"
    initialize_repository(repository, {"README.md": "# Base\n"})
    runner.relocate_candidate_git_metadata(repository)
    initial_files = runner.visible_file_manifest(repository)
    first_doc = repository / "docs/changes/feat-001-demo/spec.md"
    first_doc.parent.mkdir(parents=True)
    first_doc.write_text(
        "# Demo\n\n## 原始需求\n\nx\n\n## 用户场景\n\ny\n\n"
        "## 验收标准\n\nz\n\n## 范围\n\nw\n",
        encoding="utf-8",
    )
    runner.run_git(repository, "add", "docs/changes/feat-001-demo/spec.md")
    runner.run_git(
        repository,
        "-c",
        "user.name=Candidate",
        "-c",
        "user.email=candidate@invalid",
        "commit",
        "-m",
        "spec",
    )
    scratch = repository / ".experiment/scratch.txt"
    scratch.parent.mkdir(exist_ok=True)
    scratch.write_text("ignored scratch\n", encoding="utf-8")

    with pytest.raises(runner.PilotError, match="extra workspace entry"):
        runner.validate_gate1_repository(
            repository,
            initial_files,
            "docs/changes/feat-001-demo/spec.md",
            runner.run_git(repository, "rev-parse", "HEAD^"),
        )

    scratch.unlink()
    (repository / ".experiment/link").symlink_to(first_doc)
    with pytest.raises(runner.PilotError, match="symlink"):
        runner.validate_gate1_repository(
            repository,
            initial_files,
            "docs/changes/feat-001-demo/spec.md",
            runner.run_git(repository, "rev-parse", "HEAD^"),
        )


def test_corpus_projection_requires_clean_tracked_snapshot(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    initialize_repository(
        repository,
        {"docs/changes/feat-100-allowed/spec.md": "# Tracked\n"},
    )
    untracked = repository / "docs/changes/feat-101-draft/spec.md"
    untracked.parent.mkdir(parents=True)
    untracked.write_text("# Untracked draft\n", encoding="utf-8")

    config = {
        "case_id": "H02",
        "formal_eligible": False,
        "projection_seed": "fixed",
        "case_lineage_exclusions": ["feat-510-target"],
        "global_exclusions": ["feat-532-control"],
    }
    with pytest.raises(runner.PilotError, match="source repository must be clean"):
        runner.project_anonymous_corpus(repository, tmp_path / "artifacts", config)


def test_run_audit_critical_flag_matches_findings() -> None:
    audit = {
        "formal_eligible": False,
        "run_id": "T1",
        "critical_error": False,
        "findings": [
            {
                "type": "unsupported_material_judgment",
                "severity": "critical",
                "evidence": "unsupported choice",
                "context_refs": ["OX"],
            }
        ],
    }

    with pytest.raises(runner.PilotError, match="critical flag"):
        runner.validate_run_audit(audit, {"OX"}, "T1")


def test_blind_judge_rejects_duplicate_projection_and_criterion_ids() -> None:
    criteria = [
        {"criterion_id": f"J{index:02d}", "rating": "met", "rationale": "ok"}
        for index in range(1, 7)
    ]
    judgment = {
        "formal_eligible": False,
        "judge_id": "J1",
        "assessments": [
            {"projection_id": "P1", "criteria": criteria, "critical_error": False},
            {"projection_id": "P1", "criteria": criteria, "critical_error": False},
        ],
        "critical_error": False,
        "summary": "duplicate",
    }
    with pytest.raises(runner.PilotError, match="projection ids"):
        runner.validate_blind_judgment(judgment, "J1")

    judgment["assessments"][1]["projection_id"] = "P2"
    judgment["assessments"][1]["criteria"][-1]["criterion_id"] = "J05"
    with pytest.raises(runner.PilotError, match="criterion ids"):
        runner.validate_blind_judgment(judgment, "J1")


def test_owner_context_refs_are_derived_from_loaded_atoms() -> None:
    context = {
        "atoms": [
            {"id": "OX"},
            {"id": "OY"},
        ]
    }

    assert runner.owner_context_ids(context) == {"OX", "OY"}
    runner.validate_owner_context_refs(["OY"], context, "owner reply")
    with pytest.raises(runner.PilotError, match="unknown owner context ref"):
        runner.validate_owner_context_refs(["O01"], context, "owner reply")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("conclusion", "infrastructure_fail"),
        ("diagnostics.leakage_passed", False),
    ],
)
def test_replay_rejects_semantically_tampered_result(
    tmp_path: Path, field: str, value: object
) -> None:
    source = runner.EXPERIMENT_ROOT / "pilot/results/h02-pilot-v1"
    artifacts = tmp_path / "artifacts"
    shutil.copytree(source, artifacts)
    result = load_json(artifacts / "pilot-result.json")
    if field == "conclusion":
        result["conclusion"] = value
    else:
        result["diagnostics"]["leakage_passed"] = value
    runner.write_json(artifacts / "pilot-result.json", result)
    manifest = runner.evidence_manifest(artifacts)
    runner.write_json(artifacts / "evidence-manifest.json", manifest)
    if "evidence_manifest_sha256" in result:
        result["evidence_manifest_sha256"] = runner.sha256_bytes(
            runner.canonical_json_bytes(manifest)
        )
        runner.write_json(artifacts / "pilot-result.json", result)

    with pytest.raises(runner.PilotError, match="semantic pilot result drift"):
        runner.replay_pilot(artifacts)


def test_replay_rejects_forged_actual_attestation(tmp_path: Path) -> None:
    source = runner.EXPERIMENT_ROOT / "pilot/results/h02-pilot-v1"
    artifacts = tmp_path / "artifacts"
    shutil.copytree(source, artifacts)
    context = artifacts / "contexts/memory-builder-01"
    actual = load_json(context / "actual.json")
    actual["os_sandbox"] = {
        "mechanism": "macos_sandbox_exec_seatbelt",
        "canary_read_blocked": False,
        "profile_sha256": "0" * 64,
    }
    runner.write_json(context / "actual.json", actual)
    runner.write_json(
        artifacts / "evidence-manifest.json", runner.evidence_manifest(artifacts)
    )

    with pytest.raises(runner.PilotError, match="actual attestation"):
        runner.replay_pilot(artifacts)


def test_cli_rejects_unsealed_custom_config() -> None:
    with pytest.raises(SystemExit):
        runner.parse_args(
            [
                "prepare",
                "--repository",
                ".",
                "--workspace",
                "/tmp/workspace",
                "--artifacts",
                "/tmp/artifacts",
                "--config",
                "/tmp/custom.json",
            ]
        )
