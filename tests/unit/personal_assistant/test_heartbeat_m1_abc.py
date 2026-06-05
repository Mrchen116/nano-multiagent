"""feat-394-M1 补齐测试: A/B/C 三条退出标准.

A — tick-time 主动查询 canonical session（替换 reactive 反填）
B — transcript 修剪 API（静默轮询后会话无噪声）
C — IM heartbeat_json 落库 round-trip
"""

from __future__ import annotations

import asyncio
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


# ---------------------------------------------------------------------------
# B — transcript 修剪：静默轮询后会话无噪声
# ---------------------------------------------------------------------------


def test_polling_runner_has_trim_silent_tick_method(tmp_path: Path) -> None:
    """PollingHeartbeatRunner 必须有 trim_silent_tick 方法."""
    from personal_assistant.main import PollingHeartbeatRunner

    assert hasattr(PollingHeartbeatRunner, "trim_silent_tick"), (
        "PollingHeartbeatRunner 缺少 trim_silent_tick 方法"
    )


def test_polling_runner_trims_silent_tick_truncates_jsonl(tmp_path: Path) -> None:
    """PollingHeartbeatRunner.trim_silent_tick 截断 JSONL 到 pre_submit_line_count 行.

    这是 B 条退出标准的核心：静默轮询完成后，JSONL 文件被截断到 run 之前的行数，
    消除 heartbeat 触发 prompt + ack turn（net zero residual）。
    """
    from personal_assistant.main import PollingHeartbeatRunner

    # 准备一个包含 3 行的 JSONL 文件（模拟 run 前的 session 历史）
    session_dir = tmp_path / ".nanoassistant" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "sess-b1.jsonl"
    pre_submit_lines = [
        '{"type":"session_created","session_id":"sess-b1","created_at":"2026-01-01T00:00:00Z"}\n',
        '{"type":"turn","uuid":"msg-1","role":"user","content":"hello","timestamp":"2026-01-01T00:01:00Z"}\n',
        '{"type":"turn","uuid":"msg-2","role":"assistant","content":"hi there","timestamp":"2026-01-01T00:01:01Z"}\n',
    ]
    session_file.write_text("".join(pre_submit_lines), encoding="utf-8")

    # 模拟 heartbeat run 追加了触发 prompt 和 ack turn（2 行）
    with session_file.open("a", encoding="utf-8") as f:
        f.write(
            '{"type":"turn","uuid":"hb-prompt","role":"user","content":"Read HEARTBEAT.md...","timestamp":"2026-01-01T01:00:00Z"}\n'
        )
        f.write(
            '{"type":"turn","uuid":"hb-ok","role":"assistant","content":"HEARTBEAT_OK","timestamp":"2026-01-01T01:00:01Z"}\n'
        )

    assert session_file.read_text(encoding="utf-8").count("\n") == 5, (
        "setup: should be 5 lines"
    )

    runner = PollingHeartbeatRunner.__new__(PollingHeartbeatRunner)

    # trim_silent_tick(session_file, pre_submit_line_count) 应截断到 pre_submit_line_count 行
    asyncio.run(
        runner.trim_silent_tick(
            session_file=session_file,
            pre_submit_line_count=len(pre_submit_lines),
        )
    )

    remaining = session_file.read_text(encoding="utf-8")
    remaining_lines = [l for l in remaining.splitlines() if l.strip()]
    assert len(remaining_lines) == 3, (
        f"截断后应剩 3 行（run 前的历史）；实际剩 {len(remaining_lines)} 行:\n{remaining}"
    )
    assert "HEARTBEAT_OK" not in remaining, (
        "静默 tick 修剪后 HEARTBEAT_OK ack turn 不应残留"
    )
    assert "HEARTBEAT.md" not in remaining, (
        "静默 tick 修剪后 heartbeat 触发 prompt 不应残留"
    )


# ---------------------------------------------------------------------------
# C — IM heartbeat_json 落库 round-trip
# ---------------------------------------------------------------------------


def test_agent_profile_has_heartbeat_json_field() -> None:
    """AgentProfile domain model 必须有 heartbeat_json 字段."""
    from IM.domain.models import AgentProfile
    from dataclasses import fields

    field_names = {f.name for f in fields(AgentProfile)}
    assert "heartbeat_json" in field_names, "AgentProfile 缺少 heartbeat_json 字段"


def test_agent_profiles_db_has_heartbeat_json_column(tmp_path: Path) -> None:
    """agent_profiles 表必须有 heartbeat_json 列（DB migration）."""
    from IM.infra.db import connect, initialize_schema

    db_path = tmp_path / "im_c.db"
    conn = connect(db_path)
    initialize_schema(conn)

    cols = conn.execute("PRAGMA table_info(agent_profiles)").fetchall()
    col_names = {row["name"] for row in cols}
    assert "heartbeat_json" in col_names, (
        f"agent_profiles 表缺少 heartbeat_json 列；现有列: {sorted(col_names)}"
    )


def test_update_profile_persists_heartbeat_json(tmp_path: Path) -> None:
    """config_service.update_profile 持久化 heartbeat_json，GET 读回相同值."""
    from IM.infra.db import connect, initialize_schema
    from IM.infra.repositories import AgentProfileRepository
    from IM.application.config_service import ConfigService

    db = connect(tmp_path / "im_c2.db")
    initialize_schema(db)

    repo = AgentProfileRepository(db)
    # 创建一个 profile
    repo.upsert_profile(
        agent_id="agent-c1",
        owner_id="owner-1",
        node_id=None,
        display_name="C1 Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(tmp_path / "ws-c1"),
    )

    # update_profile 应接受 heartbeat_json 参数
    heartbeat_payload = {"enabled": True, "every": "30m", "active_hours": None}
    import json

    heartbeat_json_str = json.dumps(heartbeat_payload)

    updated = repo.update_profile(
        agent_id="agent-c1",
        profile_version=1,
        display_name="C1 Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(tmp_path / "ws-c1"),
        heartbeat_json=heartbeat_json_str,
    )

    assert updated.heartbeat_json == heartbeat_json_str, (
        f"update_profile 后 heartbeat_json 应持久化；实际={updated.heartbeat_json!r}"
    )

    # GET 重查应读回相同值
    refetched = repo.get_profile(agent_id="agent-c1")
    assert refetched is not None
    assert refetched.heartbeat_json == heartbeat_json_str, (
        f"GET 重查后 heartbeat_json 应为 {heartbeat_json_str!r}；实际={refetched.heartbeat_json!r}"
    )


def test_agents_patch_route_accepts_heartbeat_json(tmp_path: Path) -> None:
    """PATCH /im/v1/agents/{id}/config 接受并返回 heartbeat_json 字段."""
    import json
    from fastapi.testclient import TestClient
    from IM.app import create_app
    from IM.infra.repositories import (
        AgentProfileRepository,
        NodeRepository,
        UserRepository,
    )
    from im_service.integration.conftest import register_user, authorize  # noqa: PLC0415

    app = create_app(db_path=tmp_path / "im_route.db")
    with TestClient(app) as client:
        owner = register_user(client, username="hb-owner", display_name="HB Owner")
        authorize(client, owner)

        profiles = AgentProfileRepository(app.state.connection)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-hb",
            node_name="HB Node",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles.upsert_profile(
            agent_id="agent-hb-1",
            owner_id=owner.owner_id,
            display_name="HB Agent",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-hb", "agent-hb-1"),
        )
        app.state.connection.commit()

        heartbeat_payload = {"enabled": True, "every": "30m"}
        resp = client.patch(
            "/im/v1/agents/agent-hb-1/config",
            json={
                "profile_version": 1,
                "display_name": "HB Agent",
                "description": "",
                "system_prompt": "",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "heartbeat_json": json.dumps(heartbeat_payload),
            },
        )
        assert resp.status_code == 200, (
            f"PATCH 应返回 200；实际 {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "heartbeat_json" in body, (
            f"响应应包含 heartbeat_json；实际键: {list(body.keys())}"
        )
        assert body["heartbeat_json"] == json.dumps(heartbeat_payload)


def test_config_sync_notifier_includes_heartbeat_json(tmp_path: Path) -> None:
    """ConfigSyncNotifier 推送的 profile 数据包含 heartbeat_json 字段，gateway 能解析到."""
    from IM.infra.db import connect, initialize_schema
    from IM.infra.repositories import AgentProfileRepository
    from IM.application.config_service import ConfigService

    db = connect(tmp_path / "im_sync.db")
    initialize_schema(db)

    repo = AgentProfileRepository(db)
    import json

    heartbeat_json_str = json.dumps({"enabled": True, "every": "10m"})

    repo.upsert_profile(
        agent_id="agent-sync-1",
        owner_id="owner-sync",
        node_id=None,
        display_name="Sync Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(tmp_path / "ws-sync"),
    )
    repo.update_profile(
        agent_id="agent-sync-1",
        profile_version=1,
        display_name="Sync Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(tmp_path / "ws-sync"),
        heartbeat_json=heartbeat_json_str,
    )

    # GET /im/v1/agents/{id}/config 应包含 heartbeat 字段（ConfigSyncNotifier 读的接口）
    profile = repo.get_profile(agent_id="agent-sync-1")
    assert profile is not None
    assert profile.heartbeat_json == heartbeat_json_str, (
        f"profile.heartbeat_json 应为 {heartbeat_json_str!r}；实际={profile.heartbeat_json!r}"
    )
