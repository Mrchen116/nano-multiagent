from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.spec_design_alignment.experiments.feat_532_spec_memory import runner


def write_first_doc(repository: Path, lifecycle: str, unit: str, text: str) -> None:
    root = repository / "docs/changes"
    if lifecycle != "active":
        root /= lifecycle
    path = root / unit / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_projection_is_anonymous_whole_lineage_and_replayable(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    write_first_doc(repository, "active", "feat-100-allowed", "# Allowed\n")
    write_first_doc(repository, "archive", "bugfix-101-allowed", "# Archive\n")
    write_first_doc(repository, "archive", "feat-510-target", "# Secret target\n")
    write_first_doc(repository, "active", "feat-532-control", "# Control\n")
    legacy = repository / "docs/changes/archive/bugfix-102-legacy"
    legacy.mkdir(parents=True)
    (legacy / "README.md").write_text(
        "# Legacy without a first document\n", encoding="utf-8"
    )
    runner.rewrite_as_parentless_repository(repository)
    config = {
        "case_id": "H02",
        "formal_eligible": False,
        "projection_seed": "fixed-seed",
        "case_lineage_exclusions": ["feat-510-target"],
        "global_exclusions": ["feat-532-control"],
    }

    first_artifacts = tmp_path / "first"
    second_artifacts = tmp_path / "second"
    first_public, first_private = runner.project_anonymous_corpus(
        repository, first_artifacts, config
    )
    second_public, second_private = runner.project_anonymous_corpus(
        repository, second_artifacts, config
    )

    assert first_public == second_public
    assert first_private == second_private
    assert first_public["formal_eligible"] is False
    assert len(first_public["documents"]) == 2
    assert all(
        set(entry) == {"document_id", "source_locator", "sha256"}
        for entry in first_public["documents"]
    )
    assert all("feat-" not in json.dumps(entry) for entry in first_public["documents"])
    assert {entry["source_path"] for entry in first_private["source_map"]} == {
        "docs/changes/feat-100-allowed/spec.md",
        "docs/changes/archive/bugfix-101-allowed/spec.md",
    }
    assert first_private["source_commit"] == runner.run_git(
        repository, "rev-parse", "HEAD"
    )
    assert first_private["source_tree"] == runner.run_git(
        repository, "rev-parse", "HEAD^{tree}"
    )
    assert first_private["source_cleanliness"] == "clean_tracked_only"
    projected = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((first_artifacts / "corpus/documents").glob("*.txt"))
    )
    assert "Secret target" not in projected
    assert "Control" not in projected


def test_candidate_projection_has_one_skill_and_no_control_history(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    skill = repository / ".claude/skills/change-spec-author"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Test Skill\n", encoding="utf-8")

    base = tmp_path / "base"
    (base / ".claude/skills/other").mkdir(parents=True)
    (base / ".claude/skills/other/SKILL.md").write_text("secret\n", encoding="utf-8")
    (base / "evals").mkdir()
    (base / "evals/control.json").write_text("{}\n", encoding="utf-8")
    target = base / "docs/changes/feat-510-unified-tool-approval-model"
    target.mkdir(parents=True)
    (target / "spec.md").write_text("secret\n", encoding="utf-8")
    (base / "README.md").write_text("# Candidate world\n", encoding="utf-8")
    runner.rewrite_as_parentless_repository(base)

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    neutral, candidate, receipt = runner.build_repository_projections(
        repository, base, tmp_path / "workspace", artifacts
    )

    assert not (neutral / ".claude").exists()
    assert not (neutral / "evals").exists()
    assert (candidate / ".agents/skills/change-spec-author/SKILL.md").is_file()
    assert not (candidate / ".claude").exists()
    assert not (candidate / "evals").exists()
    assert not (
        candidate / "docs/changes/feat-510-unified-tool-approval-model"
    ).exists()
    assert receipt["formal_eligible"] is False
    assert receipt["candidate"]["skill_closure"] == [
        ".agents/skills/change-spec-author/SKILL.md"
    ]
    assert len(runner.run_git(candidate, "rev-list", "--parents", "HEAD").split()) == 1
    assert (
        load_json(artifacts / "control/repository-projection-receipt.json") == receipt
    )


def test_provisional_contexts_validate_and_cannot_be_formal() -> None:
    runner.validate_schema(
        runner.EXPERIMENT_ROOT / "pilot/h02/config.json",
        runner.EXPERIMENT_ROOT / "schemas/pilot-config.schema.json",
    )
    runner.validate_schema(
        runner.EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json",
        runner.EXPERIMENT_ROOT / "schemas/owner-context.schema.json",
    )
    runner.validate_schema(
        runner.EXPERIMENT_ROOT / "pilot/h02/judge-context.provisional.json",
        runner.EXPERIMENT_ROOT / "schemas/judge-context.schema.json",
    )
    assert load_json(runner.DEFAULT_CONFIG)["allowed_conclusions"] == [
        "infrastructure_pass",
        "infrastructure_fail",
    ]


def test_direct_load_memory_is_the_only_candidate_arm_difference(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template"
    (template / ".agents/skills/change-spec-author").mkdir(parents=True)
    (template / ".agents/skills/change-spec-author/SKILL.md").write_text(
        "# Spec author\n", encoding="utf-8"
    )
    (template / "README.md").write_text("# Base\n", encoding="utf-8")
    runner.rewrite_as_parentless_repository(template)
    memory_store = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "scheme_id": "direct-load-broad-first-docs-v0",
        "entries": [
            {
                "id": "M01",
                "category": "user_preference",
                "content": "Preserve omission semantics.",
                "applicability": "Configuration changes.",
                "confidence": "high",
                "source_refs": ["source-0001:L1-L2"],
            }
        ],
    }

    baseline, treatment, receipt = runner.prepare_candidate_arms(
        template, tmp_path / "arms", tmp_path / "artifacts", memory_store
    )

    baseline_files = {
        entry["path"]: entry["sha256"]
        for entry in runner.visible_file_manifest(baseline)
    }
    treatment_files = {
        entry["path"]: entry["sha256"]
        for entry in runner.visible_file_manifest(treatment)
    }
    assert set(treatment_files) - set(baseline_files) == {".experiment/task-memory.md"}
    assert all(
        treatment_files[path] == digest for path, digest in baseline_files.items()
    )
    assert runner.run_git(baseline, "rev-parse", "HEAD") == runner.run_git(
        treatment, "rev-parse", "HEAD"
    )
    assert receipt["only_allowed_difference"] is True
    assert receipt["loaded_entry_ids"] == ["M01"]
    assert Path(runner.run_git(baseline, "rev-parse", "--git-common-dir")).name == (
        runner.CANDIDATE_GIT_METADATA
    )
    assert all(
        not entry["path"].startswith(runner.CANDIDATE_GIT_METADATA)
        for entry in runner.visible_file_manifest(baseline)
    )
    assert runner.run_git(baseline, "status", "--porcelain") == ""
    assert runner.run_git(treatment, "status", "--porcelain") == ""


def test_role_manifest_binds_visible_files_and_input_envelope(tmp_path: Path) -> None:
    workspace = tmp_path / "role"
    workspace.mkdir()
    instructions = workspace / "AGENTS.md"
    instructions.write_text("# Isolated role\n", encoding="utf-8")
    output_schema = workspace / "output-schema.json"
    output_schema.write_text('{"type":"object"}\n', encoding="utf-8")
    envelope = "<role_input>{}</role_input>"

    manifest = runner.create_role_context_manifest(
        manifest_id="builder-01",
        role="memory_builder",
        lifecycle="ephemeral",
        cwd=workspace,
        instructions=instructions.read_text(encoding="utf-8"),
        envelope=envelope,
        output_schema=output_schema,
        model="gpt-test",
        reasoning_effort="medium",
        skill_closure=[],
        workspace_write=True,
        forbidden_surfaces=["case identity", "private truth"],
    )

    manifest_path = tmp_path / "manifest.json"
    runner.write_json(manifest_path, manifest)
    runner.validate_schema(
        manifest_path,
        runner.EXPERIMENT_ROOT / "schemas/role-context-manifest.schema.json",
    )
    runner.verify_role_context(manifest, workspace, envelope)

    assert manifest["tools"] == {
        "network": False,
        "shell": True,
        "workspace_write": True,
    }

    instructions.write_text("# Drifted role\n", encoding="utf-8")
    with pytest.raises(runner.PilotError, match="visible-file manifest drift"):
        runner.verify_role_context(manifest, workspace, envelope)


def test_conclusion_projection_removes_request_and_qa_without_rewriting() -> None:
    source = """# Feature

## 原始需求

secret request

## 用户场景

visible scenario

## 澄清记录

- Q: hidden
- A: hidden

## 验收标准

visible criterion
"""

    projected = runner.project_conclusions(source)

    assert "secret request" not in projected
    assert "Q: hidden" not in projected
    assert "visible scenario" in projected
    assert "visible criterion" in projected
    assert projected == runner.project_conclusions(source)


def test_next_scheme_rejects_case_specific_atoms_outside_denylist() -> None:
    proposal = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "scheme_id": "next-v1",
        "parent_scheme_id": "direct-load-broad-first-docs-v0",
        "build_policy": "Prefer recurring omission principles.",
        "consumption_policy": "Direct-load applicable entries.",
        "delta": ["Rank by cross-document recurrence."],
        "hypothesis": "Less irrelevant context improves alignment.",
        "forbidden_case_specific_atoms": ["H02", "feat-510"],
    }
    runner.validate_schema_value(
        proposal, runner.EXPERIMENT_ROOT / "schemas/next-scheme.schema.json"
    )
    runner.verify_next_scheme(proposal, ["H02", "feat-510"])
    proposal["hypothesis"] = "Optimize feat-510 directly."
    with pytest.raises(runner.PilotError, match="case-specific atom"):
        runner.verify_next_scheme(proposal, ["H02", "feat-510"])


def test_judge_leak_check_allows_neutral_product_memory_paths_only() -> None:
    allowed = {
        "docs/specs/agent/memory.md",
        ".experiment/conclusion-P1.md",
        ".experiment/conclusion-P2.md",
        ".experiment/judge-context.provisional.json",
        ".experiment/public-brief.md",
    }

    assert runner.judge_visible_surface_is_clean(allowed)
    assert not runner.judge_visible_surface_is_clean(
        allowed | {".experiment/task-memory.md"}
    )
    assert not runner.judge_visible_surface_is_clean(
        allowed | {"evals/private-transcript.json"}
    )
