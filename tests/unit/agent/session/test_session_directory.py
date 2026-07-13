from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agent.core.session.directory import SessionDirectory
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.types import (
    INTERNAL_PROMPT_SLOTS_KEY,
    NewSession,
    PromptSlotSeed,
    PromptSlotText,
    SessionAddressMismatch,
    SessionRef,
)


class _FakeConversation:
    def __init__(self, *, ref, transcript) -> None:
        self.ref = ref
        self.transcript = transcript
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _directory(tmp_path: Path) -> SessionDirectory:
    return SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=lambda ref, transcript: _FakeConversation(
            ref=ref, transcript=transcript
        ),
        default_metadata={"workspace_config_dirname": ".nanoassistant"},
    )


def test_directory_interns_one_stable_object_under_concurrent_open(
    tmp_path: Path,
) -> None:
    directory = _directory(tmp_path)
    created = directory.create(NewSession(workspace_root=tmp_path))
    ref = created.ref

    with ThreadPoolExecutor(max_workers=8) as pool:
        opened = list(pool.map(lambda _index: directory.open(ref), range(32)))

    assert all(session is created for session in opened)


def test_directory_rejects_same_session_id_at_a_different_address(
    tmp_path: Path,
) -> None:
    directory = _directory(tmp_path)
    created = directory.create(NewSession(workspace_root=tmp_path / "first"))

    with pytest.raises(SessionAddressMismatch):
        directory.open(
            SessionRef(
                session_id=created.ref.session_id,
                workspace_root=tmp_path / "second",
            )
        )


def test_prompt_seed_round_trips_but_reserved_metadata_is_never_projected(
    tmp_path: Path,
) -> None:
    directory = _directory(tmp_path)
    seed = PromptSlotSeed(
        head=(PromptSlotText(name="pa.identity", text="You are Nano."),),
        body=(PromptSlotText(name="pa.guidance", text="Keep helping."),),
    )
    created = directory.create(
        NewSession(
            workspace_root=tmp_path,
            metadata={
                "visible": "yes",
                INTERNAL_PROMPT_SLOTS_KEY: {"caller": "must be ignored"},
            },
            prompt_seed=seed,
        )
    )

    snapshot = directory.get(created.ref)

    assert snapshot is not None
    assert snapshot.metadata["visible"] == "yes"
    assert snapshot.metadata["workspace_config_dirname"] == ".nanoassistant"
    assert all(not key.startswith("__nano_internal_") for key in snapshot.metadata)
    loaded = created.transcript.load()
    assert loaded.prompt_seed == seed
    assert loaded.config.metadata[INTERNAL_PROMPT_SLOTS_KEY] == seed.to_metadata()


def test_find_by_metadata_requires_exact_parent_scope(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    root = directory.create(
        NewSession(workspace_root=tmp_path, metadata={"agent_id": "same-agent"})
    )
    parent = directory.create(NewSession(workspace_root=tmp_path))
    nested = directory.create(
        NewSession(
            workspace_root=tmp_path,
            parent_session_id=parent.ref.session_id,
            metadata={"agent_id": "same-agent"},
        )
    )

    found_root = directory.find_by_metadata(
        workspace_root=tmp_path,
        parent_session_id=None,
        query={"agent_id": "same-agent"},
    )
    found_nested = directory.find_by_metadata(
        workspace_root=tmp_path,
        parent_session_id=parent.ref.session_id,
        query={"agent_id": "same-agent"},
    )

    assert found_root == root.ref
    assert found_nested == nested.ref


@pytest.mark.asyncio
async def test_close_all_closes_every_interned_conversation(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    first = directory.create(NewSession(workspace_root=tmp_path))
    second = directory.create(NewSession(workspace_root=tmp_path))

    await directory.close_all()

    assert first.closed is True
    assert second.closed is True

