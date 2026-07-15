"""Tests for strict Feishu tenant-authorization inspection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import FeishuClient


def _mock_scope_response(*, success: bool, scopes: object = ()) -> MagicMock:
    response = MagicMock()
    response.success.return_value = success
    response.code = 0 if success else 503
    response.msg = "" if success else "temporarily unavailable"
    response.data = {"scopes": scopes}
    return response


def _client_with_response(response: object) -> FeishuClient:
    rest_client = MagicMock()
    rest_client.application.v6.scope.list.return_value = response
    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = rest_client
    return client


def test_tenant_scope_probe_only_grants_authorized_application_identity() -> None:
    client = _client_with_response(
        _mock_scope_response(
            success=True,
            scopes=[
                {
                    "scope_name": "im:message.group_msg",
                    "grant_status": 1,
                    "scope_type": "tenant",
                },
                {
                    "scope_name": "im:message:send_as_bot",
                    "grant_status": 2,
                    "scope_type": "tenant",
                },
                {
                    "scope_name": "im:chat:readonly",
                    "grant_status": 1,
                    "scope_type": "user",
                },
            ],
        )
    )

    probe = client.probe_tenant_scope_grants()

    assert probe.complete is True
    assert probe.granted_scopes == frozenset({"im:message.group_msg"})


@pytest.mark.parametrize(
    "malformed_scope",
    [
        {"scope_name": "im:message.group_msg", "scope_type": "tenant"},
        {"scope_name": "im:message.group_msg", "grant_status": 1},
        {
            "scope_name": "im:message.group_msg",
            "grant_status": 9,
            "scope_type": "tenant",
        },
        {
            "scope_name": "im:message.group_msg",
            "grant_status": 1,
            "scope_type": "robot",
        },
    ],
)
def test_tenant_scope_probe_is_unknown_for_missing_or_unknown_enums(
    malformed_scope: dict[str, object],
) -> None:
    client = _client_with_response(
        _mock_scope_response(success=True, scopes=[malformed_scope])
    )

    probe = client.probe_tenant_scope_grants()

    assert probe.complete is False
    assert probe.granted_scopes is None


@pytest.mark.parametrize(
    "response",
    [
        _mock_scope_response(success=False),
        _mock_scope_response(success=True, scopes={"not": "a list"}),
    ],
)
def test_tenant_scope_probe_is_unknown_for_api_or_payload_failure(
    response: object,
) -> None:
    probe = _client_with_response(response).probe_tenant_scope_grants()

    assert probe.complete is False
    assert probe.granted_scopes is None
