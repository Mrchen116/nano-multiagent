"""Per-skill background review orchestration."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.core.skills.curator import mark_reviewed_session_ids, reviewed_session_ids
from agent.core.skills.usage import F4Trigger

_TOOL_ALLOWLIST = ("skill_view", "skill_manage")
_MAX_TRANSCRIPT_CHARS = 12_000

BackgroundFork = Callable[..., Awaitable[Any] | Any]


@dataclass(frozen=True, slots=True)
class SkillBatchReviewResult:
    """Outcome of one per-skill batch review attempt."""

    skill_name: str
    completed: bool
    evidence_session_ids: tuple[str, ...]
    skipped_reason: str | None = None


def run_skill_batch_review(
    trigger: F4Trigger,
    *,
    run_background_analysis: BackgroundFork,
    max_transcript_chars: int = _MAX_TRANSCRIPT_CHARS,
) -> SkillBatchReviewResult:
    """Run one skill batch review from a synchronous caller."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_skill_batch_review_async(
                trigger,
                run_background_analysis=run_background_analysis,
                max_transcript_chars=max_transcript_chars,
            )
        )
    raise RuntimeError(
        "run_skill_batch_review() cannot be called from a running event loop; "
        "use run_skill_batch_review_async() instead"
    )


async def run_skill_batch_review_async(
    trigger: F4Trigger,
    *,
    run_background_analysis: BackgroundFork,
    max_transcript_chars: int = _MAX_TRANSCRIPT_CHARS,
) -> SkillBatchReviewResult:
    """Review one F4 trigger with a runtime-injected background fork callable."""

    skill_root = trigger.skill_root.expanduser().resolve()
    curator_state_path = skill_root / ".curator_state.json"
    already_reviewed = reviewed_session_ids(curator_state_path=curator_state_path)
    evidence = _load_unreviewed_transcripts(
        trigger=trigger,
        reviewed=already_reviewed,
        max_transcript_chars=max_transcript_chars,
    )
    evidence_session_ids = tuple(item.session_id for item in evidence)
    if len(evidence) < 2:
        return SkillBatchReviewResult(
            skill_name=trigger.skill_name,
            completed=False,
            evidence_session_ids=evidence_session_ids,
            skipped_reason="requires_at_least_two_unreviewed_sessions",
        )

    prompt = _build_review_prompt(trigger=trigger, evidence=evidence)
    result = run_background_analysis(
        prompt,
        tool_allowlist=_TOOL_ALLOWLIST,
        metadata={
            "background_task": "skill_batch_review",
            "skill_name": trigger.skill_name,
            "evidence_session_ids": evidence_session_ids,
        },
    )
    if inspect.isawaitable(result):
        await result
    mark_reviewed_session_ids(
        curator_state_path=curator_state_path,
        session_ids=evidence_session_ids,
    )
    return SkillBatchReviewResult(
        skill_name=trigger.skill_name,
        completed=True,
        evidence_session_ids=evidence_session_ids,
    )


@dataclass(frozen=True, slots=True)
class _TranscriptEvidence:
    session_id: str
    path: Path
    text: str


def _load_unreviewed_transcripts(
    *,
    trigger: F4Trigger,
    reviewed: frozenset[str],
    max_transcript_chars: int,
) -> tuple[_TranscriptEvidence, ...]:
    evidence: list[_TranscriptEvidence] = []
    seen: set[str] = set()
    for ref in trigger.session_refs:
        session_id = _session_id_from_ref(ref)
        if session_id is None or session_id in seen or session_id in reviewed:
            continue
        seen.add(session_id)
        path = _transcript_path(trigger.skill_root, ref, session_id=session_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        if len(text) > max_transcript_chars:
            text = text[-max_transcript_chars:]
        evidence.append(
            _TranscriptEvidence(session_id=session_id, path=path, text=text)
        )
    return tuple(evidence)


def _session_id_from_ref(ref: Mapping[str, Any]) -> str | None:
    value = ref.get("session_id")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _transcript_path(
    skill_root: Path, ref: Mapping[str, Any], *, session_id: str
) -> Path:
    raw_path = ref.get("transcript_path")
    if isinstance(raw_path, str) and raw_path.strip():
        return Path(raw_path).expanduser().resolve()
    return skill_root.expanduser().resolve().parent / "sessions" / f"{session_id}.jsonl"


def _build_review_prompt(
    *, trigger: F4Trigger, evidence: tuple[_TranscriptEvidence, ...]
) -> str:
    blocks: list[str] = []
    for item in evidence:
        blocks.append(
            f"## Session {item.session_id}\n"
            f"Transcript path: {item.path}\n"
            "```jsonl\n"
            f"{item.text}\n"
            "```"
        )
    return (
        "You are running an unattended F4 skill batch review.\n"
        f"Target skill: {trigger.skill_name}\n"
        f"Skill root: {trigger.skill_root.expanduser().resolve()}\n\n"
        f"Target SKILL.md: {_target_skill_location(trigger)}\n\n"
        "Use at least two session transcripts as evidence before changing anything.\n"
        "Only patch the existing target skill. Do not create, rename, archive, delete, "
        "or modify any other skill.\n"
        f"Allowed write path: skill_manage(action=\"patch\", name=\"{trigger.skill_name}\", ...). "
        "Do not call skill_manage with action=\"create\".\n"
        "First inspect the current skill with skill_view, then patch only if the evidence "
        "shows a concrete improvement.\n\n"
        "Evidence transcripts:\n"
        + "\n\n".join(blocks)
    )


def _target_skill_location(trigger: F4Trigger) -> Path:
    if trigger.skill_location is not None:
        return trigger.skill_location.expanduser().resolve()
    return trigger.skill_root.expanduser().resolve() / trigger.skill_name / "SKILL.md"
