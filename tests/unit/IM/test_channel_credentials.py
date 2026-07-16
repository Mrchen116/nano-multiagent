"""Contract tests for the external-channel credential envelope."""

from __future__ import annotations

import pytest

from IM.infra.channel_credentials import (
    ChannelEnvelopeAad,
    ChannelEnvelopeError,
    generate_channel_key_pair,
    open_channel_secret,
    seal_channel_secret,
)


def _aad(**changes: object) -> ChannelEnvelopeAad:
    values: dict[str, object] = {
        "owner_id": "owner-a",
        "node_id": "node-a",
        "agent_id": "agent-a",
        "channel_id": "ch-a",
        "provider": "feishu",
        "credential_revision": 1,
    }
    values.update(changes)
    return ChannelEnvelopeAad(**values)


def test_envelope_v1_matches_fixed_vector_and_roundtrips() -> None:
    """The wire format remains deterministic for fixed key and nonce material."""
    recipient = generate_channel_key_pair(private_seed=bytes(range(32)))
    envelope = seal_channel_secret(
        public_key=recipient.public_key,
        secret={"app_secret": "secret-value"},
        aad=_aad(),
        ephemeral_private_seed=bytes(range(32, 64)),
        salt=bytes(range(16)),
        nonce=bytes(range(12)),
    )

    assert envelope == {
        "version": 1,
        "algorithm": "X25519-HKDF-SHA256-AES-256-GCM",
        "ephemeral_public_key": "NYBy1jZYgNGu6jKa35EhODhR7SGijjt16WXQ0s0WYlQ=",
        "salt": "AAECAwQFBgcICQoLDA0ODw==",
        "nonce": "AAECAwQFBgcICQoL",
        "ciphertext": "j5kc+uoEe9BsAcCy+L0N+YdmxizygjSvGxpQEzdFwXoGd9VMQ8YXHOZoK5kV",
    }
    assert open_channel_secret(
        private_key=recipient.private_key, envelope=envelope, aad=_aad()
    ) == {"app_secret": "secret-value"}


@pytest.mark.parametrize(
    "tampered_aad",
    [
        _aad(owner_id="owner-b"),
        _aad(node_id="node-b"),
        _aad(agent_id="agent-b"),
        _aad(channel_id="ch-b"),
        _aad(provider="other"),
        _aad(credential_revision=2),
    ],
)
def test_envelope_rejects_every_aad_scope_change(
    tampered_aad: ChannelEnvelopeAad,
) -> None:
    """Ciphertext cannot be transplanted across an owner, node, channel, or revision."""
    pair = generate_channel_key_pair(private_seed=b"a" * 32)
    envelope = seal_channel_secret(
        public_key=pair.public_key,
        secret={"app_secret": "never-log-this"},
        aad=_aad(),
    )

    with pytest.raises(
        ChannelEnvelopeError, match="credential envelope invalid"
    ) as error:
        open_channel_secret(
            private_key=pair.private_key, envelope=envelope, aad=tampered_aad
        )
    assert "never-log-this" not in str(error.value)


def test_envelope_rejects_key_mismatch_without_disclosing_secret() -> None:
    """A different node private key fails closed with a secret-free error."""
    source = generate_channel_key_pair(private_seed=b"b" * 32)
    wrong = generate_channel_key_pair(private_seed=b"c" * 32)
    envelope = seal_channel_secret(
        public_key=source.public_key,
        secret={"app_secret": "classified"},
        aad=_aad(),
    )

    with pytest.raises(ChannelEnvelopeError) as error:
        open_channel_secret(
            private_key=wrong.private_key, envelope=envelope, aad=_aad()
        )
    assert "classified" not in str(error.value)
