#!/usr/bin/env python3
"""Validate the committed control assets for the spec/design alignment suite."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXPERIMENT_ID = "feat_397_agent_team"
EXPERIMENT_ROOT_REF = f"experiments/{EXPERIMENT_ID}"
PROTOCOL_REF = f"{EXPERIMENT_ROOT_REF}/protocol.md"
TREATMENT_LOCK_REF = f"{EXPERIMENT_ROOT_REF}/suite-treatment-lock.json"
SUITE_SEAL_REF = f"{EXPERIMENT_ROOT_REF}/suite-seal.json"
PROTOCOL_PATH = ROOT / PROTOCOL_REF
TREATMENT_LOCK_PATH = ROOT / TREATMENT_LOCK_REF
SUITE_SEAL_PATH = ROOT / SUITE_SEAL_REF
FIXED_CASE_ASSETS = {
    "case.json",
    "public/brief.md",
    "knowledge/authority-map.json",
    "judge-private/decision-inventory.json",
    "judge-private/rubric.md",
    "audit/provenance.md",
    "audit/leak-signatures.txt",
}
EXPECTED_CASE_REFS = {
    "H01": "cases/H01-feat-484-message-interactions/case.json",
    "H02": "cases/H02-feat-510-tool-approval-model/case.json",
    "H03": "cases/H03-feat-501-session-controls/case.json",
    "H04": "cases/H04-feat-519-workspace-compat-skills/case.json",
    "H05": "cases/H05-feat-515-agent-workspace-root-selection/case.json",
    "H07": "cases/H07-refactor-513-pa-workspace-layout/case.json",
    "P01": "cases/P01-cross-node-agent-migration/case.json",
    "P02": "cases/P02-agent-runtime-center/case.json",
}
BASE_RECIPE_REFS = {
    "H01": "base_repo/recipes/H01-feat-484-A.json",
    "H02": "base_repo/recipes/H02-feat-510-A.json",
    "H03": "base_repo/recipes/H03-feat-501-A.json",
    "H04": "base_repo/recipes/H04-feat-519-A.json",
    "H05": "base_repo/recipes/H05-feat-515-A.json",
    "H07": "base_repo/recipes/H07-refactor-513-A.json",
    "P01": "base_repo/recipes/P01-cross-node-agent-migration-A.json",
    "P02": "base_repo/recipes/P02-agent-runtime-center-A.json",
}
BASE_REPOSITORY_METHOD = "counterfactual-latest-base-v1"
BASE_REPOSITORY_PROJECTION = "DP1-counterfactual-latest-v1"
BASE_REPOSITORY_TRUTH_FORMULA = (
    "Code@B + ProductClaims@B + DocsFramework@F + Workflow@W"
)
BASE_REPOSITORY_LAYERS = [
    "product_world",
    "documentation_world",
    "common_compatibility",
    "arm_bundle",
    "private_controls",
]
BASE_REPOSITORY_CLOCKS = {
    "product",
    "knowledge",
    "documentation_framework",
    "workflow",
    "user",
    "model_tool",
}
H01_PROPOSED_CONTROL_PATHS = [
    "ROADMAP.md",
    "TASKS.md",
    "PROGRESS.md",
    "LOGBOOK.md",
    "TASKS",
    "PROGRESS",
    "ACCEPTANCE",
    "docs/brainstorms",
    "docs/IM-user-stream-migration-plan.md",
    "docs/IM前端蓝图.md",
]
FRAMEWORK_COMMIT = "adb93d33a2ec5443a647dd367eb67557ac72e199"
FRAMEWORK_TREE = "025b16b8c900c2b40ac23b126f99eda94e280633"
CONTROL_PREFIXES = ("case.json", "knowledge/", "judge-private/", "audit/")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
LINE_ANCHOR_RE = re.compile(r"^L([1-9][0-9]*)(?:-L([1-9][0-9]*))?$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
CHANGE_UNIT_ROOT_RE = re.compile(r"^((?:feat|bugfix|refactor|perf)-[0-9]+)(?:-|$)")
CHANGE_UNIT_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:feat|bugfix|refactor|perf)-[0-9]+(?![0-9])",
    re.IGNORECASE,
)
PROVENANCE_PLACEHOLDER_RE = re.compile(
    r"\b(?:TBD|pending|placeholder)\b", re.IGNORECASE
)
PROVENANCE_KEY_RE = re.compile(
    r"\b(?:sha(?:256)?|hash(?:es|ed)?|manifest(?:s)?|result(?:s|ing)?)\b", re.IGNORECASE
)
EVALUATION_CONTROL_ROOT = "evals/spec_design_alignment"
CANDIDATE_INPUT_ROOT = "runtime/candidate-inputs"
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SUITE_GUARDRAIL_ATOMS = (
    "feat-397-spec-design-agent-team/evaluation",
    "judge-private/",
    "owner_review_required",
)
FRESH_ROOT_BRANCH = "main"
FRESH_ROOT_COMMIT_MESSAGE = "initial repository"
FRESH_ROOT_IDENTITY = ("Repository Bootstrap", "repository@invalid")
FRESH_ROOT_EPOCH = 946684800
FRESH_ROOT_CONFIG = (
    b"[core]\n"
    b"\trepositoryformatversion = 0\n"
    b"\tfilemode = true\n"
    b"\tbare = false\n"
    b"\tlogallrefupdates = false\n"
    b"\tignorecase = true\n"
    b"\tprecomposeunicode = true\n"
)
CONTROL_COMPONENT_REFS = {
    "question_mapper": "runtime/seal-inputs/question-mapper.md",
    "judge_prompt": "runtime/seal-inputs/judge-prompt.md",
    "anonymization_protocol": "runtime/seal-inputs/anonymization.md",
    "mutation_plan": "runtime/seal-inputs/mutation-plan.md",
    "acceptance_plan": "runtime/seal-inputs/acceptance-plan.md",
}
CONTROL_COMPONENT_SECTIONS = {
    "question_mapper": {
        "inputs",
        "mapping-rules",
        "output-contract",
        "failure-handling",
    },
    "judge_prompt": {"inputs", "guardrails", "dimensions", "verdict-format"},
    "anonymization_protocol": {
        "arm-identity",
        "artifact-normalization",
        "randomization",
        "audit-log",
    },
    "mutation_plan": {
        "required-negative-mutations",
        "expected-failures",
        "execution-record",
    },
    "acceptance_plan": {"s0-s7", "downstream-selection", "stopping-rules", "reporting"},
}
RUN_PLAN_ASSET_REFS = {
    "model_reasoning": "runtime/seal-inputs/model-reasoning.json",
    "judge_reasoning": "runtime/seal-inputs/judge-reasoning.json",
    "tool_manifest": "runtime/seal-inputs/tool-manifest.json",
    "permission_manifest": "runtime/seal-inputs/permission-manifest.json",
    "sandbox_policy": "runtime/seal-inputs/sandbox-policy.json",
}
SCHEMA_PATHS = {
    "case": ROOT / "schema/case.schema.json",
    "authority": ROOT / "schema/authority-map.schema.json",
    "inventory": ROOT / "schema/decision-inventory.schema.json",
    "lineage": ROOT / "schema/lineage-manifest.schema.json",
    "owner_policy": ROOT / "schema/owner-answer-policy.schema.json",
    "permission_manifest": ROOT / "schema/permission-manifest.schema.json",
    "reasoning_settings": ROOT / "schema/reasoning-settings.schema.json",
    "sandbox_policy": ROOT / "schema/sandbox-policy.schema.json",
    "source_roots": ROOT / "schema/source-root-manifest.schema.json",
    "suite_lock": ROOT / "schema/suite-treatment-lock.schema.json",
    "suite_seal": ROOT / "schema/suite-seal.schema.json",
    "run_ledger": ROOT / "schema/run-ledger.schema.json",
    "layer": ROOT / "schema/layer-manifest.schema.json",
    "treatment": ROOT / "schema/treatment-manifest.schema.json",
    "tool_manifest": ROOT / "schema/tool-manifest.schema.json",
    "doc_system": ROOT / "schema/doc-system.schema.json",
    "doc_projection": ROOT / "schema/doc-projection.schema.json",
    "doc_validation": ROOT / "schema/doc-validation.schema.json",
    "base_recipe": ROOT / "base_repo/recipe.schema.json",
}


class Validation:
    """Collect validation errors so one run reports every actionable problem."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.json_count = 0
        self.authority_count = 0
        self.decision_count = 0
        self.source_root_count = 0
        self.schema_validation_count = 0
        self.json_cache: dict[Path, Any] = {}

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def load_json(self, path: Path) -> Any:
        if path in self.json_cache:
            return self.json_cache[path]
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            self.errors.append(f"{path.relative_to(REPO)}: invalid JSON: {exc}")
            return {}
        self.json_count += 1
        self.json_cache[path] = data
        return data


def json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without treating booleans as numbers."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            json_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


class SchemaSubsetValidator:
    """Execute the dependency-free JSON Schema subset used by this dataset."""

    def __init__(self, root_schema: dict[str, Any]) -> None:
        self.root_schema = root_schema

    def errors(self, instance: Any) -> list[str]:
        errors: list[str] = []
        self._validate(instance, self.root_schema, "$", errors)
        return errors

    def _matches(self, instance: Any, schema: Any) -> bool:
        errors: list[str] = []
        self._validate(instance, schema, "$", errors)
        return not errors

    def _resolve_ref(self, ref: str) -> Any:
        if not ref.startswith("#"):
            raise ValueError(f"only local $ref is supported, got {ref!r}")
        value: Any = self.root_schema
        fragment = ref[1:]
        if not fragment:
            return value
        if not fragment.startswith("/"):
            raise ValueError(f"invalid local JSON pointer {ref!r}")
        for raw_part in fragment[1:].split("/"):
            part = unquote(raw_part).replace("~1", "/").replace("~0", "~")
            if not isinstance(value, dict) or part not in value:
                raise ValueError(f"unresolved local $ref {ref!r}")
            value = value[part]
        return value

    @staticmethod
    def _is_type(instance: Any, expected: str) -> bool:
        types = {
            "array": lambda value: isinstance(value, list),
            "boolean": lambda value: isinstance(value, bool),
            "integer": lambda value: (
                isinstance(value, int) and not isinstance(value, bool)
            ),
            "null": lambda value: value is None,
            "number": lambda value: (
                isinstance(value, (int, float)) and not isinstance(value, bool)
            ),
            "object": lambda value: isinstance(value, dict),
            "string": lambda value: isinstance(value, str),
        }
        if expected not in types:
            raise ValueError(f"unsupported JSON Schema type {expected!r}")
        return types[expected](instance)

    def _validate(
        self, instance: Any, schema: Any, path: str, errors: list[str]
    ) -> None:
        if isinstance(schema, bool):
            if not schema:
                errors.append(f"{path}: rejected by false schema")
            return
        if not isinstance(schema, dict):
            errors.append(f"{path}: invalid schema node")
            return

        ref = schema.get("$ref")
        if ref is not None:
            try:
                resolved = self._resolve_ref(ref)
            except ValueError as exc:
                errors.append(f"{path}: {exc}")
                return
            self._validate(instance, resolved, path, errors)

        if "const" in schema and not json_equal(instance, schema["const"]):
            errors.append(f"{path}: expected const {schema['const']!r}")
        if "enum" in schema and not any(
            json_equal(instance, choice) for choice in schema["enum"]
        ):
            errors.append(f"{path}: value is not in enum {schema['enum']!r}")

        expected_type = schema.get("type")
        if expected_type is not None:
            allowed_types = (
                [expected_type] if isinstance(expected_type, str) else expected_type
            )
            if not any(self._is_type(instance, item) for item in allowed_types):
                errors.append(
                    f"{path}: expected type {expected_type!r}, got {type(instance).__name__}"
                )
                return

        if isinstance(instance, dict):
            required = schema.get("required", [])
            for name in required:
                if name not in instance:
                    errors.append(f"{path}: missing required property {name!r}")
            properties = schema.get("properties", {})
            for name, child_schema in properties.items():
                if name in instance:
                    self._validate(
                        instance[name], child_schema, f"{path}.{name}", errors
                    )
            additional = schema.get("additionalProperties", True)
            for name in instance.keys() - properties.keys():
                child_path = f"{path}.{name}"
                if additional is False:
                    errors.append(f"{child_path}: additional property is not allowed")
                elif isinstance(additional, dict):
                    self._validate(instance[name], additional, child_path, errors)
            if "minProperties" in schema and len(instance) < schema["minProperties"]:
                errors.append(
                    f"{path}: expected at least {schema['minProperties']} properties"
                )
            property_names = schema.get("propertyNames")
            if property_names is not None:
                for name in instance:
                    self._validate(
                        name, property_names, f"{path}.<property:{name}>", errors
                    )

        if isinstance(instance, list):
            item_schema = schema.get("items")
            if item_schema is not None:
                for index, item in enumerate(instance):
                    self._validate(item, item_schema, f"{path}[{index}]", errors)
            if "minItems" in schema and len(instance) < schema["minItems"]:
                errors.append(f"{path}: expected at least {schema['minItems']} items")
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errors.append(f"{path}: expected at most {schema['maxItems']} items")
            if schema.get("uniqueItems"):
                for index, item in enumerate(instance):
                    if any(json_equal(item, previous) for previous in instance[:index]):
                        errors.append(f"{path}[{index}]: duplicate item")
            if "contains" in schema:
                matches = sum(
                    self._matches(item, schema["contains"]) for item in instance
                )
                minimum = schema.get("minContains", 1)
                if matches < minimum:
                    errors.append(
                        f"{path}: expected at least {minimum} item(s) matching contains"
                    )

        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < schema["minLength"]:
                errors.append(f"{path}: expected minimum length {schema['minLength']}")
            if "pattern" in schema:
                try:
                    matched = re.search(schema["pattern"], instance) is not None
                except re.error as exc:
                    errors.append(f"{path}: invalid schema pattern: {exc}")
                else:
                    if not matched:
                        errors.append(
                            f"{path}: value does not match {schema['pattern']!r}"
                        )

        if (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and "minimum" in schema
        ):
            if instance < schema["minimum"]:
                errors.append(f"{path}: value is below minimum {schema['minimum']}")

        for child_schema in schema.get("allOf", []):
            self._validate(instance, child_schema, path, errors)
        if "oneOf" in schema:
            matches = sum(
                self._matches(instance, child_schema)
                for child_schema in schema["oneOf"]
            )
            if matches != 1:
                errors.append(
                    f"{path}: expected exactly one oneOf branch, got {matches}"
                )
        condition = schema.get("if")
        if condition is not None:
            branch = (
                schema.get("then")
                if self._matches(instance, condition)
                else schema.get("else")
            )
            if branch is not None:
                self._validate(instance, branch, path, errors)
        if "not" in schema and self._matches(instance, schema["not"]):
            errors.append(f"{path}: value matches forbidden schema")


def validate_schema_instance(
    checks: Validation,
    instance_path: Path,
    schema: dict[str, Any],
) -> None:
    instance = checks.load_json(instance_path)
    label = instance_path.relative_to(REPO)
    for error in SchemaSubsetValidator(schema).errors(instance):
        checks.errors.append(f"{label}: schema: {error}")
    checks.schema_validation_count += 1


def git_bytes(*args: str) -> bytes:
    return git_bytes_at(REPO, *args)


def isolated_git_environment() -> dict[str, str]:
    """Run control-plane Git without inherited repository or config redirects."""
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith("GIT_")
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    environment["GIT_PAGER"] = "cat"
    environment["GIT_EXTERNAL_DIFF"] = ""
    return environment


def git_bytes_at(repository: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        env=isolated_git_environment(),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def git_head_entries(repository: Path) -> dict[str, dict[str, Any]]:
    """Read the exact HEAD blob tree without checkout filters or archive attributes."""
    raw_tree = git_bytes_at(repository, "ls-tree", "-rz", "--full-tree", "HEAD")
    records: list[tuple[str, str, str, str]] = []
    for raw_record in raw_tree.split(b"\x00"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        if not separator:
            raise RuntimeError("malformed git ls-tree record")
        mode, object_type, object_id = metadata.decode().split()
        records.append((mode, object_type, object_id, raw_path.decode()))
    non_blobs = [path for _, object_type, _, path in records if object_type != "blob"]
    if non_blobs:
        raise RuntimeError(f"fresh root contains non-blob Git entries: {non_blobs[:5]}")
    request = b"".join(f"{object_id}\n".encode() for _, _, object_id, _ in records)
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repository,
        env=isolated_git_environment(),
        input=request,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    cursor = 0
    entries: dict[str, dict[str, Any]] = {}
    for mode, _, _, path in records:
        line_end = result.stdout.find(b"\n", cursor)
        if line_end < 0:
            raise RuntimeError("truncated git cat-file header")
        header = result.stdout[cursor:line_end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise RuntimeError(f"unexpected git cat-file header for {path}")
        size = int(header[2])
        start = line_end + 1
        end = start + size
        if end >= len(result.stdout) or result.stdout[end : end + 1] != b"\n":
            raise RuntimeError(f"truncated git cat-file payload for {path}")
        entries[path] = {"mode": mode, "content": result.stdout[start:end]}
        cursor = end + 1
    return entries


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def canonical_relative_path(path: str) -> str | None:
    """Accept only one lexical spelling for a POSIX relative path."""
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or "\\" in path
        or "\x00" in path
    ):
        return None
    if unicodedata.normalize("NFC", path) != path:
        return None
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def path_is_within(path: str, root: str) -> bool:
    normalized_path = canonical_relative_path(path)
    normalized_root = canonical_relative_path(root.rstrip("/"))
    if normalized_path is None or normalized_root is None:
        return False
    policy_path = unicodedata.normalize("NFC", normalized_path).casefold()
    policy_root = unicodedata.normalize("NFC", normalized_root).casefold()
    return policy_path == policy_root or policy_path.startswith(f"{policy_root}/")


def project_agents(content: bytes, headings: list[str]) -> bytes:
    """Project cutoff AGENTS bytes with the suite's single syntax-only algorithm."""
    lines = content.splitlines(keepends=True)
    first_level2 = next(
        (index for index, line in enumerate(lines) if line.startswith(b"## ")),
        len(lines),
    )
    output = list(lines[:first_level2])
    selected = {f"## {heading}".encode() for heading in headings}
    index = first_level2
    while index < len(lines):
        heading = lines[index].rstrip(b"\r\n")
        end = index + 1
        while end < len(lines) and not lines[end].startswith(b"## "):
            end += 1
        if heading in selected:
            output.extend(lines[index:end])
        index = end
    projection = b"".join(output)
    if any(
        line.rstrip(b"\r\n") == b"## Project overview"
        for line in projection.splitlines(keepends=True)
    ):
        raise ValueError("AGENTS projection retained forbidden ## Project overview")
    return projection


def archive_entries(raw_archive: bytes, prefix: str) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    with tarfile.open(fileobj=io.BytesIO(raw_archive), mode="r:") as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            path = member.name
            if prefix:
                if not path.startswith(prefix):
                    raise ValueError(
                        f"archive member {path!r} is outside prefix {prefix!r}"
                    )
                path = path[len(prefix) :]
            if not path:
                continue
            if member.issym():
                content = member.linkname.encode()
                mode = "120000"
            elif member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"cannot read archive member {member.name!r}")
                content = extracted.read()
                mode = "100755" if member.mode & 0o111 else "100644"
            else:
                continue
            entries[path] = {"mode": mode, "content": content}
    return entries


def file_manifest(entries: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "mode": entries[path]["mode"],
            "path": path,
            "sha256": hashlib.sha256(entries[path]["content"]).hexdigest(),
        }
        for path in sorted(entries)
    ]


def evaluate_source_root(
    source: dict[str, Any],
    scrub_policy: dict[str, Any],
    projection_policy: dict[str, Any],
) -> dict[str, Any]:
    control_path = Path(source["control_path"])
    if not control_path.is_absolute():
        control_path = REPO / control_path
    archive_args = ["archive", "--format=tar"]
    prefix = source["archive_prefix"]
    if prefix:
        archive_args.append(f"--prefix={prefix}")
    archive_args.append(source["cutoff_ref"])
    raw_archive = git_bytes_at(control_path, *archive_args)
    entries = archive_entries(raw_archive, prefix)

    preserve_roots = source["product_owned_instruction_roots"]
    instruction_roots = sorted(
        {
            str(Path(path).parent).replace("\\", "/")
            for path in entries
            if Path(path).name == scrub_policy["instruction_marker"]
            and not any(path_is_within(path, root) for root in preserve_roots)
        }
    )
    present_fixed_roots = [
        root
        for root in scrub_policy["fixed_remove_roots"]
        if any(path_is_within(path, root) for path in entries)
    ]
    removal_candidates = [*present_fixed_roots, *instruction_roots]
    if source["agents_policy"] == "remove" and "AGENTS.md" in entries:
        removal_candidates.append("AGENTS.md")
    removed_roots: list[str] = []
    for candidate in sorted(
        set(removal_candidates), key=lambda item: (item.count("/"), item)
    ):
        if not any(path_is_within(candidate, parent) for parent in removed_roots):
            removed_roots.append(candidate)

    exposed_root = source["exposed_root"]

    def exposed(path: str) -> str:
        return path if exposed_root == "." else f"{exposed_root.rstrip('/')}/{path}"

    removed_entries: dict[str, dict[str, Any]] = {}
    filtered_entries: dict[str, dict[str, Any]] = {}
    for path, entry in entries.items():
        target = (
            removed_entries
            if any(path_is_within(path, root) for root in removed_roots)
            else filtered_entries
        )
        target[exposed(path)] = entry

    source_agents = entries.get("AGENTS.md")
    projection: bytes | None = None
    if source["agents_policy"] == "project_from_cutoff_projection":
        if source_agents is None:
            raise ValueError("project source has no cutoff AGENTS.md")
        projection = project_agents(
            source_agents["content"], projection_policy["included_level2_headings"]
        )
        filtered_entries[exposed("AGENTS.md")] = {
            **source_agents,
            "content": projection,
        }

    return {
        "raw_archive_sha256": hashlib.sha256(raw_archive).hexdigest(),
        "source_agents_sha256": hashlib.sha256(source_agents["content"]).hexdigest()
        if source_agents
        else None,
        "agents_projection_sha256": hashlib.sha256(projection).hexdigest()
        if projection is not None
        else None,
        "expected_instruction_roots": instruction_roots,
        "expected_removed_roots": removed_roots,
        "removed_files_manifest_sha256": canonical_hash(file_manifest(removed_entries)),
        "post_filter_files_manifest_sha256": canonical_hash(
            file_manifest(filtered_entries)
        ),
        "filtered_entries": filtered_entries,
    }


def validate_source_root_manifest(
    checks: Validation,
    schema: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    path = ROOT / "source-roots.json"
    validate_schema_instance(checks, path, schema)
    data = checks.load_json(path)
    if not isinstance(data, dict):
        return {}
    base_method = data.get("base_repository_method", {})
    checks.check(
        base_method
        == {
            "method": BASE_REPOSITORY_METHOD,
            "projection": BASE_REPOSITORY_PROJECTION,
            "framework_workflow_commit": FRAMEWORK_COMMIT,
            "framework_workflow_tree": FRAMEWORK_TREE,
            "clean_policy": "remove_active_and_retired_keep_completed_archive",
        },
        "source-roots.json: base-repository method binding mismatch",
    )
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        return {}
    valid_sources = [source for source in sources if isinstance(source, dict)]
    ids = [source.get("source_id") for source in valid_sources]
    checks.check(len(ids) == len(set(ids)), "source-roots.json: duplicate source ids")
    registry: dict[str, dict[str, Any]] = {}
    for source in valid_sources:
        source_id = source.get("source_id", "<missing>")
        label = f"source-roots/{source_id}"
        control_path = Path(source.get("control_path", ""))
        if source.get("kind") == "project_repository":
            checks.check(
                source.get("control_path") == ".",
                f"{label}: project source must use this repository object store",
            )
            checks.check(
                source.get("agents_policy") == "project_from_cutoff_projection",
                f"{label}: project AGENTS policy mismatch",
            )
            checks.check(
                source.get("archive_prefix") == ""
                and source.get("exposed_root") == ".",
                f"{label}: project root/prefix mismatch",
            )
        elif source.get("kind") == "external_repository":
            checks.check(
                control_path.is_absolute(),
                f"{label}: external control path must be explicit and absolute",
            )
            checks.check(
                source.get("agents_policy") == "remove",
                f"{label}: external AGENTS policy mismatch",
            )
            checks.check(
                source.get("archive_prefix")
                == f"{source.get('exposed_root', '').rstrip('/')}/",
                f"{label}: external archive prefix/exposed root mismatch",
            )
        try:
            actual = evaluate_source_root(
                source, data["scrub_policy"], data["agents_projection"]
            )
        except (KeyError, OSError, RuntimeError, tarfile.TarError, ValueError) as exc:
            checks.errors.append(f"{label}: cannot reproduce source root: {exc}")
            continue
        checks.check(
            actual["expected_instruction_roots"]
            == source.get("expected_instruction_roots"),
            f"{label}: non-product instruction roots differ from frozen manifest",
        )
        checks.check(
            actual["expected_removed_roots"] == source.get("expected_removed_roots"),
            f"{label}: removed roots differ from frozen manifest",
        )
        expected_hashes = source.get("hashes", {})
        for name in (
            "raw_archive_sha256",
            "source_agents_sha256",
            "agents_projection_sha256",
            "removed_files_manifest_sha256",
            "post_filter_files_manifest_sha256",
        ):
            checks.check(
                actual[name] == expected_hashes.get(name),
                f"{label}: {name} mismatch: {actual[name]}",
            )
        for preserve_root in source.get("product_owned_instruction_roots", []):
            preserved_markers = [
                path
                for path in actual["filtered_entries"]
                if path.endswith("/SKILL.md")
                and path_is_within(
                    path,
                    preserve_root
                    if source.get("exposed_root") == "."
                    else f"{source['exposed_root'].rstrip('/')}/{preserve_root}",
                )
            ]
            checks.check(
                bool(preserved_markers),
                f"{label}: declared product-owned instruction root has no preserved SKILL.md",
            )
        source_symlinks = [
            path
            for path, entry in actual["filtered_entries"].items()
            if entry.get("mode") == "120000"
        ]
        checks.check(
            not source_symlinks,
            f"{label}: candidate-visible source symlinks are forbidden: {source_symlinks[:5]}",
        )
        registry[source_id] = {"source": source, "actual": actual}
    checks.source_root_count = len(registry)
    return registry


def validate_authoring_freeze_receipt(
    checks: Validation,
    lock: dict[str, Any],
    holdout_ids: set[str],
) -> None:
    """Bind workflow/profile-builder closure before any clean holdout is authored."""
    authoring_freeze = lock.get("authoring_freeze", {})
    receipt_binding = authoring_freeze.get("receipt", {})
    receipt_ref = (
        receipt_binding.get("ref", "") if isinstance(receipt_binding, dict) else ""
    )
    receipt_path = safe_runtime_control_path(receipt_ref, "runtime")
    checks.check(
        receipt_ref == "runtime/authoring-freeze-receipt.json"
        and receipt_path is not None,
        "suite-treatment-lock.json: authoring-freeze receipt is unsafe or missing",
    )
    if receipt_path is None:
        return
    receipt_bytes = receipt_path.read_bytes()
    checks.check(
        hashlib.sha256(receipt_bytes).hexdigest() == receipt_binding.get("sha256"),
        "suite-treatment-lock.json: authoring-freeze receipt sha256 mismatch",
    )
    receipt = checks.load_json(receipt_path)
    expected_receipt = {
        "schema_version": "1.0",
        "suite_id": lock.get("suite_id"),
        "status": "frozen",
        "frozen_at": authoring_freeze.get("frozen_at"),
        "workflow_clock_id": lock.get("workflow_clock_id"),
        "shared_helpers": lock.get("components", {}).get("shared_helpers"),
        "artifact_contracts": lock.get("components", {}).get("artifact_contracts"),
        "workflows": lock.get("components", {}).get("workflows"),
        "profile_builder": authoring_freeze.get("profile_builder"),
    }
    checks.check(
        isinstance(receipt, dict) and json_equal(receipt, expected_receipt),
        "suite-treatment-lock.json: authoring receipt does not exactly bind A/B workflows and profile-builder",
    )
    published_commit = receipt_binding.get("published_commit", "")
    if SHA_RE.fullmatch(published_commit or "") is None:
        checks.errors.append(
            "suite-treatment-lock.json: authoring receipt needs a published Git commit"
        )
        return
    repository_receipt_path = f"{EVALUATION_CONTROL_ROOT}/{receipt_ref}"
    try:
        published_bytes = git_bytes(
            "show", f"{published_commit}:{repository_receipt_path}"
        )
        published_at = (
            git_bytes("show", "-s", "--format=%cI", published_commit).decode().strip()
        )
    except RuntimeError as exc:
        checks.errors.append(
            f"suite-treatment-lock.json: authoring receipt publication is unreadable: {exc}"
        )
        return
    checks.check(
        published_bytes == receipt_bytes,
        "suite-treatment-lock.json: published authoring receipt bytes differ",
    )
    checks.check(
        receipt_binding.get("published_at") == published_at,
        "suite-treatment-lock.json: authoring receipt publication timestamp mismatch",
    )
    try:
        frozen_at = datetime.fromisoformat(authoring_freeze.get("frozen_at", ""))
        publication_time = datetime.fromisoformat(published_at)
    except (TypeError, ValueError):
        pass
    else:
        checks.check(
            frozen_at <= publication_time,
            "suite-treatment-lock.json: receipt predates its declared freeze",
        )
    for case_id in holdout_ids:
        case_path = f"{EVALUATION_CONTROL_ROOT}/{EXPECTED_CASE_REFS[case_id]}"
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{published_commit}:{case_path}"],
            cwd=REPO,
            env=isolated_git_environment(),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        checks.check(
            result.returncode != 0,
            f"suite-treatment-lock.json/{case_id}: clean holdout already existed in authoring-freeze commit",
        )


def validate_clean_holdout_authorship(
    checks: Validation,
    case_id: str,
    case_dir: Path,
    authoring: dict[str, Any],
    authoring_freeze: dict[str, Any],
) -> None:
    """Prove receipt -> first case-assets commit -> current sealed history ordering."""
    receipt_commit = authoring_freeze.get("receipt", {}).get("published_commit", "")
    authored_commit = authoring.get("case_authored_commit", "")
    if (
        SHA_RE.fullmatch(receipt_commit or "") is None
        or SHA_RE.fullmatch(authored_commit or "") is None
    ):
        checks.errors.append(
            f"{case_id}: clean holdout needs receipt and authored Git commits"
        )
        return

    def is_ancestor(ancestor: str, descendant: str) -> bool:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=REPO,
            env=isolated_git_environment(),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0

    checks.check(
        receipt_commit != authored_commit
        and is_ancestor(receipt_commit, authored_commit),
        f"{case_id}: authored commit is not a descendant of the published authoring freeze",
    )
    checks.check(
        is_ancestor(authored_commit, "HEAD"),
        f"{case_id}: authored commit is not an ancestor of the current sealed corpus",
    )
    try:
        authored_metadata = (
            git_bytes("rev-list", "--parents", "-n", "1", authored_commit)
            .decode()
            .strip()
            .split()
        )
        authored_commit_time = (
            git_bytes("show", "-s", "--format=%cI", authored_commit).decode().strip()
        )
    except RuntimeError as exc:
        checks.errors.append(f"{case_id}: authored commit is unreadable: {exc}")
        return
    checks.check(
        len(authored_metadata) == 2,
        f"{case_id}: authored commit must have exactly one parent",
    )
    checks.check(
        authoring.get("case_authored_at") == authored_commit_time,
        f"{case_id}: authored timestamp differs from authored commit",
    )
    if len(authored_metadata) != 2:
        return
    parent_commit = authored_metadata[1]
    case_relative_dir = str(case_dir.relative_to(ROOT)).replace("\\", "/")
    repository_case_dir = f"{EVALUATION_CONTROL_ROOT}/{case_relative_dir}"
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{parent_commit}:{repository_case_dir}"],
        cwd=REPO,
        env=isolated_git_environment(),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    checks.check(
        result.returncode != 0,
        f"{case_id}: case directory existed before the authored commit",
    )

    authored_manifest: list[dict[str, str]] = []
    for relative in sorted(FIXED_CASE_ASSETS - {"case.json"}):
        repository_path = f"{repository_case_dir}/{relative}"
        try:
            authored_bytes = git_bytes("show", f"{authored_commit}:{repository_path}")
        except RuntimeError as exc:
            checks.errors.append(
                f"{case_id}: authored asset is unreadable at {relative}: {exc}"
            )
            continue
        current_bytes = (case_dir / relative).read_bytes()
        checks.check(
            authored_bytes == current_bytes,
            f"{case_id}: authored asset changed after holdout creation: {relative}",
        )
        authored_manifest.append(
            {"path": relative, "sha256": hashlib.sha256(authored_bytes).hexdigest()}
        )
    checks.check(
        len(authored_manifest) == len(FIXED_CASE_ASSETS) - 1
        and authoring.get("authored_assets_manifest_sha256")
        == canonical_hash(authored_manifest),
        f"{case_id}: authored fixed-assets manifest hash mismatch",
    )


def validate_suite_treatment_lock(
    checks: Validation,
    schema: dict[str, Any],
    lineage_schema: dict[str, Any],
    dataset: dict[str, Any],
    registered_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate the one treatment identity and N0 derivation lock for all cases."""
    lock_ref = dataset.get("suite_treatment_lock_ref")
    checks.check(
        lock_ref == TREATMENT_LOCK_REF,
        "dataset.json: suite treatment lock ref mismatch",
    )
    path = TREATMENT_LOCK_PATH
    validate_schema_instance(checks, path, schema)
    lock = checks.load_json(path)
    if not isinstance(lock, dict):
        return {}

    statuses = {item.get("status") for item in registered_cases}
    active = bool(statuses & {"ready", "sealed"})
    if active:
        checks.check(
            statuses <= {"ready", "sealed"},
            "dataset.json: suite treatment lock freezes all eight cases together",
        )
        checks.check(
            lock.get("status") == "frozen",
            "suite-treatment-lock.json: active suite must be frozen",
        )
        checks.check(
            not has_pending(lock),
            "suite-treatment-lock.json: frozen lock contains pending values",
        )
        checks.check(
            dataset.get("suite_treatment_lock_sha256")
            == hashlib.sha256(path.read_bytes()).hexdigest(),
            "dataset.json: suite treatment lock sha256 mismatch",
        )
    else:
        checks.check(
            statuses <= {"draft", "retired"},
            "dataset.json: unsupported mixed suite status",
        )
        checks.check(
            lock.get("status") == "draft",
            "suite-treatment-lock.json: draft suite must use draft lock",
        )

    guardrails = lock.get("guardrails", {})
    checks.check(
        guardrails.get("all_candidate_atoms") == list(SUITE_GUARDRAIL_ATOMS),
        "suite-treatment-lock.json: fixed candidate guardrails differ",
    )
    bindings = lock.get("case_bindings", {})
    case_ids = {item.get("case_id") for item in registered_cases}
    checks.check(
        set(bindings) == case_ids,
        "suite-treatment-lock.json: case bindings differ from dataset",
    )
    expected_epochs = {
        "H01": ("legacy_spec_guide", []),
        "H02": ("native_specs_contributing", []),
        "H03": ("native_specs_contributing", []),
        "H04": ("native_specs_contributing", []),
        "H05": ("native_specs_contributing", []),
        "H07": ("native_specs_contributing", []),
        "P01": ("native_specs_contributing", []),
        "P02": ("native_specs_contributing", []),
    }
    epoch_hashes: dict[str, set[str]] = {}
    for case_id, (epoch, derivations) in expected_epochs.items():
        binding = bindings.get(case_id, {})
        if not isinstance(binding, dict):
            binding = {}
        checks.check(
            binding.get("normalization_epoch") == epoch,
            f"suite-treatment-lock.json/{case_id}: normalization epoch mismatch",
        )
        checks.check(
            json_equal(binding.get("common_derivations"), derivations),
            f"suite-treatment-lock.json/{case_id}: derivations differ from the task-blind epoch rule",
        )
        epoch_hashes.setdefault(epoch, set()).add(
            binding.get("common_files_manifest_sha256")
        )
    checks.check(
        all(len(hashes) == 1 for hashes in epoch_hashes.values()),
        "suite-treatment-lock.json: cases in one normalization epoch have different common manifests",
    )

    component_ids = [
        lock.get("components", {}).get("shared_helpers", {}).get("component_id"),
        lock.get("authoring_freeze", {}).get("profile_builder", {}).get("component_id"),
        *[
            item.get("component_id")
            for item in lock.get("components", {})
            .get("artifact_contracts", {})
            .values()
            if isinstance(item, dict)
        ],
        *[
            item.get("component_id")
            for item in lock.get("components", {}).get("workflows", {}).values()
            if isinstance(item, dict)
        ],
    ]
    profile_ids = [
        item.get("profile", {}).get("component_id")
        for item in bindings.values()
        if isinstance(item, dict)
    ]
    treatment_ids = [
        item.get("treatment_id")
        for item in lock.get("arms", {}).values()
        if isinstance(item, dict)
    ]
    checks.check(
        len(component_ids) == len(set(component_ids)),
        "suite-treatment-lock.json: duplicate component ids",
    )
    checks.check(
        len(profile_ids) == len(set(profile_ids)),
        "suite-treatment-lock.json: duplicate profile component ids",
    )
    checks.check(
        len(treatment_ids) == len(set(treatment_ids)),
        "suite-treatment-lock.json: duplicate treatment ids",
    )

    expected_arm_topology = {
        "A": ("workflow-current-spec-design-v1", "none"),
        "A_USER": ("workflow-current-spec-design-v1", "case_current_cross_fitted"),
        "B": ("workflow-feat397-team-v1", "case_current_cross_fitted"),
    }
    expected_arm_readiness = {
        "A": ("ready_materializable", []),
        "A_USER": ("blocked", ["frozen_cross_fitted_profile"]),
        "B": (
            "blocked",
            ["executable_agent_team_bundle", "frozen_cross_fitted_profile"],
        ),
    }
    for arm_id, (workflow_id, selector) in expected_arm_topology.items():
        arm = lock.get("arms", {}).get(arm_id, {})
        checks.check(
            (arm.get("workflow_component_id"), arm.get("profile_selector"))
            == (workflow_id, selector),
            f"suite-treatment-lock.json/{arm_id}: arm topology mismatch",
        )
        checks.check(
            (arm.get("readiness"), arm.get("blockers"))
            == expected_arm_readiness[arm_id],
            f"suite-treatment-lock.json/{arm_id}: readiness/blockers mismatch",
        )

    expected_component_ids = {
        "shared_helpers": "shared-helpers-v1",
        "single_unit": "artifact-contract-single-unit-v1",
        "portfolio": "artifact-contract-portfolio-v1",
        "current_spec_design_skills": "workflow-current-spec-design-v1",
        "spec_design_agent_team": "workflow-feat397-team-v1",
    }
    components = lock.get("components", {})
    authoring_freeze = lock.get("authoring_freeze", {})
    profile_builder = authoring_freeze.get("profile_builder", {})
    checks.check(
        profile_builder.get("component_id") == "profile-builder-v1",
        "suite-treatment-lock.json: profile builder component id mismatch",
    )
    checks.check(
        components.get("shared_helpers", {}).get("component_id")
        == expected_component_ids["shared_helpers"],
        "suite-treatment-lock.json: shared helper component id mismatch",
    )
    for contract_id in ("single_unit", "portfolio"):
        checks.check(
            components.get("artifact_contracts", {})
            .get(contract_id, {})
            .get("component_id")
            == expected_component_ids[contract_id],
            f"suite-treatment-lock.json: {contract_id} artifact component id mismatch",
        )
    for workflow_id in ("current_spec_design_skills", "spec_design_agent_team"):
        checks.check(
            components.get("workflows", {}).get(workflow_id, {}).get("component_id")
            == expected_component_ids[workflow_id],
            f"suite-treatment-lock.json: {workflow_id} component id mismatch",
        )

    lineaged_components = [
        (
            components.get("shared_helpers", {}),
            "shared_helper",
            {"shared_helper"},
            False,
        ),
        (
            components.get("artifact_contracts", {}).get("single_unit", {}),
            "artifact_contract",
            {"artifact_contract"},
            True,
        ),
        (
            components.get("artifact_contracts", {}).get("portfolio", {}),
            "artifact_contract",
            {"artifact_contract"},
            True,
        ),
        (
            components.get("workflows", {}).get("current_spec_design_skills", {}),
            "workflow",
            {"workflow"},
            True,
        ),
        (
            components.get("workflows", {}).get("spec_design_agent_team", {}),
            "workflow",
            {"workflow"},
            True,
        ),
        (profile_builder, "profile_builder", {"profile_builder"}, True),
    ]
    for component, _, _, _ in lineaged_components:
        component_id = component.get("component_id", "")
        checks.check(
            component.get("lineage_manifest_ref")
            == f"runtime/lineage/{component_id}.json",
            f"suite-treatment-lock.json/{component_id or '<missing>'}: lineage manifest path mismatch",
        )

    holdout_ids = {
        item.get("case_id")
        for item in registered_cases
        if item.get("stratum") == "prospective_holdout"
    }
    if holdout_ids:
        checks.check(
            authoring_freeze.get("status") == "frozen",
            f"suite-treatment-lock.json: clean holdouts require a prior authoring freeze: {sorted(holdout_ids)}",
        )

    suite_lineages = {"generic_historical_learning": set(), "target_derived": set()}
    all_case_ids = set(EXPECTED_CASE_REFS)
    case_contracts: dict[str, str | None] = {}
    for registered in registered_cases:
        case_id = registered.get("case_id")
        case_ref = EXPECTED_CASE_REFS.get(case_id, "")
        case_data = checks.load_json(ROOT / case_ref) if case_ref else {}
        case_contracts[case_id] = (
            case_data.get("artifact_contract") if isinstance(case_data, dict) else None
        )
    if authoring_freeze.get("status") == "frozen":
        checks.check(
            not has_pending(authoring_freeze),
            "suite-treatment-lock.json: frozen authoring lock contains pending values",
        )
        validate_authoring_freeze_receipt(checks, lock, holdout_ids)
        try:
            authoring_frozen_at = datetime.fromisoformat(
                authoring_freeze.get("frozen_at", "")
            )
        except (TypeError, ValueError):
            checks.errors.append(
                "suite-treatment-lock.json: authoring freeze timestamp is invalid"
            )
        else:
            checks.check(
                authoring_frozen_at.tzinfo is not None,
                "suite-treatment-lock.json: authoring freeze timestamp needs a timezone",
            )
        for (
            component,
            lineage_kind,
            allowed_roles,
            require_nonempty,
        ) in lineaged_components:
            component_id = component.get("component_id", "<missing>")
            dependencies = validate_locked_component(
                checks,
                component,
                f"suite-treatment-lock.json/authoring-freeze/{component_id}",
                allowed_roles,
                require_nonempty,
            )
            lineage_result = validate_lineage_manifest(
                checks,
                lineage_schema,
                component,
                dependencies,
                lineage_kind,
                f"suite-treatment-lock.json/authoring-freeze/{component_id}",
            )
            applicable_case_ids = all_case_ids
            if component_id == "artifact-contract-single-unit-v1":
                applicable_case_ids = {
                    case_id
                    for case_id, contract in case_contracts.items()
                    if contract == "single_unit"
                }
            elif component_id == "artifact-contract-portfolio-v1":
                applicable_case_ids = {
                    case_id
                    for case_id, contract in case_contracts.items()
                    if contract == "portfolio"
                }
            for lineage_class in suite_lineages:
                suite_lineages[lineage_class].update(
                    lineage_result[lineage_class] & applicable_case_ids
                )

    if lock.get("status") == "frozen":
        locked_components = [
            (
                components.get("shared_helpers", {}),
                "shared_helpers",
                {"shared_helper"},
                False,
            ),
            *[
                (
                    components.get("artifact_contracts", {}).get(contract_id, {}),
                    f"artifact_contracts/{contract_id}",
                    {"artifact_contract"},
                    True,
                )
                for contract_id in ("single_unit", "portfolio")
            ],
        ]
        checks.check(
            authoring_freeze.get("status") == "frozen",
            "suite-treatment-lock.json: full treatment freeze requires prior authoring freeze",
        )
        for component, label, roles, require_nonempty in locked_components:
            validate_locked_component(
                checks,
                component,
                f"suite-treatment-lock.json/{label}",
                roles,
                require_nonempty,
            )
        current_visible = (
            components.get("workflows", {})
            .get("current_spec_design_skills", {})
            .get("candidate_manifest_sha256")
        )
        team_visible = (
            components.get("workflows", {})
            .get("spec_design_agent_team", {})
            .get("candidate_manifest_sha256")
        )
        checks.check(
            current_visible != team_visible,
            "suite-treatment-lock.json: current and team candidate-visible workflows must differ",
        )

    for case_id, binding in bindings.items():
        if not isinstance(binding, dict):
            continue
        profile = binding.get("profile", {})
        checks.check(
            profile.get("source_path")
            == f"runtime/candidate-inputs/{case_id}/USER.cross-fitted.md",
            f"suite-treatment-lock.json/{case_id}: profile source path mismatch",
        )
        checks.check(
            profile.get("installed_path") == "USER.md",
            f"suite-treatment-lock.json/{case_id}: profile install path mismatch",
        )
        for derivation in binding.get("common_derivations", []):
            if not isinstance(derivation, dict):
                continue
            source_path = derivation.get("source_path", "")
            installed_path = derivation.get("installed_path", "")
            checks.check(
                canonical_relative_path(source_path) == source_path
                and canonical_relative_path(installed_path) == installed_path
                and not is_case_control_path(installed_path)
                and not path_is_within(installed_path, EVALUATION_CONTROL_ROOT),
                f"suite-treatment-lock.json/{case_id}: N0 derivation path is invalid",
            )
        expected_case_ref = EXPECTED_CASE_REFS.get(case_id)
        leak_path = ROOT / expected_case_ref if expected_case_ref else None
        if leak_path is not None:
            actual_hash = hashlib.sha256(
                (leak_path.parent / "audit/leak-signatures.txt").read_bytes()
            ).hexdigest()
            checks.check(
                binding.get("leak_signatures_sha256") == actual_hash,
                f"suite-treatment-lock.json/{case_id}: leak signature hash mismatch",
            )
        if lock.get("status") == "frozen":
            checks.check(
                binding.get("profile", {}).get("review_status")
                == "task_blind_approved",
                f"suite-treatment-lock.json/{case_id}: frozen profile lacks task-blind approval",
            )
            profile_dependency = locked_profile_dependency(profile)
            profile_source = safe_source_dependency_path(profile.get("source_path", ""))
            checks.check(
                profile_source is not None,
                f"suite-treatment-lock.json/{case_id}: profile source is unsafe or missing",
            )
            if profile_source is not None:
                actual_mode = (
                    "100755" if profile_source.stat().st_mode & 0o111 else "100644"
                )
                checks.check(
                    actual_mode == profile.get("mode"),
                    f"suite-treatment-lock.json/{case_id}: profile mode mismatch",
                )
                checks.check(
                    hashlib.sha256(profile_source.read_bytes()).hexdigest()
                    == profile.get("sha256"),
                    f"suite-treatment-lock.json/{case_id}: profile sha256 mismatch",
                )
            checks.check(
                canonical_hash(locked_source_manifest([profile_dependency]))
                == profile.get("dependency_manifest_sha256"),
                f"suite-treatment-lock.json/{case_id}: profile source manifest hash mismatch",
            )
            checks.check(
                canonical_hash(candidate_dependency_manifest([profile_dependency]))
                == profile.get("candidate_manifest_sha256"),
                f"suite-treatment-lock.json/{case_id}: profile candidate manifest hash mismatch",
            )
            profile_component = {
                "component_id": profile.get("component_id"),
                "dependencies": [profile_dependency],
                "dependency_manifest_sha256": profile.get("dependency_manifest_sha256"),
                "lineage_manifest_ref": profile.get("lineage_manifest_ref"),
                "lineage_manifest_sha256": profile.get("lineage_manifest_sha256"),
            }
            validate_lineage_manifest(
                checks,
                lineage_schema,
                profile_component,
                [profile_dependency],
                "cross_fitted_profile",
                f"suite-treatment-lock.json/{case_id}/profile-lineage",
                case_id,
            )
    if lock.get("status") == "frozen":
        for registered in registered_cases:
            case_id = registered.get("case_id")
            case_ref = EXPECTED_CASE_REFS.get(case_id, "")
            case_data = checks.load_json(ROOT / case_ref) if case_ref else {}
            if not isinstance(case_data, dict):
                continue
            level = case_data.get("contamination", {}).get("level")
            has_generic = case_id in suite_lineages["generic_historical_learning"]
            has_target = case_id in suite_lineages["target_derived"]
            checks.check(
                level != "C3",
                f"suite-treatment-lock.json/{case_id}: C3 direct leakage cannot be sealed",
            )
            if level == "C0":
                checks.check(
                    not has_generic and not has_target,
                    f"suite-treatment-lock.json/{case_id}: C0 conflicts with retained candidate lineage",
                )
            elif level == "C1":
                checks.check(
                    has_generic and not has_target,
                    f"suite-treatment-lock.json/{case_id}: C1 needs generic exposure and no target-derived bytes",
                )
            elif level == "C2":
                checks.check(
                    has_target,
                    f"suite-treatment-lock.json/{case_id}: C2 lacks target-derived lineage evidence",
                )
    return lock


def validate_control_document(
    checks: Validation, text: str, component_id: str, label: str
) -> None:
    """Require a non-placeholder control document with populated contract sections."""
    control_text = text.strip()
    checks.check(bool(control_text), f"{label}: control component is empty")
    checks.check(
        control_text.lower() not in {"pending", "tbd", "placeholder"},
        f"{label}: control component is only a placeholder",
    )
    sections = markdown_heading_sections(control_text)
    expected_sections = CONTROL_COMPONENT_SECTIONS[component_id]
    checks.check(
        expected_sections <= set(sections),
        f"{label}: required control sections are missing",
    )
    for section in expected_sections:
        checks.check(
            any(line.strip() for line in sections.get(section, [])),
            f"{label}: control section is empty: {section}",
        )


def validate_suite_seal(
    checks: Validation,
    schema: dict[str, Any],
    dataset: dict[str, Any],
    registered_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind the complete corpus, judge controls and run plan before outputs exist."""
    checks.check(
        dataset.get("suite_seal_ref") == SUITE_SEAL_REF,
        "dataset.json: suite seal ref mismatch",
    )
    path = SUITE_SEAL_PATH
    validate_schema_instance(checks, path, schema)
    seal = checks.load_json(path)
    if not isinstance(seal, dict):
        return {}
    statuses = {item.get("status") for item in registered_cases}
    if "sealed" in statuses:
        checks.check(
            statuses == {"sealed"},
            "dataset.json: suite seal requires all eight cases sealed together",
        )
        checks.check(
            seal.get("status") == "frozen",
            "suite-seal.json: sealed cases require a frozen suite seal",
        )
        checks.check(
            dataset.get("suite_seal_sha256")
            == hashlib.sha256(path.read_bytes()).hexdigest(),
            "dataset.json: suite seal sha256 mismatch",
        )
    else:
        checks.check(
            seal.get("status") == "draft",
            "suite-seal.json: unsealed suite must keep a draft seal",
        )

    case_seals = seal.get("case_assets", {})
    checks.check(
        set(case_seals) == set(EXPECTED_CASE_REFS),
        "suite-seal.json: case assets differ from registry",
    )
    recipe_registry = []
    for case_id, recipe_ref in BASE_RECIPE_REFS.items():
        recipe_path = ROOT / recipe_ref
        recipe = checks.load_json(recipe_path)
        recipe_registry.append(
            {
                "case_id": case_id,
                "recipe_ref": recipe_ref,
                "recipe_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
                "content_manifest_sha256": recipe.get("assertions", {}).get(
                    "expected_content_manifest_sha256"
                ),
            }
        )
    base_repository = seal.get("base_repository", {})
    checks.check(
        base_repository.get("method") == BASE_REPOSITORY_METHOD
        and base_repository.get("projection") == BASE_REPOSITORY_PROJECTION
        and base_repository.get("clean_policy")
        == "remove_active_and_retired_keep_completed_archive"
        and base_repository.get("materialized_arm") == "A"
        and base_repository.get("recipe_registry_manifest_sha256")
        == canonical_hash(recipe_registry),
        "suite-seal.json: base-repository registry binding mismatch",
    )
    checks.check(
        base_repository.get("arm_readiness")
        == {
            arm_id: suite_lock_arm.get("readiness")
            for arm_id, suite_lock_arm in checks.load_json(TREATMENT_LOCK_PATH)
            .get("arms", {})
            .items()
        },
        "suite-seal.json: base-repository arm readiness differs from treatment lock",
    )
    if seal.get("status") != "frozen":
        return seal

    checks.check(
        not has_pending(seal), "suite-seal.json: frozen seal contains pending values"
    )
    try:
        sealed_at = datetime.fromisoformat(seal.get("sealed_at", ""))
    except (TypeError, ValueError):
        checks.errors.append("suite-seal.json: sealed_at is invalid")
    else:
        checks.check(
            sealed_at.tzinfo is not None, "suite-seal.json: sealed_at needs a timezone"
        )
    for asset_name, expected_ref in (
        ("protocol", PROTOCOL_REF),
        ("validator", "validate_dataset.py"),
    ):
        asset = seal.get(asset_name, {})
        checks.check(
            asset.get("ref") == expected_ref,
            f"suite-seal.json: {asset_name} ref mismatch",
        )
        asset_path = safe_evaluation_file(expected_ref)
        checks.check(
            asset_path is not None,
            f"suite-seal.json: {asset_name} is unsafe or missing",
        )
        if asset_path is not None:
            checks.check(
                hashlib.sha256(asset_path.read_bytes()).hexdigest()
                == asset.get("sha256"),
                f"suite-seal.json: {asset_name} sha256 mismatch",
            )
    schema_manifest = [
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(SCHEMA_PATHS.values())
    ]
    checks.check(
        seal.get("schemas_manifest_sha256") == canonical_hash(schema_manifest),
        "suite-seal.json: schemas manifest hash mismatch",
    )
    source_ref = seal.get("source_root_manifest", {})
    treatment_ref = seal.get("treatment_lock", {})
    checks.check(
        source_ref.get("ref") == "source-roots.json",
        "suite-seal.json: source-root ref mismatch",
    )
    checks.check(
        treatment_ref.get("ref") == TREATMENT_LOCK_REF,
        "suite-seal.json: treatment ref mismatch",
    )
    checks.check(
        source_ref.get("sha256")
        == hashlib.sha256((ROOT / "source-roots.json").read_bytes()).hexdigest(),
        "suite-seal.json: source-root manifest sha256 mismatch",
    )
    checks.check(
        treatment_ref.get("sha256")
        == hashlib.sha256(TREATMENT_LOCK_PATH.read_bytes()).hexdigest(),
        "suite-seal.json: treatment lock sha256 mismatch",
    )
    for entry in registered_cases:
        case_id = entry.get("case_id", "<missing>")
        expected_ref = EXPECTED_CASE_REFS.get(case_id, "")
        binding = case_seals.get(case_id, {})
        checks.check(
            binding.get("case_ref") == expected_ref,
            f"suite-seal.json/{case_id}: case ref mismatch",
        )
        if not expected_ref:
            continue
        case_dir = (ROOT / expected_ref).parent
        fixed_manifest = [
            {
                "path": relative,
                "sha256": hashlib.sha256(
                    (case_dir / relative).read_bytes()
                ).hexdigest(),
            }
            for relative in sorted(FIXED_CASE_ASSETS)
        ]
        checks.check(
            binding.get("fixed_assets_manifest_sha256")
            == canonical_hash(fixed_manifest),
            f"suite-seal.json/{case_id}: fixed-assets manifest hash mismatch",
        )
        case = checks.load_json(case_dir / "case.json")
        if isinstance(case, dict):
            checks.check(
                case.get("contamination", {}).get("level") in {"C0", "C1"},
                f"suite-seal.json/{case_id}: C2/C3 cases are diagnostic-only and cannot enter the formal seal",
            )
            runtime_refs = {
                "layers": case.get("layers"),
                "owner_answer_policy": case.get("owner_answer_policy"),
            }
            checks.check(
                binding.get("runtime_refs_manifest_sha256")
                == canonical_hash(runtime_refs),
                f"suite-seal.json/{case_id}: runtime refs manifest hash mismatch",
            )
            expected_result_class = {
                "historical_regression": "historical_regression",
                "prospective_pilot": "prospective_pilot",
                "prospective_holdout": "clean_prospective_holdout",
            }.get(case.get("stratum"))
            checks.check(
                binding.get("result_class") == expected_result_class,
                f"suite-seal.json/{case_id}: result class mismatch",
            )

    control_components = seal.get("control_components", {})
    checks.check(
        set(control_components) == set(CONTROL_COMPONENT_REFS),
        "suite-seal.json: control component registry mismatch",
    )
    seen_control_refs: set[str] = set()
    for component_id, expected_ref in CONTROL_COMPONENT_REFS.items():
        component = control_components.get(component_id, {})
        ref = component.get("ref", "") if isinstance(component, dict) else ""
        checks.check(
            ref == expected_ref,
            f"suite-seal.json/{component_id}: control component ref mismatch",
        )
        checks.check(
            ref not in seen_control_refs,
            f"suite-seal.json/{component_id}: duplicate control component ref",
        )
        seen_control_refs.add(ref)
        source = safe_runtime_control_path(ref, "runtime/seal-inputs")
        checks.check(
            source is not None,
            f"suite-seal.json/{component_id}: control component is unsafe or missing",
        )
        if source is not None:
            validate_control_document(
                checks,
                source.read_text(errors="replace"),
                component_id,
                f"suite-seal.json/{component_id}",
            )
            checks.check(
                hashlib.sha256(source.read_bytes()).hexdigest()
                == component.get("sha256"),
                f"suite-seal.json/{component_id}: control component sha256 mismatch",
            )
    run_plan = seal.get("run_plan", {})
    run_plan_assets = {
        "model_reasoning": run_plan.get("model", {}).get("reasoning_settings", {}),
        "judge_reasoning": run_plan.get("judge_model", {}).get(
            "reasoning_settings", {}
        ),
        "tool_manifest": run_plan.get("tooling", {}).get("tool_manifest", {}),
        "permission_manifest": run_plan.get("tooling", {}).get(
            "permission_manifest", {}
        ),
        "sandbox_policy": run_plan.get("tooling", {}).get("sandbox_policy", {}),
    }
    run_plan_schema_ids = {
        "model_reasoning": "reasoning_settings",
        "judge_reasoning": "reasoning_settings",
        "tool_manifest": "tool_manifest",
        "permission_manifest": "permission_manifest",
        "sandbox_policy": "sandbox_policy",
    }
    for asset_id, expected_ref in RUN_PLAN_ASSET_REFS.items():
        asset = run_plan_assets.get(asset_id, {})
        checks.check(
            asset.get("ref") == expected_ref,
            f"suite-seal.json/{asset_id}: run-plan asset ref mismatch",
        )
        source = safe_runtime_control_path(asset.get("ref", ""), "runtime/seal-inputs")
        checks.check(
            source is not None,
            f"suite-seal.json/{asset_id}: run-plan asset is unsafe or missing",
        )
        if source is None:
            continue
        try:
            structured = json.loads(source.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            checks.errors.append(
                f"suite-seal.json/{asset_id}: run-plan asset is not valid JSON: {exc}"
            )
        else:
            checks.check(
                isinstance(structured, dict) and bool(structured),
                f"suite-seal.json/{asset_id}: run-plan asset must be a nonempty JSON object",
            )
            checks.check(
                not has_pending(structured),
                f"suite-seal.json/{asset_id}: run-plan asset contains placeholder values",
            )
            asset_schema = checks.load_json(SCHEMA_PATHS[run_plan_schema_ids[asset_id]])
            if isinstance(asset_schema, dict):
                validate_schema_instance(checks, source, asset_schema)
            if asset_id == "tool_manifest":
                tool_names = [
                    item.get("name")
                    for item in structured.get("tools", [])
                    if isinstance(item, dict)
                ]
                checks.check(
                    len(tool_names) == len(set(tool_names)),
                    "suite-seal.json: duplicate tool names",
                )
        checks.check(
            hashlib.sha256(source.read_bytes()).hexdigest() == asset.get("sha256"),
            f"suite-seal.json/{asset_id}: run-plan asset sha256 mismatch",
        )
    ledger_ref = seal.get("run_ledger_schema", {})
    checks.check(
        ledger_ref.get("ref") == "schema/run-ledger.schema.json",
        "suite-seal.json: run-ledger schema ref mismatch",
    )
    ledger_path = safe_runtime_control_path(ledger_ref.get("ref", ""), "schema")
    checks.check(
        ledger_path is not None,
        "suite-seal.json: run-ledger schema is unsafe or missing",
    )
    if ledger_path is not None:
        checks.check(
            hashlib.sha256(ledger_path.read_bytes()).hexdigest()
            == ledger_ref.get("sha256"),
            "suite-seal.json: run-ledger schema sha256 mismatch",
        )
    return seal


def sealed_environment_observation(run_plan: dict[str, Any]) -> dict[str, Any]:
    """Project the materialized model and runner identities recorded by each run."""
    model = run_plan.get("model", {})
    judge_model = run_plan.get("judge_model", {})
    tooling = run_plan.get("tooling", {})
    return {
        "model": {
            "model_id": model.get("model_id"),
            "build_id": model.get("build_id"),
            "reasoning_settings_sha256": model.get("reasoning_settings", {}).get(
                "sha256"
            ),
        },
        "judge_model": {
            "model_id": judge_model.get("model_id"),
            "build_id": judge_model.get("build_id"),
            "reasoning_settings_sha256": judge_model.get("reasoning_settings", {}).get(
                "sha256"
            ),
        },
        "tooling": {
            "runner_image_digest": tooling.get("runner_image_digest"),
            "tool_manifest_sha256": tooling.get("tool_manifest", {}).get("sha256"),
            "permission_manifest_sha256": tooling.get("permission_manifest", {}).get(
                "sha256"
            ),
            "sandbox_policy_sha256": tooling.get("sandbox_policy", {}).get("sha256"),
        },
    }


def validate_run_ledgers(
    checks: Validation,
    schema: dict[str, Any],
    seal: dict[str, Any],
    require_complete_runs: bool,
) -> None:
    """Validate the exact eight-case by three-arm by repetition formal run matrix."""
    ledger_root = ROOT / "runtime/run-ledgers"
    if seal.get("status") != "frozen":
        checks.check(
            not require_complete_runs,
            "suite-seal.json: complete-run validation requires a frozen suite seal",
        )
        checks.check(
            not ledger_root.exists() and not ledger_root.is_symlink(),
            "runtime/run-ledgers: formal ledgers cannot exist before suite sealing",
        )
        return
    if not ledger_root.exists():
        checks.check(
            not require_complete_runs,
            "runtime/run-ledgers: complete formal run matrix is missing",
        )
        return
    safe_root = (
        ledger_root.is_dir()
        and not ledger_root.is_symlink()
        and has_exact_filesystem_spelling(ledger_root, ROOT)
        and not has_symlink_component(ledger_root, ROOT)
        and ledger_root.resolve().is_relative_to(ROOT.resolve())
    )
    checks.check(
        safe_root,
        "runtime/run-ledgers: ledger root must be one contained ordinary directory",
    )
    if not safe_root:
        return
    repetitions = seal.get("run_plan", {}).get("repetitions_per_case_arm")
    if not isinstance(repetitions, int):
        checks.errors.append("suite-seal.json: repetition count is invalid")
        return
    expected_matrix = {
        (case_id, arm_id, repetition): f"{case_id}-{arm_id}-r{repetition:02d}.json"
        for case_id in EXPECTED_CASE_REFS
        for arm_id in ("A", "A_USER", "B")
        for repetition in range(1, repetitions + 1)
    }
    actual_paths = [path for path in ledger_root.iterdir()]
    checks.check(
        all(path.is_file() and not path.is_symlink() for path in actual_paths),
        "runtime/run-ledgers: only ordinary JSON ledger files are allowed",
    )
    actual_names = {
        path.name for path in actual_paths if path.is_file() and not path.is_symlink()
    }
    checks.check(
        actual_names == set(expected_matrix.values()),
        "runtime/run-ledgers: formal case-arm-repetition matrix is incomplete or has extras",
    )
    suite_seal_hash = hashlib.sha256(SUITE_SEAL_PATH.read_bytes()).hexdigest()
    run_plan = seal.get("run_plan", {})
    expected_environment = sealed_environment_observation(run_plan)
    expected_controls = {
        component_id: component.get("sha256")
        for component_id, component in seal.get("control_components", {}).items()
        if isinstance(component, dict)
    }
    seen_run_ids: set[str] = set()
    for (case_id, arm_id, repetition), filename in sorted(expected_matrix.items()):
        path = ledger_root / filename
        if not path.is_file() or path.is_symlink():
            continue
        validate_schema_instance(checks, path, schema)
        ledger = checks.load_json(path)
        if not isinstance(ledger, dict):
            continue
        label = f"runtime/run-ledgers/{filename}"
        expected_run_id = filename.removesuffix(".json")
        checks.check(
            ledger.get("run_id") == expected_run_id,
            f"{label}: run_id differs from filename",
        )
        checks.check(expected_run_id not in seen_run_ids, f"{label}: duplicate run_id")
        seen_run_ids.add(expected_run_id)
        checks.check(
            ledger.get("status") == "complete",
            f"{label}: formal ledger is not complete",
        )
        checks.check(
            not has_pending(ledger),
            f"{label}: complete formal ledger contains pending values",
        )
        checks.check(
            (ledger.get("case_id"), ledger.get("arm_id"), ledger.get("repetition"))
            == (case_id, arm_id, repetition),
            f"{label}: case-arm-repetition identity mismatch",
        )
        checks.check(
            ledger.get("suite_seal")
            == {"ref": SUITE_SEAL_REF, "sha256": suite_seal_hash},
            f"{label}: suite seal binding mismatch",
        )
        checks.check(
            ledger.get("observed_run_plan_sha256") == canonical_hash(run_plan),
            f"{label}: observed run-plan hash mismatch",
        )
        checks.check(
            json_equal(ledger.get("observed_environment"), expected_environment),
            f"{label}: observed model/tool environment differs from seal",
        )
        checks.check(
            ledger.get("observed_refinement_sha256")
            == canonical_hash(run_plan.get("refinement", {})),
            f"{label}: observed refinement policy differs from seal",
        )
        checks.check(
            json_equal(ledger.get("control_component_hashes"), expected_controls),
            f"{label}: mapper/judge/control component hashes differ from seal",
        )
        case_binding = seal.get("case_assets", {}).get(case_id, {})
        checks.check(
            ledger.get("case_runtime_refs_manifest_sha256")
            == case_binding.get("runtime_refs_manifest_sha256"),
            f"{label}: case runtime-ref binding mismatch",
        )
        case_path = ROOT / EXPECTED_CASE_REFS[case_id]
        case = checks.load_json(case_path)
        if not isinstance(case, dict):
            continue
        treatment_binding = case.get("layers", {}).get("arm_bundle", {})
        owner_binding = case.get("owner_answer_policy", {})
        treatment_path = runtime_ref_path(
            checks, case_id, treatment_binding, f"{label}/treatment"
        )
        owner_path = runtime_ref_path(
            checks, case_id, owner_binding, f"{label}/owner-policy"
        )
        if treatment_path is not None:
            treatment_sha = hashlib.sha256(treatment_path.read_bytes()).hexdigest()
            checks.check(
                ledger.get("treatment_manifest_sha256") == treatment_sha,
                f"{label}: treatment hash mismatch",
            )
            treatment = checks.load_json(treatment_path)
            if isinstance(treatment, dict):
                arm = treatment.get("arms", {}).get(arm_id, {})
                export = arm.get("export", {}) if isinstance(arm, dict) else {}
                checks.check(
                    ledger.get("s0_export_manifest_sha256")
                    == export.get("files_manifest_sha256"),
                    f"{label}: S0 export manifest hash mismatch",
                )
                export_root_text = export.get("materialized_root", "")
                export_root = ROOT / export_root_text
                safe_export_root = (
                    canonical_relative_path(export_root_text) == export_root_text
                    and path_is_within(export_root_text, f"runtime/{case_id}/exports")
                    and export_root.is_dir()
                    and not export_root.is_symlink()
                    and not has_symlink_component(export_root, ROOT)
                    and export_root.resolve().is_relative_to(ROOT.resolve())
                )
                checks.check(
                    safe_export_root,
                    f"{label}: treatment export root is unsafe or missing",
                )
                if safe_export_root:
                    try:
                        actual_commit = (
                            git_bytes_at(export_root, "rev-parse", "HEAD")
                            .decode()
                            .strip()
                        )
                    except RuntimeError as exc:
                        checks.errors.append(
                            f"{label}: cannot read fresh-root commit: {exc}"
                        )
                    else:
                        checks.check(
                            ledger.get("fresh_root_commit") == actual_commit,
                            f"{label}: fresh-root commit mismatch",
                        )
        if owner_path is not None:
            checks.check(
                ledger.get("owner_policy_sha256")
                == hashlib.sha256(owner_path.read_bytes()).hexdigest(),
                f"{label}: owner-answer policy hash mismatch",
            )
        budgets = case.get("budgets", {})
        counters = ledger.get("counters", {})
        if isinstance(budgets, dict) and isinstance(counters, dict):
            checks.check(
                counters.get("model_calls", 0) <= budgets.get("max_model_calls", -1),
                f"{label}: model-call budget exceeded",
            )
            checks.check(
                counters.get("input_tokens", 0) <= budgets.get("max_input_tokens", -1),
                f"{label}: input-token budget exceeded",
            )
            checks.check(
                counters.get("output_tokens", 0)
                <= budgets.get("max_output_tokens", -1),
                f"{label}: output-token budget exceeded",
            )
            checks.check(
                counters.get("wall_seconds", 0)
                <= budgets.get("wall_time_minutes", -1) * 60,
                f"{label}: wall-time budget exceeded",
            )
            checks.check(
                counters.get("user_active_seconds", 0)
                <= counters.get("wall_seconds", -1),
                f"{label}: user-active time exceeds wall time",
            )


def validate_locked_component(
    checks: Validation,
    component: dict[str, Any],
    label: str,
    allowed_roles: set[str],
    require_nonempty: bool,
) -> list[dict[str, Any]]:
    """Validate a human-auditable suite source closure and visible identity."""
    dependencies = [
        item for item in component.get("dependencies", []) if isinstance(item, dict)
    ]
    checks.check(
        not require_nonempty or bool(dependencies),
        f"{label}: frozen component is empty",
    )
    checks.check(
        all(item.get("role") in allowed_roles for item in dependencies),
        f"{label}: dependency role differs from component role",
    )
    source_paths = [item.get("source_path") for item in dependencies]
    installed_paths = [item.get("installed_path") for item in dependencies]
    checks.check(
        len(source_paths) == len(set(source_paths)), f"{label}: duplicate source paths"
    )
    checks.check(
        len(installed_paths) == len(set(installed_paths)),
        f"{label}: duplicate installed paths",
    )
    for item in dependencies:
        source_path = item.get("source_path", "")
        installed_path = item.get("installed_path", "")
        checks.check(
            canonical_relative_path(source_path) == source_path
            and canonical_relative_path(installed_path) == installed_path,
            f"{label}: dependency path is not canonical",
        )
        checks.check(
            not path_is_within(source_path, "runtime")
            and not path_is_within(source_path, EVALUATION_CONTROL_ROOT),
            f"{label}: workflow/shared/artifact source enters runtime or evaluation controls: {source_path}",
        )
        checks.check(
            not path_is_within(installed_path, ".git")
            and not is_case_control_path(installed_path)
            and not path_is_within(installed_path, EVALUATION_CONTROL_ROOT),
            f"{label}: forbidden installed path: {installed_path}",
        )
        source = safe_source_dependency_path(source_path)
        checks.check(
            source is not None, f"{label}: source is unsafe or missing: {source_path}"
        )
        if source is not None:
            actual_mode = "100755" if source.stat().st_mode & 0o111 else "100644"
            checks.check(
                actual_mode == item.get("mode"),
                f"{label}: source mode mismatch: {source_path}",
            )
            checks.check(
                hashlib.sha256(source.read_bytes()).hexdigest() == item.get("sha256"),
                f"{label}: source sha256 mismatch: {source_path}",
            )
    checks.check(
        canonical_hash(locked_source_manifest(dependencies))
        == component.get("dependency_manifest_sha256"),
        f"{label}: source dependency manifest hash mismatch",
    )
    checks.check(
        canonical_hash(candidate_dependency_manifest(dependencies))
        == component.get("candidate_manifest_sha256"),
        f"{label}: candidate-visible manifest hash mismatch",
    )
    return dependencies


def lineage_source_bytes(checks: Validation, ref: str, label: str) -> bytes | None:
    """Resolve a pinned repo, Git, or case evidence ref used by a lineage entry."""
    if not isinstance(ref, str):
        checks.errors.append(f"{label}: lineage evidence ref must be a string")
        return None
    raw_ref, anchor = split_anchor(ref)
    if anchor is not None and LINE_ANCHOR_RE.fullmatch(anchor) is None:
        checks.errors.append(f"{label}: lineage evidence needs an Lx or Lx-Ly anchor")
        return None
    try:
        scheme, remainder = raw_ref.split(":", 1)
    except ValueError:
        checks.errors.append(f"{label}: lineage evidence ref has no supported scheme")
        return None
    content: bytes | None = None
    if scheme == "repo":
        if (
            canonical_relative_path(remainder) != remainder
            or path_is_within(remainder, ".git")
            or path_is_within(remainder, EVALUATION_CONTROL_ROOT)
        ):
            checks.errors.append(f"{label}: repository evidence path is not canonical")
            return None
        lexical = REPO / remainder
        if (
            has_exact_filesystem_spelling(lexical, REPO)
            and not has_symlink_component(lexical, REPO)
            and lexical.is_file()
            and lexical.resolve().is_relative_to(REPO.resolve())
            and not lexical.resolve().is_relative_to(ROOT.resolve())
        ):
            content = lexical.read_bytes()
    elif scheme == "git":
        commit, separator, path_text = remainder.partition(":")
        if (
            not separator
            or SHA_RE.fullmatch(commit) is None
            or canonical_relative_path(path_text) != path_text
            or path_is_within(path_text, EVALUATION_CONTROL_ROOT)
        ):
            checks.errors.append(f"{label}: historical Git evidence ref is malformed")
            return None
        try:
            content = git_bytes("show", f"{commit}:{path_text}")
        except RuntimeError as exc:
            checks.errors.append(
                f"{label}: historical Git evidence is unreadable: {exc}"
            )
            return None
    elif scheme == "case":
        case_id, separator, path_text = remainder.partition(":")
        case_ref = EXPECTED_CASE_REFS.get(case_id)
        if (
            not separator
            or case_ref is None
            or canonical_relative_path(path_text) != path_text
        ):
            checks.errors.append(f"{label}: case evidence ref is malformed")
            return None
        case_dir = (ROOT / case_ref).parent
        lexical = case_dir / path_text
        if (
            has_exact_filesystem_spelling(lexical, case_dir)
            and not has_symlink_component(lexical, case_dir)
            and lexical.is_file()
            and lexical.resolve().is_relative_to(case_dir.resolve())
        ):
            content = lexical.read_bytes()
    else:
        checks.errors.append(f"{label}: unsupported lineage evidence scheme {scheme!r}")
        return None
    if content is None:
        checks.errors.append(
            f"{label}: lineage evidence does not resolve to one ordinary file"
        )
        return None
    if anchor is not None:
        match = LINE_ANCHOR_RE.fullmatch(anchor)
        assert match is not None
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        checks.check(
            start <= end <= len(content.splitlines()),
            f"{label}: lineage evidence anchor is out of range",
        )
    return content


def validate_lineage_manifest(
    checks: Validation,
    schema: dict[str, Any],
    component: dict[str, Any],
    dependencies: list[dict[str, Any]],
    expected_kind: str,
    label: str,
    profile_case_id: str | None = None,
) -> dict[str, set[str]]:
    """Validate the task-blind semantic lineage audit bound to one component."""
    component_id = component.get("component_id", "")
    ref = component.get("lineage_manifest_ref", "")
    expected_ref = f"runtime/lineage/{component_id}.json"
    checks.check(ref == expected_ref, f"{label}: lineage manifest ref mismatch")
    path = safe_runtime_control_path(ref, "runtime/lineage")
    checks.check(path is not None, f"{label}: lineage manifest is unsafe or missing")
    if path is None:
        return {"generic_historical_learning": set(), "target_derived": set()}
    validate_schema_instance(checks, path, schema)
    checks.check(
        hashlib.sha256(path.read_bytes()).hexdigest()
        == component.get("lineage_manifest_sha256"),
        f"{label}: lineage manifest sha256 mismatch",
    )
    manifest = checks.load_json(path)
    if not isinstance(manifest, dict):
        return {"generic_historical_learning": set(), "target_derived": set()}
    checks.check(
        manifest.get("status") == "frozen", f"{label}: lineage manifest must be frozen"
    )
    checks.check(
        not has_pending(manifest),
        f"{label}: frozen lineage manifest contains pending values",
    )
    checks.check(
        manifest.get("kind") == expected_kind, f"{label}: lineage kind mismatch"
    )
    checks.check(
        manifest.get("subject_component_id") == component_id,
        f"{label}: lineage component id mismatch",
    )
    checks.check(
        manifest.get("subject_manifest_sha256")
        == component.get("dependency_manifest_sha256"),
        f"{label}: lineage subject manifest hash mismatch",
    )
    review = manifest.get("review", {})
    checks.check(
        review.get("status") == "task_blind_approved",
        f"{label}: lineage lacks task-blind approval",
    )
    entries = [item for item in manifest.get("entries", []) if isinstance(item, dict)]
    checks.check(
        bool(entries) or not dependencies,
        f"{label}: nonempty frozen component has no lineage entries",
    )
    entry_ids = [item.get("entry_id") for item in entries]
    checks.check(
        len(entry_ids) == len(set(entry_ids)), f"{label}: duplicate lineage entry ids"
    )
    dependency_paths = {item.get("source_path") for item in dependencies}
    retained_paths: set[str] = set()
    retained_ranges: dict[str, set[int]] = {}
    retained_case_lineages = {
        "generic_historical_learning": set(),
        "target_derived": set(),
    }
    for entry in entries:
        entry_id = entry.get("entry_id", "<missing>")
        entry_label = f"{label}/{entry_id}"
        subject_path = entry.get("subject_path", "")
        checks.check(
            canonical_relative_path(subject_path) == subject_path,
            f"{entry_label}: subject path is not canonical",
        )
        start = entry.get("start_line")
        end = entry.get("end_line")
        checks.check(
            isinstance(start, int) and isinstance(end, int) and start <= end,
            f"{entry_label}: invalid subject line range",
        )
        affected = set(entry.get("affected_case_ids", []))
        checks.check(
            affected <= set(EXPECTED_CASE_REFS),
            f"{entry_label}: unknown affected case id",
        )
        lineage_class = entry.get("lineage_class")
        if lineage_class == "independent":
            checks.check(
                not affected,
                f"{entry_label}: independent content cannot name an affected target case",
            )
        elif lineage_class in retained_case_lineages:
            checks.check(
                bool(affected),
                f"{entry_label}: contaminated content must name affected target cases",
            )
            retained_case_lineages[lineage_class].update(affected)
        checks.check(
            entry.get("disposition") == "retain",
            f"{entry_label}: final candidate-visible lineage manifests may only inventory retained bytes",
        )
        source_case_ids: set[str] = set()
        for source_index, source_lineage in enumerate(entry.get("source_lineages", [])):
            if not isinstance(source_lineage, dict):
                continue
            source_label = f"{entry_label}/source_lineages/{source_index}"
            source_ref = source_lineage.get("ref", "")
            source_scheme = (
                source_ref.split(":", 1)[0] if isinstance(source_ref, str) else ""
            )
            source_kind = source_lineage.get("kind")
            allowed_schemes = {
                "repository_fact": {"repo", "git"},
                "historical_change": {"git", "case"},
                "independent_user_evidence": {"case"},
                "original_workflow_design": {"repo", "git"},
                "general_method": {"repo", "git"},
            }
            checks.check(
                source_scheme in allowed_schemes.get(source_kind, set()),
                f"{source_label}: lineage kind and evidence scheme disagree",
            )
            if source_scheme == "case" and isinstance(source_ref, str):
                source_case_id = source_ref.split(":", 2)[1]
                if source_case_id in EXPECTED_CASE_REFS:
                    source_case_ids.add(source_case_id)
            content = lineage_source_bytes(checks, source_ref, source_label)
            if content is not None:
                checks.check(
                    hashlib.sha256(content).hexdigest()
                    == source_lineage.get("evidence_sha256"),
                    f"{source_label}: lineage evidence sha256 mismatch",
                )
        if source_case_ids:
            checks.check(
                lineage_class == "target_derived",
                f"{entry_label}: case-control evidence must be classified target_derived",
            )
            checks.check(
                source_case_ids <= affected,
                f"{entry_label}: case-control evidence ids must be included in affected_case_ids",
            )
            if profile_case_id is not None:
                checks.check(
                    profile_case_id not in source_case_ids,
                    f"{entry_label}: cross-fitted profile cites its own case-control evidence",
                )
        if entry.get("disposition") == "retain":
            retained_paths.add(subject_path)
            checks.check(
                subject_path in dependency_paths,
                f"{entry_label}: retained subject is outside component closure",
            )
            source = safe_source_dependency_path(subject_path)
            checks.check(
                source is not None,
                f"{entry_label}: retained subject source is unsafe or missing",
            )
            if source is not None and isinstance(end, int):
                source_lines = source.read_bytes().splitlines(keepends=True)
                checks.check(
                    end <= len(source_lines),
                    f"{entry_label}: subject line range exceeds file",
                )
                if isinstance(start, int) and start <= end:
                    covered_lines = set(range(start, end + 1))
                    overlap = (
                        retained_ranges.setdefault(subject_path, set()) & covered_lines
                    )
                    checks.check(
                        not overlap,
                        f"{entry_label}: semantic range overlaps another entry: {sorted(overlap)[:10]}",
                    )
                    retained_ranges[subject_path].update(covered_lines)
                    if end <= len(source_lines):
                        subject_slice = b"".join(source_lines[start - 1 : end])
                        checks.check(
                            hashlib.sha256(subject_slice).hexdigest()
                            == entry.get("subject_slice_sha256"),
                            f"{entry_label}: semantic slice sha256 mismatch",
                        )
        if profile_case_id is not None and profile_case_id in affected:
            checks.check(
                False,
                f"{entry_label}: cross-fitted profile contains its own target lineage",
            )
    checks.check(
        retained_paths == dependency_paths,
        f"{label}: retained lineage coverage must name every dependency source path",
    )
    for dependency_path in dependency_paths:
        source = safe_source_dependency_path(dependency_path or "")
        if source is None:
            continue
        required_lines = {
            index
            for index, line in enumerate(
                source.read_text(errors="replace").splitlines(), start=1
            )
            if line.strip()
        }
        uncovered = sorted(required_lines - retained_ranges.get(dependency_path, set()))
        checks.check(
            not uncovered,
            f"{label}: nonblank candidate-visible lines lack lineage coverage in {dependency_path}: {uncovered[:10]}",
        )
    return retained_case_lineages


def leak_patterns(
    path: Path, checks: Validation, case_id: str
) -> list[tuple[str, re.Pattern[str]]]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        pattern_text = raw_line.strip()
        if not pattern_text or pattern_text.startswith("#"):
            continue
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            checks.errors.append(
                f"{case_id}/leak-signatures:{line_number}: invalid regex: {exc}"
            )
            continue
        patterns.append((pattern_text, pattern))
    return patterns


def scan_entries_for_leaks(
    checks: Validation,
    entries: dict[str, dict[str, Any]],
    patterns: list[tuple[str, re.Pattern[str]]],
    label: str,
) -> None:
    decoded: dict[str, list[str]] = {}
    for path, entry in entries.items():
        content = entry["content"]
        texts: list[str] = []
        try:
            texts.append(content.decode("utf-8"))
        except UnicodeDecodeError:
            if Path(path).suffix.lower() in TEXT_SUFFIXES:
                checks.errors.append(f"{label}: text file is not valid UTF-8: {path}")
        if b"\x00" in content:
            if Path(path).suffix.lower() in TEXT_SUFFIXES:
                checks.errors.append(f"{label}: text file contains NUL bytes: {path}")
            for encoding in ("utf-16-le", "utf-16-be"):
                try:
                    texts.append(content.decode(encoding))
                except UnicodeDecodeError:
                    pass
        decoded[path] = texts
    for pattern_text, pattern in patterns:
        hit = next(
            (
                path
                for path in entries
                if pattern.search(path)
                or any(pattern.search(text) for text in decoded[path])
            ),
            None,
        )
        checks.check(
            hit is None, f"{label}: filtered source leaks {pattern_text!r} via {hit}"
        )


def scan_entries_for_atoms(
    checks: Validation,
    entries: dict[str, dict[str, Any]],
    atoms: list[str] | tuple[str, ...],
    label: str,
) -> None:
    """Reject fixed suite-control atoms in candidate paths or text files."""
    for atom in atoms:
        lowered = atom.lower()
        encoded_atoms = [
            lowered.encode("utf-8"),
            lowered.encode("utf-16-le"),
            lowered.encode("utf-16-be"),
        ]
        hit = next(
            (
                path
                for path, entry in entries.items()
                if lowered in path.lower()
                or any(encoded in entry["content"].lower() for encoded in encoded_atoms)
            ),
            None,
        )
        checks.check(
            hit is None, f"{label}: suite guardrail atom {atom!r} survives via {hit}"
        )


def is_case_control_path(path: str) -> bool:
    """Return whether a candidate-relative path belongs to the case control plane."""
    return any(path_is_within(path, prefix.rstrip("/")) for prefix in CONTROL_PREFIXES)


def validate_case_source_roots(
    checks: Validation,
    case: dict[str, Any],
    case_dir: Path,
    authorities: dict[str, dict[str, Any]],
    source_registry: dict[str, dict[str, Any]],
) -> None:
    case_id = case.get("case_id", "<missing>")
    source_ids = case.get("source_root_ids", [])
    sources = [
        source_registry[source_id]
        for source_id in source_ids
        if source_id in source_registry
    ]
    checks.check(len(sources) == len(source_ids), f"{case_id}: unknown source_root_id")
    project_sources = [
        item for item in sources if item["source"].get("kind") == "project_repository"
    ]
    checks.check(
        len(project_sources) == 1,
        f"{case_id}: exactly one project source root is required",
    )
    if project_sources:
        project_cutoff = project_sources[0]["source"]["cutoff_ref"]
        repository_cutoffs = {
            item.get("source", {}).get("cutoff_ref")
            for item in authorities.values()
            if item.get("source", {}).get("kind") in {"repo_file", "repo_tree", "none"}
        }
        checks.check(
            repository_cutoffs == {project_cutoff},
            f"{case_id}: authority cutoffs differ from project source root",
        )

    external_sources = [
        item for item in sources if item["source"].get("kind") == "external_repository"
    ]
    external_authorities = [
        item
        for item in authorities.values()
        if item.get("source", {}).get("kind") == "external_snapshot"
    ]
    checks.check(
        len(external_sources) == len(external_authorities),
        f"{case_id}: external source/authority count mismatch",
    )
    for authority in external_authorities:
        source = authority["source"]
        matches = [
            item
            for item in external_sources
            if item["source"]["cutoff_ref"] == source.get("cutoff_ref")
        ]
        checks.check(
            len(matches) == 1,
            f"{case_id}/{authority.get('authority_id')}: external source root mismatch",
        )
        if len(matches) == 1:
            expected = matches[0]["actual"]["raw_archive_sha256"]
            checks.check(
                source.get("sha256") == expected,
                f"{case_id}/{authority.get('authority_id')}: raw archive sha256 mismatch",
            )

    patterns = leak_patterns(case_dir / "audit/leak-signatures.txt", checks, case_id)
    for source in sources:
        scan_entries_for_leaks(
            checks,
            source["actual"]["filtered_entries"],
            patterns,
            f"{case_id}/{source['source']['source_id']}",
        )


def runtime_tree_entries(root: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for path in root.rglob("*"):
        relative = str(path.relative_to(root)).replace("\\", "/")
        if path_is_within(relative, ".git"):
            continue
        if path.is_symlink():
            entries[relative] = {
                "mode": "120000",
                "content": os.readlink(path).encode(),
            }
        elif path.is_file():
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
            entries[relative] = {"mode": mode, "content": path.read_bytes()}
    return entries


def git_object_payloads(
    repository: Path, object_ids: list[str]
) -> dict[str, tuple[str, bytes]]:
    """Read raw reachable object payloads in one non-filtering batch."""
    request = b"".join(f"{object_id}\n".encode() for object_id in object_ids)
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repository,
        env=isolated_git_environment(),
        input=request,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    cursor = 0
    payloads: dict[str, tuple[str, bytes]] = {}
    for requested_id in object_ids:
        line_end = result.stdout.find(b"\n", cursor)
        if line_end < 0:
            raise RuntimeError("truncated git cat-file object header")
        header = result.stdout[cursor:line_end].split()
        if len(header) != 3 or header[0].decode() != requested_id:
            raise RuntimeError(f"unexpected git cat-file header for {requested_id}")
        object_type = header[1].decode()
        size = int(header[2])
        start = line_end + 1
        end = start + size
        if end >= len(result.stdout) or result.stdout[end : end + 1] != b"\n":
            raise RuntimeError(f"truncated git cat-file payload for {requested_id}")
        payloads[requested_id] = (object_type, result.stdout[start:end])
        cursor = end + 1
    return payloads


def validate_fresh_root_git(
    checks: Validation,
    export_root: Path,
    expected_entries: dict[str, dict[str, Any]],
    label: str,
) -> None:
    """Prove one byte-canonical local Git root with no metadata side channel."""
    aliases = [
        child.name
        for child in export_root.iterdir()
        if unicodedata.normalize("NFC", child.name).casefold() == ".git"
    ]
    checks.check(
        aliases == [".git"],
        f"{label}: fresh root needs exactly one canonical .git directory",
    )
    git_dir = export_root / ".git"
    safe_git_dir = (
        git_dir.is_dir()
        and not git_dir.is_symlink()
        and has_exact_filesystem_spelling(git_dir, export_root)
        and not has_symlink_component(git_dir, export_root)
        and git_dir.resolve().is_relative_to(export_root.resolve())
    )
    checks.check(safe_git_dir, f"{label}: .git must be a contained ordinary directory")
    if not safe_git_dir:
        return

    metadata_symlinks = [
        path.relative_to(git_dir) for path in git_dir.rglob("*") if path.is_symlink()
    ]
    checks.check(
        not metadata_symlinks,
        f"{label}: Git metadata contains symlinks: {metadata_symlinks[:5]}",
    )
    if metadata_symlinks:
        return

    expected_root_children = {"HEAD", "config", "index", "objects", "refs"}
    actual_root_children = {path.name for path in git_dir.iterdir()}
    checks.check(
        actual_root_children == expected_root_children,
        f"{label}: .git root differs from the canonical envelope: {sorted(actual_root_children)}",
    )
    for filename in ("HEAD", "config", "index"):
        checks.check(
            (git_dir / filename).is_file(),
            f"{label}: .git/{filename} must be an ordinary file",
        )
    for dirname in ("objects", "refs"):
        checks.check(
            (git_dir / dirname).is_dir(),
            f"{label}: .git/{dirname} must be an ordinary directory",
        )
    if actual_root_children != expected_root_children or not all(
        (git_dir / dirname).is_dir() for dirname in ("objects", "refs")
    ):
        return

    expected_head = f"ref: refs/heads/{FRESH_ROOT_BRANCH}\n".encode()
    checks.check(
        (git_dir / "HEAD").read_bytes() == expected_head,
        f"{label}: .git/HEAD bytes differ",
    )
    checks.check(
        (git_dir / "config").read_bytes() == FRESH_ROOT_CONFIG,
        f"{label}: .git/config bytes differ",
    )

    refs_dir = git_dir / "refs"
    heads_dir = refs_dir / "heads"
    checks.check(
        {path.name for path in refs_dir.iterdir()} == {"heads"},
        f"{label}: .git/refs is not canonical",
    )
    checks.check(heads_dir.is_dir(), f"{label}: .git/refs/heads must be a directory")
    if not heads_dir.is_dir():
        return
    expected_ref_name = FRESH_ROOT_BRANCH
    checks.check(
        {path.name for path in heads_dir.iterdir()} == {expected_ref_name},
        f"{label}: .git/refs/heads is not canonical",
    )
    head_ref = heads_dir / expected_ref_name
    if not head_ref.is_file():
        checks.errors.append(f"{label}: fixed branch ref is missing")
        return
    raw_head_oid = head_ref.read_bytes()
    head_oid = raw_head_oid.removesuffix(b"\n").decode(errors="replace")
    checks.check(
        raw_head_oid == f"{head_oid}\n".encode(), f"{label}: branch ref bytes differ"
    )
    checks.check(
        bool(re.fullmatch(r"[a-f0-9]{40}", head_oid)),
        f"{label}: branch ref is not a SHA-1 object id",
    )
    if not re.fullmatch(r"[a-f0-9]{40}", head_oid):
        return

    objects_dir = git_dir / "objects"
    object_children = {path.name for path in objects_dir.iterdir()}
    checks.check(
        {"info", "pack"} <= object_children,
        f"{label}: canonical object support directories are missing",
    )
    for dirname in ("info", "pack"):
        directory = objects_dir / dirname
        checks.check(
            directory.is_dir(), f"{label}: .git/objects/{dirname} must be a directory"
        )
        if directory.is_dir():
            checks.check(
                not any(directory.iterdir()),
                f"{label}: .git/objects/{dirname} must be empty",
            )
    loose_dirs = object_children - {"info", "pack"}
    checks.check(
        all(re.fullmatch(r"[a-f0-9]{2}", name) for name in loose_dirs),
        f"{label}: object store contains a non-canonical directory",
    )
    checks.check(
        all((objects_dir / name).is_dir() for name in loose_dirs),
        f"{label}: loose object fanout contains a non-directory",
    )

    def git_text(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=export_root,
            env=isolated_git_environment(),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    try:
        top_level = git_text("rev-parse", "--show-toplevel")
        absolute_git_dir = git_text("rev-parse", "--absolute-git-dir")
        common_dir_text = git_text("rev-parse", "--git-common-dir")
        common_dir = Path(common_dir_text)
        if not common_dir.is_absolute():
            common_dir = export_root / common_dir
        checks.check(
            Path(top_level).resolve() == export_root.resolve(),
            f"{label}: Git top-level escapes export",
        )
        checks.check(
            Path(absolute_git_dir).resolve() == git_dir.resolve(),
            f"{label}: git-dir differs from local .git",
        )
        checks.check(
            common_dir.resolve() == git_dir.resolve(),
            f"{label}: git-common-dir differs from local .git",
        )

        checks.check(
            git_text("rev-list", "--all", "--count") == "1",
            f"{label}: fresh root needs one commit",
        )
        head_parents = git_text("rev-list", "--parents", "-n", "1", "HEAD")
        checks.check(
            head_parents == head_oid,
            f"{label}: HEAD must be the fixed parentless root commit",
        )
        checks.check(
            git_text("for-each-ref", "--format=%(refname)")
            == f"refs/heads/{FRESH_ROOT_BRANCH}",
            f"{label}: fresh root exposes an unexpected ref",
        )

        tree_oid = git_text("rev-parse", "HEAD^{tree}")
        raw_commit = git_bytes_at(export_root, "cat-file", "commit", "HEAD")
        expected_commit = (
            f"tree {tree_oid}\n"
            f"author {FRESH_ROOT_IDENTITY[0]} <{FRESH_ROOT_IDENTITY[1]}> {FRESH_ROOT_EPOCH} +0000\n"
            f"committer {FRESH_ROOT_IDENTITY[0]} <{FRESH_ROOT_IDENTITY[1]}> {FRESH_ROOT_EPOCH} +0000\n"
            f"\n{FRESH_ROOT_COMMIT_MESSAGE}\n"
        ).encode()
        checks.check(
            raw_commit == expected_commit, f"{label}: raw root commit bytes differ"
        )
        canonical_commit_oid = hashlib.sha1(  # noqa: S324 - Git SHA-1 object identity is the protocol.
            f"commit {len(expected_commit)}\0".encode() + expected_commit
        ).hexdigest()
        checks.check(
            head_oid == canonical_commit_oid,
            f"{label}: root commit id is not canonical",
        )

        reachable_ids = sorted(
            set(
                git_text(
                    "rev-list", "--objects", "--no-object-names", "HEAD"
                ).splitlines()
            )
        )
        checks.check(
            head_oid in reachable_ids,
            f"{label}: HEAD is missing from reachable object closure",
        )
        payloads = git_object_payloads(export_root, reachable_ids)
        expected_loose_paths: set[str] = set()
        for object_id, (object_type, payload) in payloads.items():
            expected_loose_paths.add(f"{object_id[:2]}/{object_id[2:]}")
            loose_path = objects_dir / object_id[:2] / object_id[2:]
            canonical_object = f"{object_type} {len(payload)}\0".encode() + payload
            canonical_loose_bytes = zlib.compress(canonical_object, level=9)
            checks.check(
                loose_path.is_file(),
                f"{label}: reachable object is not loose: {object_id}",
            )
            if loose_path.is_file():
                checks.check(
                    loose_path.read_bytes() == canonical_loose_bytes,
                    f"{label}: loose object bytes are not canonical: {object_id}",
                )
        actual_loose_paths = {
            f"{directory.name}/{path.name}"
            for directory in objects_dir.iterdir()
            if re.fullmatch(r"[a-f0-9]{2}", directory.name) and directory.is_dir()
            for path in directory.iterdir()
            if path.is_file()
        }
        checks.check(
            actual_loose_paths == expected_loose_paths,
            f"{label}: loose object closure differs from HEAD",
        )
        checks.check(
            loose_dirs == {path.split("/", 1)[0] for path in expected_loose_paths},
            f"{label}: loose object fanout directories differ from HEAD closure",
        )
        for directory in objects_dir.iterdir():
            if re.fullmatch(r"[a-f0-9]{2}", directory.name) and directory.is_dir():
                checks.check(
                    all(
                        path.is_file() and re.fullmatch(r"[a-f0-9]{38}", path.name)
                        for path in directory.iterdir()
                    ),
                    f"{label}: malformed loose object path under {directory.name}",
                )

        with tempfile.TemporaryDirectory(prefix="feat397-index-") as temporary_dir:
            canonical_index = Path(temporary_dir) / "index"
            index_environment = isolated_git_environment()
            index_environment["GIT_INDEX_FILE"] = str(canonical_index)
            result = subprocess.run(
                ["git", "read-tree", "HEAD"],
                cwd=export_root,
                env=index_environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace").strip())
            checks.check(
                (git_dir / "index").read_bytes() == canonical_index.read_bytes(),
                f"{label}: .git/index bytes differ from the canonical HEAD index",
            )

        status = git_text(
            "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"
        )
        checks.check(not status, f"{label}: fresh root worktree differs from HEAD")
        fsck = git_text(
            "fsck", "--full", "--no-reflogs", "--unreachable", "--no-progress"
        )
        checks.check(not fsck, f"{label}: fresh root contains unreachable Git objects")
        head_entries = git_head_entries(export_root)
        checks.check(
            file_manifest(head_entries) == file_manifest(expected_entries),
            f"{label}: HEAD tree differs from the candidate content manifest",
        )
    except (OSError, RuntimeError, ValueError) as exc:
        checks.errors.append(f"{label}: cannot validate fresh-root Git envelope: {exc}")


def runtime_ref_path(
    checks: Validation, case_id: str, ref: dict[str, Any], label: str
) -> Path | None:
    path_text = ref.get("manifest_ref", "") if isinstance(ref, dict) else ""
    checks.check(
        canonical_relative_path(path_text) == path_text,
        f"{label}: manifest_ref is not canonical",
    )
    checks.check(
        path_text.startswith(f"runtime/{case_id}/"),
        f"{label}: manifest_ref must use runtime/{case_id}/",
    )
    path, anchor = split_anchor(path_text)
    checks.check(
        anchor is None, f"{label}: layer manifest_ref cannot contain an anchor"
    )
    resolved = (ROOT / path).resolve()
    checks.check(
        resolved.is_relative_to(ROOT.resolve()),
        f"{label}: runtime manifest escapes evaluation root",
    )
    return (
        resolved
        if path
        and canonical_relative_path(path) == path
        and anchor is None
        and resolved.is_relative_to(ROOT.resolve())
        else None
    )


def validate_runtime_ref_contract(checks: Validation, case: dict[str, Any]) -> None:
    case_id = case.get("case_id", "<missing>")
    layers = case.get("layers", {})
    if not isinstance(layers, dict):
        return
    refs: dict[str, str] = {}
    for layer_name in (
        "product_world",
        "documentation_world",
        "common_compatibility",
        "arm_bundle",
    ):
        ref = layers.get(layer_name, {})
        runtime_ref_path(checks, case_id, ref, f"{case_id}/{layer_name}")
        if isinstance(ref, dict):
            refs[layer_name] = ref.get("manifest_ref", "")
    checks.check(
        len(set(refs.values())) == 4, f"{case_id}: layer manifest refs must be unique"
    )
    treatment_ref = refs.get("arm_bundle", "")
    arms = case.get("arms", {})
    if isinstance(arms, dict):
        for arm_id in ("A", "A_USER", "B"):
            arm = arms.get(arm_id, {})
            expected = f"{treatment_ref}#/arms/{arm_id}"
            checks.check(
                isinstance(arm, dict) and arm.get("bundle_ref") == expected,
                f"{case_id}/{arm_id}: bundle_ref mismatch",
            )
    owner_policy = case.get("owner_answer_policy", {})
    checks.check(
        isinstance(owner_policy, dict)
        and owner_policy.get("manifest_ref")
        == f"runtime/{case_id}/private/owner-answer-policy.json",
        f"{case_id}: owner-answer-policy ref mismatch",
    )


def has_pending(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"pending", "tbd", "placeholder"}
    if isinstance(value, dict):
        return any(has_pending(item) for item in value.values())
    if isinstance(value, list):
        return any(has_pending(item) for item in value)
    return False


def validate_layer_manifest(
    checks: Validation,
    case: dict[str, Any],
    layer_name: str,
    schema: dict[str, Any],
    source_registry: dict[str, dict[str, Any]],
    source_manifest_hash: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    historical_entries: dict[str, dict[str, Any]] | None = None,
    suite_binding: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    case_id = case["case_id"]
    ref = case["layers"][layer_name]
    path = runtime_ref_path(checks, case_id, ref, f"{case_id}/{layer_name}")
    if path is None:
        return {}
    checks.check(path.is_file(), f"{case_id}/{layer_name}: runtime manifest is missing")
    checks.check(
        not path.is_symlink() and not has_symlink_component(path, ROOT),
        f"{case_id}/{layer_name}: runtime manifest cannot use symlinks",
    )
    if not path.is_file() or path.is_symlink() or has_symlink_component(path, ROOT):
        return {}
    validate_schema_instance(checks, path, schema)
    checks.check(
        hashlib.sha256(path.read_bytes()).hexdigest() == ref.get("sha256"),
        f"{case_id}/{layer_name}: manifest sha256 mismatch",
    )
    manifest = checks.load_json(path)
    if not isinstance(manifest, dict):
        return {}
    checks.check(
        manifest.get("status") == "frozen",
        f"{case_id}/{layer_name}: manifest must be frozen",
    )
    checks.check(
        manifest.get("case_id") == case_id,
        f"{case_id}/{layer_name}: manifest case_id mismatch",
    )
    checks.check(
        manifest.get("kind") == layer_name,
        f"{case_id}/{layer_name}: manifest kind mismatch",
    )
    checks.check(
        not has_pending(manifest),
        f"{case_id}/{layer_name}: frozen manifest contains pending values",
    )
    checks.check(
        manifest.get("source_root_manifest_sha256") == source_manifest_hash,
        f"{case_id}/{layer_name}: source-root manifest sha256 mismatch",
    )
    checks.check(
        set(manifest.get("source_root_ids", []))
        == set(case.get("source_root_ids", [])),
        f"{case_id}/{layer_name}: source_root_ids mismatch",
    )
    materialized_root_text = manifest.get("materialized_root", "")
    expected_layer_root = f"runtime/{case_id}/layers/{layer_name.replace('_', '-')}"
    checks.check(
        canonical_relative_path(materialized_root_text) == materialized_root_text
        and materialized_root_text == expected_layer_root,
        f"{case_id}/{layer_name}: materialized root is not canonical case runtime path",
    )
    materialized_root = (ROOT / materialized_root_text).resolve()
    checks.check(
        materialized_root.is_relative_to(ROOT.resolve()),
        f"{case_id}/{layer_name}: materialized root escapes evaluation",
    )
    checks.check(
        not has_symlink_component(ROOT / materialized_root_text, ROOT),
        f"{case_id}/{layer_name}: materialized root uses a symlink",
    )
    checks.check(
        materialized_root.is_dir(),
        f"{case_id}/{layer_name}: materialized root is missing",
    )
    if not materialized_root.is_dir():
        return {}
    actual_entries = runtime_tree_entries(materialized_root)
    symlinks = [
        path for path, entry in actual_entries.items() if entry.get("mode") == "120000"
    ]
    checks.check(
        not symlinks,
        f"{case_id}/{layer_name}: candidate-visible symlinks are forbidden: {symlinks[:5]}",
    )
    actual_manifest = file_manifest(actual_entries)
    declared_manifest = sorted(
        manifest.get("files", []), key=lambda item: item.get("path", "")
    )
    checks.check(
        actual_manifest == declared_manifest,
        f"{case_id}/{layer_name}: materialized files differ from manifest",
    )
    checks.check(
        canonical_hash(actual_manifest) == manifest.get("files_manifest_sha256"),
        f"{case_id}/{layer_name}: files_manifest_sha256 mismatch",
    )
    scan_entries_for_leaks(checks, actual_entries, patterns, f"{case_id}/{layer_name}")

    if layer_name == "product_world":
        expected_entries: dict[str, dict[str, Any]] = {}
        for source_id in case.get("source_root_ids", []):
            source = source_registry.get(source_id)
            if source:
                for relative, entry in source["actual"]["filtered_entries"].items():
                    checks.check(
                        relative not in expected_entries,
                        f"{case_id}: source roots collide at {relative}",
                    )
                    expected_entries[relative] = entry
        checks.check(
            file_manifest(actual_entries) == file_manifest(expected_entries),
            f"{case_id}/product_world: materialization differs from cutoff scrub output",
        )
    elif layer_name == "common_compatibility":
        expected_entries: dict[str, dict[str, Any]] = {}
        for derivation in (suite_binding or {}).get("common_derivations", []):
            if not isinstance(derivation, dict):
                continue
            source_path = derivation.get("source_path", "")
            installed_path = derivation.get("installed_path", "")
            checks.check(
                canonical_relative_path(source_path) == source_path
                and canonical_relative_path(installed_path) == installed_path,
                f"{case_id}/common_compatibility: N0 derivation path is not canonical",
            )
            source_entry = (historical_entries or {}).get(source_path)
            checks.check(
                derivation.get("transform") == "copy_bytes",
                f"{case_id}/common_compatibility: unsupported transform",
            )
            checks.check(
                source_entry is not None,
                f"{case_id}/common_compatibility: N0 source is absent: {source_path}",
            )
            checks.check(
                installed_path not in (historical_entries or {})
                and installed_path not in expected_entries,
                f"{case_id}/common_compatibility: N0 output collides: {installed_path}",
            )
            if source_entry is not None and installed_path not in expected_entries:
                expected_entries[installed_path] = source_entry
        checks.check(
            file_manifest(actual_entries) == file_manifest(expected_entries),
            f"{case_id}/common_compatibility: materialization is not the locked N0 byte-copy derivation",
        )
        checks.check(
            canonical_hash(file_manifest(expected_entries))
            == (suite_binding or {}).get("common_files_manifest_sha256"),
            f"{case_id}/common_compatibility: suite-locked files hash mismatch",
        )
        for relative in actual_entries:
            checks.check(
                not (
                    relative.endswith("/SKILL.md")
                    or relative == "SKILL.md"
                    or any(
                        path_is_within(relative, control)
                        for control in (
                            ".claude",
                            ".agents",
                            ".codex",
                            "AGENTS.md",
                            "CLAUDE.md",
                            "CODEX.md",
                            "cc-hooks-on",
                            "cc-hooks-off",
                        )
                    )
                ),
                f"{case_id}/common_compatibility: helper/control asset must move to treatment manifest: {relative}",
            )
            checks.check(
                not is_case_control_path(relative)
                and not path_is_within(relative, EVALUATION_CONTROL_ROOT),
                f"{case_id}/common_compatibility: case control path is forbidden: {relative}",
            )
    return actual_entries


def dependency_manifest(dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        dependencies,
        key=lambda item: (item.get("installed_path", ""), item.get("source_path", "")),
    )


def locked_source_manifest(dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project central lock entries to the treatment dependency shape."""
    projected = [
        {
            "source_path": item.get("source_path"),
            "installed_path": item.get("installed_path"),
            "role": item.get("role"),
            "sha256": item.get("sha256"),
        }
        for item in dependencies
    ]
    return dependency_manifest(projected)


def candidate_dependency_manifest(
    dependencies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Describe only candidate-visible dependency identity, excluding source aliases."""
    projected: list[dict[str, Any]] = []
    for item in dependencies:
        mode = item.get("mode")
        if mode is None:
            source = safe_source_dependency_path(item.get("source_path", ""))
            if source is not None:
                mode = "100755" if source.stat().st_mode & 0o111 else "100644"
        projected.append(
            {
                "installed_path": item.get("installed_path"),
                "mode": mode,
                "role": item.get("role"),
                "sha256": item.get("sha256"),
            }
        )
    return sorted(
        projected,
        key=lambda item: (item.get("installed_path", ""), item.get("role", "")),
    )


def locked_profile_dependency(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": profile.get("source_path"),
        "installed_path": profile.get("installed_path"),
        "role": "profile",
        "mode": profile.get("mode"),
        "sha256": profile.get("sha256"),
    }


def dependency_role_hash(dependencies: list[dict[str, Any]], roles: set[str]) -> str:
    selected = [item for item in dependencies if item.get("role") in roles]
    return canonical_hash(dependency_manifest(selected))


def source_dependency_path(path_text: str) -> Path:
    return (
        ROOT / path_text
        if path_is_within(path_text, CANDIDATE_INPUT_ROOT)
        else REPO / path_text
    )


def has_symlink_component(path: Path, base: Path) -> bool:
    """Check every lexical component below base without trusting resolved aliases."""
    try:
        relative = path.relative_to(base)
    except ValueError:
        return True
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def has_exact_filesystem_spelling(path: Path, base: Path) -> bool:
    """Reject case/Unicode aliases even when the host filesystem resolves them."""
    try:
        relative = path.relative_to(base)
    except ValueError:
        return False
    current = base
    for part in relative.parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current /= part
    return True


def safe_source_dependency_path(path_text: str) -> Path | None:
    """Resolve a dependency only when no symlink can escape its declared root."""
    if canonical_relative_path(path_text) != path_text:
        return None
    is_candidate_input = path_is_within(path_text, CANDIDATE_INPUT_ROOT)
    lexical = source_dependency_path(path_text)
    base = ROOT / CANDIDATE_INPUT_ROOT if is_candidate_input else REPO
    spelling_base = ROOT if is_candidate_input else REPO
    if not has_exact_filesystem_spelling(lexical, spelling_base):
        return None
    if has_symlink_component(base, ROOT if base != REPO else REPO):
        return None
    if has_symlink_component(lexical, base):
        return None
    try:
        resolved_base = base.resolve(strict=True)
        resolved = lexical.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(resolved_base) or not resolved.is_file():
        return None
    if not is_candidate_input and resolved.is_relative_to(ROOT.resolve()):
        return None
    return resolved


def safe_evaluation_file(path_text: str) -> Path | None:
    """Resolve one evaluation control file without aliases or symlinks."""
    if canonical_relative_path(path_text) != path_text:
        return None
    lexical = ROOT / path_text
    if not has_exact_filesystem_spelling(lexical, ROOT) or has_symlink_component(
        lexical, ROOT
    ):
        return None
    try:
        resolved = lexical.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
        return None
    return resolved


def safe_runtime_control_path(path_text: str, allowed_root: str) -> Path | None:
    """Resolve a runner-only runtime asset with exact spelling and containment."""
    if not path_is_within(path_text, allowed_root):
        return None
    resolved = safe_evaluation_file(path_text)
    if resolved is None:
        return None
    try:
        resolved_root = (ROOT / allowed_root).resolve(strict=True)
    except OSError:
        return None
    return resolved if resolved.is_relative_to(resolved_root) else None


def validate_component(
    checks: Validation,
    component: dict[str, Any],
    label: str,
) -> list[dict[str, Any]]:
    dependencies = [
        item
        for item in component.get("dependency_closure", [])
        if isinstance(item, dict)
    ]
    allowlist = component.get("source_allowlist", [])
    denylist = component.get("source_denylist", [])
    checks.check(
        EVALUATION_CONTROL_ROOT in denylist,
        f"{label}: source denylist must include the evaluation control root",
    )
    source_paths = [item.get("source_path") for item in dependencies]
    checks.check(
        set(source_paths) == set(allowlist),
        f"{label}: source allowlist must equal dependency closure",
    )
    checks.check(
        len(source_paths) == len(set(source_paths)),
        f"{label}: duplicate dependency source paths",
    )
    installed_paths = [item.get("installed_path") for item in dependencies]
    checks.check(
        len(installed_paths) == len(set(installed_paths)),
        f"{label}: duplicate dependency installed paths",
    )
    for item in dependencies:
        source_path = item.get("source_path", "")
        checks.check(
            canonical_relative_path(source_path) == source_path,
            f"{label}: dependency source path is not canonical: {source_path}",
        )
        checks.check(
            not path_is_within(source_path, "runtime")
            or path_is_within(source_path, CANDIDATE_INPUT_ROOT),
            f"{label}: runtime dependency must be under {CANDIDATE_INPUT_ROOT}: {source_path}",
        )
        checks.check(
            not path_is_within(source_path, EVALUATION_CONTROL_ROOT),
            f"{label}: dependency enters the evaluation control root: {source_path}",
        )
        checks.check(
            not any(path_is_within(source_path, denied) for denied in denylist),
            f"{label}: dependency {source_path} enters source denylist",
        )
        source_file = safe_source_dependency_path(source_path)
        checks.check(
            source_file is not None,
            f"{label}: dependency source must be a contained regular file without symlink ancestors: {source_path}",
        )
        if source_file is not None:
            actual_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
            checks.check(
                actual_hash == item.get("sha256"),
                f"{label}: dependency source sha256 mismatch: {source_path}",
            )
        installed_path = item.get("installed_path", "")
        checks.check(
            canonical_relative_path(installed_path) == installed_path,
            f"{label}: dependency installed path is not canonical: {installed_path}",
        )
        checks.check(
            not path_is_within(installed_path, ".git"),
            f"{label}: dependency cannot install into runner-owned .git metadata: {installed_path}",
        )
        checks.check(
            not is_case_control_path(installed_path)
            and not path_is_within(installed_path, EVALUATION_CONTROL_ROOT),
            f"{label}: dependency cannot install into a case/evaluation control path: {installed_path}",
        )
    checks.check(
        canonical_hash(dependency_manifest(dependencies))
        == component.get("files_sha256"),
        f"{label}: dependency closure hash mismatch",
    )
    return dependencies


def validate_treatment_manifest(
    checks: Validation,
    case: dict[str, Any],
    schema: dict[str, Any],
    source_registry: dict[str, dict[str, Any]],
    source_manifest_hash: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    historical_entries: dict[str, dict[str, Any]],
    common_entries: dict[str, dict[str, Any]],
    case_dir: Path,
    suite_lock: dict[str, Any],
    inventory: dict[str, Any],
) -> None:
    case_id = case["case_id"]
    ref = case["layers"]["arm_bundle"]
    path = runtime_ref_path(checks, case_id, ref, f"{case_id}/arm_bundle")
    if path is None:
        return
    checks.check(path.is_file(), f"{case_id}/arm_bundle: treatment manifest is missing")
    checks.check(
        not path.is_symlink() and not has_symlink_component(path, ROOT),
        f"{case_id}/arm_bundle: treatment manifest cannot use symlinks",
    )
    if not path.is_file() or path.is_symlink() or has_symlink_component(path, ROOT):
        return
    validate_schema_instance(checks, path, schema)
    checks.check(
        hashlib.sha256(path.read_bytes()).hexdigest() == ref.get("sha256"),
        f"{case_id}/arm_bundle: manifest sha256 mismatch",
    )
    manifest = checks.load_json(path)
    if not isinstance(manifest, dict):
        return
    checks.check(
        manifest.get("status") == "frozen",
        f"{case_id}/arm_bundle: manifest must be frozen",
    )
    checks.check(
        manifest.get("case_id") == case_id,
        f"{case_id}/arm_bundle: manifest case_id mismatch",
    )
    checks.check(
        not has_pending(manifest),
        f"{case_id}/arm_bundle: frozen manifest contains pending values",
    )
    suite_lock_hash = hashlib.sha256(TREATMENT_LOCK_PATH.read_bytes()).hexdigest()
    checks.check(
        manifest.get("suite_treatment_lock_ref") == TREATMENT_LOCK_REF
        and manifest.get("suite_treatment_lock_sha256") == suite_lock_hash,
        f"{case_id}/arm_bundle: suite treatment lock binding mismatch",
    )
    checks.check(
        manifest.get("workflow_clock_id") == suite_lock.get("workflow_clock_id"),
        f"{case_id}/arm_bundle: workflow clock differs from suite lock",
    )
    checks.check(
        manifest.get("artifact_contract") == case.get("artifact_contract"),
        f"{case_id}/arm_bundle: artifact contract differs from case",
    )
    checks.check(
        manifest.get("forbidden_atoms")
        == suite_lock.get("guardrails", {}).get("all_candidate_atoms"),
        f"{case_id}/arm_bundle: forbidden atoms differ from suite lock",
    )
    checks.check(
        manifest.get("source_root_manifest_sha256") == source_manifest_hash,
        f"{case_id}/arm_bundle: source-root manifest sha256 mismatch",
    )
    checks.check(
        manifest.get("public_brief_sha256")
        == hashlib.sha256((case_dir / "public/brief.md").read_bytes()).hexdigest(),
        f"{case_id}/arm_bundle: public brief sha256 mismatch",
    )
    shared = validate_component(
        checks, manifest.get("shared_helpers", {}), f"{case_id}/shared_helpers"
    )
    shared_roles = [item.get("role") for item in shared]
    checks.check(
        all(role in {"shared_helper", "artifact_contract"} for role in shared_roles),
        f"{case_id}/shared_helpers: only shared_helper and artifact_contract roles are allowed",
    )
    checks.check(
        any(role == "artifact_contract" for role in shared_roles),
        f"{case_id}/shared_helpers: frozen artifact contract dependency is missing",
    )
    components = suite_lock.get("components", {})
    shared_lock = components.get("shared_helpers", {})
    contract_lock = components.get("artifact_contracts", {}).get(
        case.get("artifact_contract"), {}
    )
    expected_component_ids = [
        shared_lock.get("component_id"),
        contract_lock.get("component_id"),
    ]
    checks.check(
        manifest.get("shared_helpers", {}).get("component_ids")
        == expected_component_ids,
        f"{case_id}/shared_helpers: component ids differ from suite lock",
    )
    checks.check(
        dependency_role_hash(shared, {"shared_helper"})
        == shared_lock.get("dependency_manifest_sha256"),
        f"{case_id}/shared_helpers: shared-helper closure differs from suite lock",
    )
    checks.check(
        dependency_role_hash(shared, {"artifact_contract"})
        == contract_lock.get("dependency_manifest_sha256"),
        f"{case_id}/shared_helpers: artifact-contract closure differs from suite lock",
    )
    locked_shared = shared_lock.get("dependencies", [])
    locked_contract = contract_lock.get("dependencies", [])
    actual_shared = [item for item in shared if item.get("role") == "shared_helper"]
    actual_contract = [
        item for item in shared if item.get("role") == "artifact_contract"
    ]
    checks.check(
        dependency_manifest(actual_shared) == locked_source_manifest(locked_shared)
        and canonical_hash(candidate_dependency_manifest(actual_shared))
        == shared_lock.get("candidate_manifest_sha256"),
        f"{case_id}/shared_helpers: source or candidate-visible helper manifest differs from suite lock",
    )
    checks.check(
        dependency_manifest(actual_contract) == locked_source_manifest(locked_contract)
        and canonical_hash(candidate_dependency_manifest(actual_contract))
        == contract_lock.get("candidate_manifest_sha256"),
        f"{case_id}/shared_helpers: source or candidate-visible artifact manifest differs from suite lock",
    )
    binding = suite_lock.get("case_bindings", {}).get(case_id, {})
    profile_lock = binding.get("profile", {})
    checks.check(
        inventory.get("user_policy", {}).get("profile_ref")
        == profile_lock.get("source_path"),
        f"{case_id}: inventory profile ref differs from suite lock",
    )
    checks.check(
        canonical_hash(inventory.get("user_policy", {}).get("excluded_lineages", []))
        == profile_lock.get("excluded_lineages_sha256"),
        f"{case_id}: excluded profile lineages differ from suite lock",
    )
    arms = manifest.get("arms", {})
    if not isinstance(arms, dict):
        return
    arm_dependencies: dict[str, list[dict[str, Any]]] = {}
    arm_exports: dict[str, dict[str, dict[str, Any]]] = {}
    for arm_id in ("A", "A_USER", "B"):
        arm = arms.get(arm_id, {})
        if not isinstance(arm, dict):
            continue
        checks.check(
            arm.get("arm_id") == arm_id, f"{case_id}/{arm_id}: arm_id mismatch"
        )
        case_arm = case.get("arms", {}).get(arm_id, {})
        checks.check(
            arm.get("workflow") == case_arm.get("workflow"),
            f"{case_id}/{arm_id}: treatment workflow differs from case contract",
        )
        checks.check(
            arm.get("profile_mode") == case_arm.get("user_profile"),
            f"{case_id}/{arm_id}: treatment profile mode differs from case contract",
        )
        arm_lock = suite_lock.get("arms", {}).get(arm_id, {})
        checks.check(
            arm.get("treatment_id") == arm_lock.get("treatment_id"),
            f"{case_id}/{arm_id}: treatment id differs from suite lock",
        )
        checks.check(
            arm.get("workflow_component_id") == arm_lock.get("workflow_component_id"),
            f"{case_id}/{arm_id}: workflow component id differs from suite lock",
        )
        dependencies = validate_component(
            checks,
            {**arm, "files_sha256": arm.get("bundle_sha256")},
            f"{case_id}/{arm_id}",
        )
        arm_dependencies[arm_id] = dependencies
        checks.check(
            all(item.get("role") in {"workflow", "profile"} for item in dependencies),
            f"{case_id}/{arm_id}: arm dependency uses a shared-only role",
        )
        workflow = [item for item in dependencies if item.get("role") == "workflow"]
        profiles = [item for item in dependencies if item.get("role") == "profile"]
        checks.check(
            bool(workflow), f"{case_id}/{arm_id}: workflow dependency is missing"
        )
        checks.check(
            canonical_hash(dependency_manifest(workflow)) == arm.get("workflow_sha256"),
            f"{case_id}/{arm_id}: workflow hash mismatch",
        )
        workflow_lock = components.get("workflows", {}).get(arm.get("workflow"), {})
        checks.check(
            arm.get("workflow_component_id") == workflow_lock.get("component_id")
            and dependency_role_hash(dependencies, {"workflow"})
            == workflow_lock.get("dependency_manifest_sha256"),
            f"{case_id}/{arm_id}: workflow closure differs from suite lock",
        )
        checks.check(
            dependency_manifest(workflow)
            == locked_source_manifest(workflow_lock.get("dependencies", []))
            and canonical_hash(candidate_dependency_manifest(workflow))
            == workflow_lock.get("candidate_manifest_sha256"),
            f"{case_id}/{arm_id}: workflow source or candidate-visible manifest differs from suite lock",
        )
        if arm.get("profile_mode") == "none":
            checks.check(
                not profiles
                and arm.get("profile_sha256") is None
                and arm.get("profile_component_id") is None
                and arm_lock.get("profile_selector") == "none",
                f"{case_id}/{arm_id}: no-profile arm contains a profile",
            )
        else:
            checks.check(
                len(profiles) == 1,
                f"{case_id}/{arm_id}: exactly one cross-fitted profile is required",
            )
            checks.check(
                canonical_hash(dependency_manifest(profiles))
                == arm.get("profile_sha256"),
                f"{case_id}/{arm_id}: profile hash mismatch",
            )
            checks.check(
                arm_lock.get("profile_selector") == "case_current_cross_fitted"
                and arm.get("profile_component_id") == profile_lock.get("component_id")
                and dependency_role_hash(dependencies, {"profile"})
                == profile_lock.get("dependency_manifest_sha256"),
                f"{case_id}/{arm_id}: profile closure differs from suite lock",
            )
            if len(profiles) == 1:
                locked_profile = locked_profile_dependency(profile_lock)
                checks.check(
                    profiles[0].get("source_path") == profile_lock.get("source_path")
                    and profiles[0].get("installed_path")
                    == profile_lock.get("installed_path"),
                    f"{case_id}/{arm_id}: profile path differs from suite lock",
                )
                checks.check(
                    dependency_manifest(profiles)
                    == locked_source_manifest([locked_profile])
                    and canonical_hash(candidate_dependency_manifest(profiles))
                    == profile_lock.get("candidate_manifest_sha256"),
                    f"{case_id}/{arm_id}: profile source or candidate-visible manifest differs from suite lock",
                )
        export = arm.get("export", {})
        export_root_text = export.get("materialized_root", "")
        checks.check(
            canonical_relative_path(export_root_text) == export_root_text
            and export_root_text == f"runtime/{case_id}/exports/{arm_id}",
            f"{case_id}/{arm_id}: export root is not the canonical arm path",
        )
        export_root = (ROOT / export_root_text).resolve()
        checks.check(
            export_root.is_relative_to(ROOT.resolve()),
            f"{case_id}/{arm_id}: export root escapes evaluation",
        )
        checks.check(
            not has_symlink_component(ROOT / export_root_text, ROOT),
            f"{case_id}/{arm_id}: export root uses a symlink",
        )
        checks.check(
            export_root.is_dir(), f"{case_id}/{arm_id}: export root is missing"
        )
        checks.check(
            export.get("installed_arm_ids") == [arm_id],
            f"{case_id}/{arm_id}: export must contain only selected arm id",
        )
        checks.check(
            export.get("source_scrub_manifest_sha256") == source_manifest_hash,
            f"{case_id}/{arm_id}: export source scrub hash mismatch",
        )
        if not export_root.is_dir():
            continue
        export_entries = runtime_tree_entries(export_root)
        export_symlinks = [
            path
            for path, entry in export_entries.items()
            if entry.get("mode") == "120000"
        ]
        checks.check(
            not export_symlinks,
            f"{case_id}/{arm_id}: candidate-visible symlinks are forbidden: {export_symlinks[:5]}",
        )
        arm_exports[arm_id] = export_entries
        checks.check(
            canonical_hash(file_manifest(export_entries))
            == export.get("files_manifest_sha256"),
            f"{case_id}/{arm_id}: export files manifest hash mismatch",
        )
        selected = [*shared, *dependencies]
        selected_paths = {item.get("installed_path") for item in selected}
        expected_export: dict[str, dict[str, Any]] = {}

        def add_expected(path_text: str, entry: dict[str, Any], owner: str) -> None:
            checks.check(
                path_text not in expected_export,
                f"{case_id}/{arm_id}: export path collision at {path_text} from {owner}",
            )
            if path_text not in expected_export:
                expected_export[path_text] = entry

        for relative, entry in historical_entries.items():
            add_expected(relative, entry, "product+documentation world")
        for relative, entry in common_entries.items():
            add_expected(relative, entry, "common_compatibility")
        for item in selected:
            source_file = safe_source_dependency_path(item.get("source_path", ""))
            if source_file is None:
                continue
            mode = "100755" if source_file.stat().st_mode & 0o111 else "100644"
            add_expected(
                item.get("installed_path", ""),
                {"mode": mode, "content": source_file.read_bytes()},
                f"dependency:{item.get('source_path', '')}",
            )
        checks.check(
            file_manifest(export_entries) == file_manifest(expected_export),
            f"{case_id}/{arm_id}: export is not the exact historical+common+shared+selected-arm union",
        )
        validate_fresh_root_git(
            checks, export_root, expected_export, f"{case_id}/{arm_id}"
        )
        product_instruction_roots = {
            root
            if source_registry[source_id]["source"].get("exposed_root") == "."
            else f"{source_registry[source_id]['source']['exposed_root'].rstrip('/')}/{root}"
            for source_id in case.get("source_root_ids", [])
            if source_id in source_registry
            for root in source_registry[source_id]["source"].get(
                "product_owned_instruction_roots", []
            )
        }
        for item in selected:
            installed_path = item.get("installed_path", "")
            installed = export_entries.get(installed_path)
            checks.check(
                installed is not None,
                f"{case_id}/{arm_id}: installed dependency missing: {installed_path}",
            )
            if installed is not None:
                actual_hash = hashlib.sha256(installed["content"]).hexdigest()
                checks.check(
                    actual_hash == item.get("sha256"),
                    f"{case_id}/{arm_id}: installed dependency hash mismatch: {installed_path}",
                )
        for relative in export_entries:
            is_control_asset = any(
                path_is_within(relative, control)
                for control in (
                    ".claude",
                    ".agents",
                    ".codex",
                    "CLAUDE.md",
                    "CODEX.md",
                    "cc-hooks-on",
                    "cc-hooks-off",
                )
            )
            if is_control_asset:
                checks.check(
                    relative in selected_paths,
                    f"{case_id}/{arm_id}: undeclared Agent control asset: {relative}",
                )
            if relative.endswith("/SKILL.md") or relative == "SKILL.md":
                product_owned = any(
                    path_is_within(relative, root) for root in product_instruction_roots
                )
                checks.check(
                    product_owned or relative in selected_paths,
                    f"{case_id}/{arm_id}: undeclared non-product skill asset: {relative}",
                )
            checks.check(
                not path_is_within(relative, EVALUATION_CONTROL_ROOT),
                f"{case_id}/{arm_id}: evaluation control asset survived export: {relative}",
            )
            checks.check(
                not is_case_control_path(relative),
                f"{case_id}/{arm_id}: case control asset survived export: {relative}",
            )
        scan_entries_for_leaks(
            checks, export_entries, patterns, f"{case_id}/{arm_id}-export"
        )
        scan_entries_for_atoms(
            checks,
            export_entries,
            suite_lock.get("guardrails", {}).get("all_candidate_atoms", []),
            f"{case_id}/{arm_id}-export",
        )
        for source_id in case.get("source_root_ids", []):
            source = source_registry.get(source_id)
            if not source:
                continue
            for relative, expected in source["actual"]["filtered_entries"].items():
                actual = export_entries.get(relative)
                checks.check(
                    actual is not None,
                    f"{case_id}/{arm_id}: scrubbed product file missing: {relative}",
                )
                if actual is not None:
                    checks.check(
                        actual["mode"] == expected["mode"]
                        and actual["content"] == expected["content"],
                        f"{case_id}/{arm_id}: scrubbed product file changed: {relative}",
                    )

    if all(arm_id in arm_dependencies for arm_id in ("A", "A_USER", "B")):
        checks.check(
            dependency_role_hash(arm_dependencies["A"], {"workflow"})
            == dependency_role_hash(arm_dependencies["A_USER"], {"workflow"}),
            f"{case_id}: A/A_USER workflow bytes differ",
        )
        checks.check(
            dependency_role_hash(arm_dependencies["A_USER"], {"profile"})
            == dependency_role_hash(arm_dependencies["B"], {"profile"}),
            f"{case_id}: A_USER/B profile bytes differ",
        )
        shared_paths = {item.get("installed_path") for item in shared}
        for arm_id, export_entries in arm_exports.items():
            selected_paths = shared_paths | {
                item.get("installed_path") for item in arm_dependencies[arm_id]
            }
            selected_hashes = {
                item.get("sha256") for item in [*shared, *arm_dependencies[arm_id]]
            }
            export_hashes = {
                hashlib.sha256(entry["content"]).hexdigest(): relative
                for relative, entry in export_entries.items()
            }
            for other_id, other_dependencies in arm_dependencies.items():
                if other_id == arm_id:
                    continue
                for item in other_dependencies:
                    installed_path = item.get("installed_path")
                    if installed_path not in selected_paths:
                        checks.check(
                            installed_path not in export_entries,
                            f"{case_id}/{arm_id}: non-selected {other_id} dependency survived: {installed_path}",
                        )
                    other_hash = item.get("sha256")
                    if other_hash not in selected_hashes:
                        checks.check(
                            other_hash not in export_hashes,
                            f"{case_id}/{arm_id}: renamed non-selected {other_id} bytes survived: "
                            f"{export_hashes.get(other_hash)}",
                        )
        b_dependencies = [*shared, *arm_dependencies["B"]]
        b_sources = [
            safe_source_dependency_path(item["source_path"]) for item in b_dependencies
        ]
        b_text = "\n".join(
            source.read_text(errors="replace")
            for source in b_sources
            if source is not None
        )
        for atom in manifest.get("forbidden_atoms", []):
            checks.check(
                atom.lower() not in b_text.lower(),
                f"{case_id}/B: forbidden atom present: {atom!r}",
            )
        for pattern_text, pattern in patterns:
            checks.check(
                not pattern.search(b_text),
                f"{case_id}/B: target atom present: {pattern_text!r}",
            )

    profile_path = safe_source_dependency_path(profile_lock.get("source_path", ""))
    checks.check(
        profile_path is not None,
        f"{case_id}: suite-locked cross-fitted profile is missing",
    )
    if profile_path is not None:
        profile_text = profile_path.read_text(errors="replace")
        declared_anchors = set(profile_lock.get("evidence_anchors", []))
        profile_sections = markdown_heading_sections(profile_text)
        for anchor in declared_anchors:
            bodies = profile_sections.get(anchor, [])
            checks.check(
                len(bodies) == 1 and bool(bodies[0].strip()),
                f"{case_id}: profile evidence anchor must be unique and have non-heading body: {anchor}",
            )
        expected_profile_ref = profile_lock.get("source_path", "")
        used_anchors: list[str] = []
        for decision in inventory.get("decisions", []):
            if not isinstance(decision, dict) or decision.get("class") != "P":
                continue
            profile_refs = [
                ref.removeprefix("profile:")
                for ref in decision.get("oracle", {}).get("evidence_refs", [])
                if isinstance(ref, str) and ref.startswith("profile:")
            ]
            checks.check(
                len(profile_refs) == 1,
                f"{case_id}/{decision.get('decision_id', '<missing>')}: P decision needs one profile evidence anchor",
            )
            if len(profile_refs) == 1:
                ref_path, anchor = split_anchor(profile_refs[0])
                if anchor:
                    used_anchors.append(anchor)
                checks.check(
                    ref_path == expected_profile_ref
                    and anchor in declared_anchors
                    and len(profile_sections.get(anchor or "", [])) == 1,
                    f"{case_id}/{decision.get('decision_id', '<missing>')}: profile evidence is not suite-locked",
                )
        checks.check(
            set(used_anchors) == declared_anchors
            and len(used_anchors) == len(declared_anchors),
            f"{case_id}: declared profile anchors must equal the one-per-P-decision evidence set",
        )


def validate_runtime_manifests(
    checks: Validation,
    case: dict[str, Any],
    case_dir: Path,
    schemas: dict[str, dict[str, Any]],
    source_registry: dict[str, dict[str, Any]],
    suite_lock: dict[str, Any],
) -> None:
    if case.get("status") not in {"ready", "sealed"}:
        return
    source_manifest_hash = hashlib.sha256(
        (ROOT / "source-roots.json").read_bytes()
    ).hexdigest()
    patterns = leak_patterns(
        case_dir / "audit/leak-signatures.txt", checks, case["case_id"]
    )
    product_entries = validate_layer_manifest(
        checks,
        case,
        "product_world",
        schemas["layer"],
        source_registry,
        source_manifest_hash,
        patterns,
    )
    documentation_entries = validate_layer_manifest(
        checks,
        case,
        "documentation_world",
        schemas["layer"],
        source_registry,
        source_manifest_hash,
        patterns,
    )
    base_entries = dict(product_entries)
    for relative, entry in documentation_entries.items():
        checks.check(
            relative not in base_entries,
            f"{case['case_id']}: product/documentation layers collide at {relative}",
        )
        base_entries[relative] = entry
    common_entries = validate_layer_manifest(
        checks,
        case,
        "common_compatibility",
        schemas["layer"],
        source_registry,
        source_manifest_hash,
        patterns,
        base_entries,
        suite_lock.get("case_bindings", {}).get(case["case_id"], {}),
    )
    inventory = checks.load_json(case_dir / "judge-private/decision-inventory.json")
    validate_treatment_manifest(
        checks,
        case,
        schemas["treatment"],
        source_registry,
        source_manifest_hash,
        patterns,
        base_entries,
        common_entries,
        case_dir,
        suite_lock,
        inventory if isinstance(inventory, dict) else {},
    )


def split_anchor(value: str) -> tuple[str, str | None]:
    path, marker, anchor = value.partition("#")
    return path, anchor if marker else None


def markdown_heading_slug(heading: str) -> str:
    normalized = heading.strip().lower()
    slug = "".join(ch for ch in normalized if ch.isalnum() or ch in " -_")
    slug = re.sub(r"[ _]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


def markdown_heading_sections(text: str) -> dict[str, list[str]]:
    """Map each heading slug to its section's direct non-heading content."""
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    fence_char: str | None = None
    fence_length = 0
    html_end: str | None = None
    html_until_blank = False
    html_block_tags = (
        "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|"
        "dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|"
        "frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend|li|link|main|"
        "menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|"
        "table|tbody|td|tfoot|th|thead|title|tr|track|ul"
    )
    for index, line in enumerate(lines):
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_char is not None:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_length},}}\s*$", line
            ):
                fence_char = None
                fence_length = 0
            continue
        if fence:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            continue

        stripped = line.lstrip(" ") if len(line) - len(line.lstrip(" ")) <= 3 else line
        lowered = stripped.lower()
        if html_end is not None:
            if html_end in lowered:
                html_end = None
            continue
        if html_until_blank:
            if not stripped:
                html_until_blank = False
            continue
        html_markers = (
            ("<!--", "-->"),
            ("<?", "?>"),
            ("<![cdata[", "]]>"),
            ("<!", ">"),
        )
        opened_html = False
        for opener, closer in html_markers:
            if lowered.startswith(opener):
                if closer not in lowered[len(opener) :]:
                    html_end = closer
                opened_html = True
                break
        if opened_html:
            continue
        raw_tag = re.match(r"^<(script|pre|style|textarea)(?:\s|>|$)", lowered)
        if raw_tag:
            closer = f"</{raw_tag.group(1)}>"
            if closer not in lowered:
                html_end = closer
            continue
        if re.match(rf"^</?(?:{html_block_tags})(?:\s|/?>|$)", lowered):
            html_until_blank = True
            continue
        if re.match(r"^</?[a-z][^>]*>\s*$", lowered):
            html_until_blank = True
            continue

        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append(
                (index, len(match.group(1)), markdown_heading_slug(match.group(2)))
            )
    sections: dict[str, list[str]] = {}
    for position, (line_index, level, slug) in enumerate(headings):
        end = len(lines)
        for next_index, next_level, _ in headings[position + 1 :]:
            if next_level <= level:
                end = next_index
                break
        body = "\n".join(
            line
            for line in lines[line_index + 1 : end]
            if not re.match(r"^#{1,6}\s+", line)
        ).strip()
        sections.setdefault(slug, []).append(body)
    return sections


def heading_slugs(text: str) -> set[str]:
    return set(markdown_heading_sections(text))


def validate_anchor(
    checks: Validation, content: bytes, anchor: str, label: str
) -> None:
    line_match = LINE_ANCHOR_RE.fullmatch(anchor)
    if line_match:
        start = int(line_match.group(1))
        end = int(line_match.group(2) or start)
        line_count = len(content.splitlines())
        checks.check(
            start <= end <= line_count,
            f"{label}: invalid line range #{anchor} for {line_count} lines",
        )
        return
    text = content.decode(errors="replace")
    checks.check(
        anchor.lower() in heading_slugs(text),
        f"{label}: missing Markdown heading #{anchor}",
    )


def validate_repo_ref(
    checks: Validation, namespace: str, value: str, label: str
) -> None:
    commit, separator, path_and_anchor = value.partition(":")
    checks.check(
        bool(separator) and bool(path_and_anchor),
        f"{label}: malformed {namespace} reference",
    )
    if not separator or not path_and_anchor:
        return
    checks.check(
        bool(SHA_RE.fullmatch(commit)),
        f"{label}: {namespace} commit is not a raw SHA: {commit}",
    )
    path, anchor = split_anchor(path_and_anchor)
    checks.check(
        canonical_relative_path(path) == path,
        f"{label}: {namespace} path is not canonical",
    )
    if canonical_relative_path(path) != path:
        return
    try:
        object_type = git_bytes("cat-file", "-t", f"{commit}:{path}").decode().strip()
        content = (
            git_bytes("show", f"{commit}:{path}") if object_type == "blob" else b""
        )
    except RuntimeError as exc:
        checks.errors.append(
            f"{label}: unresolved {namespace} source {commit}:{path}: {exc}"
        )
        return
    if anchor:
        checks.check(
            object_type == "blob", f"{label}: anchor on non-file source {commit}:{path}"
        )
        if object_type == "blob":
            validate_anchor(checks, content, anchor, label)


def validate_local_ref(
    checks: Validation,
    case_dir: Path,
    value: str,
    label: str,
    namespace: str,
) -> None:
    path_text, anchor = split_anchor(value)
    allowed_root = {
        "public": "public",
        "audit": "audit",
        "user-clock": "audit",
        "knowledge-clock": "audit",
        "reconstruction": "audit",
    }.get(namespace)
    canonical = canonical_relative_path(path_text)
    checks.check(
        canonical == path_text, f"{label}: case-local source path is not canonical"
    )
    checks.check(
        allowed_root is not None and path_is_within(path_text, allowed_root),
        f"{label}: {namespace} source is outside its allowed case directory",
    )
    path = case_dir / path_text
    safe = (
        canonical == path_text
        and allowed_root is not None
        and path_is_within(path_text, allowed_root)
        and path.is_file()
        and not path.is_symlink()
        and has_exact_filesystem_spelling(path, case_dir)
        and not has_symlink_component(path, case_dir)
        and path.resolve().is_relative_to(case_dir.resolve())
    )
    checks.check(
        safe, f"{label}: missing, aliased or escaped case-local source {path_text}"
    )
    if safe and anchor:
        validate_anchor(checks, path.read_bytes(), anchor, label)


def validate_contract_ref(
    checks: Validation, case_dir: Path, value: str, label: str
) -> None:
    path_text, anchor = split_anchor(value)
    canonical = canonical_relative_path(path_text)
    path = case_dir / path_text
    safe_path = (
        canonical == path_text
        and path_text == "case.json"
        and path.is_file()
        and not path.is_symlink()
        and not has_symlink_component(path, case_dir)
        and path.resolve().is_relative_to(case_dir.resolve())
    )
    checks.check(
        safe_path, f"{label}: contract source must be the canonical case.json asset"
    )
    if not safe_path:
        return
    if path.suffix != ".json":
        checks.check(
            bool(anchor), f"{label}: contract Markdown reference needs an anchor"
        )
        if anchor:
            validate_anchor(checks, path.read_bytes(), anchor, label)
        return
    checks.check(
        bool(anchor), f"{label}: contract JSON reference needs a property pointer"
    )
    if not anchor:
        return
    value_at_pointer = checks.load_json(path)
    parts = anchor.removeprefix("/").split("/")
    for raw_part in parts:
        part = unquote(raw_part).replace("~1", "/").replace("~0", "~")
        if isinstance(value_at_pointer, dict) and part in value_at_pointer:
            value_at_pointer = value_at_pointer[part]
        elif (
            isinstance(value_at_pointer, list)
            and part.isdigit()
            and int(part) < len(value_at_pointer)
        ):
            value_at_pointer = value_at_pointer[int(part)]
        else:
            checks.errors.append(f"{label}: missing contract JSON pointer #{anchor}")
            return


def validate_historical_private_ref(checks: Validation, value: str, label: str) -> None:
    commit, separator, path_and_range = value.partition(":")
    if not separator:
        checks.errors.append(f"{label}: malformed historical-private reference")
        return
    path, range_separator, line_range = path_and_range.rpartition(":")
    range_match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", line_range)
    if range_separator and range_match:
        start, end = range_match.groups()
        validate_repo_ref(
            checks, "historical-private", f"{commit}:{path}#L{start}-L{end}", label
        )
        return
    validate_repo_ref(checks, "historical-private", value, label)


def validate_external_ref(
    checks: Validation,
    authorities: dict[str, dict[str, Any]],
    value: str,
    label: str,
) -> None:
    if value in authorities:
        source = authorities[value].get("source", {})
        checks.check(
            source.get("kind") == "external_snapshot",
            f"{label}: authority is not an external snapshot",
        )
        return

    descriptor, separator, source_path = value.rpartition(":")
    mirror_id, at, cutoff = descriptor.rpartition("@")
    if not separator or not at or not mirror_id or not cutoff or not source_path:
        checks.errors.append(
            f"{label}: external reference must name an authority or mirror@cutoff:path"
        )
        return
    matches = []
    for item in authorities.values():
        source = item.get("source", {})
        if source.get("kind") != "external_snapshot":
            continue
        if source.get("cutoff_ref") == cutoff and source.get("path") == source_path:
            matches.append(item)
    checks.check(
        len(matches) == 1,
        f"{label}: external reference does not map to exactly one authority",
    )
    if len(matches) == 1:
        notes = matches[0].get("notes", "")
        checks.check(
            mirror_id in notes,
            f"{label}: external mirror id is not recorded by its authority",
        )


def validate_evidence_ref(
    checks: Validation,
    case_dir: Path,
    authorities: dict[str, dict[str, Any]],
    ref: str,
    label: str,
) -> None:
    authority_ids = set(authorities)
    if ref in authority_ids:
        return
    if ref == "public/brief.md":
        return
    namespace, separator, value = ref.partition(":")
    if not separator:
        checks.errors.append(f"{label}: unrecognized evidence reference {ref!r}")
        return
    if namespace == "authority":
        checks.check(value in authority_ids, f"{label}: unknown authority id {value}")
    elif namespace in {"cutoff", "heldout", "historical-evidence"}:
        validate_repo_ref(checks, namespace, value, label)
    elif namespace == "historical-private":
        validate_historical_private_ref(checks, value, label)
    elif namespace in {
        "public",
        "audit",
        "user-clock",
        "knowledge-clock",
        "reconstruction",
    }:
        validate_local_ref(checks, case_dir, value, label, namespace)
    elif namespace == "contract":
        validate_contract_ref(checks, case_dir, value, label)
    elif namespace == "external":
        validate_external_ref(checks, authorities, value, label)
    elif namespace == "external-provenance":
        if value in authority_ids:
            validate_external_ref(checks, authorities, value, label)
        else:
            path_text, anchor = split_anchor(value)
            checks.check(
                path_text == "audit/provenance.md",
                f"{label}: external provenance must use audit/provenance.md",
            )
            checks.check(bool(anchor), f"{label}: external provenance needs an anchor")
            if path_text == "audit/provenance.md" and anchor:
                validate_local_ref(checks, case_dir, value, label, "audit")
    elif namespace == "profile":
        profile_path, anchor = split_anchor(value)
        inventory = checks.load_json(case_dir / "judge-private/decision-inventory.json")
        expected = (
            inventory.get("user_policy", {}).get("profile_ref")
            if isinstance(inventory, dict)
            else None
        )
        checks.check(
            profile_path == expected,
            f"{label}: profile ref differs from inventory user policy",
        )
        checks.check(
            bool(anchor), f"{label}: profile evidence requires a heading anchor"
        )
    else:
        checks.errors.append(f"{label}: unsupported evidence namespace {namespace!r}")


def validate_authority_map(
    checks: Validation, case_dir: Path, case_id: str
) -> dict[str, dict[str, Any]]:
    path = case_dir / "knowledge/authority-map.json"
    data = checks.load_json(path)
    if not isinstance(data, dict):
        return {}
    checks.check(
        data.get("case_id") == case_id, f"{case_id}: authority-map case_id mismatch"
    )
    authorities = data.get("authorities", [])
    if not isinstance(authorities, list):
        return {}
    frozen = data.get("status") == "frozen"
    valid_authorities = [item for item in authorities if isinstance(item, dict)]
    ids = [item.get("authority_id") for item in valid_authorities]
    checks.check(len(ids) == len(set(ids)), f"{case_id}: duplicate authority ids")
    checks.authority_count += len(authorities)

    for item in valid_authorities:
        authority_id = item.get("authority_id", "<missing>")
        label = f"{case_id}/{authority_id}"
        availability = item.get("availability")
        exposed = item.get("exposed_path", "")
        source = item.get("source", {})
        if not isinstance(source, dict):
            continue
        kind = source.get("kind")
        cutoff = source.get("cutoff_ref", "")
        checks.check(
            canonical_relative_path(exposed) == exposed,
            f"{label}: exposed_path is not canonical",
        )
        checks.check(
            item.get("semantic_delta") is False,
            f"{label}: semantic_delta must be false",
        )

        if availability == "absent_at_cutoff":
            checks.check(
                bool(SHA_RE.fullmatch(cutoff)),
                f"{label}: absent cutoff_ref must be a raw SHA",
            )
            checks.check(
                exposed.startswith("__absent__/"),
                f"{label}: absent source needs __absent__/ sentinel",
            )
            checks.check(kind == "none", f"{label}: absent source kind must be none")
            checks.check(
                item.get("transform") == "absent_marker",
                f"{label}: absent source transform mismatch",
            )
            continue

        checks.check(
            availability == "present_at_cutoff", f"{label}: unknown availability"
        )
        checks.check(
            not is_case_control_path(exposed),
            f"{label}: candidate path enters a control directory",
        )
        checks.check(
            not exposed.startswith("__absent__/"),
            f"{label}: present source uses absent sentinel",
        )
        checks.check(
            kind in {"repo_file", "repo_tree", "external_snapshot"},
            f"{label}: unsupported present source kind {kind!r}",
        )
        source_path = source.get("path", "")
        expected_hash = source.get("sha256", "")
        if source_path:
            canonical_source_path = (
                source_path == "."
                if kind == "external_snapshot"
                else canonical_relative_path(source_path) == source_path
            )
            checks.check(
                canonical_source_path,
                f"{label}: source path is not canonical",
            )
        if frozen or expected_hash:
            checks.check(
                bool(HASH_RE.fullmatch(expected_hash)),
                f"{label}: missing/invalid sha256",
            )

        if kind == "external_snapshot":
            checks.check(bool(cutoff), f"{label}: external snapshot needs a cutoff_ref")
            if frozen:
                checks.check(
                    bool(source_path), f"{label}: frozen external snapshot needs a path"
                )
            if source_path:
                safe_path = (
                    source_path == "."
                    or canonical_relative_path(source_path) == source_path
                )
                checks.check(
                    safe_path,
                    f"{label}: external snapshot path must be a canonical repository-relative subtree or '.'",
                )
            if cutoff.startswith("file:"):
                local_root = Path(unquote(cutoff.removeprefix("file:")))
                if not local_root.is_absolute():
                    local_root = REPO / local_root
                local_path = (
                    local_root / Path(source_path)
                    if local_root.is_dir()
                    else local_root
                )
                checks.check(
                    local_path.exists(),
                    f"{label}: declared local external materialization is missing",
                )
                if local_path.is_file() and expected_hash:
                    actual_hash = hashlib.sha256(local_path.read_bytes()).hexdigest()
                    checks.check(
                        actual_hash == expected_hash,
                        f"{label}: local materialization sha256 mismatch {actual_hash}",
                    )
            continue

        checks.check(
            bool(SHA_RE.fullmatch(cutoff)),
            f"{label}: repository cutoff_ref must be a raw SHA",
        )
        if (
            kind not in {"repo_file", "repo_tree"}
            or not SHA_RE.fullmatch(cutoff)
            or not source_path
        ):
            continue
        try:
            if kind == "repo_file":
                content = git_bytes("show", f"{cutoff}:{source_path}")
            else:
                content = git_bytes("archive", cutoff, source_path)
        except RuntimeError as exc:
            checks.errors.append(f"{label}: source unavailable: {exc}")
            continue
        actual_hash = hashlib.sha256(content).hexdigest()
        if expected_hash:
            checks.check(
                actual_hash == expected_hash, f"{label}: sha256 mismatch {actual_hash}"
            )
        if item.get("transform") == "copy":
            checks.check(
                exposed == source_path, f"{label}: copy transform changes its path"
            )
    return {
        item["authority_id"]: item
        for item in valid_authorities
        if isinstance(item.get("authority_id"), str)
    }


def validate_ready_lifecycle(
    checks: Validation, case_dir: Path, case_id: str, case: dict[str, Any]
) -> None:
    """Enforce cross-file gates that become mandatory at ready/sealed."""
    if case.get("status") not in {"ready", "sealed"}:
        return

    authority = checks.load_json(case_dir / "knowledge/authority-map.json")
    inventory = checks.load_json(case_dir / "judge-private/decision-inventory.json")
    checks.check(
        isinstance(case.get("budgets"), dict),
        f"{case_id}: ready/sealed case needs budgets",
    )
    checks.check(
        isinstance(authority, dict) and authority.get("status") == "frozen",
        f"{case_id}: ready/sealed authority map must be frozen",
    )
    checks.check(
        isinstance(inventory, dict) and inventory.get("status") == "frozen",
        f"{case_id}: ready/sealed decision inventory must be frozen",
    )

    decisions = inventory.get("decisions", []) if isinstance(inventory, dict) else []
    unresolved = [
        item.get("decision_id", "<missing>")
        for item in decisions
        if isinstance(item, dict)
        and item.get("resolution_status") == "owner_review_required"
    ]
    if case.get("stratum") in {"prospective_pilot", "prospective_holdout"}:
        checks.check(
            not unresolved,
            f"{case_id}: prospective ready/sealed case has unresolved owner decisions {unresolved}",
        )
    if case.get("terminal_mode") == "gate2_complete":
        checks.check(
            not unresolved,
            f"{case_id}: gate2_complete case has unresolved owner decisions {unresolved}",
        )
    else:
        checks.check(
            case.get("terminal_mode") == "owner_review_ready_package"
            and case.get("artifact_contract") == "portfolio",
            f"{case_id}: invalid package-ready terminal contract",
        )
        unresolved_items = [
            item
            for item in decisions
            if isinstance(item, dict)
            and item.get("resolution_status") == "owner_review_required"
        ]
        for item in unresolved_items:
            expected_scope = {
                "V": "package_relative",
                "H": "affected_branch_only",
            }.get(item.get("class"))
            checks.check(
                expected_scope is not None
                and item.get("terminal_scope") == expected_scope,
                f"{case_id}/{item.get('decision_id', '<missing>')}: invalid structured terminal scope",
            )
            checks.check(
                bool(item.get("pending_boundary")),
                f"{case_id}/{item.get('decision_id', '<missing>')}: package-ready unresolved decision lacks pending boundary",
            )

    if isinstance(authority, dict):
        for item in authority.get("authorities", []):
            if (
                not isinstance(item, dict)
                or item.get("availability") != "present_at_cutoff"
            ):
                continue
            authority_id = item.get("authority_id", "<missing>")
            source = item.get("source", {})
            if not isinstance(source, dict):
                continue
            checks.check(
                bool(HASH_RE.fullmatch(source.get("sha256", ""))),
                f"{case_id}/{authority_id}: ready/sealed present source needs sha256",
            )
            if source.get("kind") == "external_snapshot":
                checks.check(
                    bool(source.get("path")),
                    f"{case_id}/{authority_id}: ready/sealed external snapshot needs path",
                )

    provenance_path = case_dir / "audit/provenance.md"
    current_section = ""
    for line_number, line in enumerate(
        provenance_path.read_text().splitlines(), start=1
    ):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            current_section = heading.group(1)
        if not PROVENANCE_PLACEHOLDER_RE.search(line):
            continue
        if PROVENANCE_KEY_RE.search(line) or "manifest" in current_section.lower():
            checks.errors.append(
                f"{case_id}/provenance:{line_number}: ready/sealed key hash/manifest/result contains placeholder"
            )


def validate_owner_answer_policy(
    checks: Validation,
    case: dict[str, Any],
    case_dir: Path,
    schema: dict[str, Any],
    authorities: dict[str, dict[str, Any]],
) -> None:
    """Bind every pre-answerable V/H to one frozen, blind replay bank."""
    if case.get("status") not in {"ready", "sealed"}:
        return
    case_id = case["case_id"]
    ref = case.get("owner_answer_policy", {})
    path_text = ref.get("manifest_ref", "") if isinstance(ref, dict) else ""
    checks.check(
        path_text == f"runtime/{case_id}/private/owner-answer-policy.json",
        f"{case_id}: owner-answer-policy ref mismatch",
    )
    path = (ROOT / path_text).resolve()
    checks.check(
        path.is_relative_to(ROOT.resolve()),
        f"{case_id}: owner-answer-policy escapes evaluation root",
    )
    checks.check(path.is_file(), f"{case_id}: owner-answer-policy manifest is missing")
    if not path.is_file():
        return
    validate_schema_instance(checks, path, schema)
    checks.check(
        hashlib.sha256(path.read_bytes()).hexdigest() == ref.get("sha256"),
        f"{case_id}: owner-answer-policy sha256 mismatch",
    )
    policy = checks.load_json(path)
    inventory_path = case_dir / "judge-private/decision-inventory.json"
    inventory = checks.load_json(inventory_path)
    if not isinstance(policy, dict) or not isinstance(inventory, dict):
        return
    checks.check(
        policy.get("case_id") == case_id,
        f"{case_id}: owner-answer-policy case_id mismatch",
    )
    checks.check(
        policy.get("status") == "frozen",
        f"{case_id}: owner-answer-policy must be frozen",
    )
    checks.check(
        not has_pending(policy),
        f"{case_id}: frozen owner-answer-policy contains pending values",
    )
    checks.check(
        policy.get("decision_inventory_sha256")
        == hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        f"{case_id}: owner-answer-policy inventory hash mismatch",
    )
    expected_mode = (
        "blind_owner_preseal"
        if case.get("stratum") in {"prospective_pilot", "prospective_holdout"}
        else "historical_owner_record"
    )
    checks.check(
        policy.get("creation_mode") == expected_mode,
        f"{case_id}: owner-answer-policy creation mode mismatch",
    )
    entries = [item for item in policy.get("entries", []) if isinstance(item, dict)]
    ids = [item.get("decision_id") for item in entries]
    checks.check(
        len(ids) == len(set(ids)),
        f"{case_id}: duplicate owner-answer-policy decision ids",
    )
    expected_ids = {
        item.get("decision_id")
        for item in inventory.get("decisions", [])
        if isinstance(item, dict)
        and item.get("class") in {"V", "H"}
        and item.get("resolution_status") == "resolved"
    }
    checks.check(
        set(ids) == expected_ids,
        f"{case_id}: owner-answer-policy does not cover exactly resolved V/H",
    )
    decision_by_id = {
        item.get("decision_id"): item
        for item in inventory.get("decisions", [])
        if isinstance(item, dict)
    }
    checks.check(
        canonical_hash(sorted(entries, key=lambda item: item.get("decision_id", "")))
        == policy.get("response_bank_sha256"),
        f"{case_id}: owner-answer-policy response bank hash mismatch",
    )
    for entry in entries:
        decision_id = entry.get("decision_id", "<missing>")
        semantic_answer = entry.get("semantic_answer", "")
        checks.check(
            bool(semantic_answer.strip())
            and not PROVENANCE_PLACEHOLDER_RE.search(semantic_answer),
            f"{case_id}/owner-policy/{decision_id}: semantic answer is blank or placeholder",
        )
        decision_evidence = set(
            decision_by_id.get(decision_id, {})
            .get("oracle", {})
            .get("evidence_refs", [])
        )
        source_refs = entry.get("source_refs", [])
        checks.check(
            bool(source_refs) and set(source_refs) <= decision_evidence,
            f"{case_id}/owner-policy/{decision_id}: response sources are not decision evidence",
        )
        for index, evidence_ref in enumerate(source_refs, start=1):
            validate_evidence_ref(
                checks,
                case_dir,
                authorities,
                evidence_ref,
                f"{case_id}/owner-policy/{decision_id}/source[{index}]",
            )


def validate_decisions(
    checks: Validation,
    case_dir: Path,
    case_id: str,
    authorities: dict[str, dict[str, Any]],
) -> None:
    path = case_dir / "judge-private/decision-inventory.json"
    data = checks.load_json(path)
    if not isinstance(data, dict):
        return
    checks.check(
        data.get("case_id") == case_id,
        f"{case_id}: decision inventory case_id mismatch",
    )
    decisions = data.get("decisions", [])
    if not isinstance(decisions, list):
        return
    valid_decisions = [item for item in decisions if isinstance(item, dict)]
    ids = [item.get("decision_id") for item in valid_decisions]
    checks.check(len(ids) == len(set(ids)), f"{case_id}: duplicate decision ids")
    checks.decision_count += len(decisions)

    expected = {
        "F": ("self_resolve_with_evidence", False, False),
        "V": ("structured_escalation", True, True),
        "H": ("mandatory_escalation", True, True),
    }
    for item in valid_decisions:
        decision_id = item.get("decision_id", "<missing>")
        label = f"{case_id}/{decision_id}"
        cls = item.get("class")
        status = item.get("resolution_status")
        if cls in expected:
            handling, must_surface, guardrail = expected[cls]
            checks.check(
                item.get("expected_handling") == handling,
                f"{label}: expected_handling mismatch",
            )
            checks.check(
                item.get("must_surface") is must_surface,
                f"{label}: must_surface mismatch",
            )
            checks.check(
                item.get("guardrail") is guardrail, f"{label}: guardrail mismatch"
            )
        elif cls == "P":
            checks.check(
                item.get("expected_handling")
                in {"auto_if_authorized", "prefill_and_confirm"},
                f"{label}: invalid P handling",
            )
            checks.check(
                item.get("guardrail") is False, f"{label}: P cannot be a guardrail"
            )
        else:
            checks.errors.append(f"{label}: unknown decision class {cls!r}")
        if cls in {"F", "P"}:
            checks.check(status == "resolved", f"{label}: F/P must be resolved")
        if status == "owner_review_required":
            checks.check(cls in {"V", "H"}, f"{label}: unresolved decision must be V/H")
        if cls == "H":
            checks.check(
                bool(item.get("activation_predicate")),
                f"{label}: missing activation_predicate",
            )
            checks.check(
                bool(item.get("inactive_safe_behavior")),
                f"{label}: missing inactive_safe_behavior",
            )
        for index, ref in enumerate(
            item.get("oracle", {}).get("evidence_refs", []), start=1
        ):
            validate_evidence_ref(
                checks, case_dir, authorities, ref, f"{label}/evidence[{index}]"
            )
        profile_refs = [
            ref
            for ref in item.get("oracle", {}).get("evidence_refs", [])
            if isinstance(ref, str) and ref.startswith("profile:")
        ]
        if cls == "P":
            checks.check(
                len(profile_refs) == 1,
                f"{label}: P decision needs exactly one anchored profile reference",
            )
        else:
            checks.check(
                not profile_refs,
                f"{label}: only P decisions may cite the candidate-visible profile",
            )


def validate_leak_signatures(checks: Validation, case_dir: Path, case_id: str) -> None:
    signature_path = case_dir / "audit/leak-signatures.txt"
    brief_path = case_dir / "public/brief.md"
    brief = brief_path.read_text()
    inventory = (case_dir / "judge-private/decision-inventory.json").read_text()
    patterns = leak_patterns(signature_path, checks, case_id)
    for pattern_text, pattern in patterns:
        checks.check(
            not pattern.search(brief),
            f"{case_id}: public brief matches private leak signature {pattern_text!r}",
        )
    scan_entries_for_atoms(
        checks,
        {
            "<initial-user-message>": {
                "mode": "100644",
                "content": brief_path.read_bytes(),
            }
        },
        SUITE_GUARDRAIL_ATOMS,
        f"{case_id}/public-brief",
    )
    if case_id.startswith("P"):
        checks.check(
            any(pattern.search(inventory) for _, pattern in patterns),
            f"{case_id}: no leak signature detects private inventory ids",
        )


def validate_markdown_links(checks: Validation) -> None:
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        for target in link_re.findall(path.read_text()):
            target = unquote(target.strip().strip("<>"))
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative, _ = split_anchor(target)
            checks.check(
                (path.parent / relative).resolve().exists(),
                f"{path.relative_to(REPO)}: broken link {target}",
            )


def git_tree_for_commit(commit: str) -> str | None:
    try:
        return git_bytes("rev-parse", f"{commit}^{{tree}}").decode().strip()
    except RuntimeError:
        return None


def git_blob_at(commit: str, path: str) -> tuple[str, bytes] | None:
    """Return one exact blob mode/content pair from the project object store."""
    try:
        record = git_bytes("ls-tree", commit, "--", path).rstrip(b"\n")
        content = git_bytes("show", f"{commit}:{path}")
    except RuntimeError:
        return None
    metadata, separator, raw_path = record.partition(b"\t")
    if not separator or raw_path.decode(errors="replace") != path:
        return None
    parts = metadata.split()
    if len(parts) != 3 or parts[1] != b"blob":
        return None
    return parts[0].decode(), content


def archive_lineage_dispositions(commit: str) -> list[dict[str, Any]]:
    """Derive archive units that import claims from B-noncompleted units."""
    raw_tree = git_bytes("ls-tree", "-rz", "--full-tree", commit, "--", "docs/changes")
    records: list[tuple[str, str, str]] = []
    noncompleted_ids: set[str] = set()
    archive_records: dict[str, list[tuple[str, str]]] = {}
    for raw_record in raw_tree.split(b"\x00"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        if not separator:
            raise RuntimeError("malformed source change-unit tree record")
        _, object_type, object_id = metadata.decode().split()
        path = raw_path.decode()
        parts = path.split("/")
        if object_type != "blob" or len(parts) < 4 or parts[:2] != ["docs", "changes"]:
            continue
        records.append((path, object_id, parts[2]))
        if parts[2] == "archive" and len(parts) >= 5:
            archive_root = "/".join(parts[:4])
            archive_records.setdefault(archive_root, []).append((path, object_id))
            continue
        root_name = parts[3] if parts[2] == "retired" and len(parts) >= 5 else parts[2]
        match = CHANGE_UNIT_ROOT_RE.match(root_name)
        if match is not None:
            noncompleted_ids.add(match.group(1).lower())

    object_ids = sorted({object_id for _, object_id, _ in records})
    payloads = git_object_payloads(REPO, object_ids) if object_ids else {}
    dispositions: list[dict[str, Any]] = []
    for archive_root, entries in sorted(archive_records.items()):
        referenced_ids: set[str] = set()
        for path, object_id in entries:
            if Path(path).suffix.lower() not in TEXT_SUFFIXES:
                continue
            content = payloads[object_id][1].decode("utf-8", errors="replace")
            referenced_ids.update(
                match.group(0).lower()
                for match in CHANGE_UNIT_REFERENCE_RE.finditer(content)
                if match.group(0).lower() in noncompleted_ids
            )
        if referenced_ids:
            dispositions.append(
                {
                    "path": archive_root,
                    "referenced_noncompleted_unit_ids": sorted(referenced_ids),
                }
            )
    return dispositions


def canonical_root_commit_sha(tree: str) -> str:
    payload = (
        f"tree {tree}\n"
        f"author {FRESH_ROOT_IDENTITY[0]} <{FRESH_ROOT_IDENTITY[1]}> {FRESH_ROOT_EPOCH} +0000\n"
        f"committer {FRESH_ROOT_IDENTITY[0]} <{FRESH_ROOT_IDENTITY[1]}> {FRESH_ROOT_EPOCH} +0000\n"
        f"\n{FRESH_ROOT_COMMIT_MESSAGE}\n"
    ).encode()
    raw = f"commit {len(payload)}\0".encode() + payload
    return hashlib.sha1(raw).hexdigest()


def validate_base_repository_recipes(
    checks: Validation,
    schema: dict[str, Any],
    suite_lock: dict[str, Any],
    source_registry: dict[str, dict[str, Any]],
    verify_materializations: bool,
) -> None:
    """Validate and optionally replay the eight formal arm-A clean-room recipes."""
    stable_receipt = checks.load_json(ROOT / "receipts/base-repository-A.json")
    if not isinstance(stable_receipt, dict):
        stable_receipt = {}
    stable_cases = {
        item.get("case_id"): item
        for item in stable_receipt.get("cases", [])
        if isinstance(item, dict)
    }
    checks.check(
        stable_receipt.get("method") == BASE_REPOSITORY_METHOD
        and stable_receipt.get("projection") == BASE_REPOSITORY_PROJECTION
        and stable_receipt.get("truth_formula") == BASE_REPOSITORY_TRUTH_FORMULA
        and stable_receipt.get("arm") == "A"
        and stable_receipt.get("status") == "materialized_verified"
        and stable_receipt.get("archive_lineage_policy")
        == "drop_noncompleted_cross_references_v1"
        and stable_receipt.get("leak_assertions")
        == {
            "forbidden_paths": ["docs/changes/feat-397-spec-design-agent-team"],
            "forbidden_atoms": ["feat-397"],
            "scan_scope": "path_and_text_all_eight_roots",
        }
        and set(stable_cases) == set(BASE_RECIPE_REFS),
        "receipts/base-repository-A.json: stable receipt registry mismatch",
    )
    recipes: dict[str, dict[str, Any]] = {}
    for case_id, recipe_ref in BASE_RECIPE_REFS.items():
        path = ROOT / recipe_ref
        validate_schema_instance(checks, path, schema)
        recipe = checks.load_json(path)
        if not isinstance(recipe, dict):
            continue
        recipes[case_id] = recipe
        label = f"base-recipe/{case_id}"
        checks.check(
            recipe.get("schema_version") == "2.0",
            f"{label}: schema version must be 2.0",
        )
        checks.check(recipe.get("case_id") == case_id, f"{label}: case id mismatch")
        contract = recipe.get("contract", {})
        checks.check(
            contract.get("method_id") == BASE_REPOSITORY_METHOD,
            f"{label}: method mismatch",
        )
        checks.check(
            contract.get("projection_level") == BASE_REPOSITORY_PROJECTION,
            f"{label}: projection level mismatch",
        )
        checks.check(
            contract.get("truth_formula") == BASE_REPOSITORY_TRUTH_FORMULA,
            f"{label}: truth formula mismatch",
        )
        checks.check(
            contract.get("layers") == BASE_REPOSITORY_LAYERS,
            f"{label}: five-layer order mismatch",
        )
        clocks = contract.get("clocks", {})
        checks.check(
            set(clocks) == BASE_REPOSITORY_CLOCKS,
            f"{label}: six-clock registry mismatch",
        )
        for clock_name in ("documentation_framework", "workflow"):
            clock = clocks.get(clock_name, {})
            checks.check(
                clock.get("commit") == FRAMEWORK_COMMIT
                and clock.get("tree") == FRAMEWORK_TREE,
                f"{label}: {clock_name} clock differs from suite-frozen F/W",
            )

        source = recipe.get("source", {})
        source_commit = source.get("expected_commit")
        source_tree = source.get("expected_tree")
        checks.check(
            source.get("ref") == source_commit,
            f"{label}: source ref is not pinned to its commit",
        )
        checks.check(
            isinstance(source_commit, str)
            and git_tree_for_commit(source_commit) == source_tree,
            f"{label}: source commit/tree cannot be reproduced",
        )
        product_clock = clocks.get("product", {})
        knowledge_clock = clocks.get("knowledge", {})
        checks.check(
            product_clock.get("commit") == source_commit
            and product_clock.get("tree") == source_tree
            and knowledge_clock.get("commit") == source_commit
            and knowledge_clock.get("tree") == source_tree,
            f"{label}: B product/knowledge clocks differ from source",
        )
        matching_sources = [
            item["source"]
            for item in source_registry.values()
            if item.get("source", {}).get("kind") == "project_repository"
            and item.get("source", {}).get("cutoff_ref") == source_commit
        ]
        checks.check(
            len(matching_sources) == 1,
            f"{label}: source-root registry does not bind one B cutoff",
        )
        if matching_sources:
            checks.check(
                matching_sources[0].get("cutoff_tree") == source_tree,
                f"{label}: source-root cutoff tree differs from recipe",
            )

        scrub = recipe.get("scrub", {})
        checks.check(
            scrub.get("change_unit_policy")
            == "remove_active_and_retired_keep_completed_archive",
            f"{label}: clean-room change-unit policy mismatch",
        )
        checks.check(
            recipe.get("assertions", {}).get("change_units_absent") is True,
            f"{label}: clean-room absence assertion is missing",
        )
        checks.check(
            scrub.get("drop_proposed_control", [])
            == (H01_PROPOSED_CONTROL_PATHS if case_id == "H01" else []),
            f"{label}: legacy proposed-control disposition mismatch",
        )
        archive_lineage = scrub.get("archive_lineage", {})
        try:
            derived_archive_drops = archive_lineage_dispositions(source_commit)
        except RuntimeError as exc:
            checks.errors.append(f"{label}: cannot derive B archive lineage: {exc}")
            derived_archive_drops = []
        checks.check(
            archive_lineage.get("policy") == "drop_noncompleted_cross_references_v1"
            and archive_lineage.get("drop_units") == derived_archive_drops,
            f"{label}: archive lineage disposition differs from task-blind B derivation",
        )
        assertions = recipe.get("assertions", {})
        forbidden_paths = set(assertions.get("forbidden_paths", []))
        checks.check(
            {entry["path"] for entry in derived_archive_drops} <= forbidden_paths
            and "docs/changes/feat-397-spec-design-agent-team" in forbidden_paths,
            f"{label}: archive/feat-397 forbidden-path assertions are incomplete",
        )
        checks.check(
            "feat-397" in assertions.get("forbidden_text", []),
            f"{label}: feat-397 forbidden-text assertion is missing",
        )
        expected_manifest = assertions.get("expected_content_manifest_sha256")
        checks.check(
            isinstance(expected_manifest, str)
            and HASH_RE.fullmatch(expected_manifest) is not None,
            f"{label}: expected content manifest is not frozen",
        )

        projection = recipe.get("docs_projection", {})
        projection_mode = projection.get("mode")
        checks.check(
            projection_mode in {"preserve_exact", "dp1_counterfactual_latest"},
            f"{label}: unsupported formal documentation projection",
        )
        if projection_mode == "dp1_counterfactual_latest":
            checks.check(
                projection.get("expected_commit") == FRAMEWORK_COMMIT
                and projection.get("expected_tree") == FRAMEWORK_TREE,
                f"{label}: DP1 framework clock differs from F",
            )
            for index, entry in enumerate(projection.get("files", [])):
                entry_label = f"{label}/docs[{index}]"
                source_clock = entry.get("source_clock")
                source_clock_commit = (
                    source_commit
                    if source_clock == "product_baseline"
                    else FRAMEWORK_COMMIT
                )
                blob = git_blob_at(source_clock_commit, entry.get("source", ""))
                checks.check(blob is not None, f"{entry_label}: source blob is missing")
                if blob is not None:
                    checks.check(
                        hashlib.sha256(blob[1]).hexdigest() == entry.get("sha256"),
                        f"{entry_label}: source blob hash mismatch",
                    )
            for index, entry in enumerate(projection.get("generated_files", [])):
                checks.check(
                    hashlib.sha256(entry.get("content", "").encode()).hexdigest()
                    == entry.get("sha256"),
                    f"{label}/generated-doc[{index}]: content hash mismatch",
                )

        arm = recipe.get("arm", {})
        checks.check(
            arm.get("id") == "A", f"{label}: formal materialization must select arm A"
        )
        checks.check(
            arm.get("ref") == FRAMEWORK_COMMIT,
            f"{label}: arm A is not pinned to Workflow@W",
        )
        for index, entry in enumerate(arm.get("files", [])):
            entry_label = f"{label}/arm[{index}]"
            blob = git_blob_at(FRAMEWORK_COMMIT, entry.get("source", ""))
            checks.check(blob is not None, f"{entry_label}: workflow blob is missing")
            if blob is not None:
                checks.check(
                    hashlib.sha256(blob[1]).hexdigest() == entry.get("sha256"),
                    f"{entry_label}: workflow blob hash mismatch",
                )
                transform = entry.get("transform")
                if transform is not None:
                    marker = f"{transform.get('heading', '')}\n".encode()
                    occurrences = blob[1].count(marker)
                    checks.check(
                        occurrences == transform.get("expected_occurrences"),
                        f"{entry_label}: workflow slice heading count mismatch",
                    )
                    if occurrences:
                        offset = blob[1].index(marker)
                        checks.check(
                            offset == 0 or blob[1][offset - 1 : offset] == b"\n",
                            f"{entry_label}: workflow slice marker is not a heading line",
                        )
                        checks.check(
                            hashlib.sha256(blob[1][:offset]).hexdigest()
                            == entry.get("output_sha256"),
                            f"{entry_label}: workflow slice output hash mismatch",
                        )
        for index, entry in enumerate(arm.get("generated_files", [])):
            checks.check(
                hashlib.sha256(entry.get("content", "").encode()).hexdigest()
                == entry.get("sha256"),
                f"{label}/generated-arm[{index}]: content hash mismatch",
            )

        git_config = recipe.get("git", {})
        checks.check(
            git_config
            == {
                "branch": FRESH_ROOT_BRANCH,
                "author_name": FRESH_ROOT_IDENTITY[0],
                "author_email": FRESH_ROOT_IDENTITY[1],
                "timestamp": f"{FRESH_ROOT_EPOCH} +0000",
                "message": f"{FRESH_ROOT_COMMIT_MESSAGE}\n",
            },
            f"{label}: canonical Git envelope differs",
        )
        seal = recipe.get("seal", {})
        checks.check(
            seal.get("suite_status") == "draft_unsealable"
            and seal.get("arm_readiness") == "ready_materializable"
            and seal.get("blocked_arms") == ["A_USER", "B"],
            f"{label}: draft seal/readiness state mismatch",
        )
        binding = (
            suite_lock.get("case_bindings", {})
            .get(case_id, {})
            .get("base_repository", {})
        )
        checks.check(
            binding
            == {
                "recipe_ref": recipe_ref,
                "recipe_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "arm": "A",
                "status": "ready_materializable",
                "projection_mode": projection_mode,
            },
            f"{label}: suite treatment binding mismatch",
        )
        stable = stable_cases.get(case_id, {})
        checks.check(
            stable.get("recipe_ref") == recipe_ref
            and stable.get("recipe_sha256")
            == hashlib.sha256(path.read_bytes()).hexdigest()
            and stable.get("content_manifest_sha256") == expected_manifest
            and stable.get("source", {}).get("commit") == source_commit
            and stable.get("source", {}).get("tree") == source_tree,
            f"{label}: stable materialization receipt differs from recipe/source",
        )
        stable_tree = stable.get("root_tree")
        checks.check(
            isinstance(stable_tree, str)
            and SHA_RE.fullmatch(stable_tree) is not None
            and stable.get("root_commit") == canonical_root_commit_sha(stable_tree),
            f"{label}: stable canonical root commit/tree mismatch",
        )

    checks.check(
        set(recipes) == set(BASE_RECIPE_REFS),
        "base recipes: formal eight-case registry is incomplete",
    )
    if not verify_materializations or set(recipes) != set(BASE_RECIPE_REFS):
        return

    try:
        from base_repo.materialize import MaterializationError, materialize
    except ImportError as exc:
        checks.errors.append(f"base recipes: cannot import materializer: {exc}")
        return

    with tempfile.TemporaryDirectory(
        prefix="feat397-base-replay-", dir="/private/tmp"
    ) as temp_dir:
        temp_root = Path(temp_dir)

        def replay(case_id: str) -> tuple[str, Path, Path, Path, dict[str, Any]]:
            case_root = temp_root / case_id
            case_root.mkdir()
            output = case_root / "repository"
            manifest = case_root / "content-manifest.json"
            receipt = case_root / "receipt.json"
            result = materialize(
                ROOT / BASE_RECIPE_REFS[case_id], REPO, output, manifest, receipt
            )
            return case_id, output, manifest, receipt, result

        completed: list[tuple[str, Path, Path, Path, dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=len(BASE_RECIPE_REFS)) as executor:
            futures = {
                executor.submit(replay, case_id): case_id
                for case_id in BASE_RECIPE_REFS
            }
            for future in as_completed(futures):
                case_id = futures[future]
                try:
                    completed.append(future.result())
                except (MaterializationError, OSError, RuntimeError, ValueError) as exc:
                    checks.errors.append(
                        f"base-recipe/{case_id}: materialization replay failed: {exc}"
                    )

        for case_id, output, manifest_path, receipt_path, result in sorted(completed):
            label = f"base-recipe/{case_id}/replay"
            try:
                manifest = json.loads(manifest_path.read_text())
                receipt = json.loads(receipt_path.read_text())
                head_entries = git_head_entries(output)
            except (OSError, RuntimeError, json.JSONDecodeError) as exc:
                checks.errors.append(f"{label}: cannot inspect replay: {exc}")
                continue
            declared_entries = manifest.get("entries", [])
            checks.check(
                file_manifest(head_entries) == declared_entries,
                f"{label}: HEAD differs from content manifest",
            )
            expected_hash = recipes[case_id]["assertions"][
                "expected_content_manifest_sha256"
            ]
            checks.check(
                manifest.get("files_manifest_sha256") == expected_hash
                and receipt.get("content_manifest_sha256") == expected_hash
                and result.get("files_manifest_sha256") == expected_hash,
                f"{label}: frozen manifest hash mismatch",
            )
            checks.check(
                receipt.get("recipe_sha256")
                == hashlib.sha256(
                    (ROOT / BASE_RECIPE_REFS[case_id]).read_bytes()
                ).hexdigest(),
                f"{label}: receipt recipe hash mismatch",
            )
            stable = stable_cases[case_id]
            checks.check(
                result.get("head") == stable.get("root_commit")
                and result.get("tree") == stable.get("root_tree"),
                f"{label}: root commit/tree differs from stable receipt",
            )
            stable_scrub = stable.get("scrub", {})
            actual_scrub = receipt.get("scrub", {})
            checks.check(
                stable_scrub.get("removed_manifest_sha256")
                == actual_scrub.get("removed_manifest_sha256")
                and stable_scrub.get("removed_entry_count")
                == len(actual_scrub.get("removed_entries", []))
                and stable_scrub.get("change_unit_roots_sha256")
                == actual_scrub.get("change_units", {}).get("removed_roots_sha256")
                and stable_scrub.get("change_unit_root_count")
                == len(actual_scrub.get("change_units", {}).get("removed_roots", []))
                and stable_scrub.get("completed_archive_preserved")
                == actual_scrub.get("change_units", {}).get(
                    "completed_archive_preserved"
                )
                and stable_scrub.get("proposed_control_roots_sha256")
                == actual_scrub.get("drop_proposed_control", {}).get(
                    "removed_roots_sha256"
                )
                and stable_scrub.get("proposed_control_root_count")
                == len(
                    actual_scrub.get("drop_proposed_control", {}).get(
                        "removed_roots", []
                    )
                )
                and stable_scrub.get("archive_lineage_roots_sha256")
                == actual_scrub.get("archive_lineage", {}).get("removed_roots_sha256")
                and stable_scrub.get("archive_lineage_root_count")
                == len(
                    actual_scrub.get("archive_lineage", {}).get("removed_roots", [])
                ),
                f"{label}: scrub receipt differs from stable summary",
            )
            scan_entries_for_atoms(checks, head_entries, ("feat-397",), label)
            checks.check(
                stable.get("documentation", {}).get("mode")
                == receipt.get("docs_projection", {}).get("mode")
                and stable.get("documentation", {}).get("files_manifest_sha256")
                == receipt.get("docs_projection", {}).get("files_manifest_sha256")
                and stable.get("arm_files_manifest_sha256")
                == receipt.get("arm", {}).get("files_manifest_sha256"),
                f"{label}: projection/arm receipt differs from stable summary",
            )
            checks.check(
                receipt.get("checks")
                == {
                    "assertions": "passed",
                    "clean_worktree": True,
                    "single_parentless_commit": True,
                    "tree_matches_manifest": True,
                },
                f"{label}: materializer checks are incomplete",
            )
            change_root = output / "docs/changes"
            unexpected = (
                sorted(
                    item.name
                    for item in change_root.iterdir()
                    if item.name not in {"README.md", "archive"}
                )
                if change_root.is_dir()
                else ["<missing>"]
            )
            checks.check(
                not unexpected,
                f"{label}: active/retired change-unit roots remain: {unexpected[:5]}",
            )
            validate_fresh_root_git(checks, output, head_entries, label)


def validate_sealable_gate(checks: Validation, suite_lock: dict[str, Any]) -> None:
    """Fail explicitly until every frozen experimental arm can be built."""
    for arm_id in ("A", "A_USER", "B"):
        arm = suite_lock.get("arms", {}).get(arm_id, {})
        if arm.get("readiness") != "ready_materializable":
            blockers = arm.get("blockers", [])
            checks.errors.append(
                f"seal gate blocked: arm {arm_id}: {', '.join(blockers) or 'unspecified blocker'}"
            )


def validate_diagnostics_split(
    checks: Validation, source_registry: dict[str, dict[str, Any]]
) -> None:
    """Keep retired comparison material visible but outside every formal registry."""
    registry = checks.load_json(ROOT / "diagnostics/registry.json")
    entries = registry.get("entries", []) if isinstance(registry, dict) else []
    ids = {item.get("diagnostic_id") for item in entries if isinstance(item, dict)}
    checks.check(
        registry.get("status") == "diagnostic_only"
        and registry.get("formal_main") is False
        and ids
        == {
            "H02-refactor-480-run-delivery-context",
            "H06-bugfix-520-compaction-context-loss",
            "claude-code-h02-0991eac5",
        },
        "diagnostics/registry.json: diagnostic-only registry mismatch",
    )
    for item in entries:
        if not isinstance(item, dict):
            continue
        checks.check(
            item.get("formal_main") is False and item.get("sealed") is False,
            f"diagnostics/{item.get('diagnostic_id', '<missing>')}: diagnostic entered formal/sealed state",
        )
    checks.check(
        "claude-code-h02-0991eac5" not in source_registry,
        "diagnostics: external Claude source leaked back into formal source roots",
    )
    rejected = next(
        (
            item
            for item in entries
            if isinstance(item, dict)
            and item.get("diagnostic_id") == "H06-bugfix-520-compaction-context-loss"
        ),
        {},
    )
    checks.check(
        rejected.get("kind") == "candidate_disposition"
        and rejected.get("status") == "owner_rejected_for_formal_suite"
        and "H06" not in EXPECTED_CASE_REFS
        and "H06" not in BASE_RECIPE_REFS
        and not any(
            source.get("source", {}).get("source_id", "").startswith("nano-h06-")
            for source in source_registry.values()
        ),
        "diagnostics: rejected bugfix-520/H06 entered or lost its formal-suite disposition",
    )


def validate_protocol_contract(checks: Validation) -> None:
    """Freeze canonical Git and formal H02 semantics in the normative protocol."""
    try:
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        checks.errors.append(f"protocol.md: cannot read protocol: {exc}")
        return
    checks.check(
        "refs/heads/evaluation" not in protocol,
        "protocol.md: obsolete evaluation branch survives",
    )
    checks.check(
        "refs/heads/main" in protocol, "protocol.md: canonical main branch is missing"
    )
    for obsolete in (
        "H02 的 portfolio",
        "H02 的 after-output",
        "D06 未获答",
        "activated D11",
    ):
        checks.check(
            obsolete not in protocol,
            f"protocol.md: obsolete H02 contract survives: {obsolete}",
        )
    checks.check(
        "H02 是正式 single-unit historical regression" in protocol
        and "H02 以 `gate2_complete` 进入 S4" in protocol,
        "protocol.md: formal H02 single-unit/gate2_complete contract is missing",
    )


def main() -> int:
    allowed_arguments = {
        "--require-complete-runs",
        "--require-sealable",
        "--verify-base-repositories",
    }
    unknown_arguments = set(sys.argv[1:]) - allowed_arguments
    if unknown_arguments:
        print(
            f"unknown validator arguments: {sorted(unknown_arguments)}", file=sys.stderr
        )
        return 2
    require_complete_runs = "--require-complete-runs" in sys.argv[1:]
    require_sealable = "--require-sealable" in sys.argv[1:]
    verify_base_repositories = "--verify-base-repositories" in sys.argv[1:]
    checks = Validation()
    schemas: dict[str, dict[str, Any]] = {}
    for name, path in SCHEMA_PATHS.items():
        schema = checks.load_json(path)
        checks.check(
            isinstance(schema, dict),
            f"{path.relative_to(REPO)}: schema root must be an object",
        )
        if isinstance(schema, dict):
            schemas[name] = schema

    source_registry = (
        validate_source_root_manifest(checks, schemas["source_roots"])
        if "source_roots" in schemas
        else {}
    )
    validate_diagnostics_split(checks, source_registry)
    validate_protocol_contract(checks)

    dataset = checks.load_json(ROOT / "dataset.json")
    if not isinstance(dataset, dict):
        print(
            "dataset validation failed: dataset.json root must be an object",
            file=sys.stderr,
        )
        return 1
    registered = dataset.get("cases", [])
    if not isinstance(registered, list):
        print(
            "dataset validation failed: dataset.json cases must be an array",
            file=sys.stderr,
        )
        return 1
    checks.check(
        len(registered) == 8, f"dataset.json: expected 8 cases, found {len(registered)}"
    )
    valid_entries = [item for item in registered if isinstance(item, dict)]
    checks.check(
        len(valid_entries) == len(registered),
        "dataset.json: every case entry must be an object",
    )
    checks.check(
        len({item.get("case_id") for item in valid_entries}) == len(valid_entries),
        "dataset.json: duplicate case ids",
    )
    checks.check(
        {item.get("case_id") for item in valid_entries} == set(EXPECTED_CASE_REFS),
        "dataset.json: case ids differ from the fixed eight-case registry",
    )
    for item in valid_entries:
        case_id = item.get("case_id")
        case_ref = item.get("case_ref", "")
        expected_ref = EXPECTED_CASE_REFS.get(case_id)
        checks.check(
            canonical_relative_path(case_ref) == case_ref and case_ref == expected_ref,
            f"dataset.json/{case_id}: case_ref differs from fixed canonical path",
        )
        if expected_ref:
            expected_path = ROOT / expected_ref
            checks.check(
                not has_symlink_component(expected_path, ROOT)
                and expected_path.resolve().is_relative_to((ROOT / "cases").resolve()),
                f"dataset.json/{case_id}: case_ref uses a symlink or escapes cases root",
            )
    suite_lock = (
        validate_suite_treatment_lock(
            checks,
            schemas["suite_lock"],
            schemas["lineage"],
            dataset,
            valid_entries,
        )
        if "suite_lock" in schemas and "lineage" in schemas
        else {}
    )
    if "base_recipe" in schemas:
        validate_base_repository_recipes(
            checks,
            schemas["base_recipe"],
            suite_lock,
            source_registry,
            verify_base_repositories,
        )
    if require_sealable:
        validate_sealable_gate(checks, suite_lock)

    for entry in valid_entries:
        case_id = entry.get("case_id", "<missing>")
        case_path = ROOT / EXPECTED_CASE_REFS.get(case_id, "__invalid__/case.json")
        case_dir = case_path.parent
        for path in case_dir.rglob("*"):
            checks.check(
                not path.is_symlink(),
                f"{case_id}: case asset tree contains symlink {path.relative_to(case_dir)}",
            )
        files = {
            str(path.relative_to(case_dir))
            for path in case_dir.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        checks.check(
            files == FIXED_CASE_ASSETS,
            f"{case_id}: fixed assets differ: {sorted(files ^ FIXED_CASE_ASSETS)}",
        )
        for relative in FIXED_CASE_ASSETS:
            asset = case_dir / relative
            checks.check(
                asset.is_file()
                and not asset.is_symlink()
                and not has_symlink_component(asset, case_dir)
                and asset.resolve().is_relative_to(case_dir.resolve()),
                f"{case_id}: fixed asset is missing, aliased or escaped: {relative}",
            )
        case = checks.load_json(case_path)
        if "case" in schemas:
            validate_schema_instance(checks, case_path, schemas["case"])
        if "authority" in schemas:
            validate_schema_instance(
                checks, case_dir / "knowledge/authority-map.json", schemas["authority"]
            )
        if "inventory" in schemas:
            validate_schema_instance(
                checks,
                case_dir / "judge-private/decision-inventory.json",
                schemas["inventory"],
            )
        if not isinstance(case, dict):
            continue
        validate_runtime_ref_contract(checks, case)
        checks.check(
            case.get("case_id") == case_id, f"{case_id}: case.json id mismatch"
        )
        checks.check(
            case.get("title") == entry.get("title"),
            f"{case_id}: dataset title mismatch",
        )
        checks.check(
            case.get("stratum") == entry.get("stratum"),
            f"{case_id}: dataset stratum mismatch",
        )
        checks.check(
            case.get("status") == entry.get("status"),
            f"{case_id}: dataset status mismatch",
        )
        checks.check(
            case.get("normalization", {}).get("level")
            == suite_lock.get("case_bindings", {})
            .get(case_id, {})
            .get("normalization_level"),
            f"{case_id}: normalization level differs from suite lock",
        )
        expected_oracle_lineage = (
            "historical_target_derived_private"
            if case.get("stratum") == "historical_regression"
            else "prospective_pre_output"
        )
        checks.check(
            case.get("contamination", {}).get("oracle_lineage")
            == expected_oracle_lineage,
            f"{case_id}: oracle lineage mismatch",
        )
        authoring = case.get("treatment_authoring", {})
        checks.check(
            authoring.get("evidence_ref") == "audit/provenance.md#lineage-audit",
            f"{case_id}: treatment-authoring evidence ref mismatch",
        )
        validate_local_ref(
            checks,
            case_dir,
            authoring.get("evidence_ref", ""),
            f"{case_id}/treatment-authoring",
            "audit",
        )
        if case.get("stratum") == "prospective_holdout":
            authoring_freeze = suite_lock.get("authoring_freeze", {})
            checks.check(
                authoring_freeze.get("status") == "frozen"
                and authoring.get("status") == "post_treatment_freeze_blind"
                and authoring.get("clean_holdout_eligible") is True,
                f"{case_id}: clean holdout lacks a prior treatment-authoring freeze",
            )
            checks.check(
                authoring.get("authoring_freeze_sha256")
                == authoring_freeze.get("receipt", {}).get("sha256"),
                f"{case_id}: clean holdout authoring-freeze receipt hash mismatch",
            )
            try:
                freeze_time = datetime.fromisoformat(
                    authoring_freeze.get("frozen_at", "")
                )
                published_time = datetime.fromisoformat(
                    authoring_freeze.get("receipt", {}).get("published_at", "")
                )
                authored_time = datetime.fromisoformat(
                    authoring.get("case_authored_at", "")
                )
            except (TypeError, ValueError):
                checks.errors.append(
                    f"{case_id}: clean holdout authoring timestamps are invalid"
                )
            else:
                checks.check(
                    freeze_time.tzinfo is not None
                    and published_time.tzinfo is not None
                    and authored_time.tzinfo is not None
                    and authored_time > published_time >= freeze_time,
                    f"{case_id}: clean holdout must be authored after the published treatment freeze",
                )
            validate_clean_holdout_authorship(
                checks, case_id, case_dir, authoring, authoring_freeze
            )
        excludes = set(
            case.get("restrictions", {}).get("candidate_export_excludes", [])
        )
        checks.check(
            {"case.json", "knowledge", "judge-private", "audit"}.issubset(excludes),
            f"{case_id}: incomplete candidate exclusions",
        )
        authorities = validate_authority_map(checks, case_dir, case_id)
        validate_case_source_roots(checks, case, case_dir, authorities, source_registry)
        validate_decisions(checks, case_dir, case_id, authorities)
        validate_leak_signatures(checks, case_dir, case_id)
        validate_ready_lifecycle(checks, case_dir, case_id, case)
        if "owner_policy" in schemas:
            validate_owner_answer_policy(
                checks, case, case_dir, schemas["owner_policy"], authorities
            )
        if "layer" in schemas and "treatment" in schemas:
            validate_runtime_manifests(
                checks, case, case_dir, schemas, source_registry, suite_lock
            )

    if "suite_seal" in schemas:
        suite_seal = validate_suite_seal(
            checks, schemas["suite_seal"], dataset, valid_entries
        )
        if "run_ledger" in schemas:
            validate_run_ledgers(
                checks, schemas["run_ledger"], suite_seal, require_complete_runs
            )

    template_bindings = [
        ("case", ROOT / "templates/case.json"),
        ("authority", ROOT / "templates/knowledge/authority-map.json"),
        ("inventory", ROOT / "templates/judge-private/decision-inventory.json"),
        ("owner_policy", ROOT / "templates/runtime/owner-answer-policy.json"),
        ("lineage", ROOT / "templates/runtime/lineage-manifest.json"),
        ("run_ledger", ROOT / "templates/runtime/run-ledger.json"),
        ("layer", ROOT / "templates/runtime/layer-manifest.json"),
        ("treatment", ROOT / "templates/runtime/treatment-manifest.json"),
        ("doc_system", ROOT / "templates/runtime/doc-system.json"),
        ("doc_projection", ROOT / "templates/runtime/doc-projection.json"),
        ("doc_validation", ROOT / "templates/runtime/doc-validation.json"),
        (
            "reasoning_settings",
            ROOT / "templates/runtime/seal-inputs/model-reasoning.json",
        ),
        (
            "reasoning_settings",
            ROOT / "templates/runtime/seal-inputs/judge-reasoning.json",
        ),
        ("tool_manifest", ROOT / "templates/runtime/seal-inputs/tool-manifest.json"),
        (
            "permission_manifest",
            ROOT / "templates/runtime/seal-inputs/permission-manifest.json",
        ),
        ("sandbox_policy", ROOT / "templates/runtime/seal-inputs/sandbox-policy.json"),
    ]
    for name, path in template_bindings:
        if name in schemas:
            validate_schema_instance(checks, path, schemas[name])
    for component_id, runtime_ref in CONTROL_COMPONENT_REFS.items():
        template_path = ROOT / "templates/runtime/seal-inputs" / Path(runtime_ref).name
        validate_control_document(
            checks,
            template_path.read_text(errors="replace"),
            component_id,
            f"templates/runtime/seal-inputs/{template_path.name}",
        )

    for path in ROOT.rglob("*.json"):
        checks.load_json(path)
    validate_markdown_links(checks)

    if checks.errors:
        print(
            f"dataset validation failed with {len(checks.errors)} error(s):",
            file=sys.stderr,
        )
        for error in checks.errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "dataset validation passed: "
        f"8 cases, {checks.source_root_count} source roots, "
        f"{checks.schema_validation_count} schema validations, {checks.json_count} JSON files, "
        f"{checks.authority_count} authorities, {checks.decision_count} decisions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
