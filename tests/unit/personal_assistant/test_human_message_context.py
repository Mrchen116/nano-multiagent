"""PA-only message occurrence/channel envelope behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.human_message_context import (
    FrozenHumanMessageContext,
    PaHumanMessageContext,
    PaTimeContext,
    apply_frozen_header,
    attach_frozen_context,
    resolve_pa_time_context,
)


def _message(
    *,
    channel_name: str,
    source: datetime | None,
    received: datetime,
) -> InboundMessage:
    return InboundMessage(
        channel_name=channel_name,
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        source_timestamp=source,
        received_timestamp=received,
    )


def test_freeze_prefers_source_time_and_maps_actual_ingress() -> None:
    time_context = PaTimeContext(
        zone=ZoneInfo("Asia/Shanghai"), prompt_label="Asia/Shanghai"
    )
    freezer = PaHumanMessageContext(time_context)
    source = datetime(2026, 8, 10, 1, 17, tzinfo=timezone.utc)
    received = source + timedelta(minutes=20)

    web = freezer.freeze(
        _message(channel_name="web_relay", source=source, received=received)
    )
    feishu = freezer.freeze(
        _message(channel_name="feishu:agent-a", source=source, received=received)
    )

    assert web == FrozenHumanMessageContext(
        version=1,
        header="[Web IM Mon 2026-08-10 09:17 CST]",
        time_zone="Asia/Shanghai",
    )
    assert feishu is not None
    assert feishu.header == "[Feishu Mon 2026-08-10 09:17 CST]"


def test_freeze_uses_fixed_receipt_when_source_is_missing() -> None:
    freezer = PaHumanMessageContext(
        PaTimeContext(zone=ZoneInfo("Asia/Shanghai"), prompt_label="Asia/Shanghai")
    )
    received = datetime(2026, 8, 10, 12, 46, tzinfo=timezone.utc)

    frozen = freezer.freeze(
        _message(channel_name="web_relay", source=None, received=received)
    )

    assert frozen is not None
    assert frozen.header == "[Web IM Mon 2026-08-10 20:46 CST]"


def test_unknown_non_human_channel_is_not_decorated() -> None:
    freezer = PaHumanMessageContext(
        PaTimeContext(zone=timezone.utc, prompt_label="UTC+00:00")
    )
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)

    assert (
        freezer.freeze(_message(channel_name="internal", source=now, received=now))
        is None
    )


def test_apply_header_copies_parts_and_preserves_multimodal_order() -> None:
    frozen = FrozenHumanMessageContext(
        version=1,
        header="[Web IM Mon 2026-08-10 09:17 CST]",
        time_zone="Asia/Shanghai",
    )
    original = [
        {"type": "text", "text": "[Alice] hello"},
        {"type": "image", "image_url": "data:image/png;base64,AA=="},
    ]

    projected = apply_frozen_header(original, frozen)

    assert projected == [
        {
            "type": "text",
            "text": "[Web IM Mon 2026-08-10 09:17 CST] [Alice] hello",
        },
        {"type": "image", "image_url": "data:image/png;base64,AA=="},
    ]
    assert original[0]["text"] == "[Alice] hello"


def test_apply_header_inserts_text_before_image_only_input() -> None:
    frozen = FrozenHumanMessageContext(
        version=1,
        header="[Feishu Mon 2026-08-10 09:18 CST]",
        time_zone="Asia/Shanghai",
    )

    assert apply_frozen_header([{"type": "image", "image_url": "data:x"}], frozen) == [
        {"type": "text", "text": frozen.header},
        {"type": "image", "image_url": "data:x"},
    ]


def test_attaching_generated_provenance_does_not_change_visible_body() -> None:
    received = datetime(2026, 8, 10, 1, 17, tzinfo=timezone.utc)
    message = _message(channel_name="web_relay", source=received, received=received)
    freezer = PaHumanMessageContext(
        PaTimeContext(zone=ZoneInfo("Asia/Shanghai"), prompt_label="Asia/Shanghai")
    )

    enriched = attach_frozen_context(message, freezer.freeze(message))

    assert enriched.text == "hello"
    assert message.metadata == {}
    assert enriched.metadata["_pa_human_message_context"]


def test_resolve_timezone_uses_iana_then_fixed_offset(tmp_path: Path) -> None:
    iana = resolve_pa_time_context(
        tz_env="Asia/Shanghai", localtime_path=tmp_path / "missing"
    )
    fixed = resolve_pa_time_context(
        tz_env="not/a-zone",
        localtime_path=tmp_path / "missing",
        local_now=datetime(
            2026,
            8,
            10,
            9,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        ),
    )

    assert iana.prompt_label == "Asia/Shanghai"
    assert fixed.prompt_label == "UTC+05:30"
