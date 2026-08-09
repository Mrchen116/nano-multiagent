"""Manual `Kernel.compact` durability and failure-atomicity regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.compaction.summarizer import CompactionSummarizer
from agent.core.errors import CompactionError
from agent.core.session.types import SessionRef
from agent.core.skills.usage import bump_skill_usage
from agent.sdk import LLMConfig, build_kernel


class _Summary:
    async def summarize(self, **_kwargs: object) -> str:
        return "Manual summary."


class _EmptySummary:
    async def summarize(self, **_kwargs: object) -> None:
        return None


class _RaisingFork:
    async def execute(self, **_kwargs: object) -> object:
        raise RuntimeError("summary provider unavailable")


def _kernel(workspace: Path):
    return build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test:model",
            base_url="http://127.0.0.1:4000",
            default_model="test:model",
        ),
        repo_root=workspace,
    )


async def _seed_session(kernel, workspace: Path):  # noqa: ANN001
    session = await kernel.create_session(workspace_root=workspace)
    kernel.append_message(
        session.session_id,
        workspace_root=workspace,
        role="user",
        content="Keep this context.",
        message_id="seed-user",
    )
    transcript = kernel._c.directory.open(  # noqa: SLF001 - inspect durable contract
        SessionRef(session_id=session.session_id, workspace_root=workspace)
    )._transcript  # noqa: SLF001 - inspect durable contract
    return session, transcript


def _history_ids(transcript) -> tuple[str, ...]:  # noqa: ANN001
    return tuple(message.message_id for message in transcript.load().messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "summarizer",
    [_EmptySummary(), CompactionSummarizer(fork=_RaisingFork())],
)
async def test_kernel_manual_compact_summary_failure_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, summarizer: object
) -> None:
    """The public SDK call never writes a boundary or mutates history on summary failure."""
    kernel = _kernel(tmp_path)
    try:
        session, transcript = await _seed_session(kernel, tmp_path)
        before = _history_ids(transcript)
        monkeypatch.setattr(
            kernel._c.engine_services, "_compaction_summarizer", summarizer
        )  # noqa: SLF001

        with pytest.raises(CompactionError) as raised:
            await kernel.compact(
                session.session_id,
                workspace_root=tmp_path,
                idempotency_key="manual-failure",
            )

        assert raised.value.details == {
            "trigger": "manual",
            "failure_kind": "summary",
            "consecutive_failures": 0,
        }

        assert _history_ids(transcript) == before
        assert not any(
            entry.__class__.__name__ == "CompactionEntry"
            for entry in transcript.list_event_entries()
        )
    finally:
        kernel.close()


@pytest.mark.asyncio
async def test_kernel_manual_compact_append_failure_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed boundary append leaves the public session's live and durable history intact."""
    kernel = _kernel(tmp_path)
    try:
        session, transcript = await _seed_session(kernel, tmp_path)
        before = transcript._path.read_bytes()  # noqa: SLF001 - durable regression
        monkeypatch.setattr(
            kernel._c.engine_services, "_compaction_summarizer", _Summary()
        )  # noqa: SLF001

        def _fail_replace(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk unavailable")

        monkeypatch.setattr("agent.core.session.jsonl_writer.os.replace", _fail_replace)
        with pytest.raises(CompactionError) as raised:
            await kernel.compact(
                session.session_id,
                workspace_root=tmp_path,
                idempotency_key="manual-append-failure",
            )

        assert raised.value.details == {
            "trigger": "manual",
            "failure_kind": "persistence",
            "consecutive_failures": 0,
            "cause": {"type": "OSError", "message": "disk unavailable"},
        }

        assert transcript._path.read_bytes() == before  # noqa: SLF001
    finally:
        try:
            kernel.close()
        except OSError:
            pass


@pytest.mark.asyncio
async def test_kernel_manual_compact_stale_commit_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel = _kernel(tmp_path)
    try:
        session, transcript = await _seed_session(kernel, tmp_path)
        before = _history_ids(transcript)
        monkeypatch.setattr(
            kernel._c.engine_services, "_compaction_summarizer", _Summary()
        )  # noqa: SLF001
        monkeypatch.setattr(transcript, "append_compaction", lambda **_kwargs: False)

        with pytest.raises(CompactionError) as raised:
            await kernel.compact(session.session_id, workspace_root=tmp_path)

        assert raised.value.details == {
            "trigger": "manual",
            "failure_kind": "stale",
            "consecutive_failures": 0,
        }
        assert _history_ids(transcript) == before
    finally:
        kernel.close()


@pytest.mark.asyncio
async def test_kernel_manual_compact_replays_same_key_after_kernel_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A restarted Kernel returns the first outcome without another compact boundary."""
    first_kernel = _kernel(tmp_path)
    session, transcript = await _seed_session(first_kernel, tmp_path)
    monkeypatch.setattr(
        first_kernel._c.engine_services, "_compaction_summarizer", _Summary()
    )  # noqa: SLF001
    try:
        first = await first_kernel.compact(
            session.session_id,
            workspace_root=tmp_path,
            focus="Keep decisions.",
            idempotency_key="manual-replay",
        )
        assert first is not None
        first_entry_count = len(transcript.list_event_entries())
    finally:
        first_kernel.close()

    restarted = _kernel(tmp_path)
    try:
        replayed = await restarted.compact(
            session.session_id,
            workspace_root=tmp_path,
            focus="Ignored on replay.",
            idempotency_key="manual-replay",
        )
        restarted_transcript = restarted._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript  # noqa: SLF001
        assert replayed == first
        assert len(restarted_transcript.list_event_entries()) == first_entry_count
    finally:
        restarted.close()


@pytest.mark.asyncio
async def test_kernel_manual_compact_keeps_a_following_public_append_reachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next public message remains chained to the compact summary after restart."""
    kernel = _kernel(tmp_path)
    session, transcript = await _seed_session(kernel, tmp_path)
    conversation = kernel._c.directory.open(  # noqa: SLF001
        SessionRef(session_id=session.session_id, workspace_root=tmp_path)
    )
    conversation._automatic_compaction_failures.record_summary_failure()  # noqa: SLF001
    conversation._automatic_compaction_failures.record_summary_failure()  # noqa: SLF001
    monkeypatch.setattr(kernel._c.engine_services, "_compaction_summarizer", _Summary())  # noqa: SLF001
    try:
        result = await kernel.compact(
            session.session_id,
            workspace_root=tmp_path,
            idempotency_key="manual-continue",
        )
        assert result is not None
        assert (  # noqa: SLF001
            conversation._automatic_compaction_failures.consecutive_failures == 0
        )
        kernel.append_message(
            session.session_id,
            workspace_root=tmp_path,
            role="user",
            content="Continue from the summary.",
            message_id="after-compact",
        )
    finally:
        kernel.close()

    restarted = _kernel(tmp_path)
    try:
        recovered = restarted._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript  # noqa: SLF001
        messages = recovered.load().messages
        assert [message.content for message in messages] == [
            "Manual summary.",
            "Continue from the summary.",
        ]
        raw = transcript._files.read_raw_entries(transcript._ref)  # noqa: SLF001
        after = next(entry for entry in raw if entry.get("uuid") == "after-compact")
        assert after["parent_uuid"] == result.entry_id
    finally:
        restarted.close()


@pytest.mark.asyncio
async def test_kernel_manual_compact_reinjection_survives_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill_root = tmp_path / ".nano" / "skills"
    skill_file = skill_root / "review" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("# Review skill\n", encoding="utf-8")
    kernel = _kernel(tmp_path)
    session, _transcript = await _seed_session(kernel, tmp_path)
    bump_skill_usage(
        skill_root=skill_root,
        skill_name="review",
        session_id=session.session_id,
        tool_call_id="skill-call-1",
        source="F1",
        location=skill_file,
    )
    monkeypatch.setattr(kernel._c.engine_services, "_compaction_summarizer", _Summary())  # noqa: SLF001
    try:
        compacted = await kernel.compact(
            session.session_id,
            workspace_root=tmp_path,
        )
        assert compacted is not None
    finally:
        kernel.close()

    restarted = _kernel(tmp_path)
    try:
        transcript = restarted._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript
        messages = transcript.load().messages

        assert [
            message.metadata.get("is_skill_reinjection") for message in messages
        ] == [
            None,
            True,
        ]
        assert messages[0].message_id == compacted.entry_id
        assert messages[1].parent_message_id == compacted.entry_id
    finally:
        restarted.close()
