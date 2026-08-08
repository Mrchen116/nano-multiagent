"""Gateway-side exact transcript resolution lifecycle contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _minimal_reporter


def _manager(
    tmp_path: Path,
    *,
    session_log_path_provider=None,
) -> IMConnectionManager:
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)

    async def connect(_url: str, _headers: object) -> object:
        raise AssertionError("session-log unit tests do not open a websocket")

    return IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        session_log_path_provider=session_log_path_provider,
        connect=connect,
    )


def test_session_log_resolution_coalesces_without_a_capacity_false_negative(
    tmp_path: Path,
) -> None:
    """Every distinct lookup remains pending; duplicate lookups share one task."""
    release = asyncio.Event()
    started = asyncio.Event()
    calls: list[tuple[str, str]] = []
    resolved: list[dict[str, object]] = []

    async def resolve(agent_id: str, conversation_id: str) -> str:
        calls.append((agent_id, conversation_id))
        if len(calls) == 3:
            started.set()
        await release.wait()
        return f"/gateway/{conversation_id}.jsonl"

    manager = _manager(tmp_path, session_log_path_provider=resolve)

    async def send(**payload: object) -> None:
        resolved.append(dict(payload))

    manager._send_session_log_resolution = send  # type: ignore[method-assign]  # noqa: SLF001

    async def exercise() -> None:
        await manager._start_session_log_resolution(  # noqa: SLF001
            request_id="same-1", agent_id="agent-a", conversation_id="same"
        )
        await manager._start_session_log_resolution(  # noqa: SLF001
            request_id="same-2", agent_id="agent-a", conversation_id="same"
        )
        await manager._start_session_log_resolution(  # noqa: SLF001
            request_id="other", agent_id="agent-a", conversation_id="other"
        )
        await manager._start_session_log_resolution(  # noqa: SLF001
            request_id="overflow", agent_id="agent-a", conversation_id="overflow"
        )
        await asyncio.wait_for(started.wait(), timeout=0.2)
        assert calls == [
            ("agent-a", "same"),
            ("agent-a", "other"),
            ("agent-a", "overflow"),
        ]
        assert not resolved
        release.set()
        await asyncio.gather(*tuple(manager._session_log_tasks))  # noqa: SLF001
        await manager.close()

    asyncio.run(exercise())

    assert {item["request_id"] for item in resolved} == {
        "same-1",
        "same-2",
        "other",
        "overflow",
    }
    assert {item["status"] for item in resolved} == {"ready"}
    assert all(item["source_jsonl_path"] for item in resolved)


def test_session_log_resolution_reports_unavailable_not_missing_transcript(
    tmp_path: Path,
) -> None:
    """An unavailable local resolver cannot be projected as a missing transcript."""
    manager = _manager(tmp_path)
    resolved: list[dict[str, object]] = []

    async def send(**payload: object) -> None:
        resolved.append(dict(payload))

    manager._send_session_log_resolution = send  # type: ignore[method-assign]  # noqa: SLF001

    async def exercise() -> None:
        await manager._start_session_log_resolution(  # noqa: SLF001
            request_id="unavailable",
            agent_id="agent-a",
            conversation_id="conversation-a",
        )
        await asyncio.gather(*tuple(manager._session_log_tasks))  # noqa: SLF001
        await manager.close()

    asyncio.run(exercise())

    assert resolved == [
        {
            "request_id": "unavailable",
            "agent_id": "agent-a",
            "conversation_id": "conversation-a",
            "source_jsonl_path": None,
            "status": "unavailable",
        }
    ]


def test_close_cancels_only_cancellable_session_log_tasks(tmp_path: Path) -> None:
    """Closing Gateway cancels a stalled resolution without leaving worker threads."""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def stalled(_agent_id: str, _conversation_id: str) -> str:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    manager = _manager(tmp_path, session_log_path_provider=stalled)

    async def send(**_payload: object) -> None:
        return None

    manager._send_session_log_resolution = send  # type: ignore[method-assign]  # noqa: SLF001

    async def exercise() -> None:
        await manager._start_session_log_resolution(  # noqa: SLF001
            request_id="stalled", agent_id="agent-a", conversation_id="conversation-a"
        )
        await asyncio.wait_for(started.wait(), timeout=0.2)
        await asyncio.wait_for(manager.close(), timeout=0.2)

    asyncio.run(exercise())

    assert cancelled.is_set()
    assert not manager._session_log_tasks  # noqa: SLF001
