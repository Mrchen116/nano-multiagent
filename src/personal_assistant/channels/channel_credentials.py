"""Gateway-owned private key and channel envelope opener."""

from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
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


@dataclass(frozen=True, slots=True)
class GatewayChannelAad:
    """Gateway copy of the immutable envelope tenant/revision scope."""

    owner_id: str
    node_id: str
    agent_id: str
    channel_id: str
    provider: str
    credential_revision: int

    def as_dict(self) -> dict[str, object]:
        """Return canonical field names shared with the IM envelope writer."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GatewayChannelKey:
    """Stable node key with public registration and private open operations."""

    private_key_pem: str
    public_key: str
    key_id: str
    algorithm: str = _ALGORITHM

    def registration_payload(self) -> dict[str, str]:
        """Project only the public key material allowed in node.register."""
        return {
            "credential_key_id": self.key_id,
            "credential_algorithm": self.algorithm,
            "credential_public_key": self.public_key,
        }

    def seal(
        self, *, secret: Mapping[str, str], aad: GatewayChannelAad
    ) -> dict[str, object]:
        """Seal bootstrap credentials to this node's own public key."""
        recipient = X25519PublicKey.from_public_bytes(
            b64decode(self.public_key, validate=True)
        )
        ephemeral = X25519PrivateKey.generate()
        salt = os.urandom(32)
        nonce = os.urandom(12)
        shared = ephemeral.exchange(recipient)
        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=_HKDF_CONTEXT,
        ).derive(shared)
        ciphertext = AESGCM(key).encrypt(
            nonce,
            _canonical_json(dict(secret)),
            _canonical_json(aad.as_dict()),
        )
        ephemeral_public = ephemeral.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "version": 1,
            "algorithm": _ALGORITHM,
            "ephemeral_public_key": b64encode(ephemeral_public).decode("ascii"),
            "salt": b64encode(salt).decode("ascii"),
            "nonce": b64encode(nonce).decode("ascii"),
            "ciphertext": b64encode(ciphertext).decode("ascii"),
        }

    def open(
        self, *, envelope: Mapping[str, object], aad: GatewayChannelAad
    ) -> dict[str, str]:
        """Decrypt a current-node envelope, failing closed on any scope mismatch."""
        try:
            if envelope.get("version") != 1 or envelope.get("algorithm") != _ALGORITHM:
                raise ValueError("unsupported envelope")
            private = serialization.load_pem_private_key(
                self.private_key_pem.encode(), password=None
            )
            if not isinstance(private, X25519PrivateKey):
                raise ValueError("wrong private key type")
            ephemeral = X25519PublicKey.from_public_bytes(
                b64decode(str(envelope["ephemeral_public_key"]), validate=True)
            )
            salt = b64decode(str(envelope["salt"]), validate=True)
            nonce = b64decode(str(envelope["nonce"]), validate=True)
            ciphertext = b64decode(str(envelope["ciphertext"]), validate=True)
            shared = private.exchange(ephemeral)
            key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=_HKDF_CONTEXT,
            ).derive(shared)
            plaintext = AESGCM(key).decrypt(
                nonce, ciphertext, _canonical_json(aad.as_dict())
            )
            decoded = json.loads(plaintext)
            if not isinstance(decoded, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in decoded.items()
            ):
                raise ValueError("invalid secret payload")
            return decoded
        except (
            InvalidTag,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError("credential envelope invalid") from exc


class GatewayChannelKeyStore:
    """Load or atomically create the node-private X25519 PEM with mode 0600."""

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve(strict=False)

    def load_or_create(self) -> GatewayChannelKey:
        """Return stable key material, creating and fsyncing it on first startup."""
        if not self._path.exists():
            self._create()
        os.chmod(self._path, 0o600)
        private_pem = self._path.read_text(encoding="ascii")
        private = serialization.load_pem_private_key(
            private_pem.encode(), password=None
        )
        if not isinstance(private, X25519PrivateKey):
            raise ValueError("channel credential key must be X25519")
        public_bytes = private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return GatewayChannelKey(
            private_key_pem=private_pem,
            public_key=b64encode(public_bytes).decode("ascii"),
            key_id=f"sha256:{hashlib.sha256(public_bytes).hexdigest()}",
        )

    def _create(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        private = X25519PrivateKey.generate()
        payload = private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.", dir=self._path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self._path)
            directory = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
