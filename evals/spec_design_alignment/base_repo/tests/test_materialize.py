from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


BASE_REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = BASE_REPO_DIR / "materialize.py"


def run(
    *args: str, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    result = subprocess.run(
        [*args],
        cwd=cwd,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def write(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def git(repository: Path, *args: str) -> str:
    return run("git", *args, cwd=repository).stdout.strip()


def build_source_repository(tmp_path: Path) -> tuple[Path, str, str, str]:
    repository = tmp_path / "source"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    git(repository, "config", "user.name", "Fixture")
    git(repository, "config", "user.email", "fixture@example.test")

    write(repository / "README.md", "product tree\n")
    write(repository / "bin" / "entry", "#!/bin/sh\necho ready\n", executable=True)
    write(
        repository / "docs" / "README.md",
        "[specs](specs/README.md)\n"
        "[workflow](development/change-workflow.md)\n"
        "[changes](changes/README.md)\n",
    )
    write(repository / "docs" / "specs" / "README.md", "current specs\n")
    write(repository / "docs" / "changes" / "README.md", "change storage\n")
    write(repository / "docs" / "development" / "README.md", "development index\n")
    write(
        repository / "docs" / "development" / "change-workflow.md",
        "current workflow route\n",
    )
    write(repository / "docs" / "order" / "actual" / "item.txt", "directory prefix\n")
    write(repository / "docs" / "order" / "actual-r10" / "item.txt", "hyphen suffix\n")
    write(
        repository / "AGENTS.md",
        "nano fixture\n\n"
        "## Project overview\nprivate runner route\n\n"
        "## 架构总览\nkeep architecture\n\n"
        "## 架构红线\nkeep boundaries\n\n"
        "## Unrelated\ndrop this\n\n"
        "## 工作红线\nkeep work rules\n",
    )
    write(
        repository / ".claude" / "skills" / "legacy" / "SKILL.md", "historical oracle\n"
    )
    write(
        repository
        / "src"
        / "personal_assistant"
        / "builtin_skills"
        / "product"
        / "SKILL.md",
        "product-owned skill\n",
    )
    write(
        repository
        / "docs"
        / "changes"
        / "feat-510-unified-tool-approval-model"
        / "spec.md",
        "feat-510 tool_approval_model\n",
    )
    write(
        repository / "docs" / "changes" / "refactor-pending" / "motivation.md",
        "unimplemented active design\n",
    )
    write(
        repository / "docs" / "changes" / "archive" / "feat-100-completed" / "spec.md",
        "completed history that imports active feat-510 claims\n",
    )
    git(repository, "add", "--all")
    git(repository, "commit", "-m", "fixture product cutoff")
    source_commit = git(repository, "rev-parse", "HEAD")
    source_tree = git(repository, "rev-parse", "HEAD^{tree}")

    write(repository / "workflow" / "author" / "SKILL.md", "current author workflow\n")
    write(
        repository / "workflow" / "reviewer" / "SKILL.md", "current reviewer workflow\n"
    )
    write(
        repository / "workflow" / "docs" / "AGENTS.md",
        "replacement root instructions\n",
    )
    git(repository, "add", "--all")
    git(repository, "commit", "-m", "fixture frozen arm")
    arm_commit = git(repository, "rev-parse", "HEAD")
    return repository, source_commit, source_tree, arm_commit


def recipe_for(
    repository: Path,
    source_commit: str,
    source_tree: str,
    arm_commit: str,
) -> dict[str, object]:
    author = (repository / "workflow/author/SKILL.md").read_bytes()
    reviewer = (repository / "workflow/reviewer/SKILL.md").read_bytes()
    required_doc_paths = (
        "AGENTS.md",
        "docs/README.md",
        "docs/changes/README.md",
        "docs/development/README.md",
        "docs/development/change-workflow.md",
        "docs/specs/README.md",
    )
    return {
        "schema_version": "1.0",
        "case_id": "H02",
        "source": {
            "ref": source_commit,
            "expected_commit": source_commit,
            "expected_tree": source_tree,
        },
        "scrub": {
            "remove_paths": [
                ".claude",
                ".agents",
                ".codex",
                "CLAUDE.md",
                "CODEX.md",
                "docs/changes/feat-510-unified-tool-approval-model",
                "docs/changes/refactor-pending",
            ],
            "instruction_marker": "SKILL.md",
            "product_instruction_roots": ["src/personal_assistant/builtin_skills"],
            "archive_lineage": {
                "policy": "drop_noncompleted_cross_references_v1",
                "drop_units": [
                    {
                        "path": "docs/changes/archive/feat-100-completed",
                        "referenced_noncompleted_unit_ids": ["feat-510"],
                    }
                ],
            },
        },
        "docs_projection": {"mode": "preserve_exact"},
        "arm": {
            "id": "A",
            "ref": arm_commit,
            "files": [
                {
                    "source": "workflow/author/SKILL.md",
                    "destination": ".claude/skills/current-author/SKILL.md",
                    "sha256": hashlib.sha256(author).hexdigest(),
                },
                {
                    "source": "workflow/reviewer/SKILL.md",
                    "destination": ".claude/skills/current-reviewer/SKILL.md",
                    "sha256": hashlib.sha256(reviewer).hexdigest(),
                },
            ],
        },
        "assertions": {
            "required_paths": [
                "README.md",
                "docs/README.md",
                "docs/changes/README.md",
                "docs/development/README.md",
                "docs/development/change-workflow.md",
                "docs/specs/README.md",
                "src/personal_assistant/builtin_skills/product/SKILL.md",
                ".claude/skills/current-author/SKILL.md",
                ".claude/skills/current-reviewer/SKILL.md",
            ],
            "required_sha256": {
                path: hashlib.sha256((repository / path).read_bytes()).hexdigest()
                for path in required_doc_paths
            },
            "forbidden_paths": [
                ".claude/skills/legacy",
                "docs/changes/feat-510-unified-tool-approval-model",
                "docs/changes/refactor-pending",
                "docs/changes/archive/feat-100-completed",
            ],
            "forbidden_text": ["feat-510", "tool_approval_model", "historical oracle"],
        },
        "git": {
            "branch": "main",
            "author_name": "Repository Bootstrap",
            "author_email": "repository@invalid",
            "timestamp": "946684800 +0000",
            "message": "initial repository\n",
        },
    }


def invoke(
    recipe_path: Path,
    repository: Path,
    output: Path,
    manifest: Path,
    receipt: Path,
) -> subprocess.CompletedProcess[str]:
    return run(
        sys.executable,
        str(SCRIPT),
        "--recipe",
        str(recipe_path),
        "--repository",
        str(repository),
        "--output",
        str(output),
        "--manifest",
        str(manifest),
        "--receipt",
        str(receipt),
        check=False,
    )


def prepare(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    repository, source_commit, source_tree, arm_commit = build_source_repository(
        tmp_path
    )
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(recipe_for(repository, source_commit, source_tree, arm_commit)),
        encoding="utf-8",
    )
    return (
        repository,
        recipe_path,
        tmp_path / "output",
        tmp_path / "manifest.json",
        tmp_path / "receipt.json",
    )


def test_cli_materializes_complete_clean_parentless_repository(tmp_path: Path) -> None:
    repository, recipe_path, output, manifest_path, receipt_path = prepare(tmp_path)
    output.mkdir()

    result = invoke(recipe_path, repository, output, manifest_path, receipt_path)

    assert result.returncode == 0, result.stderr
    assert (output / "README.md").read_text(encoding="utf-8") == "product tree\n"
    assert os.access(output / "bin" / "entry", os.X_OK)
    assert (output / "src/personal_assistant/builtin_skills/product/SKILL.md").is_file()
    assert not (output / ".claude/skills/legacy").exists()
    assert not (output / "docs/changes/feat-510-unified-tool-approval-model").exists()
    assert not (output / "docs/changes/refactor-pending").exists()
    assert (
        output / ".claude/skills/current-author/SKILL.md"
    ).read_text() == "current author workflow\n"
    assert (
        output / ".claude/skills/current-reviewer/SKILL.md"
    ).read_text() == "current reviewer workflow\n"
    assert (output / "AGENTS.md").read_text(encoding="utf-8") == (
        "nano fixture\n\n"
        "## Project overview\nprivate runner route\n\n"
        "## 架构总览\nkeep architecture\n\n"
        "## 架构红线\nkeep boundaries\n\n"
        "## Unrelated\ndrop this\n\n"
        "## 工作红线\nkeep work rules\n"
    )
    docs_index = (output / "docs/README.md").read_text(encoding="utf-8")
    assert "(development/change-workflow.md)" in docs_index
    assert "(changes/README.md)" in docs_index
    assert (output / "docs/development/change-workflow.md").is_file()
    assert (output / "docs/changes/README.md").is_file()

    assert git(output, "branch", "--show-current") == "main"
    assert git(output, "rev-list", "--all", "--count") == "1"
    assert len(git(output, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 1
    assert git(output, "status", "--porcelain=v1") == ""
    assert {path.name for path in (output / ".git").iterdir()} == {
        "HEAD",
        "config",
        "index",
        "objects",
        "refs",
    }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest_paths = {entry["path"] for entry in manifest["entries"]}
    assert "README.md" in manifest_paths
    assert ".claude/skills/current-author/SKILL.md" in manifest_paths
    assert not any(path.startswith(".git/") for path in manifest_paths)
    assert receipt["source"]["commit"] == git(
        repository, "rev-parse", f"{receipt['source']['ref']}^{{commit}}"
    )
    assert receipt["arm"]["id"] == "A"
    assert receipt["docs_projection"] == {"mode": "preserve_exact"}
    assert receipt["scrub"]["archive_lineage"] == {
        "policy": "drop_noncompleted_cross_references_v1",
        "dropped_units": [
            {
                "path": "docs/changes/archive/feat-100-completed",
                "referenced_noncompleted_unit_ids": ["feat-510"],
                "present": True,
            }
        ],
        "removed_roots": ["docs/changes/archive/feat-100-completed"],
        "removed_roots_sha256": "601701c8f8b5d0295feb48c7c2cbc1cb5fcd2b79850c2816352e43f84960222b",
    }
    assert receipt["content_manifest_sha256"] == manifest["files_manifest_sha256"]
    assert receipt["git"]["tree"] == git(output, "rev-parse", "HEAD^{tree}")
    assert receipt["checks"] == {
        "assertions": "passed",
        "clean_worktree": True,
        "single_parentless_commit": True,
        "tree_matches_manifest": True,
    }
    assert not list(tmp_path.glob(".base-repo-stage-*"))


def test_content_manifest_uses_canonical_posix_path_order(tmp_path: Path) -> None:
    repository, recipe_path, output, manifest_path, receipt_path = prepare(tmp_path)

    result = invoke(recipe_path, repository, output, manifest_path, receipt_path)

    assert result.returncode == 0, result.stderr
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = [entry["path"] for entry in manifest["entries"]]
    assert paths == sorted(paths)
    assert paths.index("docs/order/actual-r10/item.txt") < paths.index(
        "docs/order/actual/item.txt"
    )


def test_git_index_is_zero_stat_canonical(tmp_path: Path) -> None:
    repository, recipe_path, output, manifest_path, receipt_path = prepare(tmp_path)

    result = invoke(recipe_path, repository, output, manifest_path, receipt_path)

    assert result.returncode == 0, result.stderr
    canonical_index = tmp_path / "canonical-index"
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_INDEX_FILE"] = str(canonical_index)
    rebuilt = subprocess.run(
        ["git", "read-tree", "HEAD"],
        cwd=output,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert rebuilt.returncode == 0, rebuilt.stderr.decode(errors="replace")
    assert (output / ".git/index").read_bytes() == canonical_index.read_bytes()


def test_cli_refuses_nonempty_and_symlink_outputs_without_touching_them(
    tmp_path: Path,
) -> None:
    repository, recipe_path, output, manifest_path, receipt_path = prepare(tmp_path)
    output.mkdir()
    marker = output / "owned.txt"
    marker.write_text("do not touch\n", encoding="utf-8")

    nonempty = invoke(recipe_path, repository, output, manifest_path, receipt_path)

    assert nonempty.returncode == 2
    assert "non-empty" in nonempty.stderr
    assert marker.read_text(encoding="utf-8") == "do not touch\n"
    assert not manifest_path.exists()
    assert not receipt_path.exists()

    link_target = tmp_path / "link-target"
    link_target.mkdir()
    link_output = tmp_path / "link-output"
    try:
        link_output.symlink_to(link_target, target_is_directory=True)
    except OSError:
        pytest.skip("filesystem does not permit symlinks")

    linked = invoke(recipe_path, repository, link_output, manifest_path, receipt_path)

    assert linked.returncode == 2
    assert "symlink" in linked.stderr
    assert not any(link_target.iterdir())
    assert not manifest_path.exists()
    assert not receipt_path.exists()


def test_cli_does_not_publish_repository_when_leak_assertion_fails(
    tmp_path: Path,
) -> None:
    repository, recipe_path, output, manifest_path, receipt_path = prepare(tmp_path)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    source_commit = recipe["source"]["expected_commit"]
    git(repository, "checkout", source_commit)
    write(
        repository / "notes.md", "tool_approval_model leaked outside the target unit\n"
    )
    git(repository, "add", "notes.md")
    git(repository, "commit", "-m", "fixture leak")
    leaked_commit = git(repository, "rev-parse", "HEAD")
    recipe["source"] = {
        "ref": leaked_commit,
        "expected_commit": leaked_commit,
        "expected_tree": git(repository, "rev-parse", "HEAD^{tree}"),
    }
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

    result = invoke(recipe_path, repository, output, manifest_path, receipt_path)

    assert result.returncode == 2
    assert "forbidden text" in result.stderr
    assert not output.exists()
    assert not manifest_path.exists()
    assert not receipt_path.exists()


def test_cli_allows_only_declared_workflow_owned_docs_replacement(
    tmp_path: Path,
) -> None:
    repository, recipe_path, output, manifest_path, receipt_path = prepare(tmp_path)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    replacement = (repository / "workflow/docs/AGENTS.md").read_bytes()
    replacement_hash = hashlib.sha256(replacement).hexdigest()
    recipe["docs_projection"] = {
        "mode": "workflow_owned_replace",
        "ref": recipe["arm"]["ref"],
        "files": [
            {
                "source": "workflow/docs/AGENTS.md",
                "destination": "AGENTS.md",
                "sha256": replacement_hash,
            }
        ],
    }
    recipe["assertions"]["required_sha256"]["AGENTS.md"] = replacement_hash
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

    replaced = invoke(recipe_path, repository, output, manifest_path, receipt_path)

    assert replaced.returncode == 0, replaced.stderr
    assert (output / "AGENTS.md").read_bytes() == replacement
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["docs_projection"]["mode"] == "workflow_owned_replace"
    assert receipt["docs_projection"]["entries"][0]["destination"] == "AGENTS.md"

    second_output = tmp_path / "second-output"
    second_manifest = tmp_path / "second-manifest.json"
    second_receipt = tmp_path / "second-receipt.json"
    recipe["docs_projection"] = {"mode": "preserve_exact"}
    recipe["arm"]["files"][0]["destination"] = "AGENTS.md"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

    undeclared = invoke(
        recipe_path, repository, second_output, second_manifest, second_receipt
    )

    assert undeclared.returncode == 2
    assert "arm destination collides with product tree: AGENTS.md" in undeclared.stderr
    assert not second_output.exists()
