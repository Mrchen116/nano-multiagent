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


def test_batch_review_skips_roots_current_workspace_cannot_patch(
    tmp_path: Path,
) -> None:
    agent_root = tmp_path / "agent" / ".nanoassistant" / "skills"
    shared_root = tmp_path / "shared-skills"
    _write_skill(agent_root, "auto-skill", "# agent copy\n")
    _write_skill(shared_root, "auto-skill", "# shared copy\n")
    session_a = tmp_path / "sessions" / "s1.jsonl"
    session_b = tmp_path / "sessions" / "s2.jsonl"
    session_a.parent.mkdir(parents=True)
    session_a.write_text("first shared-root transcript\n", encoding="utf-8")
    session_b.write_text("second shared-root transcript\n", encoding="utf-8")
    calls: list[dict[str, object]] = []

    async def fake_fork(prompt: str, **kwargs: object) -> object:
        calls.append({"prompt": prompt, **kwargs})
        return object()

    trigger = F4Trigger(
        skill_name="auto-skill",
        skill_root=shared_root,
        session_refs=(
            {"session_id": "s1", "transcript_path": str(session_a)},
            {"session_id": "s2", "transcript_path": str(session_b)},
        ),
        call_key="call-shared",
        skill_location=shared_root / "auto-skill" / "SKILL.md",
    )

    result = run_skill_batch_review(
        trigger,
        run_background_analysis=fake_fork,
        writable_skill_root=agent_root,
    )

    assert result.completed is False
    assert result.skipped_reason == "target_root_not_writable_by_skill_manage"
    assert result.evidence_session_ids == ()
    assert calls == []
    assert (agent_root / "auto-skill" / "SKILL.md").read_text() == "# agent copy\n"
    assert (shared_root / "auto-skill" / "SKILL.md").read_text() == "# shared copy\n"


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


def test_runtime_skill_batch_queue_pop_can_filter_by_exact_root(tmp_path: Path) -> None:
    runtime = AgentRuntime(
        session_manager=SessionManager(
            store=JsonlSessionStore(data_dir=tmp_path / "sessions")
        ),
        llm_client=_UnusedLLMClient(),
        model="mock-model",
    )
    root_a = tmp_path / "workspace-a" / ".nanoassistant" / "skills"
    root_b = tmp_path / "workspace-b" / ".nanoassistant" / "skills"
    trigger_a = F4Trigger(
        skill_name="same-name",
        skill_root=root_a,
        session_refs=(),
        call_key="call-a",
    )
    trigger_b = F4Trigger(
        skill_name="same-name",
        skill_root=root_b,
        session_refs=(),
        call_key="call-b",
    )

    assert runtime.enqueue_skill_batch_review(trigger_a) is True
    assert runtime.enqueue_skill_batch_review(trigger_b) is True

    assert runtime.pop_queued_skill_batch_reviews(skill_root=root_a) == (trigger_a,)
    assert runtime.pop_queued_skill_batch_reviews(skill_root=root_a) == ()
    assert runtime.pop_queued_skill_batch_reviews(skill_root=root_b) == (trigger_b,)
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


def _write_skill(skill_root: Path, name: str, content: str) -> Path:
    path = skill_root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_session(workspace_root: Path, session_id: str, text: str) -> None:
    path = workspace_root / ".nanoassistant" / "sessions" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_created", "session_id": session_id}) + "\n"
        + json.dumps({"type": "turn", "role": "user", "content": text}) + "\n",
        encoding="utf-8",
    )
