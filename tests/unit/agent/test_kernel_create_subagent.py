"""Regression: `_SessionSubagentControl.create_subagent` passes `tool_allowlist` /
`prompt_seed` / `skills` through to the child session without folding
(feat-474 M1 R2 — the pre-existing `if skills else None` silently widened an
explicitly empty parent skill set for the child; `tool_allowlist`/`prompt_seed`
were not threaded through at all before this change).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.session.directory import SessionDirectory
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.transcript import JsonlTranscript
from agent.core.session.types import (
    INTERNAL_PROMPT_SLOTS_KEY,
    INTERNAL_RUNTIME_KEY,
    NewSession,
    PromptSlotSeed,
    PromptSlotText,
    SessionRef,
)
from agent.sdk.kernel import _SessionSubagentControl


class _FakeConversation:
    """Minimal `ConversationLike` stand-in — `create_subagent` never runs it."""

    def __init__(self, *, ref: SessionRef, transcript: JsonlTranscript) -> None:
        self.ref = ref
        self.transcript = transcript

    async def close(self) -> None:  # pragma: no cover - unused by these tests
        pass

    async def discard_turn(self, turn_id: str) -> bool:  # pragma: no cover
        return False

    def try_evict_payload(self) -> bool:  # pragma: no cover
        return False


def _control(tmp_path: Path) -> _SessionSubagentControl:
    directory = SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=lambda ref, transcript: _FakeConversation(
            ref=ref, transcript=transcript
        ),
    )
    parent = directory.create(NewSession(workspace_root=tmp_path))
    return _SessionSubagentControl(
        ref=parent.ref,
        directory=directory,
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        engine=None,  # not exercised by create_subagent / list_parent_enabled_tool_names tests
    )


def _load_prompt_seed(
    control: _SessionSubagentControl, ref: SessionRef
) -> PromptSlotSeed:
    config = JsonlTranscript(
        ref=ref, files=control.files, writer=JsonlWriter()
    ).load_config()
    return PromptSlotSeed.from_metadata(config.metadata.get(INTERNAL_PROMPT_SLOTS_KEY))


@pytest.mark.parametrize(
    ("skills", "expected"),
    [(None, None), ((), ()), (("a", "b"), ("a", "b"))],
)
def test_skills_three_states_pass_through_without_folding(
    tmp_path: Path, skills: tuple[str, ...] | None, expected: tuple[str, ...] | None
) -> None:
    control = _control(tmp_path)

    child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=skills,
        metadata={},
        parent_session_id=control.ref.session_id,
    )

    session = control.directory.get(child_ref)
    assert session is not None
    assert session.skills == expected


def test_tool_allowlist_is_written_explicitly_including_empty(tmp_path: Path) -> None:
    control = _control(tmp_path)

    child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=None,
        metadata={},
        parent_session_id=control.ref.session_id,
        tool_allowlist=["read", "bash"],
    )
    session = control.directory.get(child_ref)
    assert session is not None
    assert session.tool_allowlist == ("read", "bash")

    empty_child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=None,
        metadata={},
        parent_session_id=control.ref.session_id,
        tool_allowlist=(),
    )
    empty_session = control.directory.get(empty_child_ref)
    assert empty_session is not None
    assert empty_session.tool_allowlist == ()


def test_omitted_tool_allowlist_defaults_to_none(tmp_path: Path) -> None:
    control = _control(tmp_path)

    child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=None,
        metadata={},
        parent_session_id=control.ref.session_id,
    )
    session = control.directory.get(child_ref)
    assert session is not None
    assert session.tool_allowlist is None


def test_prompt_seed_is_persisted_for_the_child_session(tmp_path: Path) -> None:
    control = _control(tmp_path)
    seed = PromptSlotSeed(
        head=(PromptSlotText(name="agent_type.identity", text="You are Explore."),),
        body=(PromptSlotText(name="agent_type.guidance", text="READ-ONLY."),),
    )

    child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=None,
        metadata={},
        parent_session_id=control.ref.session_id,
        prompt_seed=seed,
    )

    assert _load_prompt_seed(control, child_ref) == seed


def test_runtime_model_and_effort_are_persisted_for_the_child_session(
    tmp_path: Path,
) -> None:
    control = _control(tmp_path)

    child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=None,
        metadata={},
        parent_session_id=control.ref.session_id,
        runtime_model="codexOAuth:gpt-5.6-luna",
        runtime_reasoning_effort="low",
    )

    config = JsonlTranscript(
        ref=child_ref, files=control.files, writer=JsonlWriter()
    ).load_config()
    assert config.runtime_model == "codexOAuth:gpt-5.6-luna"
    assert config.metadata[INTERNAL_RUNTIME_KEY]["reasoning_effort"] == "low"


def test_omitted_prompt_seed_defaults_to_empty(tmp_path: Path) -> None:
    control = _control(tmp_path)

    child_ref = control.create_subagent(
        workspace_root=tmp_path,
        skills=None,
        metadata={},
        parent_session_id=control.ref.session_id,
    )

    assert _load_prompt_seed(control, child_ref) == PromptSlotSeed()


def test_rejects_parent_session_id_mismatch(tmp_path: Path) -> None:
    control = _control(tmp_path)

    with pytest.raises(ValueError, match="active conversation"):
        control.create_subagent(
            workspace_root=tmp_path,
            skills=None,
            metadata={},
            parent_session_id="not-the-active-session",
        )
