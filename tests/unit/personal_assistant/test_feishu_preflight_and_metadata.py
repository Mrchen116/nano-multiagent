"""Feishu preflight, metadata durability, and activation retry regressions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from personal_assistant.channels.base import ChannelStartupError
from personal_assistant.channels.feishu.preflight import probe_feishu_runtime
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    FeishuActivationPolicy,
    ManagedChannelSpec,
    ProviderRuntimeBuild,
)
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
from personal_assistant.gateway.channel_registry import ChannelRegistry


class _Adapter:
    name = "feishu:agent-a"

    def start(self, _handler) -> None:
        pass

    def stop(self) -> None:
        pass


def _response(payload: dict[str, object], status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(payload).encode())


def _transport(*payloads: httpx.Response) -> httpx.MockTransport:
    responses = iter(payloads)

    def handle(_request: httpx.Request) -> httpx.Response:
        response = next(responses)
        response.request = _request
        return response

    return httpx.MockTransport(handle)


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"code": 10015, "msg": "wrong app secret"}, "feishu_invalid_credentials"),
        ({"code": 10014, "msg": "app disabled"}, "feishu_app_disabled"),
    ],
)
def test_preflight_preserves_official_credential_failure_categories(
    payload: dict[str, object], expected_code: str
) -> None:
    """Credential/app failures are actionable and never degrade to generic startup."""
    with pytest.raises(ChannelStartupError) as caught:
        probe_feishu_runtime(
            app_id="cli_invalid",
            app_secret="secret-invalid",
            domain="https://open.feishu.test",
            transport=_transport(_response(payload)),
        )

    assert caught.value.status_code == expected_code
    assert "secret-invalid" not in str(caught.value)


def test_preflight_distinguishes_bot_disabled_from_long_connection_unavailable() -> None:
    """Bot capability and WS endpoint setup have independent remediation codes."""
    auth = _response({"code": 0, "tenant_access_token": "tenant-token"})
    with pytest.raises(ChannelStartupError) as bot_error:
        probe_feishu_runtime(
            app_id="cli_bot",
            app_secret="secret-bot",
            domain="https://open.feishu.test",
            transport=_transport(
                auth,
                _response({"code": 230006, "msg": "Bot ability is not activated"}),
            ),
        )
    assert bot_error.value.status_code == "feishu_bot_disabled"

    with pytest.raises(ChannelStartupError) as ws_error:
        probe_feishu_runtime(
            app_id="cli_ws",
            app_secret="secret-ws",
            domain="https://open.feishu.test",
            transport=_transport(
                _response({"code": 0, "tenant_access_token": "tenant-token"}),
                _response(
                    {
                        "code": 0,
                        "data": {"bot": {"open_id": "ou-bot"}},
                    }
                ),
                _response({"code": 1000040343, "msg": "app not online"}),
            ),
        )
    assert ws_error.value.status_code == "feishu_long_connection_unavailable"


def _spec(*, revision: int = 1) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_a"},
        credentials={"app_secret": "secret-a"},
        provider_runtime={},
        generation=ChannelGeneration(
            provider_identity_fingerprint="fp-a",
            provider_identity_revision=1,
            channel_revision=revision,
            credential_revision=revision,
        ),
        credential_envelope={"ciphertext": "opaque"},
        credential_key_id="key-a",
    )


def test_preflight_metadata_is_cached_and_replayed_for_current_generation(
    tmp_path: Path,
) -> None:
    """Factory metadata survives offline delivery and replays idempotently on reconnect."""
    reports = []
    store = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json", node_id="node-a", key_id="key-a"
    )
    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda _spec, _binder, _status: ProviderRuntimeBuild(
                adapter=_Adapter(),
                initial_metadata={"bot_open_id": "ou-bot"},
            )
        },
        status_sink=lambda _status: None,
        metadata_sink=reports.append,
        manifest_store=store,
    )

    result = asyncio.run(
        manager.reconcile(
            ChannelManifest(
                owner_id="owner-a",
                node_id="node-a",
                manifest_revision=1,
                channels=(_spec(),),
            )
        )
    )
    assert result.outcome == "applied"
    cached = store.load_manifest()
    assert cached is not None
    assert cached.channels[0].provider_runtime == {"bot_open_id": "ou-bot"}
    assert reports[-1].patch == {"bot_open_id": "ou-bot"}

    reports.clear()
    manager.replay_provider_metadata()
    assert reports[0].generation == _spec().generation
    assert reports[0].patch == {"bot_open_id": "ou-bot"}


def test_activation_failure_is_not_memoized_and_retries_without_blocking_runtime() -> None:
    """A transient config-sync failure can succeed after the IM connection recovers."""
    attempts = 0

    def activate(_agent_id: str) -> bool:
        nonlocal attempts
        attempts += 1
        return attempts > 1

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda _spec, _binder, _status: _Adapter()
        },
        status_sink=lambda _status: None,
        activation_policy=FeishuActivationPolicy(activate),
    )
    applied = asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
    )

    assert applied.outcome == "applied"
    assert manager.registry.get("feishu:agent-a") is not None
    assert attempts == 1
    manager.retry_pending_activations()
    manager.retry_pending_activations()
    assert attempts == 2


def test_provider_startup_error_reaches_status_without_secret() -> None:
    """The lifecycle owner keeps the provider code instead of genericizing it."""
    statuses = []

    def fail(_spec, _binder, _status):
        raise ChannelStartupError(
            "feishu_invalid_credentials",
            "Feishu rejected the App ID or App Secret.",
        )

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": fail},
        status_sink=statuses.append,
    )
    result = asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
    )

    assert result.failed_channel_ids == ("ch-a",)
    assert statuses[-1].status_code == "feishu_invalid_credentials"
    assert statuses[-1].status_message == "Feishu rejected the App ID or App Secret."
    assert "secret-a" not in statuses[-1].status_message
