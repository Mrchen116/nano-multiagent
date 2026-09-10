"""Protect failure isolation for work RPCs sharing the node connection."""

import asyncio
import sqlite3

import pytest

from IM.ws.gateway.work import GatewayWork


@pytest.mark.asyncio
async def test_conversation_query_storage_error_is_a_correlated_result(monkeypatch):
    work = GatewayWork(connection=None, repository=None, sessions=None, registry=None)

    def locked(**kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(work.queries, "query", locked)
    result = await work.query(payload={"request_id": "read"})
    assert result == {
        "type": "conversation.query.result",
        "payload": {"request_id": "read", "ok": False, "error": "storage_unavailable"},
    }
    monkeypatch.setattr(work.queries, "query", lambda **kwargs: {"messages": []})
    assert (await work.query(payload={"request_id": "retry"}))["payload"]["ok"]


@pytest.mark.asyncio
async def test_permission_timeout_reports_unconfirmed_and_accepts_late_transport_result(
    monkeypatch,
):
    class Sessions:
        async def send(self, **kwargs):
            return True

    work = GatewayWork(
        connection=None, repository=None, sessions=Sessions(), registry=None
    )

    async def timeout(waiter, seconds):
        waiter.cancel()
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", timeout)
    with pytest.raises(ValueError, match="decision_unconfirmed"):
        await work.permission(
            node_id="node",
            root="a",
            request_id="p",
            session_id="main",
            decision="deny",
            reason="",
        )
    late = await work.permission_result(
        payload={"node_id": "node", "request_id": "p", "ok": True}
    )
    assert late["type"] == "ack"
