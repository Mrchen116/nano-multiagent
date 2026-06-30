"""Integration tests for feishu channel registration in main._build_channel_registry."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.config.local_store import ChannelConfig
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.main import _build_channel_registry


class TestBuildChannelRegistryFeishu:
    """Verify _build_channel_registry creates FeishuAdapter for feishu channels."""

    @patch("personal_assistant.main.FeishuAdapter")
    def test_feishu_channel_creates_adapter(self, mock_fa_cls: MagicMock) -> None:
        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        mock_fa_cls.assert_called_once()
        call_kwargs = mock_fa_cls.call_args[1]
        assert call_kwargs["app_id"] == "cli_a"
        assert call_kwargs["app_secret"] == "s_a"
        assert call_kwargs["agent_id"] == "plato"

    @patch("personal_assistant.main.FeishuAdapter")
    def test_multiple_feishu_accounts_registered(
        self, mock_fa_cls: MagicMock
    ) -> None:
        # Return distinct mock instances with unique names
        mock_plato = MagicMock()
        mock_plato.name = "feishu:plato"
        mock_luban = MagicMock()
        mock_luban.name = "feishu:luban"
        mock_fa_cls.side_effect = [mock_plato, mock_luban]

        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
            ChannelConfig(
                name="feishu:luban-bot",
                enabled=True,
                settings={
                    "name": "luban-bot",
                    "appId": "cli_b",
                    "appSecret": "s_b",
                    "agentId": "luban",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        assert mock_fa_cls.call_count == 2
        agent_ids = [c[1]["agent_id"] for c in mock_fa_cls.call_args_list]
        assert "plato" in agent_ids
        assert "luban" in agent_ids

    @patch("personal_assistant.main.FeishuAdapter")
    def test_feishu_disabled_not_registered(self, mock_fa_cls: MagicMock) -> None:
        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=False,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        mock_fa_cls.assert_not_called()

    @patch("personal_assistant.main.FeishuAdapter")
    @patch("personal_assistant.main.WebRelayAdapter")
    def test_feishu_coexists_with_web_relay(
        self, mock_wra_cls: MagicMock, mock_fa_cls: MagicMock
    ) -> None:
        mock_adapter = MagicMock()
        mock_adapter.name = "feishu:plato"
        mock_fa_cls.return_value = mock_adapter

        channels = (
            ChannelConfig(name="web_relay", enabled=True, settings={}),
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        mock_wra_cls.assert_called_once()
        mock_fa_cls.assert_called_once()


class TestBuildChannelRegistryFeishuRealAdapter:
    """Verify _build_channel_registry passes all required args to real FeishuAdapter.

    These tests do NOT mock FeishuAdapter — they verify the actual constructor
    receives all required keyword-only arguments (group_context_store, etc.).
    This catches parameter-mismatch bugs that mock-based tests cannot detect.
    """

    def test_real_feishu_adapter_construction(self) -> None:
        """Real FeishuAdapter must construct without TypeError."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.gateway.group_context_store import GroupContextStore

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "group_context.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)

            # This must not raise TypeError for missing keyword-only args
            adapter = FeishuAdapter(
                app_id="cli_a",
                app_secret="s_a",
                agent_id="plato",
                bot_open_id="ou_123",
                group_context_store=group_ctx,
            )
            assert adapter.name == "feishu:plato"

    def test_build_channel_registry_passes_group_context_store(self) -> None:
        """_build_channel_registry must pass group_context_store to FeishuAdapter."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.gateway.group_context_store import GroupContextStore

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "group_context.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)

            channels = (
                ChannelConfig(
                    name="feishu:plato-bot",
                    enabled=True,
                    settings={
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "s_a",
                        "agentId": "plato",
                    },
                ),
            )
            # This must not raise TypeError for missing group_context_store
            registry = _build_channel_registry(
                channels, group_context_store=group_ctx
            )
            # Verify the adapter was actually registered
            assert len(registry.list()) == 1
            adapter = registry.list()[0]
            assert isinstance(adapter, FeishuAdapter)
            assert adapter.name == "feishu:plato"

    def test_build_channel_registry_without_group_context_store_fails(self) -> None:
        """_build_channel_registry with feishu channel but no group_context_store
        creates FeishuAdapter with _group_ctx=None, which would crash at runtime
        when processing group messages (append/drain). This is the CRITICAL bug."""
        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        adapter = registry.list()[0]
        # This is the bug: _group_ctx is None, causing AttributeError at runtime
        assert adapter._group_ctx is None

    def test_bootstrap_path_creates_and_passes_group_context_store(self) -> None:
        """Simulate bootstrap path: create GroupContextStore, pass to _build_channel_registry."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.gateway.group_context_store import GroupContextStore

        with TemporaryDirectory() as tmpdir:
            runtime_dir = Path(tmpdir)
            db_path = runtime_dir / "group_context_buffer.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)

            channels = (
                ChannelConfig(
                    name="feishu:plato-bot",
                    enabled=True,
                    settings={
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "s_a",
                        "agentId": "plato",
                    },
                ),
            )
            # This is the bootstrap path: create GroupContextStore then pass it
            registry = _build_channel_registry(
                channels, group_context_store=group_ctx
            )
            adapter = registry.list()[0]
            assert isinstance(adapter, FeishuAdapter)
            assert adapter.name == "feishu:plato"
            # Verify _group_ctx is not None (would be if not passed)
            assert adapter._group_ctx is not None
            assert adapter._group_ctx is group_ctx

    def test_build_channel_registry_passes_bot_open_id(self) -> None:
        """_build_channel_registry passes bot_open_id from settings when present."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.gateway.group_context_store import GroupContextStore

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "group_context.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)

            channels = (
                ChannelConfig(
                    name="feishu:plato-bot",
                    enabled=True,
                    settings={
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "s_a",
                        "agentId": "plato",
                        "botOpenId": "ou_bot_123",
                    },
                ),
            )
            registry = _build_channel_registry(
                channels, group_context_store=group_ctx
            )
            adapter = registry.list()[0]
            assert isinstance(adapter, FeishuAdapter)
            assert adapter.name == "feishu:plato"
            # Verify bot_open_id was passed (internal attribute check)
            assert adapter._bot_open_id == "ou_bot_123"


class TestFeishuBufferKeyConsistency:
    """Group buffer key alignment between FeishuAdapter and InboundPipeline."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_buf_key_matches_inbound_pipeline(
        self, mock_fc_cls: MagicMock
    ) -> None:
        """FeishuAdapter and InboundPipeline must generate the same buffer key for
        the same group chat so that buffered context is correctly drained.
        """
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline
        from personal_assistant.channels.base import InboundMessage

        store = MagicMock(spec=GroupContextStore)
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            agent_id="plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )

        # Simulate what InboundPipeline._group_buf_key_for_agent produces
        # for a feishu group message
        msg = InboundMessage(
            channel_name="feishu:plato",
            text="hello",
            external_user_id="ou_user1",
            external_chat_id="feishu:cli_a:group:oc_grp1",
            is_group=True,
            agent_id="plato",
        )
        pipeline_key = InboundPipeline._group_buf_key_for_agent(msg, "plato")

        # Trigger a buffer operation to capture the key FeishuAdapter uses
        on_inbound = MagicMock()
        adapter.start(on_inbound)
        from personal_assistant.channels.feishu_client import FeishuMessageEvent

        event = FeishuMessageEvent(
            text="just chatting",
            sender_open_id="ou_user1",
            chat_id="oc_grp1",
            chat_type="group",
            message_id="msg_001",
            is_group=True,
            mentions=[],
        )
        adapter._handle_message(event)

        adapter_key = store.append.call_args[0][0]
        assert adapter_key == pipeline_key, (
            f"buffer key mismatch: adapter={adapter_key!r} vs pipeline={pipeline_key!r}"
        )

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_drain_key_matches_append_key(self, mock_fc_cls: MagicMock) -> None:
        """The key used to drain must match the key used to append."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.channels.feishu_client import FeishuMessageEvent

        store = MagicMock(spec=GroupContextStore)
        store.drain.return_value = []
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            agent_id="plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )

        on_inbound = MagicMock()
        adapter.start(on_inbound)

        # First buffer a message
        buffer_event = FeishuMessageEvent(
            text="just chatting",
            sender_open_id="ou_user1",
            chat_id="oc_grp1",
            chat_type="group",
            message_id="msg_002",
            is_group=True,
            mentions=[],
        )
        adapter._handle_message(buffer_event)
        append_key = store.append.call_args[0][0]

        # Then @Bot to trigger drain
        from personal_assistant.channels.feishu_client import FeishuMention

        mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
        deliver_event = FeishuMessageEvent(
            text="@_user_1 summarize",
            sender_open_id="ou_user2",
            chat_id="oc_grp1",
            chat_type="group",
            message_id="msg_003",
            is_group=True,
            mentions=[mention],
        )
        adapter._handle_message(deliver_event)
        drain_key = store.drain.call_args[0][0]

        assert append_key == drain_key, (
            f"append/drain key mismatch: append={append_key!r} vs drain={drain_key!r}"
        )
