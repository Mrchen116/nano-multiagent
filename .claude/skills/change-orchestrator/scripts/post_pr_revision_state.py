#!/usr/bin/env python3
"""Persist and inspect post-PR implementation and full-gate progress."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


STATE_FILE = "post-pr-revision.json"
VERSION = 1
MILESTONE_DIR = re.compile(r"^M(?P<number>[1-9][0-9]*)-.+$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
MILESTONE_STATES = {"unstarted", "in_progress", "implemented"}


class RevisionStateError(RuntimeError):
    """Raised when persisted revision state is missing or inconsistent."""


def git_output(repository: Path, *args: str) -> str:
    """Run Git and return stdout, translating failures into state errors."""
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RevisionStateError(message or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def require_current_head(unit_doc_root: Path, expected_head: str) -> None:
    """Bind a lifecycle transition to the exact checked-out commit."""
    if not GIT_SHA.fullmatch(expected_head):
        raise RevisionStateError(f"invalid Git head: {expected_head}")
    actual_head = git_output(unit_doc_root, "rev-parse", "HEAD")
    if actual_head != expected_head:
        raise RevisionStateError(
            f"state head {expected_head} does not match worktree HEAD {actual_head}"
        )


def design_milestone_dirs(unit_doc_root: Path, unit_id: str) -> dict[int, str]:
    """Validate the design table and return its milestone directory mapping."""
    design_path = unit_doc_root / "design.md"
    if not design_path.is_file():
        raise RevisionStateError(
            f"post-PR full unit is missing design.md: {design_path}"
        )
    row = re.compile(rf"^\|\s*{re.escape(unit_id)}-M(?P<number>[1-9][0-9]*)\s*\|")
    expected = {
        int(match.group("number"))
        for line in design_path.read_text(encoding="utf-8").splitlines()
        if (match := row.match(line))
    }
    if not expected:
        raise RevisionStateError(f"design milestone table is empty for {unit_id}")

    actual: dict[int, str] = {}
    for child in unit_doc_root.iterdir():
        match = MILESTONE_DIR.fullmatch(child.name)
        if child.is_dir() and match:
            number = int(match.group("number"))
            if number in actual:
                raise RevisionStateError(f"duplicate milestone directory M{number}")
            actual[number] = child.name
    if set(actual) != expected:
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        raise RevisionStateError(
            f"design/directory milestone mismatch; missing={missing}, extra={extra}"
        )
    return actual


def require_empty_skeleton(path: Path) -> None:
    """Require a newly designed milestone to be a trackable empty skeleton."""
    worker_outputs = [entry for entry in path.iterdir() if entry.name != ".gitkeep"]
    if worker_outputs or not (path / ".gitkeep").is_file():
        raise RevisionStateError(f"milestone is not an empty tracked skeleton: {path}")


def require_worker_outputs(path: Path) -> None:
    """Require the minimum durable outputs before recording worker sign-off."""
    if (path / ".gitkeep").exists():
        raise RevisionStateError(
            f"implemented milestone still contains .gitkeep: {path}"
        )
    for name in ("tasks.md", "progress.md"):
        if not (path / name).is_file():
            raise RevisionStateError(f"implemented milestone is missing {name}: {path}")


def state_path(unit_doc_root: Path) -> Path:
    """Return the durable state path for a unit."""
    return unit_doc_root / STATE_FILE


def load_state(unit_doc_root: Path) -> dict[str, Any] | None:
    """Load and validate the durable state file when present."""
    path = state_path(unit_doc_root)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RevisionStateError(f"cannot read {path}: {error}") from error
    if state.get("version") != VERSION:
        raise RevisionStateError(
            f"unsupported revision state version: {state.get('version')}"
        )
    if state.get("phase") not in {
        "implementation_pending",
        "full_gates_pending",
        "validated",
    }:
        raise RevisionStateError(f"invalid revision phase: {state.get('phase')}")
    milestones = state.get("added_milestones")
    if not isinstance(milestones, list) or not all(
        isinstance(item, str) for item in milestones
    ):
        raise RevisionStateError("added_milestones must be a string list")
    milestone_states = state.get("milestone_states")
    if not isinstance(milestone_states, dict) or not all(
        isinstance(name, str) and isinstance(status, str) and status in MILESTONE_STATES
        for name, status in milestone_states.items()
    ):
        raise RevisionStateError("milestone_states contains an invalid status")
    if set(milestone_states) != set(milestones):
        raise RevisionStateError("milestone_states must match added_milestones exactly")
    revision_base_head = state.get("revision_base_head")
    if not isinstance(revision_base_head, str) or not GIT_SHA.fullmatch(
        revision_base_head
    ):
        raise RevisionStateError("revision state is missing revision_base_head")
    if state["phase"] != "implementation_pending":
        if any(status != "implemented" for status in milestone_states.values()):
            raise RevisionStateError(
                "gate phases require every revision milestone to be implemented"
            )
        implemented_head = state.get("implemented_head")
        if not isinstance(implemented_head, str) or not GIT_SHA.fullmatch(
            implemented_head
        ):
            raise RevisionStateError("gate phase is missing implemented_head")
    return state


def write_state(unit_doc_root: Path, state: dict[str, Any]) -> None:
    """Atomically replace the durable state file."""
    unit_doc_root.mkdir(parents=True, exist_ok=True)
    path = state_path(unit_doc_root)
    fd, temporary = tempfile.mkstemp(prefix=f".{STATE_FILE}.", dir=unit_doc_root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def inspect_state(unit_doc_root: Path, unit_id: str) -> dict[str, Any]:
    """Return the exact resume action for the persisted revision phase."""
    state = load_state(unit_doc_root)
    if state is None:
        return {"phase": "none", "action": "feedback", "milestones": []}

    directories = design_milestone_dirs(unit_doc_root, unit_id)
    names = set(directories.values())
    added = state["added_milestones"]
    if len(added) != len(set(added)) or not set(added).issubset(names):
        raise RevisionStateError("persisted added_milestones do not match the design")
    for name, status in state["milestone_states"].items():
        if status == "unstarted":
            require_empty_skeleton(unit_doc_root / name)
        elif status == "implemented":
            require_worker_outputs(unit_doc_root / name)

    if state["phase"] == "validated":
        validated_head = state.get("validated_head")
        if not isinstance(validated_head, str) or not GIT_SHA.fullmatch(validated_head):
            raise RevisionStateError("validated state is missing validated_head")
        repo_root = Path(git_output(unit_doc_root, "rev-parse", "--show-toplevel"))
        state_relative = (
            state_path(unit_doc_root).resolve().relative_to(repo_root.resolve())
        )
        changed = set(
            git_output(
                unit_doc_root,
                "diff",
                "--name-only",
                f"{validated_head}..HEAD",
            ).splitlines()
        )
        if changed - {state_relative.as_posix()}:
            raise RevisionStateError(
                "validated state does not cover the current HEAD; reopen full gates"
            )
        return {"phase": "validated", "action": "validated", "milestones": []}
    if state["phase"] == "full_gates_pending":
        return {"phase": "full_gates_pending", "action": "full_gates", "milestones": []}

    statuses = state["milestone_states"]
    unfinished = [name for name in added if statuses[name] != "implemented"]
    action = "implement" if unfinished else "ready_for_full_gates"
    return {
        "phase": "implementation_pending",
        "action": action,
        "milestones": unfinished,
        "statuses": statuses,
    }


def create_state(
    unit_doc_root: Path,
    unit_id: str,
    revision_base_head: str,
    milestones: list[str],
) -> None:
    """Start a durable revision batch before committing design changes."""
    require_current_head(unit_doc_root, revision_base_head)
    existing = load_state(unit_doc_root)
    if existing is not None and existing["phase"] != "validated":
        raise RevisionStateError("the previous post-PR revision is not validated")
    names = set(design_milestone_dirs(unit_doc_root, unit_id).values())
    if len(milestones) != len(set(milestones)) or not set(milestones).issubset(names):
        raise RevisionStateError("new milestones do not match the revised design")
    for name in milestones:
        require_empty_skeleton(unit_doc_root / name)
    write_state(
        unit_doc_root,
        {
            "version": VERSION,
            "phase": "implementation_pending",
            "revision_base_head": revision_base_head,
            "added_milestones": milestones,
            "milestone_states": {name: "unstarted" for name in milestones},
            "implemented_head": None,
            "validated_head": None,
        },
    )


def add_milestones(
    unit_doc_root: Path,
    unit_id: str,
    revision_base_head: str,
    milestones: list[str],
) -> None:
    """Add a post-PR fix batch and return the lifecycle to implementation."""
    require_current_head(unit_doc_root, revision_base_head)
    state = load_state(unit_doc_root)
    if state is None:
        create_state(
            unit_doc_root,
            unit_id,
            revision_base_head,
            milestones,
        )
        return
    names = set(design_milestone_dirs(unit_doc_root, unit_id).values())
    if len(milestones) != len(set(milestones)) or not set(milestones).issubset(names):
        raise RevisionStateError("new milestones do not match the revised design")
    for name in milestones:
        require_empty_skeleton(unit_doc_root / name)
    state["phase"] = "implementation_pending"
    state["revision_base_head"] = revision_base_head
    state["added_milestones"] = list(
        dict.fromkeys([*state["added_milestones"], *milestones])
    )
    state["milestone_states"].update({name: "unstarted" for name in milestones})
    state["implemented_head"] = None
    state["validated_head"] = None
    write_state(unit_doc_root, state)


def mark_milestone(
    unit_doc_root: Path,
    unit_id: str,
    milestone: str,
    status: str,
    head: str,
) -> None:
    """Persist dispatch or sign-off before advancing the lifecycle."""
    require_current_head(unit_doc_root, head)
    state = load_state(unit_doc_root)
    if state is None or state["phase"] != "implementation_pending":
        raise RevisionStateError("milestones can only change during implementation")
    design_names = set(design_milestone_dirs(unit_doc_root, unit_id).values())
    if milestone not in design_names or milestone not in state["milestone_states"]:
        raise RevisionStateError(f"milestone is not in this revision: {milestone}")

    current = state["milestone_states"][milestone]
    if current == status:
        return
    expected = {
        ("unstarted", "in_progress"),
        ("in_progress", "implemented"),
    }
    if (current, status) not in expected:
        raise RevisionStateError(
            f"cannot mark milestone {milestone} from {current} to {status}"
        )
    if status == "in_progress":
        require_empty_skeleton(unit_doc_root / milestone)
    else:
        require_worker_outputs(unit_doc_root / milestone)
    state["milestone_states"][milestone] = status
    write_state(unit_doc_root, state)


def transition_state(unit_doc_root: Path, unit_id: str, phase: str, head: str) -> None:
    """Persist a monotonic phase transition before the next external action."""
    require_current_head(unit_doc_root, head)
    state = load_state(unit_doc_root)
    if state is None:
        raise RevisionStateError("post-PR revision state does not exist")
    current = state["phase"]
    if phase == "full_gates_pending":
        if current != "implementation_pending":
            raise RevisionStateError(f"cannot transition {current} to {phase}")
        if any(
            status != "implemented" for status in state["milestone_states"].values()
        ):
            raise RevisionStateError("revision milestones are not fully implemented")
        state["implemented_head"] = head
    elif phase == "validated":
        if current != "full_gates_pending":
            raise RevisionStateError(f"cannot transition {current} to {phase}")
        state["validated_head"] = head
    else:
        raise RevisionStateError(f"unsupported transition target: {phase}")
    state["phase"] = phase
    write_state(unit_doc_root, state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "add", "inspect", "mark", "transition"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--unit-doc-root", type=Path, required=True)
        subparser.add_argument("--unit-id", required=True)
    create = subparsers.choices["create"]
    create.add_argument("--revision-base-head", required=True)
    create.add_argument("--milestone", action="append", default=[])
    add = subparsers.choices["add"]
    add.add_argument("--revision-base-head", required=True)
    add.add_argument("--milestone", action="append", required=True)
    mark = subparsers.choices["mark"]
    mark.add_argument("--milestone", required=True)
    mark.add_argument("--status", choices=("in_progress", "implemented"), required=True)
    mark.add_argument("--head", required=True)
    transition = subparsers.choices["transition"]
    transition.add_argument(
        "--phase", choices=("full_gates_pending", "validated"), required=True
    )
    transition.add_argument("--head", required=True)
    args = parser.parse_args()

    try:
        if args.command == "create":
            create_state(
                args.unit_doc_root,
                args.unit_id,
                args.revision_base_head,
                args.milestone,
            )
        elif args.command == "add":
            add_milestones(
                args.unit_doc_root,
                args.unit_id,
                args.revision_base_head,
                args.milestone,
            )
        elif args.command == "inspect":
            print(
                json.dumps(
                    inspect_state(args.unit_doc_root, args.unit_id), sort_keys=True
                )
            )
        elif args.command == "mark":
            mark_milestone(
                args.unit_doc_root,
                args.unit_id,
                args.milestone,
                args.status,
                args.head,
            )
        else:
            transition_state(
                args.unit_doc_root,
                args.unit_id,
                args.phase,
                args.head,
            )
    except RevisionStateError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
