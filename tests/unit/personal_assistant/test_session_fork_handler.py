"""feat-445-M1 R3: gateway fork RPC handler — 由 source conversation 的 binding 定位源
session → kernel.fork_session(up_to) → 把新 conversation 绑定到 fork 出的新 session。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    bind_conversation_session,
    build_conversation_session_key,
)


class _FakeKernel:
    def __init__(self) -> None:
        self.fork_calls: list[dict] = []

    async def fork_session(self, session_id, *, workspace_root=None, up_to=None):
        self.fork_calls.append(
            {"session_id": session_id, "workspace_root": workspace_root, "up_to": up_to}
        )
        return SimpleNamespace(session_id=f"{session_id}-fork")


def _store(tmp_path: Path) -> PersistentSessionBindingStore:
    return PersistentSessionBindingStore(db_path=tmp_path / "bindings.sqlite3")


def _handler(tmp_path: Path, kernel: _FakeKernel, store: PersistentSessionBindingStore):
    from personal_assistant.main import _build_session_fork_handler

    agents = {"alpha": SimpleNamespace(workspace_root=tmp_path / "ws-alpha")}
    return _build_session_fork_handler(
        kernel=kernel,
        session_store=store,
        agents_getter=lambda: agents,
        channel_name="web_relay",
    )


@pytest.mark.asyncio
async def test_fork_handler_locates_source_forks_and_binds_new(tmp_path: Path) -> None:
    kernel = _FakeKernel()
    store = _store(tmp_path)
    # Pre-bind the source conversation to a kernel session.
    bind_conversation_session(
        store=store,
        channel_name="web_relay",
        conversation_id="conv-src",
        agent_id="alpha",
        kernel_session_id="ksess-src",
    )
    handler = _handler(tmp_path, kernel, store)

    result = await handler(
        {
            "source_conversation_id": "conv-src",
            "new_conversation_id": "conv-new",
            "agent_id": "alpha",
            "fork_point": {"message_id": "a3"},
        }
    )

    assert result["ok"] is True
    assert result["new_session_id"] == "ksess-src-fork"
    # kernel.fork_session called against the source session, with up_to + agent workspace
    assert kernel.fork_calls == [
        {
            "session_id": "ksess-src",
            "workspace_root": tmp_path / "ws-alpha",
            "up_to": "a3",
        }
    ]
    # new conversation now bound to the forked session
    new_binding = store.get(
        build_conversation_session_key(
            channel_name="web_relay", conversation_id="conv-new", agent_id="alpha"
        )
    )
    assert new_binding is not None
    assert new_binding.kernel_session_id == "ksess-src-fork"


@pytest.mark.asyncio
async def test_fork_handler_missing_source_binding_returns_not_ok(tmp_path: Path) -> None:
    kernel = _FakeKernel()
    store = _store(tmp_path)
    handler = _handler(tmp_path, kernel, store)

    result = await handler(
        {
            "source_conversation_id": "conv-absent",
            "new_conversation_id": "conv-new",
            "agent_id": "alpha",
            "fork_point": {"message_id": "a3"},
        }
    )
    assert result["ok"] is False
    assert result.get("error")
    assert kernel.fork_calls == []


@pytest.mark.asyncio
async def test_fork_handler_kernel_failure_returns_not_ok(tmp_path: Path) -> None:
    class _BoomKernel:
        async def fork_session(self, *a, **k):
            raise RuntimeError("fork point message_id 'a3' not found")

    store = _store(tmp_path)
    bind_conversation_session(
        store=store,
        channel_name="web_relay",
        conversation_id="conv-src",
        agent_id="alpha",
        kernel_session_id="ksess-src",
    )
    from personal_assistant.main import _build_session_fork_handler

    agents = {"alpha": SimpleNamespace(workspace_root=tmp_path / "ws")}
    handler = _build_session_fork_handler(
        kernel=_BoomKernel(),
        session_store=store,
        agents_getter=lambda: agents,
        channel_name="web_relay",
    )
    result = await handler(
        {
            "source_conversation_id": "conv-src",
            "new_conversation_id": "conv-new",
            "agent_id": "alpha",
            "fork_point": {"message_id": "a3"},
        }
    )
    assert result["ok"] is False
    assert "not found" in result.get("error", "")
    # no binding created for the new conversation on failure
    assert (
        store.get(
            build_conversation_session_key(
                channel_name="web_relay",
                conversation_id="conv-new",
                agent_id="alpha",
            )
        )
        is None
    )
