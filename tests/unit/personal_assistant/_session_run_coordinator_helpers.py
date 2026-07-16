"""Shared public-interface fixtures for SessionRunCoordinator tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.image_attachments import ImageResolution
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel


class ControlledKernel:
    """Expose deterministic synchronous submit and asynchronous terminal streams."""

    def __init__(self) -> None:
        self.create_calls: list[str] = []
        self.submit_calls: list[dict[str, Any]] = []
        self.try_steer_calls: list[dict[str, Any]] = []
        self.operations: list[tuple[str, str]] = []
        self.append_calls: list[dict[str, Any]] = []
        self.interrupt_calls: list[str] = []
        self.cancel_calls: list[str] = []
        self.inject_steer = False
        self._session_index = 0
        self._run_index = 0
        self._sessions: dict[str, str] = {}
        self._latest_run_by_session: dict[str, str] = {}
        self._events: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._stream_started: dict[str, asyncio.Event] = {}
        self._submit_changed = asyncio.Event()

    def try_steer(
        self,
        *,
        session_id: str,
        parts: list[dict[str, Any]],
        **_kwargs: Any,
    ) -> SimpleNamespace | None:
        """Mirror the public inject-only SDK seam without creating a run."""

        run_id = self._latest_run_by_session.get(session_id, "")
        call = {
            "session_id": session_id,
            "parts": parts,
            "steer": True,
            "run_id": run_id,
        }
        self.operations.append(("steer", run_id))
        self.try_steer_calls.append(call)
        self.submit_calls.append(call)
        self._submit_changed.set()
        if not self.inject_steer or not run_id:
            return None
        return SimpleNamespace(run_id=run_id, injected=True)

    async def create_session(
        self, *, workspace_root: Path, **_kwargs: Any
    ) -> SimpleNamespace:
        self.create_calls.append(str(workspace_root))
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        self._sessions[session_id] = str(workspace_root)
        return SimpleNamespace(session_id=session_id)

    def get_session(
        self, session_id: str, *, workspace_root: str | None = None
    ) -> dict[str, Any]:
        del workspace_root
        return {
            "session_id": session_id,
            "status": "active",
            "workspace_root": self._sessions[session_id],
            "metadata": {},
        }

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict[str, Any]],
        steer: bool = False,
        **_kwargs: Any,
    ) -> SimpleNamespace:
        if steer:
            run_id = self._latest_run_by_session.get(session_id, "")
            self.operations.append(("steer", run_id))
            self.submit_calls.append(
                {
                    "session_id": session_id,
                    "parts": parts,
                    "steer": True,
                    "run_id": run_id,
                }
            )
            self._submit_changed.set()
            return SimpleNamespace(run_id=run_id, injected=self.inject_steer)
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.operations.append(("submit", run_id))
        self.submit_calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "steer": False,
                "run_id": run_id,
            }
        )
        self._latest_run_by_session[session_id] = run_id
        self._events[run_id] = asyncio.Queue()
        self._stream_started[run_id] = asyncio.Event()
        self._submit_changed.set()
        return SimpleNamespace(
            run_id=run_id,
            injected=False,
            start_sequence=0,
        )

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        del after_sequence
        run_id = self._latest_run_by_session[session_id]
        queue = self._events[run_id]
        started = self._stream_started[run_id]

        async def _generate() -> AsyncIterator[dict[str, Any]]:
            started.set()
            while True:
                event = await queue.get()
                yield event
                if event.get("event") == "run_status":
                    return

        return _generate()

    async def wait_stream(self, run_id: str) -> None:
        while run_id not in self._stream_started:
            self._submit_changed.clear()
            if run_id in self._stream_started:
                break
            await asyncio.wait_for(self._submit_changed.wait(), timeout=1)
        await asyncio.wait_for(self._stream_started[run_id].wait(), timeout=1)

    async def wait_submit_count(self, count: int) -> None:
        """Wait until the synchronous Kernel boundary has observed ``count`` calls."""

        while len(self.submit_calls) < count:
            self._submit_changed.clear()
            if len(self.submit_calls) >= count:
                break
            await asyncio.wait_for(self._submit_changed.wait(), timeout=1)

    async def wait_try_steer_count(self, count: int) -> None:
        """Wait until the inject-only Kernel boundary has observed ``count`` calls."""

        while len(self.try_steer_calls) < count:
            self._submit_changed.clear()
            if len(self.try_steer_calls) >= count:
                break
            await asyncio.wait_for(self._submit_changed.wait(), timeout=1)

    def finish(
        self, run_id: str, *, status: str = "completed", text: str = "ok"
    ) -> None:
        queue = self._events[run_id]
        if text:
            queue.put_nowait(
                {"event": "assistant_message", "run_id": run_id, "content": text}
            )
        queue.put_nowait({"event": "run_status", "run_id": run_id, "status": status})

    def push(self, run_id: str, event: dict[str, Any]) -> None:
        """Publish one non-terminal stream event for a controlled run."""

        self._events[run_id].put_nowait({**event, "run_id": run_id})

    def interrupt(self, session_id: str) -> None:
        run_id = self._latest_run_by_session[session_id]
        self.operations.append(("interrupt", run_id))
        self.interrupt_calls.append(session_id)

    def append_message(
        self, session_id: str, *, role: str, content: str, **_kwargs: Any
    ) -> dict[str, str]:
        run_id = self._latest_run_by_session[session_id]
        self.operations.append(("append", run_id))
        self.append_calls.append(
            {"session_id": session_id, "role": role, "content": content}
        )
        return {"session_id": session_id, "role": role, "content": content}

    def cancel(self, run_id: str) -> None:
        self.cancel_calls.append(run_id)


class CountingImageResolver:
    """Count attachment resolution without depending on image bytes."""

    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, attachments: object) -> ImageResolution:
        del attachments
        self.calls += 1
        return ImageResolution(parts=())


def build_dependencies(
    tmp_path: Path,
) -> tuple[
    ControlledKernel,
    LiveAgentCatalog,
    GatewaySessionBinder,
    OutboundRouter,
    GroupContextStore,
]:
    """Build real catalog/binder/router/group owners around a controlled Kernel."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    kernel = ControlledKernel()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a", workspace_root=workspace, title="Agent A"
            ),
        )
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
    )
    router = OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),)))
    group_store = GroupContextStore(tmp_path / "group.sqlite3")
    return kernel, catalog, binder, router, group_store


def inbound(*, chat_id: str, text: str, is_group: bool = False) -> InboundMessage:
    """Build one routed inbound message with stable sender metadata."""

    return InboundMessage(
        channel_name="web_relay",
        text=text,
        external_user_id="user-a",
        external_chat_id=chat_id,
        is_group=is_group,
        agent_id="agent-a",
        metadata={"sender_display_name": "Alice"},
    )
