"""Provider-owned Feishu credential, bot, and long-connection preflight."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import httpx

from personal_assistant.channels.base import ChannelStartupError


_INVALID_CREDENTIAL_CODES = {10005, 10012, 10013, 10015, 99991543}
_APP_DISABLED_CODES = {10014}
_BOT_DISABLED_CODES = {230006, 232025}


@dataclass(frozen=True, slots=True)
class FeishuPreflightResult:
    """Return non-sensitive provider identity after all startup gates pass."""

    bot_open_id: str


def probe_feishu_runtime(
    *,
    app_id: str,
    app_secret: str,
    domain: str,
    transport: httpx.BaseTransport | None = None,
) -> FeishuPreflightResult:
    """Verify credentials, bot capability, and WS endpoint before child startup.

    Args:
        app_id: Feishu application identifier.
        app_secret: Feishu application secret; never included in errors.
        domain: Feishu Open Platform API origin.
        transport: Optional HTTPX transport used by deterministic tests.

    Returns:
        Validated bot identity used by the runtime generation.

    Raises:
        ChannelStartupError: With a stable, actionable provider failure category.
    """
    base_url = domain.rstrip("/")
    try:
        with httpx.Client(transport=transport, timeout=10.0) as client:
            auth = client.post(
                f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            auth_payload = _payload(auth)
            auth_code = _code(auth_payload, auth.status_code)
            if auth_code != 0:
                _raise_auth_error(auth_code, str(auth_payload.get("msg") or ""))
            tenant_token = str(auth_payload.get("tenant_access_token") or "")
            if not tenant_token:
                raise ChannelStartupError(
                    "feishu_invalid_credentials",
                    "Feishu rejected the App ID or App Secret.",
                )

            bot = client.get(
                f"{base_url}/open-apis/bot/v3/info",
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            bot_payload = _payload(bot)
            bot_code = _code(bot_payload, bot.status_code)
            if bot_code in _BOT_DISABLED_CODES:
                raise ChannelStartupError(
                    "feishu_bot_disabled",
                    "Enable the Bot capability and publish the Feishu app.",
                )
            if bot_code != 0:
                raise ChannelStartupError(
                    "feishu_bot_unavailable",
                    "Feishu could not verify the Bot capability; check app availability.",
                )
            raw_bot = bot_payload.get("bot")
            if isinstance(raw_bot, Mapping):
                identity = raw_bot
            else:
                bot_data = bot_payload.get("data")
                bot_mapping = bot_data if isinstance(bot_data, Mapping) else {}
                nested_bot = bot_mapping.get("bot")
                identity = (
                    nested_bot if isinstance(nested_bot, Mapping) else bot_mapping
                )
            bot_open_id = str(identity.get("open_id") or "")
            if not bot_open_id:
                raise ChannelStartupError(
                    "feishu_bot_disabled",
                    "Enable the Bot capability and publish the Feishu app.",
                )

            endpoint = client.post(
                f"{base_url}/callback/ws/endpoint",
                headers={"locale": "zh"},
                json={"AppID": app_id, "AppSecret": app_secret},
            )
            endpoint_payload = _payload(endpoint)
            endpoint_code = _code(endpoint_payload, endpoint.status_code)
            endpoint_data = endpoint_payload.get("data")
            endpoint_mapping = (
                endpoint_data if isinstance(endpoint_data, Mapping) else {}
            )
            if endpoint_code != 0 or not str(endpoint_mapping.get("URL") or ""):
                raise ChannelStartupError(
                    "feishu_long_connection_unavailable",
                    "Configure and publish Feishu long-connection event callbacks.",
                )
            return FeishuPreflightResult(bot_open_id=bot_open_id)
    except ChannelStartupError:
        raise
    except httpx.HTTPError as exc:
        raise ChannelStartupError(
            "feishu_preflight_unavailable",
            "Feishu preflight is temporarily unavailable; retry the connection.",
        ) from exc


def _payload(response: httpx.Response) -> Mapping[str, object]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ChannelStartupError(
            "feishu_preflight_unavailable",
            "Feishu preflight returned an unreadable response; retry the connection.",
        ) from exc
    if not isinstance(payload, Mapping):
        raise ChannelStartupError(
            "feishu_preflight_unavailable",
            "Feishu preflight returned an unreadable response; retry the connection.",
        )
    return payload


def _code(payload: Mapping[str, object], http_status: int) -> int:
    raw = payload.get("code")
    if isinstance(raw, int):
        return raw
    return 0 if 200 <= http_status < 300 else http_status


def _raise_auth_error(code: int, message: str) -> None:
    normalized_message = message.casefold()
    if "secret" in normalized_message and (
        "invalid" in normalized_message or "wrong" in normalized_message
    ):
        raise ChannelStartupError(
            "feishu_invalid_credentials",
            "Feishu rejected the App ID or App Secret.",
        )
    if code in _APP_DISABLED_CODES:
        raise ChannelStartupError(
            "feishu_app_disabled",
            "Enable the Feishu app for this tenant and publish it.",
        )
    if code in _INVALID_CREDENTIAL_CODES or code in {401, 403}:
        raise ChannelStartupError(
            "feishu_invalid_credentials",
            "Feishu rejected the App ID or App Secret.",
        )
    raise ChannelStartupError(
        "feishu_preflight_unavailable",
        "Feishu could not authenticate the app; verify its availability and retry.",
    )
