"""feat-445-M1 R3: gateway fork RPC handler — 由 source conversation 的 binding 定位源
session → kernel.fork_session(up_to) → 把新 conversation 绑定到 fork 出的新 session。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import (
    ConversationBindingRequest,
    GatewaySessionBinder,
    build_session_fork_handler,
)
from personal_assistant.gateway.session_keys import build_conversation_session_key


class _FakeKernel:
    def __init__(self, fork_id_map=None) -> None:
        self.fork_calls: list[dict] = []
        self._fork_id_map = fork_id_map or {}

    async def fork_session(self, session_id, *, workspace_root=None, up_to=None):
        self.fork_calls.append(
            {"session_id": session_id, "workspace_root": workspace_root, "up_to": up_to}
        )
        return SimpleNamespace(
            session_id=f"{session_id}-fork", fork_id_map=dict(self._fork_id_map)
        )


def _owners(tmp_path: Path, kernel: object):
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="alpha", workspace_root=tmp_path / "ws-alpha"),)
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=kernel,
        db_path=tmp_path / "bindings.sqlite3",
    )
    handler = build_session_fork_handler(
        kernel=kernel, session_binder=binder, channel_name="web_relay"
    )
    return catalog, binder, handler


def _bind(
    binder: GatewaySessionBinder,
    catalog: LiveAgentCatalog,
    *,
    conversation_id: str,
    channel_name: str = "web_relay",
    kernel_session_id: str = "ksess-src",
) -> None:
    agent = catalog.require("alpha")
    result = binder.bind_conversation(
        ConversationBindingRequest(
            channel_name=channel_name,
            conversation_id=conversation_id,
            agent_id="alpha",
            kernel_session_id=kernel_session_id,
            guard=binder.capture_write_guard(agent),
        ),
        agent,
    )
    assert result.status == "bound"


@pytest.mark.asyncio
async def test_fork_handler_locates_source_forks_and_binds_new(tmp_path: Path) -> None:
    kernel = _FakeKernel(fork_id_map={"a3": "branch-a3"})
    catalog, binder, handler = _owners(tmp_path, kernel)
    _bind(binder, catalog, conversation_id="conv-src")

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
    # feat-445-M2 #5: the source→branch kernel-uuid map is propagated back to IM.
    assert result["id_map"] == {"a3": "branch-a3"}
    # kernel.fork_session called against the source session, with up_to + agent workspace
    assert kernel.fork_calls == [
        {
            "session_id": "ksess-src",
            "workspace_root": tmp_path / "ws-alpha",
            "up_to": "a3",
        }
    ]
    # new conversation now bound to the forked session
    new_binding = binder.lookup(
        build_conversation_session_key(
            channel_name="web_relay", conversation_id="conv-new", agent_id="alpha"
        )
    )
    assert new_binding is not None
    assert new_binding.kernel_session_id == "ksess-src-fork"


@pytest.mark.asyncio
async def test_fork_handler_missing_source_binding_returns_not_ok(
    tmp_path: Path,
) -> None:
    kernel = _FakeKernel()
    _catalog, _binder, handler = _owners(tmp_path, kernel)

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
async def test_fork_handler_uses_external_source_binding_for_shadow_conversation(
    tmp_path: Path,
) -> None:
    kernel = _FakeKernel()
    catalog, binder, handler = _owners(tmp_path, kernel)
    _bind(binder, catalog, channel_name="feishu", conversation_id="oc_group")

    result = await handler(
        {
            "source_conversation_id": "shadow-conv",
            "source_external_source": "feishu",
            "source_external_chat_id": "oc_group",
            "new_conversation_id": "conv-new",
            "agent_id": "alpha",
            "fork_point": {"message_id": "a3"},
        }
    )

    assert result["ok"] is True
    assert result["new_session_id"] == "ksess-src-fork"
    assert kernel.fork_calls == [
        {
            "session_id": "ksess-src",
            "workspace_root": tmp_path / "ws-alpha",
            "up_to": "a3",
        }
    ]
    new_binding = binder.lookup(
        build_conversation_session_key(
            channel_name="web_relay", conversation_id="conv-new", agent_id="alpha"
        )
    )
    assert new_binding is not None
    assert new_binding.kernel_session_id == "ksess-src-fork"


@pytest.mark.asyncio
async def test_fork_handler_kernel_failure_returns_not_ok(tmp_path: Path) -> None:
    class _BoomKernel:
        async def fork_session(self, *a, **k):
            raise RuntimeError("fork point message_id 'a3' not found")

    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="alpha", workspace_root=tmp_path / "ws"),)
    )
    boom_kernel = _BoomKernel()
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=boom_kernel,
        db_path=tmp_path / "bindings.sqlite3",
    )
    _bind(binder, catalog, conversation_id="conv-src")
    handler = build_session_fork_handler(
        kernel=boom_kernel,
        session_binder=binder,
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
        binder.lookup(
            build_conversation_session_key(
                channel_name="web_relay",
                conversation_id="conv-new",
                agent_id="alpha",
            )
        )
        is None
    )


@pytest.mark.asyncio
async def test_fork_publish_race_returns_failure_without_stale_branch_binding(
    tmp_path: Path,
) -> None:
    """A fork completed for an old snapshot must enter the existing rollback path."""

    import asyncio

    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
    from personal_assistant.gateway.session_binder import GatewaySessionBinder
    from personal_assistant.gateway.session_binder import build_session_fork_handler

    class _BlockingKernel(_FakeKernel):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def fork_session(self, session_id, *, workspace_root=None, up_to=None):
            self.started.set()
            await self.release.wait()
            return await super().fork_session(
                session_id,
                workspace_root=workspace_root,
                up_to=up_to,
            )

    workspace_old = tmp_path / "old"
    workspace_new = tmp_path / "new"
    workspace_old.mkdir()
    workspace_new.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="alpha",
                workspace_root=workspace_old,
            ),
        )
    )
    kernel = _BlockingKernel()
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=kernel,
        db_path=tmp_path / "bindings.sqlite3",
    )
    _bind(binder, catalog, conversation_id="conv-src")
    handler = build_session_fork_handler(
        kernel=kernel,
        session_binder=binder,
        channel_name="web_relay",
    )

    fork = asyncio.create_task(
        handler(
            {
                "source_conversation_id": "conv-src",
                "new_conversation_id": "conv-new",
                "agent_id": "alpha",
                "fork_point": {"message_id": "a3"},
            }
        )
    )
    await kernel.started.wait()
    current = catalog.publish(
        AgentWorkspaceConfig(agent_id="alpha", workspace_root=workspace_new)
    )
    binder.invalidate_stale("alpha", current_revision=current.revision)
    kernel.release.set()
    result = await fork

    assert result["ok"] is False
    assert result["error"] == "agent config changed while session fork was running"
    assert binder.lookup("web_relay:conv-new:alpha") is None


@pytest.mark.asyncio
async def test_fork_captures_source_binding_and_revision_atomically(
    tmp_path: Path,
) -> None:
    """A publish between source lookup and snapshot capture cannot relabel the fork."""

    old_workspace = tmp_path / "old-atomic"
    new_workspace = tmp_path / "new-atomic"
    old_workspace.mkdir()
    new_workspace.mkdir()
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="alpha", workspace_root=old_workspace),)
    )

    kernel = _FakeKernel()
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)
    old_snapshot = catalog.require("alpha")
    bound = binder.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id="conv-src",
            agent_id="alpha",
            kernel_session_id="ksess-src",
            guard=binder.capture_write_guard(old_snapshot),
        ),
        old_snapshot,
    )
    assert bound.status == "bound"
    original_get = binder._repository.get  # noqa: SLF001
    publish_on_get = True

    def _publishing_get(session_key: str):
        nonlocal publish_on_get
        binding = original_get(session_key)
        if publish_on_get:
            publish_on_get = False
            catalog.publish(
                AgentWorkspaceConfig(
                    agent_id="alpha",
                    workspace_root=new_workspace,
                )
            )
        return binding

    binder._repository.get = _publishing_get  # type: ignore[method-assign]  # noqa: SLF001
    handler = build_session_fork_handler(
        kernel=kernel,
        session_binder=binder,
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

    assert result == {
        "ok": False,
        "error": "agent config changed while session fork was running",
    }
    assert kernel.fork_calls[0]["workspace_root"] == old_workspace
    assert binder.lookup("web_relay:conv-new:alpha") is None
