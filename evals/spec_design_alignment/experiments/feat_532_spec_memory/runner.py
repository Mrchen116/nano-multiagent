#!/usr/bin/env python3
"""Run and replay the feat-532 non-scoring H02 infrastructure pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parent
SUITE_ROOT = EXPERIMENT_ROOT.parents[1]
DEFAULT_CONFIG = EXPERIMENT_ROOT / "pilot/h02/config.json"
FIRST_DOCUMENT_NAMES = ("spec.md", "motivation.md", "incident.md", "fix.md")
FRESH_GIT_ENVIRONMENT = {
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_ATTR_NOSYSTEM": "1",
}
UNIT_DIR_RE = re.compile(r"^(?:feat|bugfix|refactor|perf)-[0-9]+(?:-|$)")


class PilotError(RuntimeError):
    """Report a fail-closed pilot contract violation."""


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for hash and seal identities."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    """Return the lowercase SHA-256 digest for bytes."""
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Return a file content identity."""
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object or fail with its path."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PilotError(f"invalid JSON at {path}: {error}") from error
    if not isinstance(value, dict):
        raise PilotError(f"expected JSON object at {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    """Write one stable UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_schema(instance_path: Path, schema_path: Path) -> None:
    """Validate an instance with the suite dependency-free schema subset."""
    repository_root = EXPERIMENT_ROOT.parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from evals.spec_design_alignment.validate_dataset import SchemaSubsetValidator

    errors = SchemaSubsetValidator(load_json(schema_path)).errors(load_json(instance_path))
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise PilotError(f"schema validation failed for {instance_path}:\n{joined}")


def require_empty_destination(path: Path, label: str) -> None:
    """Refuse ambiguous or destructive output destinations."""
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise PilotError(f"{label} must be absent or an empty directory: {path}")


def ensure_distinct_roots(workspace: Path, artifacts: Path) -> None:
    """Keep disposable workspaces and durable artifacts outside one another."""
    workspace = workspace.resolve(strict=False)
    artifacts = artifacts.resolve(strict=False)
    if workspace == artifacts or workspace in artifacts.parents or artifacts in workspace.parents:
        raise PilotError("workspace and artifacts must be distinct sibling roots")


def visible_file_manifest(root: Path) -> list[dict[str, str]]:
    """List ordinary role-visible files, excluding Git metadata."""
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink() or ".git" in relative.parts:
            continue
        entries.append({"path": relative.as_posix(), "sha256": sha256_file(path)})
    return entries


def run_git(repository: Path, *args: str) -> str:
    """Run Git without host configuration or repository redirection."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(FRESH_GIT_ENVIRONMENT)
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PilotError(f"git {' '.join(args)} failed in {repository}: {detail}")
    return result.stdout.strip()


def rewrite_as_parentless_repository(root: Path) -> dict[str, str]:
    """Remove inherited Git history and commit the current projection once."""
    shutil.rmtree(root / ".git", ignore_errors=True)
    run_git(root, "init", "--initial-branch=main")
    run_git(root, "add", "-A")
    run_git(
        root,
        "-c",
        "user.name=Evaluation Bootstrap",
        "-c",
        "user.email=evaluation@invalid",
        "commit",
        "-m",
        "initial evaluation repository",
    )
    head = run_git(root, "rev-parse", "HEAD")
    parents = run_git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    if len(parents) != 1:
        raise PilotError("projected repository is not parentless")
    if run_git(root, "remote"):
        raise PilotError("projected repository unexpectedly has a remote")
    if run_git(root, "status", "--porcelain"):
        raise PilotError("projected repository is not clean")
    return {"head": head, "tree": run_git(root, "rev-parse", "HEAD^{tree}")}


def materialize_h02_base(repository: Path, workspace: Path, artifacts: Path, config: dict[str, Any]) -> Path:
    """Materialize the shared H02 base recipe without changing its semantics."""
    repository_root = EXPERIMENT_ROOT.parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from evals.spec_design_alignment.base_repo.materialize import materialize

    output = workspace / "shared-h02-base"
    manifest = artifacts / "control/shared-base-manifest.json"
    receipt = artifacts / "control/shared-base-receipt.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    materialize(
        SUITE_ROOT / config["base_recipe"],
        repository,
        output,
        manifest,
        receipt,
    )
    return output


def first_document_sources(repository: Path) -> list[tuple[str, Path]]:
    """Enumerate one versioned first document for every change unit."""
    sources: list[tuple[str, Path]] = []
    roots = (
        ("active", repository / "docs/changes"),
        ("archive", repository / "docs/changes/archive"),
        ("retired", repository / "docs/changes/retired"),
    )
    for lifecycle, root in roots:
        if not root.is_dir():
            continue
        for unit in sorted(path for path in root.iterdir() if path.is_dir()):
            if lifecycle == "active" and unit.name in {"archive", "retired"}:
                continue
            if UNIT_DIR_RE.match(unit.name) is None:
                continue
            documents = [unit / name for name in FIRST_DOCUMENT_NAMES if (unit / name).is_file()]
            if not documents:
                continue
            if len(documents) > 1:
                raise PilotError(
                    f"change unit has ambiguous first documents: {unit} -> {documents}"
                )
            sources.append((lifecycle, documents[0]))
    return sources


def project_anonymous_corpus(
    repository: Path,
    artifacts: Path,
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project the allowed first-document corpus without exposing unit identity."""
    excluded = set(config["case_lineage_exclusions"]) | set(config["global_exclusions"])
    selected: list[tuple[str, Path]] = []
    excluded_sources: list[dict[str, str]] = []
    for lifecycle, path in first_document_sources(repository):
        unit_name = path.parent.name
        entry = {
            "lifecycle": lifecycle,
            "path": path.relative_to(repository).as_posix(),
            "sha256": sha256_file(path),
        }
        if unit_name in excluded:
            excluded_sources.append(entry)
        else:
            selected.append((lifecycle, path))

    rng = random.Random(config["projection_seed"])
    rng.shuffle(selected)
    documents_root = artifacts / "corpus/documents"
    documents_root.mkdir(parents=True, exist_ok=True)
    public_entries: list[dict[str, str]] = []
    source_map: list[dict[str, str]] = []
    for index, (lifecycle, source) in enumerate(selected, start=1):
        document_id = f"doc-{index:04d}"
        source_locator = f"source-{index:04d}"
        content = source.read_bytes()
        destination = documents_root / f"{document_id}.md"
        destination.write_bytes(content)
        public_entries.append(
            {
                "document_id": document_id,
                "source_locator": source_locator,
                "sha256": sha256_bytes(content),
            }
        )
        source_map.append(
            {
                "document_id": document_id,
                "source_locator": source_locator,
                "lifecycle": lifecycle,
                "source_path": source.relative_to(repository).as_posix(),
                "source_sha256": sha256_bytes(content),
            }
        )
    public_manifest = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "projection": "anonymous_whole_first_documents_v1",
        "documents": public_entries,
    }
    private_receipt = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "case_id": config["case_id"],
        "excluded_units": sorted(excluded),
        "excluded_sources": sorted(excluded_sources, key=lambda item: item["path"]),
        "source_map": source_map,
    }
    write_json(artifacts / "corpus/public-manifest.json", public_manifest)
    write_json(artifacts / "control/corpus-projection-receipt.json", private_receipt)
    return public_manifest, private_receipt


def copy_projection(source: Path, destination: Path) -> None:
    """Copy a repository projection without inherited Git metadata."""
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git"))


def build_repository_projections(
    repository: Path,
    base: Path,
    workspace: Path,
    artifacts: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    """Create neutral and single-Skill candidate repositories."""
    neutral = workspace / "neutral-repo"
    copy_projection(base, neutral)
    for forbidden in (
        ".claude",
        ".agents",
        ".codex",
        "evals",
        "docs/changes/feat-510-unified-tool-approval-model",
        "docs/changes/feat-397-spec-design-agent-team",
        "docs/changes/feat-532-spec-memory-loop",
    ):
        target = neutral / forbidden
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    neutral_git = rewrite_as_parentless_repository(neutral)

    candidate = workspace / "candidate-template"
    copy_projection(neutral, candidate)
    skill_source = repository / ".claude/skills/change-spec-author"
    skill_destination = candidate / ".agents/skills/change-spec-author"
    skill_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_source, skill_destination)
    candidate_git = rewrite_as_parentless_repository(candidate)

    forbidden_paths = (
        ".claude",
        ".codex",
        "evals",
        "docs/changes/feat-510-unified-tool-approval-model",
    )
    for relative in forbidden_paths:
        if (candidate / relative).exists():
            raise PilotError(f"candidate projection retained forbidden path: {relative}")

    candidate_manifest = visible_file_manifest(candidate)
    skill_files = [
        entry["path"]
        for entry in candidate_manifest
        if entry["path"].startswith(".agents/skills/change-spec-author/")
    ]
    if not skill_files or any(
        entry["path"].startswith(".agents/skills/")
        and not entry["path"].startswith(".agents/skills/change-spec-author/")
        for entry in candidate_manifest
    ):
        raise PilotError("candidate does not contain exactly one Skill closure")

    projection_receipt = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "neutral": {
            "git": neutral_git,
            "visible_files": visible_file_manifest(neutral),
        },
        "candidate": {
            "git": candidate_git,
            "visible_files": candidate_manifest,
            "skill_closure": skill_files,
        },
    }
    write_json(artifacts / "control/repository-projection-receipt.json", projection_receipt)
    return neutral, candidate, projection_receipt


def checked_relative(root: Path, relative: str, label: str) -> Path:
    """Resolve a declared relative fixture path inside its authority root."""
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise PilotError(f"{label} escapes its root: {relative}")
    if not path.is_file():
        raise PilotError(f"{label} is missing: {path}")
    return path


def prepare_inputs(
    repository: Path,
    workspace: Path,
    artifacts: Path,
    config_path: Path,
) -> dict[str, Any]:
    """Materialize all deterministic inputs needed before the first LLM call."""
    repository = repository.resolve()
    workspace = workspace.resolve(strict=False)
    artifacts = artifacts.resolve(strict=False)
    if not (repository / ".git").exists():
        raise PilotError(f"repository is not a Git checkout: {repository}")
    ensure_distinct_roots(workspace, artifacts)
    require_empty_destination(workspace, "workspace")
    require_empty_destination(artifacts, "artifacts")
    workspace.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)

    config_path = config_path.resolve()
    config = load_json(config_path)
    validate_schema(config_path, EXPERIMENT_ROOT / "schemas/pilot-config.schema.json")
    owner_context = EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json"
    judge_context = EXPERIMENT_ROOT / "pilot/h02/judge-context.provisional.json"
    validate_schema(owner_context, EXPERIMENT_ROOT / "schemas/owner-context.schema.json")
    validate_schema(judge_context, EXPERIMENT_ROOT / "schemas/judge-context.schema.json")
    if config["formal_eligible"] is not False or config["repetitions"] != 1:
        raise PilotError("M0 must remain a non-scoring 1x1 pilot")

    base = materialize_h02_base(repository, workspace, artifacts, config)
    public_corpus, private_corpus = project_anonymous_corpus(repository, artifacts, config)
    neutral, candidate, projection = build_repository_projections(
        repository, base, workspace, artifacts
    )

    brief = checked_relative(SUITE_ROOT, config["public_brief"], "public brief")
    scheme = EXPERIMENT_ROOT / "pilot/h02/scheme-v0.json"
    static_inputs = {
        "config_sha256": sha256_file(config_path),
        "owner_context_sha256": sha256_file(owner_context),
        "judge_context_sha256": sha256_file(judge_context),
        "scheme_sha256": sha256_file(scheme),
        "public_brief_sha256": sha256_file(brief),
        "runner_sha256": sha256_file(Path(__file__)),
        "role_context_schema_sha256": sha256_file(
            EXPERIMENT_ROOT / "schemas/role-context-manifest.schema.json"
        ),
        "corpus_public_manifest_sha256": sha256_bytes(canonical_json_bytes(public_corpus)),
        "corpus_projection_receipt_sha256": sha256_bytes(
            canonical_json_bytes(private_corpus)
        ),
        "repository_projection_receipt_sha256": sha256_bytes(
            canonical_json_bytes(projection)
        ),
    }
    sealed_inputs_sha256 = sha256_bytes(canonical_json_bytes(static_inputs))
    seal = {
        "schema_version": "1.0",
        "pilot_id": config["pilot_id"],
        "case_id": config["case_id"],
        "formal_eligible": False,
        "repetitions": 1,
        "allowed_conclusions": config["allowed_conclusions"],
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "retry_limit_after_model_start": 0,
        "shared_feat397_assets_unchanged": True,
        "inputs": static_inputs,
        "sealed_inputs_sha256": sealed_inputs_sha256,
    }
    write_json(artifacts / "pilot-seal.json", seal)
    summary = {
        "pilot_id": config["pilot_id"],
        "case_id": config["case_id"],
        "formal_eligible": False,
        "workspace": str(workspace),
        "artifacts": str(artifacts),
        "neutral_repository": str(neutral),
        "candidate_template": str(candidate),
        "sealed_inputs_sha256": sealed_inputs_sha256,
    }
    write_json(artifacts / "prepare-summary.json", summary)
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the pilot command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="materialize deterministic inputs")
    prepare.add_argument("--repository", required=True, type=Path)
    prepare.add_argument("--workspace", required=True, type=Path)
    prepare.add_argument("--artifacts", required=True, type=Path)
    prepare.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute one runner command and print a machine-readable summary."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "prepare":
            result = prepare_inputs(
                args.repository, args.workspace, args.artifacts, args.config
            )
        else:
            raise PilotError(f"unsupported command: {args.command}")
    except (OSError, PilotError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
