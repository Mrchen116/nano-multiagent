#!/usr/bin/env python3
"""Materialize one sealed evaluation base repository from a declarative recipe."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any
import unicodedata
import zlib


FRESH_ROOT_BRANCH = "main"
FRESH_ROOT_COMMIT_MESSAGE = "initial repository"
FRESH_ROOT_IDENTITY = ("Repository Bootstrap", "repository@invalid")
FRESH_ROOT_EPOCH = 946684800
UNIT_ID_RE = re.compile(r"^(?:feat|bugfix|refactor|perf)-[0-9]+$")
FRESH_ROOT_CONFIG = (
    b"[core]\n"
    b"\trepositoryformatversion = 0\n"
    b"\tfilemode = true\n"
    b"\tbare = false\n"
    b"\tlogallrefupdates = false\n"
    b"\tignorecase = true\n"
    b"\tprecomposeunicode = true\n"
)


class MaterializationError(RuntimeError):
    """The recipe or requested materialization violates the sealed input contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def isolated_git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    environment["GIT_PAGER"] = "cat"
    environment["GIT_EXTERNAL_DIFF"] = ""
    return environment


def run_git(
    repository: Path,
    *args: str,
    input_bytes: bytes | None = None,
    extra_environment: dict[str, str] | None = None,
) -> bytes:
    environment = isolated_git_environment()
    if extra_environment:
        environment.update(extra_environment)
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        env=environment,
        input=input_bytes,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        detail = (
            result.stderr.decode(errors="replace").strip()
            or result.stdout.decode(errors="replace").strip()
        )
        raise MaterializationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def canonical_relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MaterializationError(f"{label} must be a non-empty relative path")
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise MaterializationError(
            f"{label} is not a canonical relative path: {value!r}"
        )
    if unicodedata.normalize("NFC", value) != value:
        raise MaterializationError(f"{label} is not NFC-normalized: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise MaterializationError(
            f"{label} is not a canonical relative path: {value!r}"
        )
    if parts[0].casefold() == ".git":
        raise MaterializationError(f"{label} may not target Git metadata: {value!r}")
    return value


def path_is_within(path: str, root: str) -> bool:
    folded_path = unicodedata.normalize("NFC", path).casefold()
    folded_root = unicodedata.normalize("NFC", root.rstrip("/")).casefold()
    return folded_path == folded_root or folded_path.startswith(f"{folded_root}/")


def require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MaterializationError(f"{label} must be an object")
    return value


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MaterializationError(f"{label} must be a non-empty string")
    return value


def require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise MaterializationError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise MaterializationError(f"{label} contains duplicates")
    return value


def require_sha(value: object, label: str) -> str:
    text = require_string(value, label)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise MaterializationError(f"{label} must be a lowercase SHA-256")
    return text


def load_recipe(path: Path) -> tuple[dict[str, Any], bytes]:
    if not path.is_file() or path.is_symlink():
        raise MaterializationError(f"recipe must be an ordinary file: {path}")
    raw = path.read_bytes()
    try:
        recipe = json.loads(raw)
    except json.JSONDecodeError as error:
        raise MaterializationError(f"recipe is not valid JSON: {error}") from error
    recipe = require_mapping(recipe, "recipe")
    schema_version = recipe.get("schema_version")
    if schema_version not in {"1.0", "2.0"}:
        raise MaterializationError("recipe.schema_version must be '1.0' or '2.0'")
    require_string(recipe.get("case_id"), "recipe.case_id")
    if schema_version == "2.0":
        contract = require_mapping(recipe.get("contract"), "recipe.contract")
        if contract.get("method_id") != "counterfactual-latest-base-v1":
            raise MaterializationError("recipe.contract.method_id mismatch")
        if contract.get("projection_level") != "DP1-counterfactual-latest-v1":
            raise MaterializationError("recipe.contract.projection_level mismatch")
        if (
            contract.get("truth_formula")
            != "Code@B + ProductClaims@B + DocsFramework@F + Workflow@W"
        ):
            raise MaterializationError("recipe.contract.truth_formula mismatch")
        clocks = require_mapping(contract.get("clocks"), "recipe.contract.clocks")
        if set(clocks) != {
            "product",
            "knowledge",
            "documentation_framework",
            "workflow",
            "user",
            "model_tool",
        }:
            raise MaterializationError(
                "recipe.contract.clocks must contain the six frozen clocks"
            )
        if contract.get("layers") != [
            "product_world",
            "documentation_world",
            "common_compatibility",
            "arm_bundle",
            "private_controls",
        ]:
            raise MaterializationError(
                "recipe.contract.layers must contain the five ordered layers"
            )
        seal = require_mapping(recipe.get("seal"), "recipe.seal")
        if seal.get("suite_status") != "draft_unsealable":
            raise MaterializationError(
                "recipe.seal.suite_status must remain draft_unsealable"
            )
    source = require_mapping(recipe.get("source"), "recipe.source")
    require_string(source.get("ref"), "recipe.source.ref")
    require_string(source.get("expected_commit"), "recipe.source.expected_commit")
    require_string(source.get("expected_tree"), "recipe.source.expected_tree")
    scrub = require_mapping(recipe.get("scrub"), "recipe.scrub")
    for index, item in enumerate(
        require_string_list(scrub.get("remove_paths"), "recipe.scrub.remove_paths")
    ):
        canonical_relative_path(item, f"recipe.scrub.remove_paths[{index}]")
    for index, item in enumerate(
        require_string_list(
            scrub.get("drop_proposed_control", []),
            "recipe.scrub.drop_proposed_control",
        )
    ):
        canonical_relative_path(item, f"recipe.scrub.drop_proposed_control[{index}]")
    require_string(scrub.get("instruction_marker"), "recipe.scrub.instruction_marker")
    for index, item in enumerate(
        require_string_list(
            scrub.get("product_instruction_roots"),
            "recipe.scrub.product_instruction_roots",
        )
    ):
        canonical_relative_path(
            item, f"recipe.scrub.product_instruction_roots[{index}]"
        )
    if (
        schema_version == "2.0"
        and scrub.get("change_unit_policy")
        != "remove_active_and_retired_keep_completed_archive"
    ):
        raise MaterializationError(
            "recipe.scrub.change_unit_policy must be "
            "'remove_active_and_retired_keep_completed_archive'"
        )
    archive_lineage_raw = scrub.get("archive_lineage")
    if schema_version == "2.0" or archive_lineage_raw is not None:
        archive_lineage = require_mapping(
            archive_lineage_raw, "recipe.scrub.archive_lineage"
        )
        unexpected = sorted(set(archive_lineage) - {"policy", "drop_units"})
        if unexpected:
            raise MaterializationError(
                f"recipe.scrub.archive_lineage has unsupported fields: {unexpected}"
            )
        if archive_lineage.get("policy") != "drop_noncompleted_cross_references_v1":
            raise MaterializationError(
                "recipe.scrub.archive_lineage.policy must be "
                "'drop_noncompleted_cross_references_v1'"
            )
        drop_units = archive_lineage.get("drop_units")
        if not isinstance(drop_units, list) or not drop_units:
            raise MaterializationError(
                "recipe.scrub.archive_lineage.drop_units must be a non-empty array"
            )
        drop_paths: list[str] = []
        for index, raw_entry in enumerate(drop_units):
            entry = require_mapping(
                raw_entry,
                f"recipe.scrub.archive_lineage.drop_units[{index}]",
            )
            if set(entry) != {"path", "referenced_noncompleted_unit_ids"}:
                raise MaterializationError(
                    "recipe.scrub.archive_lineage.drop_units entries must contain only "
                    "path and referenced_noncompleted_unit_ids"
                )
            relative = canonical_relative_path(
                entry.get("path"),
                f"recipe.scrub.archive_lineage.drop_units[{index}].path",
            )
            if (
                not relative.startswith("docs/changes/archive/")
                or relative.count("/") != 3
            ):
                raise MaterializationError(
                    "recipe.scrub.archive_lineage drop path must be one whole archive unit root"
                )
            referenced_ids = require_string_list(
                entry.get("referenced_noncompleted_unit_ids"),
                "recipe.scrub.archive_lineage.drop_units"
                f"[{index}].referenced_noncompleted_unit_ids",
            )
            if (
                not referenced_ids
                or referenced_ids != sorted(set(referenced_ids))
                or any(
                    UNIT_ID_RE.fullmatch(unit_id) is None for unit_id in referenced_ids
                )
            ):
                raise MaterializationError(
                    "recipe.scrub.archive_lineage referenced unit ids must be non-empty, "
                    "unique, sorted change-unit ids"
                )
            drop_paths.append(relative)
        if drop_paths != sorted(set(drop_paths)):
            raise MaterializationError(
                "recipe.scrub.archive_lineage drop paths must be unique and sorted"
            )

    projection = require_mapping(
        recipe.get("docs_projection"), "recipe.docs_projection"
    )
    projection_mode = require_string(
        projection.get("mode"), "recipe.docs_projection.mode"
    )
    if projection_mode == "preserve_exact":
        unexpected = sorted(set(projection) - {"mode"})
        if unexpected:
            raise MaterializationError(
                f"recipe.docs_projection preserve_exact has unsupported fields: {unexpected}"
            )
    elif projection_mode == "workflow_owned_replace":
        unexpected = sorted(set(projection) - {"mode", "ref", "files"})
        if unexpected:
            raise MaterializationError(
                f"recipe.docs_projection workflow_owned_replace has unsupported fields: {unexpected}"
            )
        require_string(projection.get("ref"), "recipe.docs_projection.ref")
        projection_files = projection.get("files")
        if not isinstance(projection_files, list) or not projection_files:
            raise MaterializationError(
                "recipe.docs_projection.files must be a non-empty array"
            )
        projection_destinations: set[str] = set()
        for index, raw_entry in enumerate(projection_files):
            entry = require_mapping(raw_entry, f"recipe.docs_projection.files[{index}]")
            unexpected_entry = sorted(set(entry) - {"source", "destination", "sha256"})
            if unexpected_entry:
                raise MaterializationError(
                    f"recipe.docs_projection.files[{index}] has unsupported fields: {unexpected_entry}"
                )
            canonical_relative_path(
                entry.get("source"), f"recipe.docs_projection.files[{index}].source"
            )
            destination = canonical_relative_path(
                entry.get("destination"),
                f"recipe.docs_projection.files[{index}].destination",
            )
            if destination in projection_destinations:
                raise MaterializationError(
                    f"duplicate docs projection destination: {destination}"
                )
            projection_destinations.add(destination)
            require_sha(
                entry.get("sha256"), f"recipe.docs_projection.files[{index}].sha256"
            )
    elif projection_mode == "dp1_counterfactual_latest":
        unexpected = sorted(
            set(projection)
            - {
                "mode",
                "ref",
                "expected_commit",
                "expected_tree",
                "product_claim_source",
                "files",
                "generated_files",
            }
        )
        if unexpected:
            raise MaterializationError(
                f"recipe.docs_projection dp1_counterfactual_latest has unsupported fields: {unexpected}"
            )
        require_string(projection.get("ref"), "recipe.docs_projection.ref")
        require_string(
            projection.get("expected_commit"), "recipe.docs_projection.expected_commit"
        )
        require_string(
            projection.get("expected_tree"), "recipe.docs_projection.expected_tree"
        )
        if projection.get("product_claim_source") != "baseline_only":
            raise MaterializationError(
                "recipe.docs_projection.product_claim_source must be 'baseline_only'"
            )
        projection_files = projection.get("files")
        generated_files = projection.get("generated_files")
        if not isinstance(projection_files, list) or not projection_files:
            raise MaterializationError(
                "recipe.docs_projection.files must be a non-empty array"
            )
        if not isinstance(generated_files, list) or not generated_files:
            raise MaterializationError(
                "recipe.docs_projection.generated_files must be a non-empty array"
            )
        projection_destinations: set[str] = set()
        for index, raw_entry in enumerate(projection_files):
            entry = require_mapping(raw_entry, f"recipe.docs_projection.files[{index}]")
            if sorted(
                set(entry)
                - {
                    "source",
                    "source_clock",
                    "destination",
                    "sha256",
                    "output_sha256",
                    "install",
                    "transform",
                }
            ):
                raise MaterializationError(
                    f"recipe.docs_projection.files[{index}] has unsupported fields"
                )
            canonical_relative_path(
                entry.get("source"), f"recipe.docs_projection.files[{index}].source"
            )
            destination = canonical_relative_path(
                entry.get("destination"),
                f"recipe.docs_projection.files[{index}].destination",
            )
            if destination in projection_destinations:
                raise MaterializationError(
                    f"duplicate docs projection destination: {destination}"
                )
            projection_destinations.add(destination)
            require_sha(
                entry.get("sha256"), f"recipe.docs_projection.files[{index}].sha256"
            )
            require_sha(
                entry.get("output_sha256"),
                f"recipe.docs_projection.files[{index}].output_sha256",
            )
            if entry.get("source_clock") not in {
                "product_baseline",
                "documentation_framework",
            }:
                raise MaterializationError(
                    f"recipe.docs_projection.files[{index}].source_clock is invalid"
                )
            if entry.get("install") not in {"create", "replace"}:
                raise MaterializationError(
                    f"recipe.docs_projection.files[{index}].install must be create or replace"
                )
            transform = require_mapping(
                entry.get("transform"),
                f"recipe.docs_projection.files[{index}].transform",
            )
            transform_kind = transform.get("kind")
            if transform_kind == "move_exact":
                if set(transform) != {"kind"}:
                    raise MaterializationError(
                        f"recipe.docs_projection.files[{index}].transform move_exact has extra fields"
                    )
            elif transform_kind == "replace_exact":
                if set(transform) != {"kind", "old", "new", "expected_replacements"}:
                    raise MaterializationError(
                        f"recipe.docs_projection.files[{index}].transform replace_exact fields mismatch"
                    )
                require_string(
                    transform.get("old"),
                    f"recipe.docs_projection.files[{index}].transform.old",
                )
                require_string(
                    transform.get("new"),
                    f"recipe.docs_projection.files[{index}].transform.new",
                )
                if (
                    not isinstance(transform.get("expected_replacements"), int)
                    or transform["expected_replacements"] < 1
                ):
                    raise MaterializationError(
                        f"recipe.docs_projection.files[{index}].transform.expected_replacements is invalid"
                    )
            else:
                raise MaterializationError(
                    f"recipe.docs_projection.files[{index}].transform.kind is invalid"
                )
        for index, raw_entry in enumerate(generated_files):
            entry = require_mapping(
                raw_entry, f"recipe.docs_projection.generated_files[{index}]"
            )
            if sorted(
                set(entry) - {"destination", "mode", "content", "sha256", "install"}
            ):
                raise MaterializationError(
                    f"recipe.docs_projection.generated_files[{index}] has unsupported fields"
                )
            destination = canonical_relative_path(
                entry.get("destination"),
                f"recipe.docs_projection.generated_files[{index}].destination",
            )
            if destination in projection_destinations:
                raise MaterializationError(
                    f"duplicate docs projection destination: {destination}"
                )
            projection_destinations.add(destination)
            if entry.get("mode") != "100644":
                raise MaterializationError(
                    f"recipe.docs_projection.generated_files[{index}].mode must be 100644"
                )
            require_string(
                entry.get("content"),
                f"recipe.docs_projection.generated_files[{index}].content",
            )
            require_sha(
                entry.get("sha256"),
                f"recipe.docs_projection.generated_files[{index}].sha256",
            )
            if entry.get("install") not in {"create", "replace"}:
                raise MaterializationError(
                    f"recipe.docs_projection.generated_files[{index}].install must be create or replace"
                )
    else:
        raise MaterializationError(
            "recipe.docs_projection.mode must be preserve_exact, workflow_owned_replace, "
            "or dp1_counterfactual_latest"
        )

    arm = require_mapping(recipe.get("arm"), "recipe.arm")
    require_string(arm.get("id"), "recipe.arm.id")
    require_string(arm.get("ref"), "recipe.arm.ref")
    files = arm.get("files")
    if not isinstance(files, list) or not files:
        raise MaterializationError("recipe.arm.files must be a non-empty array")
    destinations: set[str] = set()
    for index, raw_entry in enumerate(files):
        entry = require_mapping(raw_entry, f"recipe.arm.files[{index}]")
        allowed_fields = {"source", "destination", "sha256"}
        if schema_version == "2.0":
            allowed_fields.update({"install", "output_sha256", "transform"})
        unexpected_entry = sorted(set(entry) - allowed_fields)
        if unexpected_entry:
            raise MaterializationError(
                f"recipe.arm.files[{index}] has unsupported fields: {unexpected_entry}"
            )
        canonical_relative_path(
            entry.get("source"), f"recipe.arm.files[{index}].source"
        )
        destination = canonical_relative_path(
            entry.get("destination"), f"recipe.arm.files[{index}].destination"
        )
        if destination in destinations:
            raise MaterializationError(f"duplicate arm destination: {destination}")
        destinations.add(destination)
        require_sha(entry.get("sha256"), f"recipe.arm.files[{index}].sha256")
        if schema_version == "2.0" and entry.get("install") not in {
            "create",
            "replace",
            "preserve_exact",
        }:
            raise MaterializationError(
                f"recipe.arm.files[{index}].install must be create, replace, or preserve_exact"
            )
        has_transform = "transform" in entry
        if has_transform != ("output_sha256" in entry):
            raise MaterializationError(
                f"recipe.arm.files[{index}] must pair transform with output_sha256"
            )
        if has_transform:
            if entry.get("install") == "preserve_exact":
                raise MaterializationError(
                    f"recipe.arm.files[{index}] cannot transform a preserve_exact entry"
                )
            require_sha(
                entry.get("output_sha256"), f"recipe.arm.files[{index}].output_sha256"
            )
            transform = require_mapping(
                entry.get("transform"), f"recipe.arm.files[{index}].transform"
            )
            if set(transform) != {"kind", "heading", "expected_occurrences"}:
                raise MaterializationError(
                    f"recipe.arm.files[{index}].transform fields mismatch"
                )
            if transform.get("kind") != "keep_before_heading":
                raise MaterializationError(
                    f"recipe.arm.files[{index}].transform.kind is invalid"
                )
            heading = require_string(
                transform.get("heading"),
                f"recipe.arm.files[{index}].transform.heading",
            )
            if "\n" in heading or "\r" in heading or not heading.startswith("## "):
                raise MaterializationError(
                    f"recipe.arm.files[{index}].transform.heading must be one level-two heading"
                )
            if (
                not isinstance(transform.get("expected_occurrences"), int)
                or transform["expected_occurrences"] < 1
            ):
                raise MaterializationError(
                    f"recipe.arm.files[{index}].transform.expected_occurrences is invalid"
                )
    generated_arm_files = arm.get("generated_files", [])
    if not isinstance(generated_arm_files, list):
        raise MaterializationError("recipe.arm.generated_files must be an array")
    if schema_version == "1.0" and generated_arm_files:
        raise MaterializationError(
            "recipe.arm.generated_files is only supported by schema_version 2.0"
        )
    for index, raw_entry in enumerate(generated_arm_files):
        entry = require_mapping(raw_entry, f"recipe.arm.generated_files[{index}]")
        if sorted(set(entry) - {"destination", "mode", "content", "sha256", "install"}):
            raise MaterializationError(
                f"recipe.arm.generated_files[{index}] has unsupported fields"
            )
        destination = canonical_relative_path(
            entry.get("destination"), f"recipe.arm.generated_files[{index}].destination"
        )
        if destination in destinations:
            raise MaterializationError(f"duplicate arm destination: {destination}")
        destinations.add(destination)
        if entry.get("mode") != "100644":
            raise MaterializationError(
                f"recipe.arm.generated_files[{index}].mode must be 100644"
            )
        require_string(
            entry.get("content"), f"recipe.arm.generated_files[{index}].content"
        )
        require_sha(entry.get("sha256"), f"recipe.arm.generated_files[{index}].sha256")
        if entry.get("install") not in {"create", "replace"}:
            raise MaterializationError(
                f"recipe.arm.generated_files[{index}].install must be create or replace"
            )

    assertions = require_mapping(recipe.get("assertions"), "recipe.assertions")
    for field in ("required_paths", "forbidden_paths"):
        for index, item in enumerate(
            require_string_list(assertions.get(field), f"recipe.assertions.{field}")
        ):
            canonical_relative_path(item, f"recipe.assertions.{field}[{index}]")
    require_string_list(
        assertions.get("forbidden_text"), "recipe.assertions.forbidden_text"
    )
    required_hashes = require_mapping(
        assertions.get("required_sha256"), "recipe.assertions.required_sha256"
    )
    for raw_path, digest in required_hashes.items():
        canonical_relative_path(
            raw_path, f"recipe.assertions.required_sha256 key {raw_path!r}"
        )
        require_sha(digest, f"recipe.assertions.required_sha256[{raw_path!r}]")
    for field in (
        "required_text_by_path",
        "forbidden_text_by_path",
        "required_resolved_links",
    ):
        values_by_path = require_mapping(
            assertions.get(field, {}), f"recipe.assertions.{field}"
        )
        for raw_path, raw_values in values_by_path.items():
            canonical_relative_path(
                raw_path, f"recipe.assertions.{field} key {raw_path!r}"
            )
            require_string_list(raw_values, f"recipe.assertions.{field}[{raw_path!r}]")
    if "expected_content_manifest_sha256" in assertions:
        require_sha(
            assertions["expected_content_manifest_sha256"],
            "recipe.assertions.expected_content_manifest_sha256",
        )
    if schema_version == "2.0" and assertions.get("change_units_absent") is not True:
        raise MaterializationError("recipe.assertions.change_units_absent must be true")

    git = require_mapping(recipe.get("git"), "recipe.git")
    branch = require_string(git.get("branch"), "recipe.git.branch")
    if branch.startswith("-") or any(character.isspace() for character in branch):
        raise MaterializationError("recipe.git.branch is not a safe branch name")
    require_string(git.get("author_name"), "recipe.git.author_name")
    require_string(git.get("author_email"), "recipe.git.author_email")
    require_string(git.get("timestamp"), "recipe.git.timestamp")
    require_string(git.get("message"), "recipe.git.message")
    if schema_version == "2.0":
        expected_git = {
            "branch": FRESH_ROOT_BRANCH,
            "author_name": FRESH_ROOT_IDENTITY[0],
            "author_email": FRESH_ROOT_IDENTITY[1],
            "timestamp": f"{FRESH_ROOT_EPOCH} +0000",
            "message": f"{FRESH_ROOT_COMMIT_MESSAGE}\n",
        }
        if git != expected_git:
            raise MaterializationError(
                "recipe.git differs from the canonical fresh-root identity"
            )
    return recipe, raw


def ensure_existing_path_has_no_symlink(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if not current.exists() and not current.is_symlink():
            break
        if current.is_symlink():
            raise MaterializationError(f"{label} uses a symlink component: {current}")


def validate_output_paths(output: Path, manifest: Path, receipt: Path) -> bool:
    absolute_paths = [path.absolute() for path in (output, manifest, receipt)]
    if len(set(absolute_paths)) != 3:
        raise MaterializationError(
            "output, manifest, and receipt paths must be distinct"
        )
    for path, label in (
        (output, "output"),
        (manifest, "manifest"),
        (receipt, "receipt"),
    ):
        ensure_existing_path_has_no_symlink(path, label)
        if not path.parent.is_dir():
            raise MaterializationError(
                f"{label} parent must already exist: {path.parent}"
            )
    for control_path, label in (
        (manifest.absolute(), "manifest"),
        (receipt.absolute(), "receipt"),
    ):
        if (
            output.absolute() == control_path
            or output.absolute() in control_path.parents
        ):
            raise MaterializationError(
                f"{label} must stay outside the candidate output"
            )
        if control_path.exists() or control_path.is_symlink():
            raise MaterializationError(
                f"refusing to overwrite existing {label}: {control_path}"
            )
    if output.is_symlink():
        raise MaterializationError(f"output may not be a symlink: {output}")
    if not output.exists():
        return False
    if not output.is_dir():
        raise MaterializationError(f"output must be a directory: {output}")
    if any(output.iterdir()):
        raise MaterializationError(f"refusing to overwrite non-empty output: {output}")
    return True


def resolve_commit(repository: Path, ref: str) -> tuple[str, str]:
    commit = (
        run_git(
            repository, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
        )
        .decode()
        .strip()
    )
    tree = (
        run_git(
            repository,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{commit}^{{tree}}",
        )
        .decode()
        .strip()
    )
    return commit, tree


def validate_source_tree(repository: Path, commit: str) -> None:
    raw = run_git(repository, "ls-tree", "-rz", "--full-tree", commit)
    for record in raw.split(b"\x00"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise MaterializationError("source tree contains a malformed Git record")
        mode, object_type, _ = metadata.decode().split()
        path = raw_path.decode()
        canonical_relative_path(path, "source Git path")
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise MaterializationError(
                f"source tree contains unsupported entry {mode} {object_type} {path}"
            )


def extract_git_archive(raw_archive: bytes, destination: Path) -> None:
    seen_files: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(raw_archive), mode="r:") as archive:
        for member in archive.getmembers():
            raw_name = member.name.rstrip("/")
            if not raw_name:
                continue
            name = canonical_relative_path(raw_name, "archive member")
            target = destination / name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise MaterializationError(
                    f"archive contains a symlink or special entry: {name}"
                )
            if name in seen_files or target.exists():
                raise MaterializationError(
                    f"archive contains a duplicate entry: {name}"
                )
            seen_files.add(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise MaterializationError(f"cannot read archive entry: {name}")
            target.write_bytes(extracted.read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def file_mode(path: Path) -> str:
    return "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"


def content_manifest(root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise MaterializationError(f"candidate tree contains a symlink: {relative}")
        if path.is_file():
            entries.append(
                {
                    "mode": file_mode(path),
                    "path": relative,
                    "sha256": sha256_bytes(path.read_bytes()),
                }
            )
    return entries


def remove_path(root: Path, relative: str) -> bool:
    target = root / relative
    if not target.exists():
        return False
    if target.is_symlink():
        raise MaterializationError(f"scrub target is a symlink: {relative}")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.is_file():
        target.unlink()
    else:
        raise MaterializationError(
            f"scrub target is not an ordinary file or directory: {relative}"
        )
    return True


def scrub_tree(root: Path, scrub: dict[str, Any]) -> dict[str, Any]:
    removed_before: dict[str, dict[str, str]] = {
        entry["path"]: entry for entry in content_manifest(root)
    }
    explicit_results: list[dict[str, object]] = []
    removed_roots: list[str] = []
    for relative in scrub["remove_paths"]:
        present = remove_path(root, relative)
        explicit_results.append({"path": relative, "present": present})
        if present:
            removed_roots.append(relative)

    proposed_control_results: list[dict[str, object]] = []
    removed_proposed_control_roots: list[str] = []
    for relative in scrub.get("drop_proposed_control", []):
        present = remove_path(root, relative)
        proposed_control_results.append({"path": relative, "present": present})
        if present:
            removed_roots.append(relative)
            removed_proposed_control_roots.append(relative)

    archive_lineage = scrub.get("archive_lineage", {})
    archive_lineage_results: list[dict[str, object]] = []
    removed_archive_lineage_roots: list[str] = []
    for entry in archive_lineage.get("drop_units", []):
        relative = entry["path"]
        present = remove_path(root, relative)
        archive_lineage_results.append(
            {
                "path": relative,
                "referenced_noncompleted_unit_ids": entry[
                    "referenced_noncompleted_unit_ids"
                ],
                "present": present,
            }
        )
        if present:
            removed_roots.append(relative)
            removed_archive_lineage_roots.append(relative)

    marker = scrub["instruction_marker"]
    preserve_roots = scrub["product_instruction_roots"]
    instruction_roots: list[str] = []
    for marker_path in sorted(root.rglob(marker)):
        if marker_path.is_symlink() or not marker_path.is_file():
            raise MaterializationError(
                f"instruction marker is not an ordinary file: {marker_path}"
            )
        relative_marker = marker_path.relative_to(root).as_posix()
        if any(
            path_is_within(relative_marker, preserve) for preserve in preserve_roots
        ):
            continue
        instruction_root = marker_path.parent.relative_to(root).as_posix()
        if instruction_root == ".":
            raise MaterializationError(
                "repository-root instruction marker needs an explicit scrub rule"
            )
        instruction_roots.append(instruction_root)
    for instruction_root in sorted(
        set(instruction_roots), key=lambda value: (value.count("/"), value)
    ):
        if any(path_is_within(instruction_root, parent) for parent in removed_roots):
            continue
        if remove_path(root, instruction_root):
            removed_roots.append(instruction_root)

    change_unit_policy = scrub.get("change_unit_policy")
    removed_change_unit_roots: list[str] = []
    preserved_completed_archive = False
    if change_unit_policy == "remove_active_and_retired_keep_completed_archive":
        change_root = root / "docs/changes"
        if change_root.exists():
            if not change_root.is_dir() or change_root.is_symlink():
                raise MaterializationError("docs/changes must be an ordinary directory")
            for child in sorted(change_root.iterdir(), key=lambda path: path.name):
                relative = child.relative_to(root).as_posix()
                if (
                    child.name == "README.md"
                    and child.is_file()
                    and not child.is_symlink()
                ):
                    continue
                if (
                    child.name == "archive"
                    and child.is_dir()
                    and not child.is_symlink()
                ):
                    preserved_completed_archive = True
                    continue
                if remove_path(root, relative):
                    removed_roots.append(relative)
                    removed_change_unit_roots.append(relative)

    remaining_paths = {entry["path"] for entry in content_manifest(root)}
    removed_entries = [
        removed_before[path] for path in sorted(set(removed_before) - remaining_paths)
    ]
    return {
        "explicit_paths": explicit_results,
        "removed_roots": sorted(removed_roots),
        "removed_entries": removed_entries,
        "removed_manifest_sha256": canonical_hash(removed_entries),
        "change_units": {
            "policy": change_unit_policy or "not_configured",
            "removed_roots": removed_change_unit_roots,
            "removed_roots_sha256": canonical_hash(removed_change_unit_roots),
            "completed_archive_preserved": preserved_completed_archive,
        },
        "drop_proposed_control": {
            "policy": "legacy_epoch_task_blind"
            if proposed_control_results
            else "not_configured",
            "paths": proposed_control_results,
            "removed_roots": removed_proposed_control_roots,
            "removed_roots_sha256": canonical_hash(removed_proposed_control_roots),
        },
        "archive_lineage": {
            "policy": archive_lineage.get("policy", "not_configured"),
            "dropped_units": archive_lineage_results,
            "removed_roots": removed_archive_lineage_roots,
            "removed_roots_sha256": canonical_hash(removed_archive_lineage_roots),
        },
    }


def git_blob(repository: Path, commit: str, source: str) -> tuple[str, bytes]:
    raw = run_git(repository, "ls-tree", "-z", commit, "--", source)
    records = [record for record in raw.split(b"\x00") if record]
    if len(records) != 1:
        raise MaterializationError(f"arm source must resolve to one Git blob: {source}")
    metadata, separator, raw_path = records[0].partition(b"\t")
    if not separator or raw_path.decode() != source:
        raise MaterializationError(f"arm source did not resolve exactly: {source}")
    mode, object_type, object_id = metadata.decode().split()
    if object_type != "blob" or mode not in {"100644", "100755"}:
        raise MaterializationError(f"arm source is not an ordinary file: {source}")
    return mode, run_git(repository, "cat-file", "blob", object_id)


def apply_docs_projection(
    root: Path,
    repository: Path,
    projection: dict[str, Any],
    baseline_commit: str,
) -> dict[str, Any]:
    mode = projection["mode"]
    if mode == "preserve_exact":
        return {"mode": mode}

    commit, tree = resolve_commit(repository, projection["ref"])
    if mode == "dp1_counterfactual_latest":
        if commit != projection["expected_commit"]:
            raise MaterializationError(
                "documentation framework commit mismatch: "
                f"expected {projection['expected_commit']}, got {commit}"
            )
        if tree != projection["expected_tree"]:
            raise MaterializationError(
                "documentation framework tree mismatch: "
                f"expected {projection['expected_tree']}, got {tree}"
            )

        def install_projection_file(
            destination: str,
            content: bytes,
            file_mode_value: str,
            install: str,
        ) -> dict[str, str]:
            target = root / destination
            before: dict[str, str] = {}
            if install == "create":
                if target.exists() or target.is_symlink():
                    raise MaterializationError(
                        f"DP1 create destination already exists: {destination}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
            elif install == "replace":
                if not target.is_file() or target.is_symlink():
                    raise MaterializationError(
                        f"DP1 replace destination is not an ordinary file: {destination}"
                    )
                before = {
                    "before_mode": file_mode(target),
                    "before_sha256": sha256_bytes(target.read_bytes()),
                }
            else:
                raise MaterializationError(f"unsupported DP1 install mode: {install}")
            target.write_bytes(content)
            target.chmod(0o755 if file_mode_value == "100755" else 0o644)
            return before

        entries: list[dict[str, str]] = []
        for entry in projection["files"]:
            source_commit = (
                baseline_commit
                if entry["source_clock"] == "product_baseline"
                else commit
            )
            source_mode, source_content = git_blob(
                repository, source_commit, entry["source"]
            )
            source_digest = sha256_bytes(source_content)
            if source_digest != entry["sha256"]:
                raise MaterializationError(
                    f"DP1 framework source hash mismatch for {entry['source']}: "
                    f"expected {entry['sha256']}, got {source_digest}"
                )
            transform = entry["transform"]
            content = source_content
            if transform["kind"] == "replace_exact":
                old = transform["old"].encode()
                replacement_count = content.count(old)
                if replacement_count != transform["expected_replacements"]:
                    raise MaterializationError(
                        f"DP1 replace count mismatch for {entry['source']}: "
                        f"expected {transform['expected_replacements']}, got {replacement_count}"
                    )
                content = content.replace(old, transform["new"].encode())
            output_digest = sha256_bytes(content)
            if output_digest != entry["output_sha256"]:
                raise MaterializationError(
                    f"DP1 output hash mismatch for {entry['destination']}: "
                    f"expected {entry['output_sha256']}, got {output_digest}"
                )
            receipt_entry = {
                "source": entry["source"],
                "source_clock": entry["source_clock"],
                "source_commit": source_commit,
                "source_sha256": source_digest,
                "destination": entry["destination"],
                "install": entry["install"],
                "mode": source_mode,
                "sha256": output_digest,
                "transform": transform["kind"],
                "truth_domain": "framework"
                if entry["source_clock"] == "documentation_framework"
                else "product_current",
            }
            receipt_entry.update(
                install_projection_file(
                    entry["destination"],
                    content,
                    source_mode,
                    entry["install"],
                )
            )
            entries.append(receipt_entry)
        for entry in projection["generated_files"]:
            content = entry["content"].encode()
            digest = sha256_bytes(content)
            if digest != entry["sha256"]:
                raise MaterializationError(
                    f"DP1 generated hash mismatch for {entry['destination']}: "
                    f"expected {entry['sha256']}, got {digest}"
                )
            receipt_entry = {
                "destination": entry["destination"],
                "install": entry["install"],
                "mode": entry["mode"],
                "sha256": digest,
                "truth_domain": "navigation",
            }
            receipt_entry.update(
                install_projection_file(
                    entry["destination"],
                    content,
                    entry["mode"],
                    entry["install"],
                )
            )
            entries.append(receipt_entry)
        return {
            "mode": mode,
            "method_id": "counterfactual-latest-base-v1",
            "projection_level": "DP1-counterfactual-latest-v1",
            "product_claim_source": "baseline_only",
            "ref": projection["ref"],
            "commit": commit,
            "tree": tree,
            "entries": entries,
            "files_manifest_sha256": canonical_hash(entries),
        }

    entries: list[dict[str, str]] = []
    for entry in projection["files"]:
        source = entry["source"]
        destination = entry["destination"]
        source_mode, content = git_blob(repository, commit, source)
        digest = sha256_bytes(content)
        if digest != entry["sha256"]:
            raise MaterializationError(
                f"docs projection source hash mismatch for {source}: expected {entry['sha256']}, got {digest}"
            )
        target = root / destination
        if not target.is_file() or target.is_symlink():
            raise MaterializationError(
                f"docs projection destination must replace an existing ordinary file: {destination}"
            )
        before_mode = file_mode(target)
        before_hash = sha256_bytes(target.read_bytes())
        target.write_bytes(content)
        target.chmod(0o755 if source_mode == "100755" else 0o644)
        entries.append(
            {
                "source": source,
                "destination": destination,
                "before_mode": before_mode,
                "before_sha256": before_hash,
                "mode": source_mode,
                "sha256": digest,
            }
        )
    return {
        "mode": mode,
        "ref": projection["ref"],
        "commit": commit,
        "tree": tree,
        "entries": entries,
    }


def overlay_arm(root: Path, repository: Path, arm: dict[str, Any]) -> dict[str, Any]:
    commit, tree = resolve_commit(repository, arm["ref"])
    entries: list[dict[str, Any]] = []
    for entry in arm["files"]:
        source = entry["source"]
        destination = entry["destination"]
        mode, source_content = git_blob(repository, commit, source)
        source_digest = sha256_bytes(source_content)
        if source_digest != entry["sha256"]:
            raise MaterializationError(
                f"arm source hash mismatch for {source}: expected {entry['sha256']}, got {source_digest}"
            )
        content = source_content
        transform = entry.get("transform")
        if transform is not None:
            marker = f"{transform['heading']}\n".encode()
            occurrences = content.count(marker)
            if occurrences != transform["expected_occurrences"]:
                raise MaterializationError(
                    f"arm heading count mismatch for {source}: "
                    f"expected {transform['expected_occurrences']}, got {occurrences}"
                )
            offset = content.index(marker)
            if offset and content[offset - 1 : offset] != b"\n":
                raise MaterializationError(
                    f"arm transform marker is not a complete heading line: {source}"
                )
            content = content[:offset]
            output_digest = sha256_bytes(content)
            if output_digest != entry["output_sha256"]:
                raise MaterializationError(
                    f"arm output hash mismatch for {destination}: "
                    f"expected {entry['output_sha256']}, got {output_digest}"
                )
        else:
            output_digest = source_digest
        target = root / destination
        install = entry.get("install", "create")
        if install == "create":
            if target.exists() or target.is_symlink():
                raise MaterializationError(
                    f"arm destination collides with product tree: {destination}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o755 if mode == "100755" else 0o644)
        elif install == "replace":
            if not target.is_file() or target.is_symlink():
                raise MaterializationError(
                    f"arm replacement target is not an ordinary file: {destination}"
                )
            target.write_bytes(content)
            target.chmod(0o755 if mode == "100755" else 0o644)
        elif install == "preserve_exact":
            if not target.is_file() or target.is_symlink():
                raise MaterializationError(
                    f"arm preserved target is not an ordinary file: {destination}"
                )
            if file_mode(target) != mode or target.read_bytes() != content:
                raise MaterializationError(
                    f"arm preserved target differs from Workflow@W: {destination}"
                )
        else:
            raise MaterializationError(f"unsupported arm install mode: {install}")
        receipt_entry: dict[str, Any] = {
            "mode": mode,
            "path": destination,
            "sha256": output_digest,
        }
        if "install" in entry:
            receipt_entry["install"] = install
            receipt_entry["source"] = source
        if transform is not None:
            receipt_entry["source_sha256"] = source_digest
            receipt_entry["transform"] = transform
        entries.append(receipt_entry)
    for entry in arm.get("generated_files", []):
        destination = entry["destination"]
        content = entry["content"].encode()
        digest = sha256_bytes(content)
        if digest != entry["sha256"]:
            raise MaterializationError(
                f"generated arm hash mismatch for {destination}: expected {entry['sha256']}, got {digest}"
            )
        target = root / destination
        if entry["install"] == "create":
            if target.exists() or target.is_symlink():
                raise MaterializationError(
                    f"generated arm destination collides with product tree: {destination}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.is_file() or target.is_symlink():
            raise MaterializationError(
                f"generated arm replacement target is not an ordinary file: {destination}"
            )
        target.write_bytes(content)
        target.chmod(0o644)
        entries.append(
            {
                "install": entry["install"],
                "mode": entry["mode"],
                "path": destination,
                "sha256": digest,
                "source": "generated_composed_workflow",
            }
        )
    return {
        "id": arm["id"],
        "ref": arm["ref"],
        "commit": commit,
        "tree": tree,
        "entries": sorted(entries, key=lambda item: item["path"]),
        "files_manifest_sha256": canonical_hash(
            sorted(entries, key=lambda item: item["path"])
        ),
    }


def validate_assertions(
    root: Path, assertions: dict[str, Any], entries: list[dict[str, str]]
) -> None:
    for relative in assertions["required_paths"]:
        target = root / relative
        if not target.exists() or target.is_symlink():
            raise MaterializationError(f"required path is missing: {relative}")
    for relative in assertions["forbidden_paths"]:
        target = root / relative
        if target.exists() or target.is_symlink():
            raise MaterializationError(f"forbidden path remains: {relative}")
    for relative, expected in assertions["required_sha256"].items():
        target = root / relative
        if not target.is_file() or target.is_symlink():
            raise MaterializationError(
                f"required hash path is not an ordinary file: {relative}"
            )
        actual = sha256_bytes(target.read_bytes())
        if actual != expected:
            raise MaterializationError(
                f"required hash mismatch for {relative}: expected {expected}, got {actual}"
            )
    manifest_by_path = {entry["path"]: entry for entry in entries}
    for forbidden_text in assertions["forbidden_text"]:
        needle = forbidden_text.encode()
        matches = [
            path
            for path in sorted(manifest_by_path)
            if needle in (root / path).read_bytes()
        ]
        if matches:
            raise MaterializationError(
                f"forbidden text {forbidden_text!r} remains in {matches[:5]}"
            )
    for relative, required_texts in assertions.get("required_text_by_path", {}).items():
        target = root / relative
        if not target.is_file() or target.is_symlink():
            raise MaterializationError(
                f"required-text path is not an ordinary file: {relative}"
            )
        content = target.read_bytes()
        for required_text in required_texts:
            if required_text.encode() not in content:
                raise MaterializationError(
                    f"required text {required_text!r} is missing from {relative}"
                )
    for relative, forbidden_texts in assertions.get(
        "forbidden_text_by_path", {}
    ).items():
        target = root / relative
        if not target.is_file() or target.is_symlink():
            raise MaterializationError(
                f"forbidden-text path is not an ordinary file: {relative}"
            )
        content = target.read_bytes()
        for forbidden_text in forbidden_texts:
            if forbidden_text.encode() in content:
                raise MaterializationError(
                    f"forbidden text {forbidden_text!r} remains in {relative}"
                )
    resolved_root = root.resolve()
    for relative, required_links in assertions.get(
        "required_resolved_links", {}
    ).items():
        target = root / relative
        if not target.is_file() or target.is_symlink():
            raise MaterializationError(
                f"link-check path is not an ordinary file: {relative}"
            )
        content = target.read_bytes()
        for link in required_links:
            if f"]({link})".encode() not in content:
                raise MaterializationError(
                    f"required link {link!r} is missing from {relative}"
                )
            link_path = link.split("#", 1)[0].split("?", 1)[0]
            if (
                not link_path
                or link_path.startswith("/")
                or "\\" in link_path
                or "://" in link_path
                or "\x00" in link_path
            ):
                raise MaterializationError(
                    f"required link is not repository-relative: {link!r}"
                )
            resolved_target = (target.parent / link_path).resolve()
            if (
                not resolved_target.is_relative_to(resolved_root)
                or not resolved_target.exists()
                or resolved_target.is_symlink()
            ):
                raise MaterializationError(
                    f"required link does not resolve inside the candidate repository: {link!r}"
                )
    expected_manifest_hash = assertions.get("expected_content_manifest_sha256")
    if expected_manifest_hash is not None:
        actual_manifest_hash = canonical_hash(entries)
        if actual_manifest_hash != expected_manifest_hash:
            raise MaterializationError(
                f"content manifest hash mismatch: expected {expected_manifest_hash}, got {actual_manifest_hash}"
            )
    if assertions.get("change_units_absent") is True:
        change_root = root / "docs/changes"
        if not change_root.is_dir() or change_root.is_symlink():
            raise MaterializationError("clean-room docs/changes root is missing")
        unexpected = sorted(
            child.name
            for child in change_root.iterdir()
            if child.name not in {"README.md", "archive"}
        )
        if unexpected:
            raise MaterializationError(
                f"active or retired change-unit roots remain after clean-room scrub: {unexpected[:5]}"
            )
        index = change_root / "README.md"
        if not index.is_file() or index.is_symlink():
            raise MaterializationError(
                "clean-room lifecycle framework index is missing"
            )


def canonicalize_git_repository(root: Path, branch: str, head: str) -> None:
    """Reduce `git init` output to the validator's byte-canonical envelope."""
    reachable = sorted(
        set(
            run_git(root, "rev-list", "--objects", "--no-object-names", "HEAD")
            .decode()
            .splitlines()
        )
    )
    payloads: dict[str, tuple[str, bytes]] = {}
    batch = run_git(
        root,
        "cat-file",
        "--batch",
        input_bytes=b"".join(f"{item}\n".encode() for item in reachable),
    )
    cursor = 0
    for object_id in reachable:
        line_end = batch.find(b"\n", cursor)
        if line_end < 0:
            raise MaterializationError("git cat-file batch header is truncated")
        header = batch[cursor:line_end].split()
        if len(header) != 3 or header[0].decode() != object_id:
            raise MaterializationError(
                f"unexpected git cat-file batch header for {object_id}"
            )
        object_type = header[1].decode()
        size = int(header[2])
        start = line_end + 1
        end = start + size
        if end >= len(batch) or batch[end : end + 1] != b"\n":
            raise MaterializationError(
                f"git cat-file batch payload is truncated for {object_id}"
            )
        payloads[object_id] = (object_type, batch[start:end])
        cursor = end + 1

    git_dir = root / ".git"
    for child in list(git_dir.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()

    objects_dir = git_dir / "objects"
    (objects_dir / "info").mkdir(parents=True)
    (objects_dir / "pack").mkdir()
    for object_id, (object_type, payload) in payloads.items():
        object_path = objects_dir / object_id[:2] / object_id[2:]
        object_path.parent.mkdir(exist_ok=True)
        canonical_object = f"{object_type} {len(payload)}\0".encode() + payload
        object_path.write_bytes(zlib.compress(canonical_object, level=9))

    (git_dir / "refs/heads").mkdir(parents=True)
    (git_dir / "refs/heads" / branch).write_text(f"{head}\n", encoding="ascii")
    (git_dir / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="ascii")
    (git_dir / "config").write_bytes(FRESH_ROOT_CONFIG)
    index_environment = isolated_git_environment()
    index_environment["GIT_INDEX_FILE"] = str(git_dir / "index")
    result = subprocess.run(
        ["git", "read-tree", "HEAD"],
        cwd=root,
        env=index_environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise MaterializationError(
            "git read-tree failed while building canonical index: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )


def initialize_git_repository(
    root: Path, git_config: dict[str, Any], entries: list[dict[str, str]]
) -> dict[str, str]:
    run_git(root, "init", f"--initial-branch={git_config['branch']}")
    run_git(root, "config", "core.filemode", "true")
    run_git(root, "add", "--all", "--force")
    identity_environment = {
        "GIT_AUTHOR_NAME": git_config["author_name"],
        "GIT_AUTHOR_EMAIL": git_config["author_email"],
        "GIT_AUTHOR_DATE": git_config["timestamp"],
        "GIT_COMMITTER_NAME": git_config["author_name"],
        "GIT_COMMITTER_EMAIL": git_config["author_email"],
        "GIT_COMMITTER_DATE": git_config["timestamp"],
    }
    run_git(
        root,
        "commit",
        "--no-gpg-sign",
        "--no-verify",
        "--file=-",
        input_bytes=git_config["message"].encode(),
        extra_environment=identity_environment,
    )
    head = run_git(root, "rev-parse", "HEAD").decode().strip()
    tree = run_git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    if run_git(root, "rev-list", "--all", "--count").decode().strip() != "1":
        raise MaterializationError(
            "fresh repository does not contain exactly one commit"
        )
    if run_git(root, "rev-list", "--parents", "-n", "1", "HEAD").decode().split() != [
        head
    ]:
        raise MaterializationError(
            "fresh repository root commit unexpectedly has a parent"
        )
    if (
        run_git(root, "branch", "--show-current").decode().strip()
        != git_config["branch"]
    ):
        raise MaterializationError("fresh repository is on the wrong branch")
    if run_git(root, "status", "--porcelain=v1"):
        raise MaterializationError("fresh repository worktree is not clean")

    index_entries: dict[str, tuple[str, str]] = {}
    raw_index = run_git(root, "ls-files", "--stage", "-z")
    for record in raw_index.split(b"\x00"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise MaterializationError("fresh repository index is malformed")
        mode, object_id, stage = metadata.decode().split()
        if stage != "0":
            raise MaterializationError(
                "fresh repository index contains a non-zero stage"
            )
        index_entries[raw_path.decode()] = (mode, object_id)
    expected_by_path = {entry["path"]: entry for entry in entries}
    if set(index_entries) != set(expected_by_path):
        raise MaterializationError(
            "fresh repository index paths differ from the content manifest"
        )
    for path, entry in expected_by_path.items():
        mode, object_id = index_entries[path]
        if mode != entry["mode"]:
            raise MaterializationError(f"fresh repository mode mismatch for {path}")
        if (
            sha256_bytes(run_git(root, "cat-file", "blob", object_id))
            != entry["sha256"]
        ):
            raise MaterializationError(f"fresh repository content mismatch for {path}")
    canonicalize_git_repository(root, git_config["branch"], head)
    return {"branch": git_config["branch"], "head": head, "tree": tree}


def write_staged_json(parent: Path, value: dict[str, Any]) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=".base-repo-control-", dir=parent)
    path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
            )
            stream.write(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def publish_repository(stage: Path, output: Path, output_was_empty: bool) -> None:
    if not output_was_empty:
        stage.rename(output)
        return
    if any(output.iterdir()):
        raise MaterializationError(
            f"output became non-empty during materialization: {output}"
        )
    moved: list[Path] = []
    try:
        for child in sorted(stage.iterdir(), key=lambda path: path.name):
            destination = output / child.name
            child.rename(destination)
            moved.append(destination)
    except BaseException:
        for path in reversed(moved):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        raise


def materialize(
    recipe_path: Path,
    repository: Path,
    output: Path,
    manifest_path: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    recipe, raw_recipe = load_recipe(recipe_path)
    if not repository.is_dir() or repository.is_symlink():
        raise MaterializationError(
            f"repository must be an ordinary directory: {repository}"
        )
    ensure_existing_path_has_no_symlink(repository, "repository")
    run_git(repository, "rev-parse", "--git-dir")
    output_was_empty = validate_output_paths(output, manifest_path, receipt_path)

    source = recipe["source"]
    source_commit, source_tree = resolve_commit(repository, source["ref"])
    if source_commit != source["expected_commit"]:
        raise MaterializationError(
            f"source commit mismatch: expected {source['expected_commit']}, got {source_commit}"
        )
    if source_tree != source["expected_tree"]:
        raise MaterializationError(
            f"source tree mismatch: expected {source['expected_tree']}, got {source_tree}"
        )
    validate_source_tree(repository, source_commit)
    raw_archive = run_git(repository, "archive", "--format=tar", source_commit)

    stage = Path(tempfile.mkdtemp(prefix=".base-repo-stage-", dir=output.parent))
    staged_manifest: Path | None = None
    staged_receipt: Path | None = None
    try:
        extract_git_archive(raw_archive, stage)
        scrub_receipt = scrub_tree(stage, recipe["scrub"])
        projection_receipt = apply_docs_projection(
            stage,
            repository,
            recipe["docs_projection"],
            source_commit,
        )
        arm_receipt = overlay_arm(stage, repository, recipe["arm"])
        entries = content_manifest(stage)
        validate_assertions(stage, recipe["assertions"], entries)
        content_manifest_hash = canonical_hash(entries)
        git_receipt = initialize_git_repository(stage, recipe["git"], entries)

        manifest = {
            "schema_version": "1.0",
            "case_id": recipe["case_id"],
            "arm_id": recipe["arm"]["id"],
            "entries": entries,
            "files_manifest_sha256": content_manifest_hash,
        }
        if recipe["schema_version"] == "2.0":
            manifest["method_id"] = recipe["contract"]["method_id"]
            manifest["projection_level"] = recipe["contract"]["projection_level"]
        receipt = {
            "schema_version": "1.0",
            "case_id": recipe["case_id"],
            "recipe_sha256": sha256_bytes(raw_recipe),
            "source": {
                "ref": source["ref"],
                "commit": source_commit,
                "tree": source_tree,
                "raw_archive_sha256": sha256_bytes(raw_archive),
            },
            "scrub": scrub_receipt,
            "docs_projection": projection_receipt,
            "arm": arm_receipt,
            "content_manifest_sha256": content_manifest_hash,
            "git": git_receipt,
            "checks": {
                "assertions": "passed",
                "clean_worktree": True,
                "single_parentless_commit": True,
                "tree_matches_manifest": True,
            },
        }
        if recipe["schema_version"] == "2.0":
            receipt["contract"] = recipe["contract"]
            receipt["seal"] = recipe["seal"]
        staged_manifest = write_staged_json(manifest_path.parent, manifest)
        staged_receipt = write_staged_json(receipt_path.parent, receipt)
        publish_repository(stage, output, output_was_empty)
        os.replace(staged_manifest, manifest_path)
        staged_manifest = None
        os.replace(staged_receipt, receipt_path)
        staged_receipt = None
        return {
            "output": str(output),
            "manifest": str(manifest_path),
            "receipt": str(receipt_path),
            "head": git_receipt["head"],
            "tree": git_receipt["tree"],
            "files_manifest_sha256": content_manifest_hash,
        }
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if staged_manifest is not None:
            staged_manifest.unlink(missing_ok=True)
        if staged_receipt is not None:
            staged_receipt.unlink(missing_ok=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = materialize(
            args.recipe.absolute(),
            args.repository.absolute(),
            args.output.absolute(),
            args.manifest.absolute(),
            args.receipt.absolute(),
        )
    except (MaterializationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
