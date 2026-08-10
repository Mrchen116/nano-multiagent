"""Freeze PA human-message time and ingress facts into model-only context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personal_assistant.channels.base import InboundMessage

_METADATA_KEY = "_pa_human_message_context"


@dataclass(frozen=True, slots=True)
class PaTimeContext:
    """Hold the immutable local timezone used by one Gateway process.

    Args:
        zone: Timezone used to render message occurrence instants.
        prompt_label: Stable timezone label exposed in the PA system prompt.
    """

    zone: tzinfo
    prompt_label: str


@dataclass(frozen=True, slots=True)
class FrozenHumanMessageContext:
    """Carry the versioned header frozen for one admitted human message.

    Args:
        version: Persisted envelope format version.
        header: Complete generated model-only header.
        time_zone: Startup timezone label used to render the header.
    """

    version: int
    header: str
    time_zone: str

    def as_metadata(self) -> dict[str, object]:
        """Return the JSON-safe representation persisted with buffered input."""

        return {
            "version": self.version,
            "header": self.header,
            "time_zone": self.time_zone,
        }

    @classmethod
    def from_metadata(
        cls, metadata: Mapping[str, Any]
    ) -> FrozenHumanMessageContext | None:
        """Read a trusted frozen object without interpreting user text.

        Args:
            metadata: Inbound metadata that may contain a frozen v1 object.

        Returns:
            A valid frozen context, or ``None`` when the marker is absent or invalid.
        """

        raw = metadata.get(_METADATA_KEY)
        if not isinstance(raw, Mapping):
            return None
        version = raw.get("version")
        header = raw.get("header")
        time_zone = raw.get("time_zone")
        if version != 1 or not isinstance(header, str) or not header:
            return None
        if not isinstance(time_zone, str) or not time_zone:
            return None
        return cls(version=1, header=header, time_zone=time_zone)


class PaHumanMessageContext:
    """Freeze source-or-receipt time and actual ingress for PA human messages."""

    def __init__(self, time_context: PaTimeContext) -> None:
        """Create a freezer bound to one Gateway-startup timezone snapshot.

        Args:
            time_context: Immutable timezone and prompt label for this process.
        """
        self._time_context = time_context

    def freeze(self, message: InboundMessage) -> FrozenHumanMessageContext | None:
        """Return one immutable v1 header for supported PA human ingress.

        Args:
            message: Raw inbound message with normalized source and receipt times.

        Returns:
            Frozen v1 context for Web IM or Feishu, otherwise ``None``.
        """

        channel = _channel_label(message.channel_name)
        if channel is None:
            return None
        occurrence = _aware_timestamp(message.source_timestamp)
        if occurrence is None:
            occurrence = _aware_timestamp(message.received_timestamp)
        if occurrence is None:
            return None
        local = occurrence.astimezone(self._time_context.zone)
        zone_label = local.tzname() or self._time_context.prompt_label
        day = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[local.weekday()]
        rendered = f"{day} {local:%Y-%m-%d %H:%M}"
        return FrozenHumanMessageContext(
            version=1,
            header=f"[{channel} {rendered} {zone_label}]",
            time_zone=self._time_context.prompt_label,
        )


def attach_frozen_context(
    message: InboundMessage,
    frozen: FrozenHumanMessageContext | None,
) -> InboundMessage:
    """Copy a message with its generated model-context provenance attached.

    Args:
        message: Raw inbound message to preserve.
        frozen: Generated context to attach, or ``None`` for no change.

    Returns:
        The original message when no context exists, otherwise a metadata-enriched copy.
    """

    if frozen is None:
        return message
    return replace(
        message,
        metadata={
            **message.metadata,
            _METADATA_KEY: frozen.as_metadata(),
        },
    )


def apply_frozen_header(
    parts: Sequence[Mapping[str, Any]],
    frozen: FrozenHumanMessageContext | None,
) -> list[dict[str, Any]]:
    """Copy model parts and prepend the generated header to their first text.

    Args:
        parts: Ordered raw model input parts.
        frozen: Generated context to apply, or ``None`` for a plain copy.

    Returns:
        Copied parts with the header on the first text or before image-only input.
    """

    projected = [dict(part) for part in parts]
    if frozen is None:
        return projected
    for part in projected:
        if part.get("type") != "text":
            continue
        text = part.get("text")
        if isinstance(text, str):
            part["text"] = f"{frozen.header} {text}" if text else frozen.header
            return projected
    projected.insert(0, {"type": "text", "text": frozen.header})
    return projected


def resolve_pa_time_context(
    *,
    tz_env: str | None,
    localtime_path: Path = Path("/etc/localtime"),
    local_now: datetime | None = None,
) -> PaTimeContext:
    """Resolve the one timezone snapshot used for a Gateway process.

    Args:
        tz_env: Current ``TZ`` environment value, when present.
        localtime_path: Standard localtime symlink used to recover an IANA name.
        local_now: Optional local aware instant used by deterministic tests.

    Returns:
        An IANA-backed context when possible, otherwise a fixed UTC offset.
    """

    for candidate in (tz_env, _iana_name_from_localtime(localtime_path)):
        if not candidate:
            continue
        try:
            return PaTimeContext(zone=ZoneInfo(candidate), prompt_label=candidate)
        except ZoneInfoNotFoundError:
            continue
    current = local_now or datetime.now().astimezone()
    offset = current.utcoffset() or timedelta(0)
    label = _fixed_offset_label(offset)
    return PaTimeContext(zone=timezone(offset, name=label), prompt_label=label)


def _channel_label(channel_name: str) -> str | None:
    if channel_name == "web_relay":
        return "Web IM"
    if channel_name == "feishu" or channel_name.startswith("feishu:"):
        return "Feishu"
    return None


def _aware_timestamp(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value


def _iana_name_from_localtime(path: Path) -> str | None:
    try:
        resolved = str(path.resolve(strict=True))
    except OSError:
        return None
    marker = "/zoneinfo/"
    if marker not in resolved:
        return None
    candidate = resolved.split(marker, 1)[1]
    return candidate or None


def _fixed_offset_label(offset: timedelta) -> str:
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    absolute = abs(total_minutes)
    hours, minutes = divmod(absolute, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


__all__ = [
    "FrozenHumanMessageContext",
    "PaHumanMessageContext",
    "PaTimeContext",
    "apply_frozen_header",
    "attach_frozen_context",
    "resolve_pa_time_context",
]
