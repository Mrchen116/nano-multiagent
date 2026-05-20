from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from pathlib import Path
import importlib.util
from typing import Any

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "ACCEPTANCE" / "m170-runtime" / "m170_rerun_acceptance.py"
SPEC = importlib.util.spec_from_file_location("m170_rerun_acceptance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
m170_rerun_acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m170_rerun_acceptance)


def _create_current_main_runtime_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                sender_user_id TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                content TEXT NOT NULL,
                attachments_json TEXT NOT NULL DEFAULT '[]',
                delivery_status TEXT NOT NULL DEFAULT 'sent',
                created_at TEXT NOT NULL
            );

            CREATE TABLE relay_tasks (
                relay_task_id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                target_node_id TEXT,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT,
                status TEXT NOT NULL,
                receipt_status TEXT,
                receipt_detail TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE conversation_events (
                event_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                message_id TEXT,
                event_type TEXT NOT NULL,
                delivery_status TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO messages (id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "msg-1",
                "conv-1",
                "user-1",
                "human",
                "@agent-m170-alpha please answer exactly as configured.",
                "[]",
                "delivered",
                "2026-03-16T10:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO relay_tasks (relay_task_id, message_id, conversation_id, target_node_id, payload_json, idempotency_key, status, receipt_status, receipt_detail, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "relay-1",
                "msg-1",
                "conv-1",
                "m170-node",
                json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 1}),
                "idem-1",
                "completed",
                "delivered",
                "ALPHA_ACK_M170",
                "2026-03-16T10:00:01Z",
                "2026-03-16T10:00:02Z",
            ),
        )
        connection.executemany(
            "INSERT INTO conversation_events (event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "evt-1",
                    "conv-1",
                    "msg-1",
                    "message.sent",
                    "sent",
                    json.dumps({"message_id": "msg-1"}),
                    "2026-03-16T10:00:00Z",
                ),
                (
                    "evt-2",
                    "conv-1",
                    "msg-1",
                    "relay.completed",
                    "delivered",
                    json.dumps({"relay_task_id": "relay-1", "receipt_detail": "ALPHA_ACK_M170"}),
                    "2026-03-16T10:00:02Z",
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def runtime_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "im_service.sqlite3"
    _create_current_main_runtime_db(db_path)
    monkeypatch.setattr(m170_rerun_acceptance, "DB_PATH", db_path)
    return db_path


def test_latest_message_matching_reads_current_main_message_schema(runtime_db: Path) -> None:
    row = m170_rerun_acceptance.latest_message_matching("@agent-m170-alpha please answer exactly as configured.")

    assert row == {
        "id": "msg-1",
        "conversation_id": "conv-1",
        "sender_user_id": "user-1",
        "sender_type": "human",
        "content": "@agent-m170-alpha please answer exactly as configured.",
        "created_at": "2026-03-16T10:00:00Z",
    }



def test_relay_for_message_reads_current_main_relay_schema(runtime_db: Path) -> None:
    row = m170_rerun_acceptance.relay_for_message("msg-1")

    assert row == {
        "relay_task_id": "relay-1",
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "target_node_id": "m170-node",
        "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 1}),
        "status": "completed",
        "receipt_status": "delivered",
        "receipt_detail": "ALPHA_ACK_M170",
    }



def test_events_for_message_reads_current_main_event_schema(runtime_db: Path) -> None:
    rows = m170_rerun_acceptance.events_for_message("msg-1")

    assert rows == [
        {
            "event_id": "evt-1",
            "event_type": "message.sent",
            "delivery_status": "sent",
            "payload_json": json.dumps({"message_id": "msg-1"}),
            "created_at": "2026-03-16T10:00:00Z",
        },
        {
            "event_id": "evt-2",
            "event_type": "relay.completed",
            "delivery_status": "delivered",
            "payload_json": json.dumps({"relay_task_id": "relay-1", "receipt_detail": "ALPHA_ACK_M170"}),
            "created_at": "2026-03-16T10:00:02Z",
        },
    ]



def test_no_reply_probe_flags_internal_status_leaks() -> None:
    body_text = "suppressed_by=no_reply_token\nAgent replied\nThe latest agent response finished successfully."

    probe = m170_rerun_acceptance.build_no_reply_probe(
        body_text=body_text,
        message={"id": "msg-2"},
        relay={"relay_task_id": "relay-2", "receipt_detail": "NO_REPLY"},
        events=[],
    )

    assert probe["status"] == "failed"
    assert probe["violations"] == [
        "NO_REPLY",
        "suppressed_by=no_reply_token",
        "Agent replied",
        "The latest agent response finished successfully.",
    ]



def test_result_json_includes_current_main_turn_summaries() -> None:
    result = m170_rerun_acceptance.build_turn_result(
        message={"id": "msg-1", "conversation_id": "conv-1"},
        relay={
            "relay_task_id": "relay-1",
            "receipt_detail": "ALPHA_ACK_M170",
            "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 3}),
        },
        events=[{"event_type": "message.sent"}, {"event_type": "relay.completed"}],
    )

    assert result == {
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "relay_task_id": "relay-1",
        "receipt_detail": "ALPHA_ACK_M170",
        "mentioned_agent_ids": ["agent-m170-alpha"],
        "config_profile_version": 3,
        "event_types": ["message.sent", "relay.completed"],
        "message": {"id": "msg-1", "conversation_id": "conv-1"},
        "relay": {
            "relay_task_id": "relay-1",
            "receipt_detail": "ALPHA_ACK_M170",
            "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 3}),
        },
        "events": [{"event_type": "message.sent"}, {"event_type": "relay.completed"}],
    }


class _RecordingLocator:
    def __init__(self, sink: list[tuple[str, str]]) -> None:
        self._sink = sink

    @property
    def first(self) -> "_RecordingLocator":
        self._sink.append(("first", ""))
        return self

    def filter(self, *, has_text: object | None = None) -> "_RecordingLocator":
        recorded = ""
        if has_text is not None:
            recorded = getattr(has_text, "pattern", str(has_text))
        self._sink.append(("filter", recorded))
        return self

    async def wait_for(self, timeout: int) -> None:
        self._sink.append(("wait_for", str(timeout)))

    async def click(self) -> None:
        self._sink.append(("click", ""))


class _MentionPickerPage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_by_role(self, role: str, name: str | None = None) -> _RecordingLocator:
        self.calls.append(("role", role if name is None else f"{role}:{name}"))
        return _RecordingLocator(self.calls)


class _FallbackMentionOption:
    def __init__(self, sink: list[tuple[str, str]], text: str) -> None:
        self._sink = sink
        self._text = text

    async def inner_text(self) -> str:
        self._sink.append(("inner_text", self._text))
        return self._text

    async def click(self) -> None:
        self._sink.append(("fallback_click", self._text))


class _FallbackMentionFilter:
    def __init__(self, sink: list[tuple[str, str]]) -> None:
        self._sink = sink

    @property
    def first(self) -> "_FallbackMentionFilter":
        return self

    async def wait_for(self, timeout: int) -> None:
        self._sink.append(("wait_for", str(timeout)))
        raise m170_rerun_acceptance.PlaywrightTimeoutError("fast-path miss")


class _FallbackMentionList:
    def __init__(self, sink: list[tuple[str, str]], texts: list[str]) -> None:
        self._sink = sink
        self._texts = texts

    def filter(self, *, has_text: object | None = None) -> _FallbackMentionFilter:
        recorded = ""
        if has_text is not None:
            recorded = getattr(has_text, "pattern", str(has_text))
        self._sink.append(("filter", recorded))
        return _FallbackMentionFilter(self._sink)

    async def count(self) -> int:
        self._sink.append(("count", str(len(self._texts))))
        return len(self._texts)

    def nth(self, index: int) -> _FallbackMentionOption:
        self._sink.append(("nth", str(index)))
        return _FallbackMentionOption(self._sink, self._texts[index])


class _FallbackMentionPage:
    def __init__(self, texts: list[str]) -> None:
        self.calls: list[tuple[str, str]] = []
        self._texts = texts

    def get_by_role(self, role: str, name: str | None = None):
        self.calls.append(("role", role if name is None else f"{role}:{name}"))
        if role == "option":
            return _FallbackMentionList(self.calls, self._texts)
        return _FallbackMentionFilter(self.calls)

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        self.calls.append(("timeout", str(timeout_ms)))


class _SelectorPage:
    def __init__(self, values: list[Any]) -> None:
        self._values = list(values)
        self.calls: list[str] = []

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        self.calls.append(f"timeout:{timeout_ms}")


def test_wait_for_turn_completion_returns_structured_turn_without_ack_text(runtime_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed_selectors: list[str] = []

    def fake_fetchone_dict(query: str, params: tuple = ()) -> dict[str, Any] | None:
        observed_selectors.append(query)
        if "FROM messages" in query:
            return {
                "id": "msg-1",
                "conversation_id": "conv-1",
                "sender_user_id": "user-1",
                "sender_type": "human",
                "content": "@agent-m170-alpha please answer exactly as configured.",
                "created_at": "2026-03-16T10:00:00Z",
            }
        if "FROM relay_tasks" in query:
            return {
                "relay_task_id": "relay-1",
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "target_node_id": "m170-node",
                "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 1}),
                "status": "completed",
                "receipt_status": "delivered",
                "receipt_detail": "assistant output changed by product copy",
            }
        return None

    monkeypatch.setattr(m170_rerun_acceptance, "fetchone_dict", fake_fetchone_dict)
    monkeypatch.setattr(
        m170_rerun_acceptance,
        "fetchall_dicts",
        lambda query, params=(): [
            {
                "event_id": "evt-1",
                "event_type": "message.sent",
                "delivery_status": "sent",
                "payload_json": json.dumps({"message_id": "msg-1"}),
                "created_at": "2026-03-16T10:00:00Z",
            },
            {
                "event_id": "evt-2",
                "event_type": "relay.completed",
                "delivery_status": "delivered",
                "payload_json": json.dumps({"relay_task_id": "relay-1"}),
                "created_at": "2026-03-16T10:00:02Z",
            },
        ]
        if "FROM conversation_events" in query
        else [],
    )

    result = asyncio.run(
        m170_rerun_acceptance.wait_for_turn_completion(
            _SelectorPage([None]),
            text="@agent-m170-alpha please answer exactly as configured.",
        )
    )

    assert result["relay"]["receipt_detail"] == "assistant output changed by product copy"
    assert result["event_types"] == ["message.sent", "relay.completed"]
    assert all("ALPHA_ACK_M170" not in query for query in observed_selectors)
    assert all("BETA_ACK_M170" not in query for query in observed_selectors)


def test_wait_for_turn_completion_times_out_when_relay_never_completes(runtime_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        m170_rerun_acceptance,
        "fetchone_dict",
        lambda query, params=(): {
            "id": "msg-1",
            "conversation_id": "conv-1",
            "sender_user_id": "user-1",
            "sender_type": "human",
            "content": "@agent-m170-alpha please answer exactly as configured.",
            "created_at": "2026-03-16T10:00:00Z",
        }
        if "FROM messages" in query
        else {
            "relay_task_id": "relay-1",
            "message_id": "msg-1",
            "conversation_id": "conv-1",
            "target_node_id": "m170-node",
            "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 1}),
            "status": "queued",
            "receipt_status": None,
            "receipt_detail": None,
        },
    )
    monkeypatch.setattr(m170_rerun_acceptance, "fetchall_dicts", lambda query, params=(): [])

    with pytest.raises(TimeoutError, match="@agent-m170-alpha please answer exactly as configured."):
        asyncio.run(
            m170_rerun_acceptance.wait_for_turn_completion(
                _SelectorPage([None, None]),
                text="@agent-m170-alpha please answer exactly as configured.",
                timeout_ms=20,
                poll_interval_ms=10,
            )
        )


def test_wait_for_turn_completion_uses_latest_matching_prefix_for_picker_messages(runtime_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed_params: list[tuple[Any, ...]] = []

    def fake_fetchone_dict(query: str, params: tuple = ()) -> dict[str, Any] | None:
        observed_params.append(params)
        if "FROM messages" in query:
            if params == ("@agent:agent-m170-beta please answer via picker route.%",):
                return {
                    "id": "msg-picker",
                    "conversation_id": "conv-1",
                    "sender_user_id": "user-1",
                    "sender_type": "human",
                    "content": "@agent:agent-m170-beta\nplease answer via picker route.",
                    "created_at": "2026-03-16T10:01:00Z",
                }
            return None
        if "FROM relay_tasks" in query:
            return {
                "relay_task_id": "relay-picker",
                "message_id": "msg-picker",
                "conversation_id": "conv-1",
                "target_node_id": "m170-node",
                "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-beta"], "config_profile_version": 1}),
                "status": "completed",
                "receipt_status": "delivered",
                "receipt_detail": "picker route finished",
            }
        return None

    monkeypatch.setattr(m170_rerun_acceptance, "fetchone_dict", fake_fetchone_dict)
    monkeypatch.setattr(
        m170_rerun_acceptance,
        "fetchall_dicts",
        lambda query, params=(): [
            {
                "event_id": "evt-picker",
                "event_type": "relay.completed",
                "delivery_status": "delivered",
                "payload_json": json.dumps({"relay_task_id": "relay-picker"}),
                "created_at": "2026-03-16T10:01:02Z",
            }
        ],
    )

    result = asyncio.run(
        m170_rerun_acceptance.wait_for_turn_completion(
            _SelectorPage([None]),
            text="@agent:agent-m170-beta please answer via picker route.",
        )
    )

    assert result["message_id"] == "msg-picker"
    assert result["relay_task_id"] == "relay-picker"
    assert any(param and param[0] == "@agent:agent-m170-beta please answer via picker route.%" for param in observed_params)


def test_wait_for_turn_completion_ignores_stale_turns_from_other_conversations(runtime_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed_message_params: list[tuple[Any, ...]] = []

    def fake_fetchone_dict(query: str, params: tuple = ()) -> dict[str, Any] | None:
        if "FROM messages" in query:
            observed_message_params.append(params)
            if params == ("@agent-m170-alpha please answer exactly as configured.", "conv-current"):
                return {
                    "id": "msg-current",
                    "conversation_id": "conv-current",
                    "sender_user_id": "user-1",
                    "sender_type": "human",
                    "content": "@agent-m170-alpha please answer exactly as configured.",
                    "created_at": "2026-03-16T10:05:00Z",
                }
            if params == ("@agent-m170-alpha please answer exactly as configured.",):
                return {
                    "id": "msg-stale",
                    "conversation_id": "conv-stale",
                    "sender_user_id": "user-1",
                    "sender_type": "human",
                    "content": "@agent-m170-alpha please answer exactly as configured.",
                    "created_at": "2026-03-16T09:00:00Z",
                }
            return None
        if "FROM relay_tasks" in query:
            message_id = params[0]
            return {
                "relay_task_id": f"relay-{message_id}",
                "message_id": message_id,
                "conversation_id": "conv-current" if message_id == "msg-current" else "conv-stale",
                "target_node_id": "m170-node",
                "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 3}),
                "status": "completed",
                "receipt_status": "delivered",
                "receipt_detail": "ALPHA_ACK_M170",
            }
        return None

    monkeypatch.setattr(m170_rerun_acceptance, "fetchone_dict", fake_fetchone_dict)
    monkeypatch.setattr(
        m170_rerun_acceptance,
        "fetchall_dicts",
        lambda query, params=(): [
            {
                "event_id": "evt-current",
                "event_type": "relay.completed",
                "delivery_status": "delivered",
                "payload_json": json.dumps({"relay_task_id": "relay-msg-current"}),
                "created_at": "2026-03-16T10:05:02Z",
            }
        ],
    )

    result = asyncio.run(
        m170_rerun_acceptance.wait_for_turn_completion(
            _SelectorPage([None]),
            text="@agent-m170-alpha please answer exactly as configured.",
            conversation_id="conv-current",
        )
    )

    assert result["message_id"] == "msg-current"
    assert result["conversation_id"] == "conv-current"
    assert observed_message_params[0] == ("@agent-m170-alpha please answer exactly as configured.", "conv-current")
    assert ("@agent-m170-alpha please answer exactly as configured.",) not in observed_message_params



def test_finalize_run_artifacts_promotes_only_complete_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    staged_json = staged_dir / "m170-rerun-result.json"
    staged_home = staged_dir / "m170-rerun-home.png"
    staged_picker = staged_dir / "m170-rerun-picker.png"
    staged_json.write_text(json.dumps({"run_id": "run-123", "screenshots": []}), encoding="utf-8")
    staged_home.write_text("home", encoding="utf-8")
    staged_picker.write_text("picker", encoding="utf-8")

    out_json = tmp_path / "published-result.json"
    shot_home = tmp_path / "published-home.png"
    shot_picker = tmp_path / "published-picker.png"
    shot_home.write_text("previous-home", encoding="utf-8")

    monkeypatch.setattr(m170_rerun_acceptance, "OUT_JSON", out_json)
    monkeypatch.setattr(m170_rerun_acceptance, "SHOT_HOME", shot_home)
    monkeypatch.setattr(m170_rerun_acceptance, "SHOT_PICKER", shot_picker)

    result = {
        "run_id": "run-123",
        "screenshots": [str(staged_home), str(staged_picker)],
    }

    published = m170_rerun_acceptance.finalize_run_artifacts(result=result, staged_dir=staged_dir)

    assert published["run_id"] == "run-123"
    assert out_json.exists()
    assert json.loads(out_json.read_text(encoding="utf-8"))["run_id"] == "run-123"
    assert shot_home.read_text(encoding="utf-8") == "home"
    assert shot_picker.read_text(encoding="utf-8") == "picker"
    assert staged_json.exists() is False
    assert staged_home.exists() is False



def test_finalize_run_artifacts_preserves_previous_publish_when_stage_is_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    staged_json = staged_dir / "m170-rerun-result.json"
    staged_home = staged_dir / "m170-rerun-home.png"
    staged_json.write_text(json.dumps({"run_id": "run-broken", "screenshots": []}), encoding="utf-8")
    staged_home.write_text("new-home", encoding="utf-8")

    out_json = tmp_path / "published-result.json"
    shot_home = tmp_path / "published-home.png"
    shot_picker = tmp_path / "published-picker.png"
    out_json.write_text(json.dumps({"run_id": "run-prev", "screenshots": []}), encoding="utf-8")
    shot_home.write_text("previous-home", encoding="utf-8")
    shot_picker.write_text("previous-picker", encoding="utf-8")

    monkeypatch.setattr(m170_rerun_acceptance, "OUT_JSON", out_json)
    monkeypatch.setattr(m170_rerun_acceptance, "SHOT_HOME", shot_home)
    monkeypatch.setattr(m170_rerun_acceptance, "SHOT_PICKER", shot_picker)

    with pytest.raises(FileNotFoundError, match="m170-rerun-picker.png"):
        m170_rerun_acceptance.finalize_run_artifacts(
            result={"run_id": "run-broken", "screenshots": [str(staged_home), str(staged_dir / 'm170-rerun-picker.png')]},
            staged_dir=staged_dir,
        )

    assert json.loads(out_json.read_text(encoding="utf-8"))["run_id"] == "run-prev"
    assert shot_home.read_text(encoding="utf-8") == "previous-home"
    assert shot_picker.read_text(encoding="utf-8") == "previous-picker"



def test_pick_mention_candidate_tolerates_multiline_picker_copy() -> None:
    page = _MentionPickerPage()

    asyncio.run(
        m170_rerun_acceptance._pick_mention_candidate(
            page,
            label="Agent M170 Beta",
            handle="@agent:agent-m170-beta",
        )
    )

    assert page.calls == [
        ("role", "option"),
        ("filter", re.compile(r"Agent\ M170\ Beta\s+Agent\ M170\ Beta mention", re.IGNORECASE).pattern),
        ("first", ""),
        ("wait_for", "3000"),
        ("click", ""),
    ]



def test_pick_mention_candidate_falls_back_to_option_inner_text() -> None:
    page = _FallbackMentionPage([
        "Agent M170 Alpha\nAgent M170 Alpha mention",
        "Agent M170 Beta\nAgent M170 Beta mention",
    ])

    asyncio.run(
        m170_rerun_acceptance._pick_mention_candidate(
            page,
            label="Agent M170 Beta",
            handle="@agent:agent-m170-beta",
        )
    )

    assert ("fallback_click", "Agent M170 Beta\nAgent M170 Beta mention") in page.calls
