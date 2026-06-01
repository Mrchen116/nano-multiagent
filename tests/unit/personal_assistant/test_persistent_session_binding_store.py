"""M248: PersistentSessionBindingStore SQLite 持久化测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    SessionBinding,
)


def _make_reply_context(chat_id: str = "chat-1") -> ReplyContext:
    return ReplyContext(channel_name="web_relay", target_chat_id=chat_id)


# ---------------------------------------------------------------------------
# R1 — bind / get / drop_agent / 持久化恢复
# ---------------------------------------------------------------------------


class TestR1PersistAndRecover:
    """bind/get/drop_agent 与跨实例持久化恢复。"""

    def test_bind_and_get_returns_same_binding(self, tmp_path: Path) -> None:
        """bind 写入后 get 能读取相同 binding。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        binding = store.bind(
            session_key="ch:chat:agent-1",
            kernel_session_id="ksess-abc",
            reply_context=rc,
        )

        result = store.get("ch:chat:agent-1")

        assert result is not None
        assert result.session_key == "ch:chat:agent-1"
        assert result.kernel_session_id == "ksess-abc"
        assert result.reply_context == rc

    def test_get_unknown_key_returns_none(self, tmp_path: Path) -> None:
        """get 不存在的 session_key 返回 None。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        assert store.get("no-such-key") is None

    def test_bind_upsert_overwrites_existing(self, tmp_path: Path) -> None:
        """bind 同一 session_key 两次，第二次覆盖（upsert 语义）。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc1 = _make_reply_context("chat-1")
        rc2 = _make_reply_context("chat-2")
        store.bind(session_key="ch:c:a", kernel_session_id="ksess-1", reply_context=rc1)
        store.bind(session_key="ch:c:a", kernel_session_id="ksess-2", reply_context=rc2)

        result = store.get("ch:c:a")

        assert result is not None
        assert result.kernel_session_id == "ksess-2"
        assert result.reply_context == rc2

    def test_persistent_recovery_across_instances(self, tmp_path: Path) -> None:
        """重新构造同一 db_path 实例后 get 仍能返回持久化 binding。"""
        db_path = tmp_path / "sb.sqlite3"
        rc = _make_reply_context("persist-chat")
        store1 = PersistentSessionBindingStore(db_path=db_path)
        store1.bind(
            session_key="ch:persist:agent-x",
            kernel_session_id="ksess-persist",
            reply_context=rc,
        )
        del store1

        store2 = PersistentSessionBindingStore(db_path=db_path)
        result = store2.get("ch:persist:agent-x")

        assert result is not None
        assert result.kernel_session_id == "ksess-persist"

    def test_drop_agent_removes_matching_bindings(self, tmp_path: Path) -> None:
        """drop_agent 按 :{agent_id} suffix 删除相关行，其他行不受影响。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        store.bind(
            session_key="ch:c1:agent-A", kernel_session_id="ksess-1", reply_context=rc
        )
        store.bind(
            session_key="ch:c2:agent-A", kernel_session_id="ksess-2", reply_context=rc
        )
        store.bind(
            session_key="ch:c3:agent-B", kernel_session_id="ksess-3", reply_context=rc
        )

        store.drop_agent("agent-A")

        assert store.get("ch:c1:agent-A") is None
        assert store.get("ch:c2:agent-A") is None
        assert store.get("ch:c3:agent-B") is not None

    def test_drop_agent_unknown_agent_is_noop(self, tmp_path: Path) -> None:
        """drop_agent 对不存在的 agent_id 不报错。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        store.bind(
            session_key="ch:c:agent-Z", kernel_session_id="ksess-z", reply_context=rc
        )

        store.drop_agent("no-such-agent")

        assert store.get("ch:c:agent-Z") is not None

    def test_db_file_created(self, tmp_path: Path) -> None:
        """构造 PersistentSessionBindingStore 后 db 文件存在。"""
        db_path = tmp_path / "sb.sqlite3"
        PersistentSessionBindingStore(db_path=db_path)
        assert db_path.exists()

    def test_db_parent_created_if_missing(self, tmp_path: Path) -> None:
        """db_path 父目录不存在时自动创建。"""
        db_path = tmp_path / "subdir" / "sb.sqlite3"
        PersistentSessionBindingStore(db_path=db_path)
        assert db_path.exists()


# ---------------------------------------------------------------------------
# R2 — kernel session 验证
# ---------------------------------------------------------------------------


class TestR2KernelValidation:
    """get() 不再探测 kernel —— 直接返回存储的 binding。

    bugfix-348 (Option C): 内核无状态，按 workspace_root 定位 session 文件。
    binding 行不携带 workspace_root，所以 get() 无法（也不应）做带 workspace_root
    的存活校验。存活/workspace 校验上移到 InboundPipeline._ensure_binding ->
    _binding_matches_workspace_root，那里知道 agent 的 workspace_root。
    set_kernel_client 仍保留为兼容性 setter，但 get() 不再调用它。
    """

    def test_get_returns_stored_binding_without_probing_kernel(
        self, tmp_path: Path
    ) -> None:
        """即使注入了 kernel_client，get() 也不调用 get_session()。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        store.bind(session_key="ch:c:a", kernel_session_id="ksess-ok", reply_context=rc)

        mock_client = MagicMock()
        store.set_kernel_client(mock_client)

        result = store.get("ch:c:a")

        assert result is not None
        assert result.kernel_session_id == "ksess-ok"
        # get() must not probe the kernel — validation lives in the pipeline now.
        mock_client.get_session.assert_not_called()

    def test_get_does_not_delete_binding_even_if_kernel_would_404(
        self, tmp_path: Path
    ) -> None:
        """get() 不再因 kernel 探测失败而删除 binding；binding 持久保留。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        store.bind(
            session_key="ch:c:a", kernel_session_id="ksess-dead", reply_context=rc
        )

        mock_client = MagicMock()
        mock_client.get_session.side_effect = RuntimeError(
            "kernel request failed (404)"
        )
        store.set_kernel_client(mock_client)

        result = store.get("ch:c:a")

        # binding is returned as-is; the pipeline's workspace-aware check decides
        # whether to refresh it.
        assert result is not None
        assert result.kernel_session_id == "ksess-dead"
        # record still in DB across a fresh instance
        store2 = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        assert store2.get("ch:c:a") is not None

    def test_get_without_kernel_client_returns_binding(self, tmp_path: Path) -> None:
        """kernel_client 为 None 时直接返回 binding。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        store.bind(session_key="ch:c:a", kernel_session_id="ksess-x", reply_context=rc)

        result = store.get("ch:c:a")

        assert result is not None
        assert result.kernel_session_id == "ksess-x"

    def test_get_unknown_key_returns_none(self, tmp_path: Path) -> None:
        """key 不存在时返回 None，不触碰 kernel_client。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        mock_client = MagicMock()
        store.set_kernel_client(mock_client)

        result = store.get("missing-key")

        assert result is None
        mock_client.get_session.assert_not_called()
