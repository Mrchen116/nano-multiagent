"""Cryptographic envelope for secrets controlled by the IM service."""

from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from typing import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_ALGORITHM = "X25519-HKDF-SHA256-AES-256-GCM"
_HKDF_CONTEXT = b"nano-multiagent/channel-envelope-v1"


class ChannelEnvelopeError(ValueError):
    """Report a closed credential-envelope failure without secret material."""


@dataclass(frozen=True, slots=True)
class ChannelEnvelopeAad:
    """Bind one ciphertext to its complete tenant and desired-state scope."""

    owner_id: str
    node_id: str
    agent_id: str
    channel_id: str
    provider: str
    credential_revision: int


@dataclass(frozen=True, slots=True)
class ChannelKeyPair:
    """Raw base64 X25519 key material and its stable public identifier."""

    private_key: str
    public_key: str
    key_id: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _derive_key(shared_secret: bytes, *, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_HKDF_CONTEXT,
    ).derive(shared_secret)


def generate_channel_key_pair(*, private_seed: bytes | None = None) -> ChannelKeyPair:
    """Generate raw X25519 key material for a Gateway credential key file."""
    private_bytes = private_seed if private_seed is not None else os.urandom(32)
    if len(private_bytes) != 32:
        raise ValueError("X25519 private seed must be 32 bytes")
    private_key = X25519PrivateKey.from_private_bytes(private_bytes)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return ChannelKeyPair(
        private_key=b64encode(private_bytes).decode("ascii"),
        public_key=b64encode(public_bytes).decode("ascii"),
        key_id=f"sha256:{hashlib.sha256(public_bytes).hexdigest()}",
    )


def seal_channel_secret(
    *,
    public_key: str,
    secret: Mapping[str, str],
    aad: ChannelEnvelopeAad,
    ephemeral_private_seed: bytes | None = None,
    salt: bytes | None = None,
    nonce: bytes | None = None,
) -> dict[str, object]:
    """Seal a secret for one node using envelope version 1."""
    ephemeral_seed = ephemeral_private_seed or os.urandom(32)
    resolved_salt = salt or os.urandom(16)
    resolved_nonce = nonce or os.urandom(12)
    if len(ephemeral_seed) != 32 or len(resolved_salt) != 16 or len(resolved_nonce) != 12:
        raise ValueError("invalid channel envelope entropy length")
    recipient = X25519PublicKey.from_public_bytes(b64decode(public_key, validate=True))
    ephemeral = X25519PrivateKey.from_private_bytes(ephemeral_seed)
    shared = ephemeral.exchange(recipient)
    key = _derive_key(shared, salt=resolved_salt)
    ciphertext = AESGCM(key).encrypt(
        resolved_nonce, _canonical_json(dict(secret)), _canonical_json(asdict(aad))
    )
    ephemeral_public = ephemeral.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "version": 1,
        "algorithm": _ALGORITHM,
        "ephemeral_public_key": b64encode(ephemeral_public).decode("ascii"),
        "salt": b64encode(resolved_salt).decode("ascii"),
        "nonce": b64encode(resolved_nonce).decode("ascii"),
        "ciphertext": b64encode(ciphertext).decode("ascii"),
    }


def open_channel_secret(
    *, private_key: str, envelope: Mapping[str, object], aad: ChannelEnvelopeAad
) -> dict[str, str]:
    """Open a version-1 envelope, failing closed on any key or AAD mismatch."""
    try:
        if envelope.get("version") != 1 or envelope.get("algorithm") != _ALGORITHM:
            raise ValueError("unsupported envelope")
        private = X25519PrivateKey.from_private_bytes(
            b64decode(private_key, validate=True)
        )
        ephemeral = X25519PublicKey.from_public_bytes(
            b64decode(str(envelope["ephemeral_public_key"]), validate=True)
        )
        salt = b64decode(str(envelope["salt"]), validate=True)
        nonce = b64decode(str(envelope["nonce"]), validate=True)
        ciphertext = b64decode(str(envelope["ciphertext"]), validate=True)
        plaintext = AESGCM(_derive_key(private.exchange(ephemeral), salt=salt)).decrypt(
            nonce, ciphertext, _canonical_json(asdict(aad))
        )
        decoded = json.loads(plaintext)
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in decoded.items()
        ):
            raise ValueError("invalid secret payload")
        return decoded
    except (InvalidTag, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ChannelEnvelopeError("credential envelope invalid") from exc
