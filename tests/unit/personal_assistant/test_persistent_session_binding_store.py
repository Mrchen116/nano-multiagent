"""M248: PersistentSessionBindingStore SQLite 持久化测试。"""

from __future__ import annotations

from pathlib import Path
import pytest

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    SessionBinding,
    build_reply_context,
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

    def test_default_db_path_uses_current_pa_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An implicit binding store never recreates the retired PA home."""
        monkeypatch.setenv("HOME", str(tmp_path))

        store = PersistentSessionBindingStore()

        assert (
            store._db_path == tmp_path / ".nanoassistant" / "session_bindings.sqlite3"
        )  # noqa: SLF001
        assert store._db_path.exists()  # noqa: SLF001
        assert not (tmp_path / ".nano-assistant").exists()

    def test_build_reply_context_excludes_inbound_image_payloads(self) -> None:
        message = InboundMessage(
            channel_name="feishu:agent-a",
            text="[图片]",
            external_user_id="user-1",
            external_chat_id="chat-1",
            is_group=False,
            metadata={
                "message_id": "msg-1",
                "attachments": [{"url": "data:image/png;base64,large"}],
                "kernel_input_parts": [{"type": "image", "attachment_index": 0}],
                "image_resolution_failure": "download",
            },
        )

        assert build_reply_context(message).metadata == {"message_id": "msg-1"}


# ---------------------------------------------------------------------------
# R3 feat-394-M4: find_by_kernel_session_id — 与内存版契约一致
# ---------------------------------------------------------------------------


class TestR3FindByKernelSessionId:
    """PersistentSessionBindingStore.find_by_kernel_session_id 契约测试。

    feat-394-M4 R2-1 fix: cron 工具链调用 session_store.find_by_kernel_session_id
    (main.py:3021)，但 PersistentSessionBindingStore 只有内存版 SessionBindingStore
    有该方法。运行时抛 AttributeError → agent 报"cron tool is blocked by a hook"。

    契约与内存版 SessionBindingStore.find_by_kernel_session_id(:55) 一致：
    - 存在则返回第一个匹配的 SessionBinding
    - 不存在则返回 None
    - 多个绑定只匹配 kernel_session_id 的那一个
    """

    def test_find_by_kernel_session_id_returns_matching_binding(
        self, tmp_path: Path
    ) -> None:
        """bind 后按 kernel_session_id 能查回同一 binding。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context("chat-1")
        store.bind(
            session_key="web_relay:chat-1:agent-A",
            kernel_session_id="ksess-xyz",
            reply_context=rc,
        )

        result = store.find_by_kernel_session_id("ksess-xyz")

        assert result is not None
        assert result.kernel_session_id == "ksess-xyz"
        assert result.session_key == "web_relay:chat-1:agent-A"

    def test_find_by_kernel_session_id_returns_none_when_missing(
        self, tmp_path: Path
    ) -> None:
        """不存在的 kernel_session_id 返回 None。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")

        result = store.find_by_kernel_session_id("no-such-ksess")

        assert result is None

    def test_find_by_kernel_session_id_ignores_other_bindings(
        self, tmp_path: Path
    ) -> None:
        """多条 binding 中只返回匹配的那一条。"""
        store = PersistentSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        rc = _make_reply_context()
        store.bind(
            session_key="web_relay:c1:agent-A",
            kernel_session_id="ksess-aaa",
            reply_context=rc,
        )
        store.bind(
            session_key="web_relay:c2:agent-B",
            kernel_session_id="ksess-bbb",
            reply_context=rc,
        )

        result = store.find_by_kernel_session_id("ksess-bbb")

        assert result is not None
        assert result.kernel_session_id == "ksess-bbb"
        assert result.session_key == "web_relay:c2:agent-B"

    def test_find_by_kernel_session_id_survives_restart(self, tmp_path: Path) -> None:
        """持久化后重新创建 store 实例仍能查到 binding。"""
        db_path = tmp_path / "sb.sqlite3"
        rc = _make_reply_context("chat-persist")
        store1 = PersistentSessionBindingStore(db_path=db_path)
        store1.bind(
            session_key="web_relay:chat-persist:agent-X",
            kernel_session_id="ksess-persist",
            reply_context=rc,
        )
        del store1

        store2 = PersistentSessionBindingStore(db_path=db_path)
        result = store2.find_by_kernel_session_id("ksess-persist")

        assert result is not None
        assert result.kernel_session_id == "ksess-persist"
