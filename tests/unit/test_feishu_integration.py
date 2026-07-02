"""Integration tests for feishu channel registration in main._build_channel_registry."""

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.config.local_store import (
    ChannelConfig,
)
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.main import _build_channel_registry


def _feishu_settings(**overrides) -> dict[str, str]:
    settings = {
        "appId": "cli_a",
        "appSecret": "s_a",
        "ownerOpenId": "ou_owner",
    }
    settings.update(overrides)
    return settings


class TestBuildChannelRegistryFeishu:
    """Verify _build_channel_registry creates FeishuAdapter for feishu channels."""

    @patch("personal_assistant.main.FeishuAdapter")
    def test_feishu_channel_creates_adapter(self, mock_fa_cls: MagicMock) -> None:
        from personal_assistant.gateway.group_context_store import GroupContextStore

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "group_context.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)
            channels = (
                ChannelConfig(
                    name="feishu:plato",
                    enabled=True,
                    settings=_feishu_settings(),
                ),
            )
            registry = _build_channel_registry(channels, group_context_store=group_ctx)
            mock_fa_cls.assert_called_once()
            call_kwargs = mock_fa_cls.call_args[1]
            assert call_kwargs["app_id"] == "cli_a"
            assert call_kwargs["app_secret"] == "s_a"
            assert call_kwargs["name"] == "feishu:plato"

    @patch("personal_assistant.main.FeishuAdapter")
    def test_multiple_feishu_accounts_registered(self, mock_fa_cls: MagicMock) -> None:
        from personal_assistant.gateway.group_context_store import GroupContextStore

        # Return distinct mock instances with unique names
        mock_plato = MagicMock()
        mock_plato.name = "feishu:plato"
        mock_luban = MagicMock()
        mock_luban.name = "feishu:luban"
        mock_fa_cls.side_effect = [mock_plato, mock_luban]

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "group_context.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)
            channels = (
                ChannelConfig(
                    name="feishu:plato",
                    enabled=True,
                    settings=_feishu_settings(),
                ),
                ChannelConfig(
                    name="feishu:luban",
                    enabled=True,
                    settings=_feishu_settings(appId="cli_b", appSecret="s_b"),
                ),
            )
            registry = _build_channel_registry(channels, group_context_store=group_ctx)
            assert mock_fa_cls.call_count == 2
            names = [c[1]["name"] for c in mock_fa_cls.call_args_list]
            assert "feishu:plato" in names
            assert "feishu:luban" in names

    @patch("personal_assistant.main.FeishuAdapter")
    def test_feishu_disabled_not_registered(self, mock_fa_cls: MagicMock) -> None:
        channels = (
            ChannelConfig(
                name="feishu:plato",
                enabled=False,
                settings=_feishu_settings(),
            ),
        )
        # Disabled feishu channels don't need group_context_store
        registry = _build_channel_registry(channels)
        mock_fa_cls.assert_not_called()

    @patch("personal_assistant.main.FeishuAdapter")
    @patch("personal_assistant.main.WebRelayAdapter")
    def test_feishu_coexists_with_web_relay(
        self, mock_wra_cls: MagicMock, mock_fa_cls: MagicMock
    ) -> None:
        from personal_assistant.gateway.group_context_store import GroupContextStore

        mock_adapter = MagicMock()
        mock_adapter.name = "feishu:plato"
        mock_fa_cls.return_value = mock_adapter

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "group_context.sqlite3"
            group_ctx = GroupContextStore(db_path=db_path)
            channels = (
                ChannelConfig(name="web_relay", enabled=True, settings={}),
                ChannelConfig(
                    name="feishu:plato",
                    enabled=True,
                    settings=_feishu_settings(),
                ),
            )
            registry = _build_channel_registry(channels, group_context_store=group_ctx)
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
                name="feishu:plato",
                bot_open_id="ou_123",
                owner_open_id="ou_owner",
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
                    name="feishu:plato",
                    enabled=True,
                    settings=_feishu_settings(),
                ),
            )
            # This must not raise TypeError for missing group_context_store
            registry = _build_channel_registry(channels, group_context_store=group_ctx)
            # Verify the adapter was actually registered
            assert len(registry.list()) == 1
            adapter = registry.list()[0]
            assert isinstance(adapter, FeishuAdapter)
            assert adapter.name == "feishu:plato"

    def test_build_channel_registry_without_group_context_store_raises(self) -> None:
        """_build_channel_registry with feishu channel but no group_context_store
        must raise ValueError immediately rather than creating a broken adapter."""
        channels = (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "s_a",
                },
            ),
        )
        with pytest.raises(ValueError, match="group_context_store"):
            _build_channel_registry(channels)

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
                    name="feishu:plato",
                    enabled=True,
                    settings=_feishu_settings(),
                ),
            )
            # This is the bootstrap path: create GroupContextStore then pass it
            registry = _build_channel_registry(channels, group_context_store=group_ctx)
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
                    name="feishu:plato",
                    enabled=True,
                    settings=_feishu_settings(botOpenId="ou_bot_123"),
                ),
            )
            registry = _build_channel_registry(channels, group_context_store=group_ctx)
            adapter = registry.list()[0]
            assert isinstance(adapter, FeishuAdapter)
            assert adapter.name == "feishu:plato"
            # Verify bot_open_id was passed (internal attribute check)
            assert adapter._bot_open_id == "ou_bot_123"
            assert adapter._owner_open_id == "ou_owner"

    @patch("personal_assistant.main.FeishuAdapter")
    def test_build_channel_registry_allows_missing_owner_open_id(
        self, mock_fa_cls: MagicMock
    ) -> None:
        """Runbook configs can start without ownerOpenId; only "你" display is disabled."""
        channels = (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "botOpenId": "ou_bot_123",
                },
            ),
        )
        with TemporaryDirectory() as tmpdir:
            group_ctx = GroupContextStore(db_path=Path(tmpdir) / "group.sqlite3")
            _build_channel_registry(channels, group_context_store=group_ctx)

        mock_fa_cls.assert_called_once()
        assert mock_fa_cls.call_args.kwargs["owner_open_id"] is None

    @patch("personal_assistant.main.FeishuAdapter")
    def test_build_channel_registry_warns_without_group_message_delivery_flag(
        self, mock_fa_cls: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing ordinary group-message delivery declaration must be diagnosable."""
        channels = (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings=_feishu_settings(botOpenId="ou_bot_123"),
            ),
        )

        with TemporaryDirectory() as tmpdir, caplog.at_level(
            logging.WARNING, logger="personal_assistant.main"
        ):
            group_ctx = GroupContextStore(db_path=Path(tmpdir) / "group.sqlite3")
            _build_channel_registry(channels, group_context_store=group_ctx)

        assert "receiveAllGroupMessages" in caplog.text
        assert "ordinary group messages" in caplog.text
        assert "feat-447-M12" in caplog.text

    @patch("personal_assistant.main.FeishuAdapter")
    def test_build_channel_registry_does_not_warn_when_group_message_delivery_declared(
        self, mock_fa_cls: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        channels = (
            ChannelConfig(
                name="feishu:plato",
                enabled=True,
                settings=_feishu_settings(
                    botOpenId="ou_bot_123",
                    receiveAllGroupMessages=True,
                ),
            ),
        )

        with TemporaryDirectory() as tmpdir, caplog.at_level(
            logging.WARNING, logger="personal_assistant.main"
        ):
            group_ctx = GroupContextStore(db_path=Path(tmpdir) / "group.sqlite3")
            _build_channel_registry(channels, group_context_store=group_ctx)

        assert "receiveAllGroupMessages" not in caplog.text


class TestFeishuBufferKeyConsistency:
    """Group buffer key alignment between FeishuAdapter and InboundPipeline."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_sync_only_inbound_metadata_matches_pipeline_external_buffer_key(
        self, mock_fc_cls: MagicMock
    ) -> None:
        """FeishuAdapter emits external identity metadata consumed by Pipeline buffer keys."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline

        store = MagicMock(spec=GroupContextStore)
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )
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

        store.append.assert_not_called()
        inbound = on_inbound.call_args[0][0]
        assert inbound.metadata["sync_only"] is True
        assert InboundPipeline._group_buf_key_for_agent(inbound, "plato") == (
            "feishu:feishu:cli_a:group:oc_grp1:plato"
        )

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_mention_does_not_drain_adapter_buffer(
        self, mock_fc_cls: MagicMock
    ) -> None:
        """Group buffer drain is owned by InboundPipeline, not FeishuAdapter."""
        from personal_assistant.channels.feishu_adapter import FeishuAdapter

        store = MagicMock(spec=GroupContextStore)
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )

        on_inbound = MagicMock()
        adapter.start(on_inbound)

        from personal_assistant.channels.feishu_client import (
            FeishuMention,
            FeishuMessageEvent,
        )

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

        store.append.assert_not_called()
        store.drain.assert_not_called()
        inbound = on_inbound.call_args[0][0]
        assert inbound.metadata["mentioned_agent_ids"] == ["plato"]
        assert "sync_only" not in inbound.metadata
