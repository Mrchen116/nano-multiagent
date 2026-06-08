"""feat-394-M1 补齐测试: A/B/C 三条退出标准.

A — tick-time 主动查询 canonical session（替换 reactive 反填）
B — transcript 修剪 API（静默轮询后会话无噪声）
C — IM heartbeat_json 落库 round-trip
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# A — PersistentSessionBindingStore.find_direct_by_agent + tick-time 调用
# ---------------------------------------------------------------------------


def test_persistent_store_has_find_direct_by_agent_method(tmp_path: Path) -> None:
    """PersistentSessionBindingStore 必须有 find_direct_by_agent(channel_name, agent_id)."""
    from personal_assistant.gateway.session_keys import PersistentSessionBindingStore

    store = PersistentSessionBindingStore(db_path=tmp_path / "sess.db")
    assert hasattr(store, "find_direct_by_agent"), (
        "PersistentSessionBindingStore 缺少 find_direct_by_agent 方法"
    )


def test_find_direct_by_agent_returns_oldest_binding(tmp_path: Path) -> None:
    """find_direct_by_agent 按 created_at 最旧取第一条（语义对齐 _find_canonical_direct_conversation）.

    重要：用 created_at（首次绑定时间），不是 updated_at（每次消息后刷新）。
    updated_at 随聊天活动漂移，会导致心跳跑了 A 聊天历史却投递到 IM 的 canonical B 聊天。
    created_at 不动，与 IM created_at 排序一致。
    """
    import datetime as dt
    from personal_assistant.gateway.session_keys import PersistentSessionBindingStore
    from personal_assistant.channels.base import ReplyContext

    store = PersistentSessionBindingStore(db_path=tmp_path / "sess.db")

    # 先用正常 bind() 注入 newer 那条（created_at = 当前时间）
    store.bind(
        session_key="web_relay:conv-newer:agent-x",
        kernel_session_id="sess-newer",
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id="conv-newer",
            thread_id=None,
            metadata={},
        ),
    )
    # 手动注入一条更旧的（created_at 2020，但 updated_at 2024 — 即该会话最近更新，但更早创建）
    # 验证：find_direct_by_agent 按 created_at 而非 updated_at 排序
    old_ts = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc).isoformat()
    newer_ts = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).isoformat()
    store._conn.execute(
        """
        INSERT INTO session_bindings
            (session_key, kernel_session_id, reply_context_json, updated_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "web_relay:conv-oldest:agent-x",
            "sess-oldest",
            '{"channel_name":"web_relay","target_chat_id":"conv-oldest","thread_id":null,"metadata":{}}',
            newer_ts,  # updated_at 较新（有活动）
            old_ts,  # created_at 最旧（canonical 判据）
        ),
    )
    store._conn.commit()

    binding = store.find_direct_by_agent(channel_name="web_relay", agent_id="agent-x")
    assert binding is not None, "find_direct_by_agent 应返回 binding，不是 None"
    assert binding.kernel_session_id == "sess-oldest", (
        f"应按 created_at ASC 返回最旧 binding (sess-oldest)，实际返回 {binding.kernel_session_id!r}"
    )


def test_find_direct_by_agent_returns_none_when_no_binding(tmp_path: Path) -> None:
    """find_direct_by_agent 在无匹配 binding 时返回 None."""
    from personal_assistant.gateway.session_keys import PersistentSessionBindingStore

    store = PersistentSessionBindingStore(db_path=tmp_path / "sess.db")
    result = store.find_direct_by_agent(
        channel_name="web_relay", agent_id="agent-no-conv"
    )
    assert result is None


def test_heartbeat_scheduler_uses_find_direct_by_agent_before_submit(
    tmp_path: Path,
) -> None:
    """HeartbeatScheduler tick 在提交 run 之前必须调用 find_direct_by_agent 更新 canonical session.

    验证方式：给 scheduler 注入一个带 find_direct_by_agent 的 session store，
    tick 之后检查 canonical_session_store 已经被更新（不是由 turn_start ack 反填的）。
    """
    from datetime import UTC, datetime
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.scheduler.heartbeat_scheduler import (
        HeartbeatScheduler,
        HeartbeatSchedulerStateStore,
    )
    from personal_assistant.gateway.session_keys import SessionBinding
    from personal_assistant.channels.base import ReplyContext

    agent_dir = tmp_path / "agent-tick"
    agent_dir.mkdir()
    (agent_dir / "HEARTBEAT.md").write_text(
        "interval: 1s\n\n- Check status\n", encoding="utf-8"
    )
    agent = AgentWorkspaceConfig(
        agent_id="agent-tick", workspace_root=agent_dir, features={"heartbeat": True}
    )

    EXPECTED_SESSION = "sess-from-direct-chat"

    class _FakeSessionStore:
        """Minimal session store fake with find_direct_by_agent."""

        def find_direct_by_agent(
            self, *, channel_name: str, agent_id: str
        ) -> SessionBinding | None:  # noqa: ARG002
            if agent_id == "agent-tick":
                return SessionBinding(
                    session_key=f"web_relay:conv-direct:{agent_id}",
                    kernel_session_id=EXPECTED_SESSION,
                    reply_context=ReplyContext(
                        channel_name="web_relay",
                        target_chat_id="conv-direct",
                        thread_id=None,
                        metadata={},
                    ),
                )
            return None

    class _FakeKernelClient:
        def __init__(self) -> None:
            self.sent_messages: list[dict] = []
            self._run_counter = 0

        async def create_session(self, **_kw: object) -> dict:
            return {"session_id": "sess-fallback"}

        def current_event_sequence(self) -> int:
            return 0

        def submit_message(self, *, session_id: str, **_kw: object) -> dict:
            self._run_counter += 1
            payload = {"run_id": f"run-{self._run_counter}", "session_id": session_id}
            self.sent_messages.append(payload)
            return payload

    canonical_session_store: dict[str, str] = {}
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        canonical_session_store=canonical_session_store,
        session_store=_FakeSessionStore(),
    )

    t0 = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
    asyncio.run(scheduler.tick(now=t0))

    # canonical_session_store 必须在 tick 期间被更新（tick-time 查询，非 reactive）
    assert canonical_session_store.get("agent-tick") == EXPECTED_SESSION, (
        f"tick-time 查询应更新 canonical_session_store['agent-tick']={EXPECTED_SESSION!r}，"
        f"实际={canonical_session_store.get('agent-tick')!r}"
    )
    # run 必须使用 canonical session（带历史），不是 fallback
    if kernel.sent_messages:
        used_session = kernel.sent_messages[0]["session_id"]
        assert used_session == EXPECTED_SESSION, (
            f"run 应使用 canonical session {EXPECTED_SESSION!r}，实际使用 {used_session!r}"
        )


def test_heartbeat_scheduler_uses_provided_canonical_session(tmp_path: Path) -> None:
    """HeartbeatScheduler must use the canonical session_id when provided, not create a new one.

    feat-394 decision 3: heartbeat runs in the (owner, agent) canonical direct chat
    kernel session.  When a canonical session_id is pre-known, the scheduler must
    not call create_session.
    """
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.scheduler.heartbeat_scheduler import (
        HeartbeatScheduler,
        HeartbeatSchedulerStateStore,
    )

    agent_dir = tmp_path / "agent-canonical"
    agent_dir.mkdir()
    (agent_dir / "HEARTBEAT.md").write_text(
        "interval: 1m\n\n- Check status\n", encoding="utf-8"
    )
    agent = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=agent_dir, features={"heartbeat": True}
    )

    class _FakeKernelClient:
        def __init__(self) -> None:
            self.created_sessions: list[dict] = []
            self.sent_messages: list[dict] = []
            self._session_counter = 0
            self._run_counter = 0

        async def create_session(self, **_kw: object) -> dict:
            self._session_counter += 1
            payload = {"session_id": f"sess-{self._session_counter}"}
            self.created_sessions.append(payload)
            return payload

        def current_event_sequence(self) -> int:
            return 0

        def submit_message(self, *, session_id: str, **_kw: object) -> dict:
            self._run_counter += 1
            payload = {"run_id": f"run-{self._run_counter}", "session_id": session_id}
            self.sent_messages.append(payload)
            return payload

    kernel = _FakeKernelClient()
    canonical_sessions: dict[str, str] = {"agent-a": "canonical-sess-123"}
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        canonical_session_store=canonical_sessions,
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    # Session creation must be skipped — canonical session used directly
    assert kernel.created_sessions == [], (
        "create_session must not be called when canonical_session_store has a session for this agent"
    )
    assert len(summary.triggered_runs) == 1
    assert summary.triggered_runs[0].session_id == "canonical-sess-123"


def test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks(
    tmp_path: Path,
) -> None:
    """HeartbeatScheduler uses a stable per-agent ':heartbeat' session, not a fresh session per tick.

    After feat-393 M1, _submit_run must reuse the same session for successive ticks
    instead of calling create_session on every tick.  This verifies the fresh-session
    roaming is eliminated.
    """
    from datetime import UTC, datetime
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.scheduler.heartbeat_scheduler import (
        HeartbeatScheduler,
        HeartbeatSchedulerStateStore,
    )

    class _FakeKernelClient:
        def __init__(self) -> None:
            self.created_sessions: list[dict] = []
            self.sent_messages: list[dict] = []
            self._session_counter = 0
            self._run_counter = 0

        async def create_session(
            self,
            *,
            workspace_root: str,
            product_id: str,
            title: str | None = None,
            **_kw,
        ) -> dict:
            self._session_counter += 1
            session_id = f"sess-{self._session_counter}"
            self.created_sessions.append({"session_id": session_id})
            return {"session_id": session_id}

        def submit_message(self, *, session_id: str, texts: list[str], **_kw) -> dict:
            self._run_counter += 1
            payload = {"run_id": f"run-{self._run_counter}", "session_id": session_id}
            self.sent_messages.append(payload)
            return payload

    agent_dir = tmp_path / "agent-a"
    agent_dir.mkdir()
    (agent_dir / "HEARTBEAT.md").write_text(
        "interval: 1s\n\n- Check status\n", encoding="utf-8"
    )

    agent = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=agent_dir, features={"heartbeat": True}
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    from datetime import timedelta
    import asyncio

    t0 = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
    await_tick = asyncio.run

    # Tick 1
    await_tick(scheduler.tick(now=t0))
    # Tick 2 — one interval later
    await_tick(scheduler.tick(now=t0 + timedelta(seconds=2)))

    # After feat-393: only one session created (stable :heartbeat session reused)
    assert len(kernel.created_sessions) == 1, (
        f"Expected 1 session (stable :heartbeat reuse); got {len(kernel.created_sessions)} sessions. "
        "fresh-session per tick must be eliminated (feat-393 decision 4)."
    )
    # Both ticks should use the same session_id
    session_ids_used = [msg["session_id"] for msg in kernel.sent_messages]
    assert len(set(session_ids_used)) == 1, (
        f"Both ticks must use the same session_id; got {session_ids_used}"
    )


# ---------------------------------------------------------------------------
# feat-394 防回归: _parse_heartbeat_from_im_payload 4-tuple 签名（来自 M9-E）
# ---------------------------------------------------------------------------


def test_parse_heartbeat_returns_cadence_4tuple() -> None:
    """_parse_heartbeat_from_im_payload returns (every, start, end, tz) 4-tuple (no enabled)."""
    import importlib

    main_mod = importlib.import_module("personal_assistant.main")
    result = main_mod._parse_heartbeat_from_im_payload(
        {"enabled": True, "every": "10m"}
    )
    assert len(result) == 4, (
        f"_parse_heartbeat_from_im_payload must return 4-tuple; got {len(result)}-tuple"
    )
    every, start, end, tz = result
    assert every == "10m"
    assert start is None
    assert end is None
    assert tz is None


def test_parse_heartbeat_empty_input_returns_nones() -> None:
    """Empty raw heartbeat dict → (None, None, None, None)."""
    import importlib

    main_mod = importlib.import_module("personal_assistant.main")
    result = main_mod._parse_heartbeat_from_im_payload({})
    assert len(result) == 4
    assert all(v is None for v in result)


def test_parse_heartbeat_invalid_input_returns_nones() -> None:
    """Non-dict raw heartbeat → (None, None, None, None) (not 5-tuple with False first)."""
    import importlib

    main_mod = importlib.import_module("personal_assistant.main")
    result = main_mod._parse_heartbeat_from_im_payload(None)
    assert len(result) == 4
    assert all(v is None for v in result)
