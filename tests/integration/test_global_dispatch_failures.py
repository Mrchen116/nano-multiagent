"""Protect global message delivery from attachment and journal failures."""

import json
import sqlite3
from dataclasses import replace

import pytest

from tests.integration.test_global_gateway_runtime import (
    _Model,
    _close,
    _message,
    _receive,
    _runtime,
    _wait,
)


@pytest.mark.asyncio
async def test_file_without_mime_is_consumed_as_attachment_and_does_not_hold_reply(
    tmp_path,
):
    model = _Model()
    rt = await _runtime(tmp_path, model)
    attachment = {"url": "/im/v1/files/report", "filename": "report.pdf"}
    try:
        message = replace(
            _message("file", "See report"), metadata={"attachments": [attachment]}
        )
        await _receive(rt, message)
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert [row["text"] for row in rt.manager.sent] == ["Acknowledged"]
        assert rt.inbox.blocking_entries("worker", "c_group001") == []
        tool_results = [
            str(m.content)
            for r in model.requests
            for m in r.messages
            if m.role == "tool"
        ]
        assert any("report.pdf" in text for text in tool_results)
        assert not any("attachment_unavailable" in text for text in tool_results)
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_delivered_message_stays_successful_if_work_recording_fails(
    tmp_path, monkeypatch
):
    model = _Model()
    rt = await _runtime(tmp_path, model)
    record = rt.recorder.record

    def fail_confirmation(**kwargs):
        if kwargs["event_type"] == "dispatch_confirmed":
            raise sqlite3.OperationalError("database is locked")
        return record(**kwargs)

    monkeypatch.setattr(rt.recorder, "record", fail_confirmation)
    try:
        await _receive(rt, _message("m1", "Acknowledge"))
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert len(rt.manager.sent) == 1
        result = next(
            m.content
            for m in model.requests[-1].messages
            if m.role == "tool" and m.tool_call_id == "send-first"
        )
        assert json.loads(result)["ok"] is True
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_missing_global_run_identity_cannot_create_a_withheld_draft(tmp_path):
    rt = await _runtime(tmp_path, _Model())
    try:
        binding = await rt.coordinator.resolve(rt.catalog.require("worker"))
        rt.inbox.receive(
            agent_id="worker",
            target="c_group001",
            ingress_key="m1",
            source_message_id="m1",
            sender={},
            content=[{"type": "text", "text": "unread correction"}],
            kind="group",
            channel="web_relay",
        )
        result = await rt.handler.handle(
            {
                "to": "c_group001",
                "text": "reply",
                "from_session_id": "worker|tool_call:missing",
                "source_agent_id": "worker",
                "origin_kernel_session_id": binding.kernel_session_id,
                "dispatch_request_id": "missing",
            }
        )
        assert result["ok"] is False and "identity is missing" in result["error"]
        assert not rt.manager.sent
        assert not any(
            e["type"] == "draft_withheld" for e in rt.store.read_unacked_events()
        )
    finally:
        await _close(rt)
