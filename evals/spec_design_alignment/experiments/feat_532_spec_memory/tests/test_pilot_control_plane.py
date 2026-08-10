from __future__ import annotations

import json
from pathlib import Path

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
    (legacy / "README.md").write_text("# Legacy without a first document\n", encoding="utf-8")
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
    projected = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((first_artifacts / "corpus/documents").glob("*.md"))
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
    assert not (candidate / "docs/changes/feat-510-unified-tool-approval-model").exists()
    assert receipt["formal_eligible"] is False
    assert receipt["candidate"]["skill_closure"] == [
        ".agents/skills/change-spec-author/SKILL.md"
    ]
    assert len(runner.run_git(candidate, "rev-list", "--parents", "HEAD").split()) == 1
    assert load_json(artifacts / "control/repository-projection-receipt.json") == receipt


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
