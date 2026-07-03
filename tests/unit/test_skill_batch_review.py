import json
from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.skills.curator import mark_reviewed_session_ids
from agent.core.skills.usage import F4Trigger
from agent.platform.background.skill_batch_review import run_skill_batch_review


class _UnusedLLMClient:
    async def generate(self, request: LLMGenerateRequest):
        raise AssertionError("LLM should not be called")


def test_batch_review_skips_when_less_than_two_transcripts(tmp_path: Path) -> None:
    skill_root = tmp_path / ".nanoassistant" / "skills"
    _write_session(tmp_path, "s1", "one session")
    calls: list[dict[str, object]] = []

    async def fake_fork(prompt: str, **kwargs: object) -> object:
        calls.append({"prompt": prompt, **kwargs})
        return object()

    result = run_skill_batch_review(
        _trigger(skill_root, ["s1"]),
        run_background_analysis=fake_fork,
    )

    assert result.completed is False
    assert result.skipped_reason == "requires_at_least_two_unreviewed_sessions"
    assert result.evidence_session_ids == ("s1",)
    assert calls == []


def test_batch_review_filters_already_reviewed_sessions(tmp_path: Path) -> None:
    skill_root = tmp_path / ".nanoassistant" / "skills"
    _write_session(tmp_path, "s1", "already reviewed")
    _write_session(tmp_path, "s2", "new evidence")
    mark_reviewed_session_ids(
        curator_state_path=skill_root / ".curator_state.json",
        session_ids=("s1",),
    )
    calls: list[dict[str, object]] = []

    async def fake_fork(prompt: str, **kwargs: object) -> object:
        calls.append({"prompt": prompt, **kwargs})
        return object()

    result = run_skill_batch_review(
        _trigger(skill_root, ["s1", "s2"]),
        run_background_analysis=fake_fork,
    )

    assert result.completed is False
    assert result.skipped_reason == "requires_at_least_two_unreviewed_sessions"
    assert result.evidence_session_ids == ("s2",)
    assert calls == []


def test_batch_review_invokes_patch_only_background_fork(tmp_path: Path) -> None:
    skill_root = tmp_path / ".nanoassistant" / "skills"
    skill_dir = skill_root / "auto-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# auto-skill\n", encoding="utf-8")
    _write_session(tmp_path, "s1", "first transcript uses auto-skill")
    _write_session(tmp_path, "s2", "second transcript also uses auto-skill")
    calls: list[dict[str, object]] = []

    async def fake_fork(prompt: str, **kwargs: object) -> object:
        calls.append({"prompt": prompt, **kwargs})
        return object()

    result = run_skill_batch_review(
        _trigger(skill_root, ["s1", "s2"]),
        run_background_analysis=fake_fork,
    )

    assert result.completed is True
    assert result.skipped_reason is None
    assert result.evidence_session_ids == ("s1", "s2")
    assert len(calls) == 1
    call = calls[0]
    assert call["tool_allowlist"] == ("skill_view", "skill_manage")
    prompt = call["prompt"]
    assert isinstance(prompt, str)
    assert "auto-skill" in prompt
    assert f"Target SKILL.md: {skill_dir / 'SKILL.md'}" in prompt
    assert "first transcript uses auto-skill" in prompt
    assert "second transcript also uses auto-skill" in prompt
    assert "skill_manage(action=\"patch\"" in prompt
    assert "Do not create" in prompt
    state = json.loads((skill_root / ".curator_state.json").read_text())
    assert state["reviewed_session_ids"] == ["s1", "s2"]


def test_runtime_skill_batch_queue_dedupes_by_name_and_root(tmp_path: Path) -> None:
    runtime = AgentRuntime(
        session_manager=SessionManager(
            store=JsonlSessionStore(data_dir=tmp_path / "sessions")
        ),
        llm_client=_UnusedLLMClient(),
        model="mock-model",
    )
    trigger_a = F4Trigger(
        skill_name="same-name",
        skill_root=tmp_path / "root-a",
        session_refs=(),
        call_key="call-a",
    )
    trigger_b = F4Trigger(
        skill_name="same-name",
        skill_root=tmp_path / "root-b",
        session_refs=(),
        call_key="call-b",
    )

    assert runtime.enqueue_skill_batch_review(trigger_a) is True
    assert runtime.enqueue_skill_batch_review(trigger_b) is True
    assert runtime.enqueue_skill_batch_review(trigger_a) is False

    queued = runtime.pop_queued_skill_batch_reviews()

    assert queued == (trigger_a, trigger_b)
    runtime.finish_skill_batch_review(trigger_a)
    runtime.finish_skill_batch_review(trigger_b)


def _trigger(skill_root: Path, session_ids: list[str]) -> F4Trigger:
    return F4Trigger(
        skill_name="auto-skill",
        skill_root=skill_root,
        session_refs=tuple({"session_id": session_id} for session_id in session_ids),
        call_key="call-1",
        skill_location=skill_root / "auto-skill" / "SKILL.md",
    )


def _write_session(workspace_root: Path, session_id: str, text: str) -> None:
    path = workspace_root / ".nanoassistant" / "sessions" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_created", "session_id": session_id}) + "\n"
        + json.dumps({"type": "turn", "role": "user", "content": text}) + "\n",
        encoding="utf-8",
    )
