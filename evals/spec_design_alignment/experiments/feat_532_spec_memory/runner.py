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
import tempfile
from typing import Any

from evals.spec_design_alignment.experiments.feat_532_spec_memory import (
    sandbox_wrapper,
)


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
CANDIDATE_GIT_METADATA = ".evaluation-git"
ROLE_READABLE_ROOTS = ["role_runtime", "system_runtime", "workspace"]


class PilotError(RuntimeError):
    """Report a fail-closed pilot contract violation."""


class CodexSession:
    """Run one isolated real Codex session and retain only sanitized evidence."""

    def __init__(
        self,
        *,
        role: str,
        workspace: Path,
        workspace_boundary: Path,
        artifacts: Path,
        runtime_root: Path,
        model: str,
        reasoning_effort: str,
        lifecycle: str,
        workspace_write: bool,
        skill_closure: list[str],
        forbidden_surfaces: list[str],
    ) -> None:
        self.role = role
        self.workspace = workspace
        self.workspace_boundary = workspace_boundary
        self.artifacts = artifacts
        self.runtime_root = runtime_root
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.lifecycle = lifecycle
        self.workspace_write = workspace_write
        self.skill_closure = skill_closure
        self.forbidden_surfaces = forbidden_surfaces
        self.session_id: str | None = None
        self.turn = 0
        self.home = runtime_root / "home"
        self.codex_home = runtime_root / "codex-home"
        self.tmpdir = runtime_root / "tmp"
        self.home.mkdir(parents=True)
        self.codex_home.mkdir(parents=True)
        self.tmpdir.mkdir(parents=True)
        self.host_home = Path.home().resolve()
        self._copy_host_auth()

    def _copy_host_auth(self) -> None:
        """Copy only the host auth token into the disposable session home."""
        configured = os.environ.get("CODEX_HOME")
        host_codex_home = (
            Path(configured).expanduser() if configured else Path.home() / ".codex"
        )
        auth = host_codex_home / "auth.json"
        if not auth.is_file():
            raise PilotError(f"Codex authentication is unavailable at {auth}")
        destination = self.codex_home / "auth.json"
        shutil.copyfile(auth, destination)
        destination.chmod(0o600)

    def _environment(self) -> dict[str, str]:
        """Expose only execution essentials and configured transport variables."""
        allowed = {
            "PATH",
            "LANG",
            "LC_ALL",
            "TERM",
            "TMPDIR",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "no_proxy",
        }
        environment = {
            key: value for key, value in os.environ.items() if key in allowed
        }
        environment.update(
            {
                "HOME": str(self.home),
                "CODEX_HOME": str(self.codex_home),
                "CODEX_CI": "1",
                "TMPDIR": str(self.tmpdir),
            }
        )
        return environment

    def _sanitize(self, text: str) -> str:
        """Remove disposable and host absolute roots from durable evidence."""
        replacements = {
            str(self.runtime_root): "$ROLE_RUNTIME",
            str(self.workspace): "$ROLE_WORKSPACE",
            str(Path.home()): "$HOST_HOME",
        }
        for source, destination in replacements.items():
            text = text.replace(source, destination)
        return text

    def invoke(
        self,
        *,
        manifest_id: str,
        instructions: str,
        envelope: str,
        output_schema: Path,
        role_override: str | None = None,
    ) -> dict[str, Any]:
        """Invoke or resume the session after sealing the exact request context."""
        self.turn += 1
        effective_role = role_override or self.role
        last_message = self.runtime_root / f"last-message-{self.turn:02d}.json"
        runtime_schema = self.runtime_root / f"output-schema-{self.turn:02d}.json"
        shutil.copyfile(output_schema, runtime_schema)
        environment = self._environment()
        codex_executable = shutil.which("codex", path=environment.get("PATH"))
        if codex_executable is None:
            raise PilotError("Codex CLI is unavailable in the sealed PATH")
        common = [
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--disable",
            "memories",
            "--disable",
            "plugins",
            "--disable",
            "apps",
            "-m",
            self.model,
            "-c",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "-c",
            'approval_policy="never"',
            "-c",
            'sandbox_mode="danger-full-access"',
            "--output-schema",
            str(runtime_schema),
            "--json",
            "-o",
            str(last_message),
        ]
        if self.session_id is None:
            command = [
                codex_executable,
                "exec",
                *common,
                "-s",
                "danger-full-access",
                "-C",
                str(self.workspace),
                "-",
            ]
        else:
            command = [
                codex_executable,
                "exec",
                "resume",
                *common,
                self.session_id,
                "-",
            ]
        manifest = create_role_context_manifest(
            manifest_id=manifest_id,
            role=effective_role,
            lifecycle=self.lifecycle,
            cwd=self.workspace,
            instructions=instructions,
            envelope=envelope,
            output_schema=output_schema,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            skill_closure=self.skill_closure,
            workspace_write=self.workspace_write,
            forbidden_surfaces=self.forbidden_surfaces,
            command=command,
            environment=environment,
            runtime_root=self.runtime_root,
            artifacts=self.artifacts,
            host_home=self.host_home,
        )
        invocation_dir = self.artifacts / "contexts" / manifest_id
        expected = invocation_dir / "expected.json"
        write_json(expected, manifest)
        validate_schema(
            expected, EXPERIMENT_ROOT / "schemas/role-context-manifest.schema.json"
        )
        verify_role_context(manifest, self.workspace, envelope)
        (invocation_dir / "input-envelope.txt").write_text(envelope, encoding="utf-8")
        result = run_confined_subprocess(
            manifest_id=manifest_id,
            command=command,
            workspace=self.workspace,
            workspace_boundary=self.workspace_boundary,
            artifacts=self.artifacts,
            runtime_root=self.runtime_root,
            host_home=self.host_home,
            environment=environment,
            envelope=envelope,
            actual_path=invocation_dir / "actual.json",
            workspace_write=self.workspace_write,
        )
        actual = load_json(invocation_dir / "actual.json")
        validate_schema(
            invocation_dir / "actual.json",
            EXPERIMENT_ROOT / "schemas/role-context-attestation.schema.json",
        )
        verify_context_attestation(manifest, actual, envelope)
        sanitized_stdout = self._sanitize(result.stdout)
        sanitized_stderr = self._sanitize(result.stderr)
        (invocation_dir / "events.jsonl").write_text(sanitized_stdout, encoding="utf-8")
        (invocation_dir / "stderr.txt").write_text(sanitized_stderr, encoding="utf-8")
        if result.returncode:
            detail = sanitized_stderr.strip() or sanitized_stdout[-2000:].strip()
            raise PilotError(
                f"real Codex {manifest_id} failed with exit {result.returncode}: "
                f"{detail[-2000:]}"
            )

        events: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise PilotError(
                    f"invalid Codex JSONL event for {manifest_id}"
                ) from error
            if isinstance(event, dict):
                events.append(event)
        if self.session_id is None:
            started = next(
                (event for event in events if event.get("type") == "thread.started"),
                None,
            )
            if not started or not isinstance(started.get("thread_id"), str):
                raise PilotError(f"Codex session id missing for {manifest_id}")
            self.session_id = started["thread_id"]
        if not last_message.is_file():
            raise PilotError(f"Codex structured output missing for {manifest_id}")
        output = load_json(last_message)
        durable_output = invocation_dir / "output.json"
        write_json(durable_output, output)
        validate_schema(durable_output, output_schema)
        write_json(
            invocation_dir / "invocation-receipt.json",
            {
                "schema_version": "1.0",
                "manifest_id": manifest_id,
                "formal_eligible": False,
                "real_codex_cli": True,
                "session_id": self.session_id,
                "turn": self.turn,
                "exit_code": result.returncode,
                "event_count": len(events),
                "output_sha256": sha256_bytes(canonical_json_bytes(output)),
                "temporary_auth_copy_retained": False,
            },
        )
        return output


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
    validate_schema_value(load_json(instance_path), schema_path, str(instance_path))


def validate_schema_value(
    instance: dict[str, Any], schema_path: Path, label: str = "JSON object"
) -> None:
    """Validate an already-loaded JSON object against a versioned schema."""
    repository_root = EXPERIMENT_ROOT.parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from evals.spec_design_alignment.validate_dataset import SchemaSubsetValidator

    errors = SchemaSubsetValidator(load_json(schema_path)).errors(instance)
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise PilotError(f"schema validation failed for {label}:\n{joined}")


def require_empty_destination(path: Path, label: str) -> None:
    """Refuse ambiguous or destructive output destinations."""
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise PilotError(f"{label} must be absent or an empty directory: {path}")


def ensure_distinct_roots(workspace: Path, artifacts: Path) -> None:
    """Keep disposable workspaces and durable artifacts outside one another."""
    workspace = workspace.resolve(strict=False)
    artifacts = artifacts.resolve(strict=False)
    if (
        workspace == artifacts
        or workspace in artifacts.parents
        or artifacts in workspace.parents
    ):
        raise PilotError("workspace and artifacts must be distinct sibling roots")


def visible_file_manifest(root: Path) -> list[dict[str, str]]:
    """List ordinary role-visible files, excluding Git metadata."""
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or path.is_symlink()
            or ".git" in relative.parts
            or CANDIDATE_GIT_METADATA in relative.parts
        ):
            continue
        entries.append({"path": relative.as_posix(), "sha256": sha256_file(path)})
    return entries


def normalized_execution_argv(
    command: list[str],
    *,
    workspace: Path,
    runtime_root: Path,
    artifacts: Path,
    host_home: Path,
) -> list[str]:
    """Replace machine-specific execution roots with sealed semantic labels."""
    replacements = (
        (str(workspace), "$ROLE_WORKSPACE"),
        (str(runtime_root), "$ROLE_RUNTIME"),
        (str(artifacts), "$ARTIFACTS_ROOT"),
        (str(host_home), "$HOST_HOME"),
    )
    normalized: list[str] = []
    for value in command:
        for source, label in replacements:
            value = value.replace(source, label)
        normalized.append(value)
    return normalized


def run_confined_subprocess(
    *,
    manifest_id: str,
    command: list[str],
    workspace: Path,
    workspace_boundary: Path,
    artifacts: Path,
    runtime_root: Path,
    host_home: Path,
    environment: dict[str, str],
    envelope: str,
    actual_path: Path,
    workspace_write: bool,
) -> subprocess.CompletedProcess[str]:
    """Run one role through the independent macOS confinement wrapper."""
    try:
        return sandbox_wrapper.execute_confined(
            manifest_id=manifest_id,
            command=command,
            workspace=workspace,
            workspace_boundary=workspace_boundary,
            artifacts=artifacts,
            runtime_root=runtime_root,
            host_home=host_home,
            environment=environment,
            envelope=envelope,
            actual_path=actual_path,
            workspace_write=workspace_write,
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise PilotError(
            f"role confinement failed for {manifest_id}: {error}"
        ) from error


def create_role_context_manifest(
    *,
    manifest_id: str,
    role: str,
    lifecycle: str,
    cwd: Path,
    instructions: str,
    envelope: str,
    output_schema: Path,
    model: str,
    reasoning_effort: str,
    skill_closure: list[str],
    workspace_write: bool,
    forbidden_surfaces: list[str],
    command: list[str] | None = None,
    environment: dict[str, str] | None = None,
    runtime_root: Path | None = None,
    artifacts: Path | None = None,
    host_home: Path | None = None,
) -> dict[str, Any]:
    """Bind one real Codex invocation to its complete visible context."""
    runtime_root = runtime_root or cwd / ".runtime"
    artifacts = artifacts or cwd / ".artifacts"
    host_home = host_home or Path.home()
    command = command or ["codex", "exec"]
    environment = environment or {
        "HOME": str(runtime_root / "home"),
        "CODEX_HOME": str(runtime_root / "codex-home"),
        "TMPDIR": str(runtime_root / "tmp"),
    }
    return {
        "schema_version": "1.0",
        "manifest_id": manifest_id,
        "role": role,
        "formal_eligible": False,
        "lifecycle": lifecycle,
        "cwd": "workspace",
        "model": model,
        "reasoning_effort": reasoning_effort,
        "instructions_sha256": sha256_bytes(instructions.encode("utf-8")),
        "input_envelope_sha256": sha256_bytes(envelope.encode("utf-8")),
        "output_schema_sha256": sha256_file(output_schema),
        "visible_files": visible_file_manifest(cwd),
        "skill_closure": skill_closure,
        "readable_roots": ROLE_READABLE_ROOTS,
        "execution": {
            "cwd": "workspace",
            "resolved_argv": normalized_execution_argv(
                command,
                workspace=cwd,
                runtime_root=runtime_root,
                artifacts=artifacts,
                host_home=host_home,
            ),
            "environment_policy": {
                "keys": sorted(environment),
                "home": "role_runtime/home",
                "codex_home": "role_runtime/codex-home",
                "tmpdir": "role_runtime/tmp",
            },
        },
        "tools": {
            "shell": True,
            "workspace_write": workspace_write,
            "network": False,
        },
        "isolation": {
            "home": "temporary_isolated",
            "codex_home": "temporary_isolated",
            "ignore_user_config": True,
            "filesystem_read": "macos_sandbox_exec_seatbelt",
        },
        "forbidden_surfaces": forbidden_surfaces,
    }


def verify_role_context(
    manifest: dict[str, Any], cwd: Path, envelope: str
) -> dict[str, Any]:
    """Recompute the role context and reject any pre-call or post-call drift."""
    visible_files = visible_file_manifest(cwd)
    if visible_files != manifest["visible_files"]:
        raise PilotError(f"visible-file manifest drift for {manifest['manifest_id']}")
    envelope_sha256 = sha256_bytes(envelope.encode("utf-8"))
    if envelope_sha256 != manifest["input_envelope_sha256"]:
        raise PilotError(f"input envelope drift for {manifest['manifest_id']}")
    return {
        "manifest_id": manifest["manifest_id"],
        "visible_files": visible_files,
        "input_envelope_sha256": envelope_sha256,
    }


def verify_context_attestation(
    manifest: dict[str, Any], actual: dict[str, Any], envelope: str
) -> None:
    """Compare independently observed execution facts with the sealed expectation."""
    manifest_id = manifest["manifest_id"]
    expected = {
        "manifest_id": manifest_id,
        "cwd": manifest["execution"]["cwd"],
        "resolved_argv": manifest["execution"]["resolved_argv"],
        "environment_policy": manifest["execution"]["environment_policy"],
        "readable_roots": manifest["readable_roots"],
        "initial_visible_files": manifest["visible_files"],
        "input_envelope_sha256": manifest["input_envelope_sha256"],
        "tools": manifest["tools"],
    }
    observed = {
        key: actual[key]
        for key in (
            "manifest_id",
            "cwd",
            "resolved_argv",
            "environment_policy",
            "readable_roots",
            "initial_visible_files",
            "input_envelope_sha256",
        )
    }
    observed["tools"] = {
        key: actual["tools"][key] for key in ("shell", "workspace_write", "network")
    }
    if observed != expected:
        raise PilotError(f"actual attestation drift for {manifest_id}")
    if actual["input_envelope_sha256"] != sha256_bytes(envelope.encode("utf-8")):
        raise PilotError(f"actual attestation envelope drift for {manifest_id}")
    sandbox = actual["os_sandbox"]
    if (
        sandbox["mechanism"] != "macos_sandbox_exec_seatbelt"
        or sandbox["canary_read_blocked"] is not True
        or sandbox["tool_network_blocked"] is not True
    ):
        raise PilotError(f"actual attestation confinement failed for {manifest_id}")


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


def relocate_candidate_git_metadata(root: Path) -> None:
    """Keep parentless Git metadata writable inside Codex workspace-write."""
    source = root / ".git"
    destination = root / CANDIDATE_GIT_METADATA
    if not source.is_dir() or destination.exists():
        raise PilotError(f"candidate Git metadata cannot be relocated: {root}")
    source.rename(destination)
    info_exclude = destination / "info/exclude"
    info_exclude.parent.mkdir(parents=True, exist_ok=True)
    info_exclude.write_text(
        f"/{CANDIDATE_GIT_METADATA}/\n/.experiment/\n",
        encoding="utf-8",
    )
    source.write_text(f"gitdir: {CANDIDATE_GIT_METADATA}\n", encoding="utf-8")
    common_dir = Path(run_git(root, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = root / common_dir
    if common_dir.resolve() != destination.resolve():
        raise PilotError("candidate Git common-dir relocation failed")


def materialize_h02_base(
    repository: Path, workspace: Path, artifacts: Path, config: dict[str, Any]
) -> Path:
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


def require_clean_repository_snapshot(repository: Path) -> dict[str, Any]:
    """Bind corpus inputs to one clean tracked Git commit and tree."""
    status = run_git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise PilotError("source repository must be clean before corpus projection")
    return {
        "source_commit": run_git(repository, "rev-parse", "HEAD"),
        "source_tree": run_git(repository, "rev-parse", "HEAD^{tree}"),
        "source_cleanliness": "clean_tracked_only",
    }


def first_document_sources(
    repository: Path, source_commit: str
) -> list[tuple[str, str]]:
    """Enumerate tracked first documents from one frozen Git commit."""
    tracked = run_git(
        repository,
        "ls-tree",
        "-r",
        "--name-only",
        source_commit,
        "--",
        "docs/changes",
    ).splitlines()
    grouped: dict[tuple[str, str], list[str]] = {}
    for relative in tracked:
        parts = Path(relative).parts
        if len(parts) == 4 and parts[:2] == ("docs", "changes"):
            lifecycle = "active"
            unit_name = parts[2]
            filename = parts[3]
        elif (
            len(parts) == 5
            and parts[:2] == ("docs", "changes")
            and parts[2] in {"archive", "retired"}
        ):
            lifecycle = parts[2]
            unit_name = parts[3]
            filename = parts[4]
        else:
            continue
        if UNIT_DIR_RE.match(unit_name) is None or filename not in FIRST_DOCUMENT_NAMES:
            continue
        grouped.setdefault((lifecycle, unit_name), []).append(relative)
    sources: list[tuple[str, str]] = []
    for (lifecycle, unit_name), documents in sorted(grouped.items()):
        if len(documents) > 1:
            raise PilotError(
                "change unit has ambiguous first documents: "
                f"{unit_name} -> {sorted(documents)}"
            )
        sources.append((lifecycle, documents[0]))
    return sources


def git_file_bytes(repository: Path, source_commit: str, relative: str) -> bytes:
    """Read exact tracked bytes from a frozen Git commit."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(FRESH_GIT_ENVIRONMENT)
    result = subprocess.run(
        ["git", "show", f"{source_commit}:{relative}"],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise PilotError(f"cannot read tracked corpus source {relative}: {detail}")
    return result.stdout


def project_anonymous_corpus(
    repository: Path,
    artifacts: Path,
    config: dict[str, Any],
    source_snapshot: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project the allowed first-document corpus without exposing unit identity."""
    source_snapshot = source_snapshot or require_clean_repository_snapshot(repository)
    excluded = set(config["case_lineage_exclusions"]) | set(config["global_exclusions"])
    selected: list[tuple[str, str]] = []
    excluded_sources: list[dict[str, str]] = []
    for lifecycle, relative in first_document_sources(
        repository, source_snapshot["source_commit"]
    ):
        unit_name = Path(relative).parent.name
        content = git_file_bytes(repository, source_snapshot["source_commit"], relative)
        entry = {
            "lifecycle": lifecycle,
            "path": relative,
            "sha256": sha256_bytes(content),
        }
        if unit_name in excluded:
            excluded_sources.append(entry)
        else:
            selected.append((lifecycle, relative))

    rng = random.Random(config["projection_seed"])
    rng.shuffle(selected)
    documents_root = artifacts / "corpus/documents"
    documents_root.mkdir(parents=True, exist_ok=True)
    public_entries: list[dict[str, str]] = []
    source_map: list[dict[str, str]] = []
    for index, (lifecycle, source) in enumerate(selected, start=1):
        document_id = f"doc-{index:04d}"
        source_locator = f"source-{index:04d}"
        content = git_file_bytes(repository, source_snapshot["source_commit"], source)
        destination = documents_root / f"{document_id}.txt"
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
                "source_path": source,
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
        **source_snapshot,
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
            raise PilotError(
                f"candidate projection retained forbidden path: {relative}"
            )

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
    write_json(
        artifacts / "control/repository-projection-receipt.json", projection_receipt
    )
    return neutral, candidate, projection_receipt


def render_task_memory(memory_store: dict[str, Any]) -> str:
    """Render a frozen builder store for the direct-load candidate adapter."""
    lines = [
        "# Provisional cross-fitted task memory",
        "",
        "This non-scoring pilot memory is fallible cross-case context, not owner truth.",
        "Use an entry only when it applies to the current repository evidence and task.",
        "",
    ]
    for entry in memory_store["entries"]:
        refs = ", ".join(entry["source_refs"])
        lines.extend(
            [
                f"## {entry['id']} — {entry['category']}",
                "",
                entry["content"],
                "",
                f"Applicability: {entry['applicability']}",
                f"Confidence: {entry['confidence']}",
                f"Source refs: {refs}",
                "",
            ]
        )
    return "\n".join(lines)


def prepare_candidate_arms(
    candidate_template: Path,
    arms_root: Path,
    artifacts: Path,
    memory_store: dict[str, Any],
) -> tuple[Path, Path, dict[str, Any]]:
    """Create fresh arm repositories whose only input difference is task memory."""
    baseline = arms_root / "candidate-01"
    treatment = arms_root / "candidate-02"
    if arms_root.exists():
        raise PilotError(f"candidate arms root already exists: {arms_root}")
    arms_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate_template, baseline)
    shutil.copytree(candidate_template, treatment)
    relocate_candidate_git_metadata(baseline)
    relocate_candidate_git_metadata(treatment)

    task_memory = treatment / ".experiment/task-memory.md"
    task_memory.parent.mkdir(parents=True)
    task_memory.write_text(render_task_memory(memory_store), encoding="utf-8")

    baseline_files = {
        entry["path"]: entry["sha256"] for entry in visible_file_manifest(baseline)
    }
    treatment_files = {
        entry["path"]: entry["sha256"] for entry in visible_file_manifest(treatment)
    }
    extra = set(treatment_files) - set(baseline_files)
    shared_mismatch = {
        path
        for path, digest in baseline_files.items()
        if treatment_files.get(path) != digest
    }
    only_allowed_difference = (
        extra == {".experiment/task-memory.md"} and not shared_mismatch
    )
    if not only_allowed_difference:
        raise PilotError(
            "candidate arms differ outside the registered direct-load task memory"
        )
    baseline_head = run_git(baseline, "rev-parse", "HEAD")
    treatment_head = run_git(treatment, "rev-parse", "HEAD")
    if baseline_head != treatment_head:
        raise PilotError("candidate arm repositories do not share the same base HEAD")

    receipt = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "consumption_policy": "direct_load",
        "baseline_head": baseline_head,
        "treatment_head": treatment_head,
        "memory_store_sha256": sha256_bytes(canonical_json_bytes(memory_store)),
        "task_context_sha256": sha256_file(task_memory),
        "loaded_entry_ids": [entry["id"] for entry in memory_store["entries"]],
        "only_allowed_difference": only_allowed_difference,
        "allowed_difference": ".experiment/task-memory.md",
    }
    write_json(artifacts / "memory/runtime-consumption-receipt.json", receipt)
    (artifacts / "memory/task-memory.md").write_text(
        render_task_memory(memory_store), encoding="utf-8"
    )
    return baseline, treatment, receipt


def validate_memory_provenance(
    memory_store: dict[str, Any],
    public_manifest: dict[str, Any],
    private_receipt: dict[str, Any],
    documents_root: Path,
) -> dict[str, Any]:
    """Resolve opaque builder citations without revealing lineage to the builder."""
    public_by_locator = {
        entry["source_locator"]: entry for entry in public_manifest["documents"]
    }
    private_by_locator = {
        entry["source_locator"]: entry for entry in private_receipt["source_map"]
    }
    resolved_entries: list[dict[str, Any]] = []
    for entry in memory_store["entries"]:
        resolved_refs: list[dict[str, Any]] = []
        for source_ref in entry["source_refs"]:
            match = re.fullmatch(
                r"(source-[0-9]{4}):L([1-9][0-9]*)(?:-L([1-9][0-9]*))?",
                source_ref,
            )
            if match is None:
                raise PilotError(f"invalid Memory source ref: {source_ref}")
            locator, start_text, end_text = match.groups()
            if locator not in public_by_locator or locator not in private_by_locator:
                raise PilotError(f"unknown Memory source locator: {locator}")
            document_id = public_by_locator[locator]["document_id"]
            document = documents_root / f"{document_id}.txt"
            line_count = len(document.read_text(encoding="utf-8").splitlines())
            start = int(start_text)
            end = int(end_text or start_text)
            if start > end or end > line_count:
                raise PilotError(
                    f"Memory source range exceeds {document_id}: {source_ref}"
                )
            source = private_by_locator[locator]
            resolved_refs.append(
                {
                    "opaque_ref": source_ref,
                    "source_path": source["source_path"],
                    "source_sha256": source["source_sha256"],
                }
            )
        resolved_entries.append({"memory_id": entry["id"], "refs": resolved_refs})
    return {
        "schema_version": "1.0",
        "formal_eligible": False,
        "memory_store_sha256": sha256_bytes(canonical_json_bytes(memory_store)),
        "entries": resolved_entries,
    }


def validate_memory_store_semantics(memory_store: dict[str, Any]) -> None:
    """Enforce constraints omitted from the model-compatible response schema."""
    entries = memory_store["entries"]
    if not 1 <= len(entries) <= 24:
        raise PilotError("Memory store must contain 1..24 entries")
    identifiers = [entry["id"] for entry in entries]
    if len(identifiers) != len(set(identifiers)) or any(
        re.fullmatch(r"M[0-9]{2}", identifier) is None for identifier in identifiers
    ):
        raise PilotError("Memory store identifiers are invalid or duplicated")
    for entry in entries:
        if not entry["content"].strip() or not entry["applicability"].strip():
            raise PilotError(f"Memory entry is empty: {entry['id']}")
        refs = entry["source_refs"]
        if not refs or len(refs) != len(set(refs)):
            raise PilotError(
                f"Memory entry refs are empty or duplicated: {entry['id']}"
            )


def build_memory(
    *,
    artifacts: Path,
    workspace_root: Path,
    runtime_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run the task-blind Memory builder exactly once."""
    workspace = workspace_root / "memory-builder"
    workspace.mkdir(parents=True, exist_ok=True)
    instructions = (EXPERIMENT_ROOT / "prompts/memory-builder.md").read_text(
        encoding="utf-8"
    )
    (workspace / "AGENTS.md").write_text(instructions, encoding="utf-8")
    shutil.copyfile(
        EXPERIMENT_ROOT / "pilot/h02/scheme-v0.json", workspace / "scheme.json"
    )
    shutil.copyfile(
        artifacts / "corpus/public-manifest.json", workspace / "corpus-manifest.json"
    )
    shutil.copytree(artifacts / "corpus/documents", workspace / "documents")
    envelope = (
        "<builder_input>\n"
        "Read scheme.json, corpus-manifest.json, and every file in documents/. "
        "Build the single provisional Memory store.\n"
        "</builder_input>"
    )
    session = CodexSession(
        role="memory_builder",
        workspace=workspace,
        workspace_boundary=workspace_root.parent,
        artifacts=artifacts,
        runtime_root=runtime_root / "memory-builder",
        model=config["model"],
        reasoning_effort=config["reasoning_effort"],
        lifecycle="ephemeral",
        workspace_write=True,
        skill_closure=[],
        forbidden_surfaces=[
            "held-out case identity",
            "lineage exclusions",
            "target brief or repository",
            "private truth or rubric",
        ],
    )
    output_schema = EXPERIMENT_ROOT / "schemas/memory-store.schema.json"
    memory_store = session.invoke(
        manifest_id="memory-builder-01",
        instructions=instructions,
        envelope=envelope,
        output_schema=output_schema,
    )
    validate_memory_store_semantics(memory_store)
    write_json(artifacts / "memory/store.json", memory_store)
    public_manifest = load_json(artifacts / "corpus/public-manifest.json")
    private_receipt = load_json(artifacts / "control/corpus-projection-receipt.json")
    provenance = validate_memory_provenance(
        memory_store,
        public_manifest,
        private_receipt,
        artifacts / "corpus/documents",
    )
    write_json(artifacts / "memory/provenance.json", provenance)
    build_receipt = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "real_codex_cli": True,
        "builder_invocations": 1,
        "scheme_sha256": sha256_file(workspace / "scheme.json"),
        "corpus_manifest_sha256": sha256_file(workspace / "corpus-manifest.json"),
        "visible_files": visible_file_manifest(workspace),
        "memory_store_sha256": sha256_bytes(canonical_json_bytes(memory_store)),
        "provenance_sha256": sha256_bytes(canonical_json_bytes(provenance)),
    }
    write_json(artifacts / "memory/build-receipt.json", build_receipt)
    return memory_store


def prepare_owner_workspace(workspace: Path, brief: str) -> str:
    """Materialize the Simulator-safe, provisional Owner context only."""
    workspace.mkdir(parents=True, exist_ok=True)
    instructions = (EXPERIMENT_ROOT / "prompts/owner-simulator.md").read_text(
        encoding="utf-8"
    )
    (workspace / "AGENTS.md").write_text(instructions, encoding="utf-8")
    shutil.copyfile(
        EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json",
        workspace / "owner-context.provisional.json",
    )
    (workspace / "public-brief.md").write_text(brief, encoding="utf-8")
    return instructions


def owner_context_ids(owner_context: dict[str, Any]) -> set[str]:
    """Return the unique atom IDs loaded into one Owner context."""
    identifiers = [atom["id"] for atom in owner_context["atoms"]]
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise PilotError("Owner context atom IDs are empty or duplicated")
    return set(identifiers)


def validate_owner_context_refs(
    references: list[str], owner_context: dict[str, Any], label: str
) -> None:
    """Reject duplicate or unknown Owner-context references."""
    if len(references) != len(set(references)):
        raise PilotError(f"{label} contains duplicate owner context refs")
    unknown = set(references) - owner_context_ids(owner_context)
    if unknown:
        raise PilotError(
            f"{label} contains unknown owner context ref: {sorted(unknown)}"
        )


def candidate_first_document(repository: Path, declared_path: str) -> Path:
    """Resolve and minimally structure-check a Candidate Gate 1 artifact."""
    if not declared_path or Path(declared_path).is_absolute():
        raise PilotError(f"Candidate returned invalid first_doc_path: {declared_path}")
    declared = repository / declared_path
    if declared.is_symlink():
        raise PilotError(f"Candidate first document is a symlink: {declared_path}")
    candidate = declared.resolve()
    try:
        relative = candidate.relative_to(repository.resolve())
    except ValueError as error:
        raise PilotError(
            f"Candidate first_doc_path escapes repository: {declared_path}"
        ) from error
    if (
        len(relative.parts) != 4
        or relative.parts[:2] != ("docs", "changes")
        or relative.name not in FIRST_DOCUMENT_NAMES
        or not candidate.is_file()
    ):
        raise PilotError(
            f"Candidate did not produce one active first document: {declared_path}"
        )
    content = candidate.read_text(encoding="utf-8")
    required_markers = ("原始需求", "用户场景", "验收标准", "范围")
    if any(marker not in content for marker in required_markers):
        raise PilotError(
            f"Candidate first document is structurally incomplete: {declared_path}"
        )
    return candidate


def workspace_symlinks(repository: Path) -> list[str]:
    """List symlinks outside relocated Git metadata without following them."""
    links: list[str] = []
    for current, directories, files in os.walk(repository, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name for name in directories if name not in {".git", CANDIDATE_GIT_METADATA}
        ]
        for name in [*directories, *files]:
            path = current_path / name
            if path.is_symlink():
                links.append(path.relative_to(repository).as_posix())
    return sorted(set(links))


def validate_gate1_repository(
    repository: Path,
    initial_files: list[dict[str, str]],
    first_doc_path: str,
    base_head: str,
) -> None:
    """Require a clean Gate 1 repo with exactly one new ordinary first document."""
    status = run_git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise PilotError(f"Candidate Gate 1 repository is not clean: {status}")
    changed_paths = run_git(repository, "diff", "--name-only", base_head).splitlines()
    if changed_paths != [first_doc_path]:
        raise PilotError(
            f"Candidate changed files outside its first document: {changed_paths}"
        )
    links = workspace_symlinks(repository)
    if links:
        raise PilotError(f"Candidate Gate 1 repository contains a symlink: {links}")
    before = {entry["path"]: entry["sha256"] for entry in initial_files}
    after = {
        entry["path"]: entry["sha256"] for entry in visible_file_manifest(repository)
    }
    if set(after) - set(before) != {first_doc_path}:
        raise PilotError(
            "Candidate Gate 1 repository contains an extra workspace entry"
        )
    if set(before) - set(after) or any(
        after[path] != digest for path, digest in before.items()
    ):
        raise PilotError("Candidate Gate 1 repository changed a frozen input file")


def run_candidate_arm(
    *,
    arm: str,
    repository: Path,
    artifacts: Path,
    workspace_root: Path,
    runtime_root: Path,
    config: dict[str, Any],
    brief: str,
    memory_store: dict[str, Any],
) -> dict[str, Any]:
    """Run one persistent Candidate and its independent persistent Owner session."""
    candidate_instructions = (EXPERIMENT_ROOT / "prompts/candidate-task.md").read_text(
        encoding="utf-8"
    )
    candidate = CodexSession(
        role="candidate",
        workspace=repository,
        workspace_boundary=workspace_root.parent,
        artifacts=artifacts,
        runtime_root=runtime_root / f"candidate-{arm}",
        model=config["model"],
        reasoning_effort=config["reasoning_effort"],
        lifecycle="persistent",
        workspace_write=True,
        skill_closure=[".agents/skills/change-spec-author/SKILL.md"],
        forbidden_surfaces=[
            "other arm",
            "private truth or rubric",
            "owner context",
            "parent repository history",
            "design or implementation phase",
        ],
    )
    owner_workspace = workspace_root / ("owner-01" if arm == "baseline" else "owner-02")
    owner_instructions = prepare_owner_workspace(owner_workspace, brief)
    owner_context = load_json(
        EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json"
    )
    owner = CodexSession(
        role="owner_simulator",
        workspace=owner_workspace,
        workspace_boundary=workspace_root.parent,
        artifacts=artifacts,
        runtime_root=runtime_root / f"owner-{arm}",
        model=config["model"],
        reasoning_effort=config["reasoning_effort"],
        lifecycle="persistent",
        workspace_write=False,
        skill_closure=[],
        forbidden_surfaces=[
            "arm identity or Memory",
            "other run",
            "judge truth or rubric",
            "parent repository or host history",
        ],
    )
    initial_candidate_files = visible_file_manifest(repository)
    candidate_turn_schema = EXPERIMENT_ROOT / "schemas/candidate-turn.schema.json"
    owner_reply_schema = EXPERIMENT_ROOT / "schemas/owner-reply.schema.json"
    owner.invoke(
        manifest_id=f"owner-{arm}-init",
        instructions=owner_instructions,
        envelope=(
            "<owner_session_initialization>Read the immutable role instructions, "
            "public brief, and provisional owner context. Return only the ready "
            "object; do not disclose any atom.</owner_session_initialization>"
        ),
        output_schema=EXPERIMENT_ROOT / "schemas/owner-ready.schema.json",
    )
    candidate_envelope = (
        f"{candidate_instructions}\n\n<public_brief>\n{brief.rstrip()}\n</public_brief>"
    )
    transcript: list[dict[str, Any]] = []
    gate_output: dict[str, Any] | None = None
    for turn in range(1, config["max_candidate_turns"] + 1):
        candidate_output = candidate.invoke(
            manifest_id=f"candidate-{arm}-{turn:02d}",
            instructions=candidate_instructions,
            envelope=candidate_envelope,
            output_schema=candidate_turn_schema,
        )
        transcript.append(
            {"actor": "candidate", "turn": turn, "output": candidate_output}
        )
        status = candidate_output["status"]
        if status == "gate1_complete":
            if candidate_output["owner_message"]:
                raise PilotError(
                    f"{arm} Candidate completed with a nonempty owner_message"
                )
            gate_output = candidate_output
            break
        if status == "blocked":
            raise PilotError(f"{arm} Candidate reported blocked")
        question = candidate_output["owner_message"].strip()
        if not question or candidate_output["first_doc_path"]:
            raise PilotError(f"{arm} Candidate returned malformed needs_owner output")
        owner_envelope = (
            "<owner_turn>\n"
            "Answer only this quoted Candidate message.\n"
            f"<candidate_message>{json.dumps(question, ensure_ascii=False)}</candidate_message>\n"
            "</owner_turn>"
        )
        owner_output = owner.invoke(
            manifest_id=f"owner-{arm}-{turn:02d}",
            instructions=owner_instructions,
            envelope=owner_envelope,
            output_schema=owner_reply_schema,
        )
        if not owner_output["reply"].strip():
            raise PilotError(f"{arm} Owner returned an invalid open answer")
        validate_owner_context_refs(
            owner_output["used_context_refs"], owner_context, f"{arm} Owner reply"
        )
        transcript.append({"actor": "owner", "turn": turn, "output": owner_output})
        if owner_output["status"] == "needs_real_owner":
            raise PilotError(f"{arm} provisional Owner context needs real owner")
        candidate_envelope = (
            "<owner_reply>\n"
            f"{json.dumps(owner_output, ensure_ascii=False, sort_keys=True)}\n"
            "</owner_reply>\n"
            "Continue the same Gate 1 workflow and return only the structured turn status."
        )
    if gate_output is None:
        raise PilotError(f"{arm} Candidate exceeded the frozen turn limit")
    first_document = candidate_first_document(repository, gate_output["first_doc_path"])
    frozen_content = first_document.read_bytes()
    frozen_head = run_git(repository, "rev-parse", "HEAD")
    frozen_status = run_git(repository, "status", "--porcelain")
    base_head = load_json(artifacts / "memory/runtime-consumption-receipt.json")[
        f"{arm}_head"
    ]
    validate_gate1_repository(
        repository,
        initial_candidate_files,
        gate_output["first_doc_path"],
        base_head,
    )
    run_root = artifacts / "runs" / arm
    run_root.mkdir(parents=True)
    shutil.copyfile(first_document, run_root / "first-document.md")
    (run_root / "first-document.patch").write_text(
        run_git(
            repository,
            "diff",
            "--no-ext-diff",
            base_head,
            "--",
            gate_output["first_doc_path"],
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        run_root / "transcript.json", {"formal_eligible": False, "turns": transcript}
    )

    trace_instructions = (EXPERIMENT_ROOT / "prompts/memory-trace.md").read_text(
        encoding="utf-8"
    )
    trace_entries = memory_store["entries"] if arm == "treatment" else []
    before_trace = visible_file_manifest(repository)
    trace_envelope = (
        f"{trace_instructions}\n\n"
        "<memory_entries>\n"
        f"{json.dumps(trace_entries, ensure_ascii=False, sort_keys=True)}\n"
        "</memory_entries>"
    )
    trace = candidate.invoke(
        manifest_id=f"memory-trace-{arm}-01",
        instructions=trace_instructions,
        envelope=trace_envelope,
        output_schema=EXPERIMENT_ROOT / "schemas/memory-trace.schema.json",
        role_override="memory_trace",
    )
    if visible_file_manifest(repository) != before_trace:
        raise PilotError(f"{arm} Candidate edited files after first-document freeze")
    if first_document.read_bytes() != frozen_content:
        raise PilotError(f"{arm} frozen first document changed during trace")
    trace_ids = [event["memory_id"] for event in trace["events"]]
    expected_ids = [entry["id"] for entry in trace_entries]
    if sorted(trace_ids) != sorted(expected_ids) or len(trace_ids) != len(
        set(trace_ids)
    ):
        raise PilotError(
            f"{arm} Memory trace does not cover the direct-load store exactly"
        )
    write_json(run_root / "memory-trace.json", trace)
    receipt = {
        "schema_version": "1.0",
        "run_id": f"H02-{arm}-r1",
        "arm": arm,
        "formal_eligible": False,
        "real_candidate_session": True,
        "real_owner_session": owner.session_id is not None,
        "candidate_session_id": candidate.session_id,
        "owner_session_id": owner.session_id,
        "candidate_turns": len(
            [entry for entry in transcript if entry["actor"] == "candidate"]
        ),
        "owner_turns": len(
            [entry for entry in transcript if entry["actor"] == "owner"]
        ),
        "first_doc_path": gate_output["first_doc_path"],
        "first_doc_sha256": sha256_bytes(frozen_content),
        "frozen_head": frozen_head,
        "frozen_status": frozen_status,
        "memory_trace_sha256": sha256_bytes(canonical_json_bytes(trace)),
    }
    write_json(run_root / "run-receipt.json", receipt)
    return receipt


def project_conclusions(first_document: str) -> str:
    """Remove raw request and clarification sections without semantic rewriting."""
    hidden_titles = {
        "原始需求",
        "原始报告",
        "澄清记录",
        "original request",
        "clarifications",
    }
    output: list[str] = []
    hidden_level: int | None = None
    for line in first_document.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip().lower()
            if level == 2 and title in hidden_titles:
                hidden_level = level
                continue
            if hidden_level is not None and level <= hidden_level:
                hidden_level = None
        if hidden_level is None:
            output.append(line)
    return "\n".join(output).strip() + "\n"


def verify_next_scheme(proposal: dict[str, Any], forbidden_atoms: list[str]) -> None:
    """Reject a generated scheme that embeds a held-out case-specific atom."""
    if proposal["forbidden_case_specific_atoms"] != forbidden_atoms:
        raise PilotError("next scheme changed the frozen forbidden-atom list")
    if (
        not proposal["scheme_id"].strip()
        or not proposal["build_policy"].strip()
        or not proposal["consumption_policy"].strip()
        or not proposal["hypothesis"].strip()
        or not proposal["delta"]
        or any(not item.strip() for item in proposal["delta"])
    ):
        raise PilotError("next scheme contains an empty required proposal field")
    searchable = (
        canonical_json_bytes(
            {
                key: value
                for key, value in proposal.items()
                if key != "forbidden_case_specific_atoms"
            }
        )
        .decode("utf-8")
        .lower()
    )
    for atom in forbidden_atoms:
        if atom.lower() in searchable:
            raise PilotError(f"next scheme contains case-specific atom: {atom}")


def transcript_pairs(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    """Project a run transcript to anonymous Candidate question/Owner reply pairs."""
    pairs: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for turn in transcript["turns"]:
        if turn["actor"] == "candidate" and turn["output"]["status"] == "needs_owner":
            pending = {
                "question_index": len(pairs) + 1,
                "candidate_question": turn["output"]["owner_message"],
            }
        elif turn["actor"] == "owner" and pending is not None:
            pending.update(
                {
                    "owner_reply": turn["output"]["reply"],
                    "used_context_refs": turn["output"]["used_context_refs"],
                    "owner_status": turn["output"]["status"],
                }
            )
            pairs.append(pending)
            pending = None
    if pending is not None:
        raise PilotError("Candidate transcript ends with an unanswered question")
    return pairs


def invoke_ephemeral_role(
    *,
    role: str,
    manifest_id: str,
    instructions_path: Path,
    output_schema: Path,
    files: dict[str, bytes | str | dict[str, Any] | list[Any]],
    envelope: str,
    workspace: Path,
    artifacts: Path,
    runtime_root: Path,
    config: dict[str, Any],
    forbidden_surfaces: list[str],
    workspace_write: bool = False,
) -> dict[str, Any]:
    """Materialize and invoke one immutable, single-use role workspace."""
    workspace.mkdir(parents=True, exist_ok=True)
    instructions = instructions_path.read_text(encoding="utf-8")
    (workspace / "AGENTS.md").write_text(instructions, encoding="utf-8")
    for relative, value in files.items():
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            destination.write_bytes(value)
        elif isinstance(value, str):
            destination.write_text(value, encoding="utf-8")
        else:
            write_json(destination, value)
    session = CodexSession(
        role=role,
        workspace=workspace,
        workspace_boundary=workspace.parent.parent,
        artifacts=artifacts,
        runtime_root=runtime_root,
        model=config["model"],
        reasoning_effort=config["reasoning_effort"],
        lifecycle="ephemeral",
        workspace_write=workspace_write,
        skill_closure=[],
        forbidden_surfaces=forbidden_surfaces,
    )
    before = visible_file_manifest(workspace)
    output = session.invoke(
        manifest_id=manifest_id,
        instructions=instructions,
        envelope=envelope,
        output_schema=output_schema,
    )
    if visible_file_manifest(workspace) != before:
        raise PilotError(f"immutable role edited its workspace: {manifest_id}")
    return output


def prepare_anonymous_evaluation_inputs(
    artifacts: Path, config: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any]]:
    """Freeze randomized transcript/projection identities before judging."""
    rng = random.Random(config["projection_seed"] + ":evaluation")
    arms = ["baseline", "treatment"]
    rng.shuffle(arms)
    mapping = {f"T{index}": arm for index, arm in enumerate(arms, start=1)}
    projection_mapping = {
        f"P{index}": arm for index, arm in enumerate(reversed(arms), start=1)
    }
    anonymous: dict[str, Any] = {"transcripts": {}, "projections": {}}
    evaluation_root = artifacts / "evaluation"
    for transcript_id, arm in mapping.items():
        transcript = load_json(artifacts / f"runs/{arm}/transcript.json")
        pairs = transcript_pairs(transcript)
        anonymous["transcripts"][transcript_id] = {
            "formal_eligible": False,
            "transcript_id": transcript_id,
            "pairs": pairs,
        }
        write_json(
            evaluation_root / f"anonymous-transcript-{transcript_id}.json",
            anonymous["transcripts"][transcript_id],
        )
    for projection_id, arm in projection_mapping.items():
        source = (artifacts / f"runs/{arm}/first-document.md").read_text(
            encoding="utf-8"
        )
        projected = project_conclusions(source)
        if not projected.strip():
            raise PilotError(f"empty conclusion projection for {projection_id}")
        anonymous["projections"][projection_id] = projected
        (evaluation_root / f"conclusion-{projection_id}.md").write_text(
            projected, encoding="utf-8"
        )
    receipt = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "transcript_mapping": mapping,
        "projection_mapping": projection_mapping,
        "projection_rule": "remove_level2_raw_request_and_clarification_sections_v1",
        "transcript_hashes": {
            key: sha256_bytes(canonical_json_bytes(value))
            for key, value in anonymous["transcripts"].items()
        },
        "projection_hashes": {
            key: sha256_bytes(value.encode("utf-8"))
            for key, value in anonymous["projections"].items()
        },
    }
    write_json(artifacts / "control/evaluation-identity-receipt.json", receipt)
    return mapping, anonymous


def validate_run_audit(
    audit: dict[str, Any], allowed_refs: set[str], run_id: str
) -> None:
    """Validate one run audit's identity, evidence, refs, and critical flag."""
    if audit["run_id"] != run_id:
        raise PilotError(f"run auditor returned the wrong transcript id: {run_id}")
    for finding in audit["findings"]:
        if not finding["evidence"].strip():
            raise PilotError(f"run auditor returned empty evidence: {run_id}")
        references = finding["context_refs"]
        if (
            len(references) != len(set(references))
            or not set(references) <= allowed_refs
        ):
            raise PilotError(f"run auditor returned malformed evidence: {run_id}")
    has_critical = any(
        finding["severity"] == "critical" for finding in audit["findings"]
    )
    if audit["critical_error"] is not has_critical:
        raise PilotError(f"run auditor critical flag is inconsistent: {run_id}")


def validate_blind_judgment(judgment: dict[str, Any], judge_id: str) -> None:
    """Validate exact projection and criterion identities without dict deduplication."""
    if judgment["judge_id"] != judge_id:
        raise PilotError(f"blind judge returned the wrong id: {judge_id}")
    projection_ids = [item["projection_id"] for item in judgment["assessments"]]
    if (
        len(projection_ids) != 2
        or len(projection_ids) != len(set(projection_ids))
        or set(projection_ids) != {"P1", "P2"}
    ):
        raise PilotError(f"blind judge projection ids are invalid: {judge_id}")
    expected_criteria = {f"J{index:02d}" for index in range(1, 7)}
    for item in judgment["assessments"]:
        criterion_ids = [criterion["criterion_id"] for criterion in item["criteria"]]
        if (
            len(criterion_ids) != 6
            or len(criterion_ids) != len(set(criterion_ids))
            or set(criterion_ids) != expected_criteria
        ):
            raise PilotError(f"blind judge criterion ids are invalid: {judge_id}")
    has_critical = any(item["critical_error"] for item in judgment["assessments"])
    if judgment["critical_error"] is not has_critical:
        raise PilotError(f"blind judge critical flag is inconsistent: {judge_id}")


def judgment_signature(judgment: dict[str, Any]) -> dict[str, Any]:
    """Project a validated blind judgment to its semantic comparison signature."""
    return {
        item["projection_id"]: {
            "critical_error": item["critical_error"],
            "criteria": {
                criterion["criterion_id"]: criterion["rating"]
                for criterion in item["criteria"]
            },
        }
        for item in judgment["assessments"]
    }


def run_audits_and_scoring(
    *,
    neutral_repository: Path,
    artifacts: Path,
    workspace_root: Path,
    runtime_root: Path,
    config: dict[str, Any],
    brief: str,
    memory_store: dict[str, Any],
) -> dict[str, Any]:
    """Run the complete anonymous audit, scoring, judging, and Loop matrix."""
    mapping, anonymous = prepare_anonymous_evaluation_inputs(artifacts, config)
    owner_context = load_json(
        EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json"
    )
    owner_instructions = (EXPERIMENT_ROOT / "prompts/owner-simulator.md").read_text(
        encoding="utf-8"
    )
    allowed_owner_refs = owner_context_ids(owner_context)
    audit_outputs: dict[str, Any] = {}
    burden_outputs: dict[str, Any] = {}
    for transcript_id in ("T1", "T2"):
        transcript = anonymous["transcripts"][transcript_id]
        audit = invoke_ephemeral_role(
            role="owner_run_auditor",
            manifest_id=f"run-auditor-{transcript_id}",
            instructions_path=EXPERIMENT_ROOT / "prompts/run-auditor.md",
            output_schema=EXPERIMENT_ROOT / "schemas/run-audit.schema.json",
            files={
                "public-brief.md": brief,
                "owner-context.provisional.json": owner_context,
                "owner-instructions.md": owner_instructions,
                "transcript.json": transcript,
            },
            envelope=(
                f'<audit_input transcript_id="{transcript_id}">Read the four '
                "workspace inputs and audit this one transcript.</audit_input>"
            ),
            workspace=workspace_root / f"run-auditor-{transcript_id}",
            artifacts=artifacts,
            runtime_root=runtime_root / f"run-auditor-{transcript_id}",
            config=config,
            forbidden_surfaces=[
                "arm identity or Memory",
                "Candidate spec",
                "judge truth or rubric",
                "other run",
            ],
        )
        validate_run_audit(audit, allowed_owner_refs, transcript_id)
        audit_outputs[transcript_id] = audit
        write_json(artifacts / f"evaluation/run-audit-{transcript_id}.json", audit)

        burden = invoke_ephemeral_role(
            role="burden_scorer",
            manifest_id=f"burden-{transcript_id}",
            instructions_path=EXPERIMENT_ROOT / "prompts/burden-scorer.md",
            output_schema=EXPERIMENT_ROOT / "schemas/burden.schema.json",
            files={"transcript.json": transcript},
            envelope=(
                f'<burden_input transcript_id="{transcript_id}">Read '
                "transcript.json and count semantic Owner contributions.</burden_input>"
            ),
            workspace=workspace_root / f"burden-{transcript_id}",
            artifacts=artifacts,
            runtime_root=runtime_root / f"burden-{transcript_id}",
            config=config,
            forbidden_surfaces=[
                "arm identity or Memory",
                "spec quality or rubric",
                "other transcript",
            ],
        )
        if burden["transcript_id"] != transcript_id:
            raise PilotError(
                f"burden scorer returned the wrong transcript id: {transcript_id}"
            )
        if burden["contribution_units"] < 0 or burden["contribution_units"] != len(
            burden["items"]
        ):
            raise PilotError(
                f"burden scorer returned an inconsistent ledger: {transcript_id}"
            )
        for item in burden["items"]:
            if not set(item["owner_atoms"]) <= allowed_owner_refs:
                raise PilotError(
                    f"burden scorer returned an unknown Owner atom: {transcript_id}"
                )
        burden_outputs[transcript_id] = burden
        write_json(artifacts / f"evaluation/burden-{transcript_id}.json", burden)

    batch = invoke_ephemeral_role(
        role="owner_batch_auditor",
        manifest_id="batch-auditor-01",
        instructions_path=EXPERIMENT_ROOT / "prompts/batch-auditor.md",
        output_schema=EXPERIMENT_ROOT / "schemas/batch-audit.schema.json",
        files={
            "owner-context.provisional.json": owner_context,
            "transcript-T1.json": anonymous["transcripts"]["T1"],
            "transcript-T2.json": anonymous["transcripts"]["T2"],
        },
        envelope=(
            "<batch_audit_input>Read the provisional context and both anonymous "
            "transcripts; assess only substantive consistency.</batch_audit_input>"
        ),
        workspace=workspace_root / "batch-auditor",
        artifacts=artifacts,
        runtime_root=runtime_root / "batch-auditor",
        config=config,
        forbidden_surfaces=[
            "arm identity or Memory",
            "Candidate specs",
            "quality scores",
        ],
    )
    write_json(artifacts / "evaluation/batch-audit.json", batch)

    judge_context = load_json(
        EXPERIMENT_ROOT / "pilot/h02/judge-context.provisional.json"
    )
    judge_outputs: list[dict[str, Any]] = []
    for judge_number in (1, 2):
        workspace = workspace_root / f"judge-{judge_number}"
        copy_projection(neutral_repository, workspace)
        judge = invoke_ephemeral_role(
            role="blind_quality_judge",
            manifest_id=f"blind-judge-{judge_number}",
            instructions_path=EXPERIMENT_ROOT / "prompts/blind-judge.md",
            output_schema=EXPERIMENT_ROOT / "schemas/blind-judgment.schema.json",
            files={
                ".experiment/public-brief.md": brief,
                ".experiment/judge-context.provisional.json": judge_context,
                ".experiment/conclusion-P1.md": anonymous["projections"]["P1"],
                ".experiment/conclusion-P2.md": anonymous["projections"]["P2"],
            },
            envelope=(
                f'<judge_input judge_id="J{judge_number}">Inspect the neutral '
                "repository and all four .experiment inputs. Assess P1 and P2 "
                "independently.</judge_input>"
            ),
            workspace=workspace,
            artifacts=artifacts,
            runtime_root=runtime_root / f"judge-{judge_number}",
            config=config,
            forbidden_surfaces=[
                "arm or Memory identity",
                "Candidate-Owner Q&A or burden",
                "run repository or metadata",
                "formal effect conclusion",
            ],
        )
        validate_blind_judgment(judge, f"J{judge_number}")
        judge_outputs.append(judge)
        write_json(artifacts / f"evaluation/blind-judge-{judge_number}.json", judge)

    judge_disagreement = judgment_signature(judge_outputs[0]) != judgment_signature(
        judge_outputs[1]
    )
    frozen_anonymous_results = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "quality_judgments": judge_outputs,
        "burden": burden_outputs,
        "memory_traces": {
            transcript_id: load_json(artifacts / f"runs/{arm}/memory-trace.json")
            for transcript_id, arm in mapping.items()
        },
        "cost": {
            "builder_calls": 1,
            "candidate_sessions": 2,
            "owner_sessions": 2,
            "run_audits": 2,
            "batch_audits": 1,
            "burden_scores": 2,
            "blind_judges": 2,
        },
        "failure_classification": {
            "owner_run_critical": any(
                output["critical_error"] for output in audit_outputs.values()
            ),
            "owner_batch_critical": batch["critical_error"],
            "judge_disagreement": judge_disagreement,
        },
    }
    write_json(
        artifacts / "evaluation/frozen-anonymous-results.json",
        frozen_anonymous_results,
    )
    scheme = load_json(EXPERIMENT_ROOT / "pilot/h02/scheme-v0.json")
    loop_workspace = workspace_root / "loop-experimenter"
    next_scheme = invoke_ephemeral_role(
        role="loop_experimenter",
        manifest_id="loop-experimenter-01",
        instructions_path=EXPERIMENT_ROOT / "prompts/loop-experimenter.md",
        output_schema=EXPERIMENT_ROOT / "schemas/next-scheme.schema.json",
        files={
            "previous-scheme.json": scheme,
            "anonymous-results.json": frozen_anonymous_results,
            "memory-store.json": memory_store,
        },
        envelope=(
            "<loop_input>Read the three frozen inputs and propose the next "
            "suite-global scheme. Preserve the forbidden atom list verbatim.</loop_input>"
        ),
        workspace=loop_workspace,
        artifacts=artifacts,
        runtime_root=runtime_root / "loop-experimenter",
        config=config,
        forbidden_surfaces=[
            "raw private truth or Owner answer bank",
            "case or arm identity",
            "raw Candidate-Owner transcripts",
            "unfrozen scores",
        ],
    )
    verify_next_scheme(next_scheme, scheme["forbidden_case_specific_atoms"])
    write_json(artifacts / "evaluation/next-scheme.json", next_scheme)
    return {
        "run_audits": audit_outputs,
        "batch_audit": batch,
        "burden": burden_outputs,
        "blind_judges": judge_outputs,
        "judge_disagreement": judge_disagreement,
        "next_scheme": next_scheme,
    }


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
    source_snapshot = require_clean_repository_snapshot(repository)
    host_home = Path.home().resolve()
    if workspace == host_home or host_home in workspace.parents:
        raise PilotError(
            "workspace must be outside host home for role read confinement"
        )
    ensure_distinct_roots(workspace, artifacts)
    require_empty_destination(workspace, "workspace")
    require_empty_destination(artifacts, "artifacts")
    workspace.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    (workspace / ".role-context-canary").write_text(
        "feat-532 role boundary canary; no role may read this file\n",
        encoding="utf-8",
    )

    config_path = config_path.resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise PilotError("M0 only accepts the versioned default pilot config")
    config = load_json(config_path)
    validate_schema(config_path, EXPERIMENT_ROOT / "schemas/pilot-config.schema.json")
    owner_context = EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json"
    judge_context = EXPERIMENT_ROOT / "pilot/h02/judge-context.provisional.json"
    validate_schema(
        owner_context, EXPERIMENT_ROOT / "schemas/owner-context.schema.json"
    )
    validate_schema(
        judge_context, EXPERIMENT_ROOT / "schemas/judge-context.schema.json"
    )
    if config["formal_eligible"] is not False or config["repetitions"] != 1:
        raise PilotError("M0 must remain a non-scoring 1x1 pilot")

    base = materialize_h02_base(repository, workspace, artifacts, config)
    public_corpus, private_corpus = project_anonymous_corpus(
        repository, artifacts, config, source_snapshot
    )
    neutral, candidate, projection = build_repository_projections(
        repository, base, workspace, artifacts
    )

    brief = checked_relative(SUITE_ROOT, config["public_brief"], "public brief")
    scheme = EXPERIMENT_ROOT / "pilot/h02/scheme-v0.json"
    pilot_asset_paths = (
        sorted((EXPERIMENT_ROOT / "schemas").glob("*.json"))
        + sorted((EXPERIMENT_ROOT / "prompts").glob("*.md"))
        + sorted((EXPERIMENT_ROOT / "pilot/h02").glob("*.json"))
    )
    static_inputs = {
        "config_sha256": sha256_file(config_path),
        "source_snapshot": source_snapshot,
        "owner_context_sha256": sha256_file(owner_context),
        "judge_context_sha256": sha256_file(judge_context),
        "scheme_sha256": sha256_file(scheme),
        "public_brief_sha256": sha256_file(brief),
        "runner_sha256": sha256_file(Path(__file__)),
        "sandbox_wrapper_sha256": sha256_file(EXPERIMENT_ROOT / "sandbox_wrapper.py"),
        "base_recipe_sha256": sha256_file(SUITE_ROOT / config["base_recipe"]),
        "shared_base_manifest_sha256": sha256_file(
            artifacts / "control/shared-base-manifest.json"
        ),
        "shared_base_receipt_sha256": sha256_file(
            artifacts / "control/shared-base-receipt.json"
        ),
        "role_context_schema_sha256": sha256_file(
            EXPERIMENT_ROOT / "schemas/role-context-manifest.schema.json"
        ),
        "corpus_public_manifest_sha256": sha256_bytes(
            canonical_json_bytes(public_corpus)
        ),
        "corpus_projection_receipt_sha256": sha256_bytes(
            canonical_json_bytes(private_corpus)
        ),
        "repository_projection_receipt_sha256": sha256_bytes(
            canonical_json_bytes(projection)
        ),
        "pilot_assets": {
            path.relative_to(EXPERIMENT_ROOT).as_posix(): sha256_file(path)
            for path in pilot_asset_paths
        },
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
        "codex_cli_version": subprocess.run(
            ["codex", "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
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


def check_pilot_leakage(
    artifacts: Path, config: dict[str, Any], *, persist: bool = True
) -> dict[str, Any]:
    """Mechanically verify the role projections and durable secret boundary."""
    findings: list[str] = []
    forbidden_names = {"auth.json", "config.toml", "history.jsonl", "session.sqlite3"}
    for path in artifacts.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            findings.append(f"forbidden durable file: {path.relative_to(artifacts)}")
    memory_store = load_json(artifacts / "memory/store.json")
    memory_text = canonical_json_bytes(memory_store).decode("utf-8").lower()
    scheme = load_json(EXPERIMENT_ROOT / "pilot/h02/scheme-v0.json")
    for atom in scheme["forbidden_case_specific_atoms"]:
        if atom.lower() in memory_text:
            findings.append(
                f"Memory store contains forbidden case-specific atom: {atom}"
            )

    manifests = {
        path.parent.name: load_json(path)
        for path in (artifacts / "contexts").glob("*/expected.json")
    }
    for manifest_id, manifest in manifests.items():
        context_root = artifacts / "contexts" / manifest_id
        actual = load_json(context_root / "actual.json")
        validate_schema(
            context_root / "actual.json",
            EXPERIMENT_ROOT / "schemas/role-context-attestation.schema.json",
        )
        verify_context_attestation(
            manifest,
            actual,
            (context_root / "input-envelope.txt").read_text(encoding="utf-8"),
        )
        paths = {entry["path"] for entry in manifest["visible_files"]}
        if manifest["tools"]["network"] is not False:
            findings.append(f"network enabled: {manifest_id}")
        role = manifest["role"]
        if role == "memory_builder" and any(
            path not in {"AGENTS.md", "scheme.json", "corpus-manifest.json"}
            and not path.startswith("documents/")
            for path in paths
        ):
            findings.append(f"builder visible-file closure widened: {manifest_id}")
        if role in {"candidate", "memory_trace"}:
            forbidden = (
                ".claude/",
                ".codex/",
                "evals/",
                "docs/changes/feat-510-unified-tool-approval-model/",
            )
            if any(path.startswith(forbidden) for path in paths):
                findings.append(f"Candidate retained forbidden surface: {manifest_id}")
            skill_paths = {path for path in paths if path.startswith(".agents/skills/")}
            if not skill_paths or any(
                not path.startswith(".agents/skills/change-spec-author/")
                for path in skill_paths
            ):
                findings.append(f"Candidate Skill closure drifted: {manifest_id}")
        if role == "owner_simulator" and any(
            "memory" in path.lower() or "judge" in path.lower() for path in paths
        ):
            findings.append(
                f"Owner visible surface leaked evaluation data: {manifest_id}"
            )
        if role == "blind_quality_judge" and not judge_visible_surface_is_clean(paths):
            findings.append(f"judge visible surface leaked arm signal: {manifest_id}")
        if role == "burden_scorer" and paths != {"AGENTS.md", "transcript.json"}:
            findings.append(
                f"burden scorer visible-file closure drifted: {manifest_id}"
            )
        if role == "loop_experimenter" and any(
            token in path.lower()
            for path in paths
            for token in ("owner-context", "judge-context", "transcript")
        ):
            findings.append(f"Loop experimenter saw forbidden raw input: {manifest_id}")

    baseline = manifests.get("candidate-baseline-01")
    treatment = manifests.get("candidate-treatment-01")
    if baseline is None or treatment is None:
        findings.append("missing initial Candidate manifests")
    else:
        baseline_files = {
            entry["path"]: entry["sha256"] for entry in baseline["visible_files"]
        }
        treatment_files = {
            entry["path"]: entry["sha256"] for entry in treatment["visible_files"]
        }
        extra = set(treatment_files) - set(baseline_files)
        mismatch = {
            path
            for path, digest in baseline_files.items()
            if treatment_files.get(path) != digest
        }
        if extra != {".experiment/task-memory.md"} or mismatch:
            findings.append("initial Candidate arms differ outside direct-load Memory")

    forbidden_runtime_markers = (
        b"feat-532-pilot-runtime-",
        b"/codex-home/auth.json",
        b"$ROLE_RUNTIME/auth.json",
    )
    for path in artifacts.rglob("*"):
        if path.is_file() and any(
            marker in path.read_bytes() for marker in forbidden_runtime_markers
        ):
            findings.append(
                f"durable artifact contains temporary session-home path: {path.relative_to(artifacts)}"
            )

    result = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "passed": not findings,
        "findings": findings,
        "checked_role_manifests": len(manifests),
    }
    if persist:
        write_json(artifacts / "leakage-check.json", result)
    return result


def judge_visible_surface_is_clean(paths: set[str]) -> bool:
    """Check the judge overlay without rejecting neutral product filenames."""
    forbidden_prefixes = (".agents/", ".claude/", "evals/")
    allowed_overlay = {
        ".experiment/conclusion-P1.md",
        ".experiment/conclusion-P2.md",
        ".experiment/judge-context.provisional.json",
        ".experiment/public-brief.md",
    }
    overlay = {path for path in paths if path.startswith(".experiment/")}
    return not any(path.startswith(forbidden_prefixes) for path in paths) and (
        overlay == allowed_overlay
    )


def evidence_manifest(artifacts: Path) -> dict[str, Any]:
    """Hash every durable pilot artifact except the manifest itself."""
    excluded = {"evidence-manifest.json"}
    return {
        "schema_version": "1.0",
        "formal_eligible": False,
        "files": [
            {
                "path": path.relative_to(artifacts).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in sorted(artifacts.rglob("*"))
            if path.is_file() and path.name not in excluded
        ],
    }


def semantic_pilot_result(artifacts: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the non-scoring pilot result from sealed durable evidence."""
    owner_context = load_json(
        EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json"
    )
    allowed_refs = owner_context_ids(owner_context)
    run_audits = {
        transcript_id: load_json(
            artifacts / f"evaluation/run-audit-{transcript_id}.json"
        )
        for transcript_id in ("T1", "T2")
    }
    for transcript_id, audit in run_audits.items():
        validate_run_audit(audit, allowed_refs, transcript_id)
    batch_audit = load_json(artifacts / "evaluation/batch-audit.json")
    judges = [
        load_json(artifacts / f"evaluation/blind-judge-{judge_number}.json")
        for judge_number in (1, 2)
    ]
    for judge_number, judgment in enumerate(judges, start=1):
        validate_blind_judgment(judgment, f"J{judge_number}")
    judge_disagreement = judgment_signature(judges[0]) != judgment_signature(judges[1])
    leakage = load_json(artifacts / "leakage-check.json")
    owner_critical = (
        any(output["critical_error"] for output in run_audits.values())
        or batch_audit["critical_error"]
    )
    conclusion = (
        "infrastructure_pass"
        if leakage["passed"] and not owner_critical
        else "infrastructure_fail"
    )
    return {
        "schema_version": "1.0",
        "pilot_id": config["pilot_id"],
        "case_id": config["case_id"],
        "formal_eligible": False,
        "repetitions": 1,
        "conclusion": conclusion,
        "effect_claim": None,
        "diagnostics": {
            "owner_simulator_critical_error": owner_critical,
            "judge_disagreement": judge_disagreement,
            "judge_disagreement_policy": (
                "pilot_inconclusive_no_third_call"
                if judge_disagreement
                else "not_applicable"
            ),
            "leakage_passed": leakage["passed"],
        },
        "matrix": {
            "projection": 1,
            "memory_builder": 1,
            "agentic_consumer": 0,
            "candidate_sessions": 2,
            "owner_sessions": 2,
            "run_audits": 2,
            "batch_audits": 1,
            "burden_scores": 2,
            "blind_judges": 2,
            "loop_experimenter": 1,
        },
        "setup_burden": {
            "owner_confirmed_minutes": 0,
            "note": "Provisional M0 fixtures only; formal owner setup is deferred to M1.",
        },
        "pilot_seal_sha256": sha256_file(artifacts / "pilot-seal.json"),
    }


def run_pilot(
    repository: Path,
    workspace: Path,
    artifacts: Path,
    config_path: Path,
) -> dict[str, Any]:
    """Execute the complete non-scoring 1x1 H02 pilot with real Codex roles."""
    prepared = prepare_inputs(repository, workspace, artifacts, config_path)
    config = load_json(config_path.resolve())
    brief_path = checked_relative(SUITE_ROOT, config["public_brief"], "public brief")
    brief = brief_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(
        prefix="feat-532-pilot-runtime-", dir=workspace.parent
    ) as temporary:
        runtime_root = Path(temporary)
        roles_root = workspace / "roles"
        memory_store = build_memory(
            artifacts=artifacts,
            workspace_root=roles_root,
            runtime_root=runtime_root,
            config=config,
        )
        baseline, treatment, _ = prepare_candidate_arms(
            Path(prepared["candidate_template"]),
            workspace / "candidate-arms",
            artifacts,
            memory_store,
        )
        run_candidate_arm(
            arm="baseline",
            repository=baseline,
            artifacts=artifacts,
            workspace_root=roles_root,
            runtime_root=runtime_root,
            config=config,
            brief=brief,
            memory_store=memory_store,
        )
        run_candidate_arm(
            arm="treatment",
            repository=treatment,
            artifacts=artifacts,
            workspace_root=roles_root,
            runtime_root=runtime_root,
            config=config,
            brief=brief,
            memory_store=memory_store,
        )
        run_audits_and_scoring(
            neutral_repository=Path(prepared["neutral_repository"]),
            artifacts=artifacts,
            workspace_root=roles_root,
            runtime_root=runtime_root,
            config=config,
            brief=brief,
            memory_store=memory_store,
        )

    check_pilot_leakage(artifacts, config)
    result = semantic_pilot_result(artifacts, config)
    if result["conclusion"] not in config["allowed_conclusions"]:
        raise PilotError(f"pilot emitted forbidden conclusion: {result['conclusion']}")
    write_json(artifacts / "pilot-result.json", result)
    write_json(artifacts / "evidence-manifest.json", evidence_manifest(artifacts))
    return result


def output_schema_for_manifest(manifest: dict[str, Any]) -> Path:
    """Return the frozen output schema for one durable invocation manifest."""
    role = manifest["role"]
    schema_by_role = {
        "memory_builder": "memory-store.schema.json",
        "candidate": "candidate-turn.schema.json",
        "memory_trace": "memory-trace.schema.json",
        "owner_run_auditor": "run-audit.schema.json",
        "owner_batch_auditor": "batch-audit.schema.json",
        "burden_scorer": "burden.schema.json",
        "blind_quality_judge": "blind-judgment.schema.json",
        "loop_experimenter": "next-scheme.schema.json",
    }
    if role == "owner_simulator":
        name = (
            "owner-ready.schema.json"
            if manifest["manifest_id"].endswith("-init")
            else "owner-reply.schema.json"
        )
    else:
        name = schema_by_role[role]
    return EXPERIMENT_ROOT / "schemas" / name


def replay_pilot(artifacts: Path) -> dict[str, Any]:
    """Replay all deterministic seals, schemas, identities, and leakage checks."""
    artifacts = artifacts.resolve()
    result = load_json(artifacts / "pilot-result.json")
    seal = load_json(artifacts / "pilot-seal.json")
    if result["formal_eligible"] is not False or result["effect_claim"] is not None:
        raise PilotError("pilot result crossed the non-scoring boundary")
    if result["conclusion"] not in seal["allowed_conclusions"]:
        raise PilotError("pilot result conclusion is outside the sealed vocabulary")
    if result["pilot_seal_sha256"] != sha256_file(artifacts / "pilot-seal.json"):
        raise PilotError("pilot seal hash drift")

    inputs = seal["inputs"]
    if seal["sealed_inputs_sha256"] != sha256_bytes(canonical_json_bytes(inputs)):
        raise PilotError("sealed input identity drift")
    current_assets = {
        path.relative_to(EXPERIMENT_ROOT).as_posix(): sha256_file(path)
        for path in sorted((EXPERIMENT_ROOT / "schemas").glob("*.json"))
        + sorted((EXPERIMENT_ROOT / "prompts").glob("*.md"))
        + sorted((EXPERIMENT_ROOT / "pilot/h02").glob("*.json"))
    }
    if current_assets != inputs["pilot_assets"]:
        raise PilotError("versioned pilot assets drifted from the seal")
    if sha256_file(Path(__file__)) != inputs["runner_sha256"]:
        raise PilotError("runner drifted from the pilot seal")
    if (
        sha256_file(EXPERIMENT_ROOT / "sandbox_wrapper.py")
        != inputs["sandbox_wrapper_sha256"]
    ):
        raise PilotError("sandbox wrapper drifted from the pilot seal")
    if (
        sha256_file(artifacts / "control/shared-base-manifest.json")
        != inputs["shared_base_manifest_sha256"]
    ):
        raise PilotError("shared base manifest drift")
    if (
        sha256_file(artifacts / "control/shared-base-receipt.json")
        != inputs["shared_base_receipt_sha256"]
    ):
        raise PilotError("shared base receipt drift")
    corpus_receipt = load_json(artifacts / "control/corpus-projection-receipt.json")
    observed_snapshot = {
        key: corpus_receipt[key]
        for key in ("source_commit", "source_tree", "source_cleanliness")
    }
    if observed_snapshot != inputs["source_snapshot"]:
        raise PilotError("corpus source snapshot drift")

    context_roots = sorted((artifacts / "contexts").iterdir())
    role_counts: dict[str, int] = {}
    session_ids: dict[str, set[str]] = {}
    for context_root in context_roots:
        manifest = load_json(context_root / "expected.json")
        actual = load_json(context_root / "actual.json")
        validate_schema(
            context_root / "expected.json",
            EXPERIMENT_ROOT / "schemas/role-context-manifest.schema.json",
        )
        validate_schema(
            context_root / "actual.json",
            EXPERIMENT_ROOT / "schemas/role-context-attestation.schema.json",
        )
        envelope = (context_root / "input-envelope.txt").read_text(encoding="utf-8")
        verify_context_attestation(manifest, actual, envelope)
        schema = output_schema_for_manifest(manifest)
        if manifest["output_schema_sha256"] != sha256_file(schema):
            raise PilotError(f"output schema drift: {context_root.name}")
        validate_schema(context_root / "output.json", schema)
        output = load_json(context_root / "output.json")
        if manifest["role"] == "owner_simulator" and not manifest[
            "manifest_id"
        ].endswith("-init"):
            validate_owner_context_refs(
                output["used_context_refs"],
                load_json(EXPERIMENT_ROOT / "pilot/h02/owner-context.provisional.json"),
                manifest["manifest_id"],
            )
        invocation = load_json(context_root / "invocation-receipt.json")
        if not invocation["real_codex_cli"] or invocation["exit_code"] != 0:
            raise PilotError(f"non-real or failed role receipt: {context_root.name}")
        if invocation["output_sha256"] != sha256_bytes(canonical_json_bytes(output)):
            raise PilotError(f"role output hash drift: {context_root.name}")
        role_counts[manifest["role"]] = role_counts.get(manifest["role"], 0) + 1
        session_ids.setdefault(manifest["role"], set()).add(invocation["session_id"])

    exact_counts = {
        "memory_builder": 1,
        "owner_run_auditor": 2,
        "owner_batch_auditor": 1,
        "burden_scorer": 2,
        "blind_quality_judge": 2,
        "loop_experimenter": 1,
        "memory_trace": 2,
    }
    for role, expected_count in exact_counts.items():
        if role_counts.get(role) != expected_count:
            raise PilotError(f"role invocation count drift for {role}")
    if role_counts.get("candidate", 0) < 2 or role_counts.get("owner_simulator", 0) < 2:
        raise PilotError("Candidate or Owner persistent session evidence is incomplete")
    if len(session_ids.get("candidate", set())) != 2:
        raise PilotError("Candidate sessions were not isolated per arm")
    if len(session_ids.get("owner_simulator", set())) != 2:
        raise PilotError("Owner sessions were not isolated per run")

    identity = load_json(artifacts / "control/evaluation-identity-receipt.json")
    for projection_id, arm in identity["projection_mapping"].items():
        source = (artifacts / f"runs/{arm}/first-document.md").read_text(
            encoding="utf-8"
        )
        projected = project_conclusions(source)
        if projected != (
            artifacts / f"evaluation/conclusion-{projection_id}.md"
        ).read_text(encoding="utf-8"):
            raise PilotError(f"conclusion projection drift: {projection_id}")
    task_memory = artifacts / "memory/task-memory.md"
    if (
        sha256_file(task_memory)
        != load_json(artifacts / "memory/runtime-consumption-receipt.json")[
            "task_context_sha256"
        ]
    ):
        raise PilotError("direct-load task context drift")

    next_scheme = load_json(artifacts / "evaluation/next-scheme.json")
    validate_schema_value(
        next_scheme,
        EXPERIMENT_ROOT / "schemas/next-scheme.schema.json",
        "evaluation/next-scheme.json",
    )
    verify_next_scheme(
        next_scheme,
        load_json(EXPERIMENT_ROOT / "pilot/h02/scheme-v0.json")[
            "forbidden_case_specific_atoms"
        ],
    )
    config = load_json(DEFAULT_CONFIG)
    stored_leakage = load_json(artifacts / "leakage-check.json")
    computed_leakage = check_pilot_leakage(artifacts, config, persist=False)
    if stored_leakage != computed_leakage:
        raise PilotError("leakage result drift")
    semantic_result = semantic_pilot_result(artifacts, config)
    if result != semantic_result:
        raise PilotError("semantic pilot result drift")
    expected_manifest = load_json(artifacts / "evidence-manifest.json")
    actual_manifest = evidence_manifest(artifacts)
    if expected_manifest != actual_manifest:
        raise PilotError("durable evidence manifest drift")
    return {
        "pilot_id": result["pilot_id"],
        "formal_eligible": False,
        "conclusion": result["conclusion"],
        "replay": "verified",
        "role_invocations": sum(role_counts.values()),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the pilot command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="materialize deterministic inputs")
    prepare.add_argument("--repository", required=True, type=Path)
    prepare.add_argument("--workspace", required=True, type=Path)
    prepare.add_argument("--artifacts", required=True, type=Path)
    run = subparsers.add_parser("run-pilot", help="run the complete real Codex pilot")
    run.add_argument("--repository", required=True, type=Path)
    run.add_argument("--workspace", required=True, type=Path)
    run.add_argument("--artifacts", required=True, type=Path)
    replay = subparsers.add_parser("replay", help="verify durable pilot evidence")
    replay.add_argument("--artifacts", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute one runner command and print a machine-readable summary."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "prepare":
            result = prepare_inputs(
                args.repository, args.workspace, args.artifacts, DEFAULT_CONFIG
            )
        elif args.command == "run-pilot":
            result = run_pilot(
                args.repository, args.workspace, args.artifacts, DEFAULT_CONFIG
            )
        elif args.command == "replay":
            result = replay_pilot(args.artifacts)
        else:
            raise PilotError(f"unsupported command: {args.command}")
    except (OSError, PilotError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
