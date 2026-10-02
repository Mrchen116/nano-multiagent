"""Enroll an existing node's locally verified key while public ingress is closed."""

from __future__ import annotations

import argparse
from base64 import b64decode
from contextlib import closing
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

from IM.infra.db import connect


def enroll_device(*, db_path: Path, node_id: str, public_key: str, key_id: str) -> None:
    """Record only the public half of a locally inspected existing device key.

    Args:
        db_path: IM database on the maintenance host.
        node_id: Existing node selected by the local operator.
        public_key: Base64 raw X25519 public key exported on the Gateway host.
        key_id: SHA-256 fingerprint independently checked against that device.
    """
    public = b64decode(public_key, validate=True)
    X25519PublicKey.from_public_bytes(public)
    if key_id != "sha256:" + hashlib.sha256(public).hexdigest():
        raise ValueError("key_id does not match the public key")
    public_text = public_key
    with closing(connect(db_path)) as c, c:
        c.execute("BEGIN IMMEDIATE")
        node = c.execute(
            "SELECT owner_id FROM nodes WHERE node_id=?", (node_id,)
        ).fetchone()
        if node is None:
            raise ValueError("node not found")
        existing = c.execute(
            "SELECT public_key FROM node_credential_keys WHERE node_id=?", (node_id,)
        ).fetchone()
        if existing is not None and existing["public_key"] != public_text:
            raise ValueError(
                "registered device key differs; key replacement is not supported"
            )
        c.execute(
            "INSERT OR IGNORE INTO node_credential_keys VALUES (?,?,?,'X25519-HKDF-SHA256-AES-256-GCM',?,datetime('now'))",
            (node_id, node["owner_id"] or "", key_id, public_text),
        )
        c.execute(
            "INSERT OR IGNORE INTO node_binding_state(node_id,node_epoch,owner_id) VALUES (?,0,?)",
            (node_id, node["owner_id"] or ""),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--key-id", required=True)
    args = parser.parse_args()
    enroll_device(
        db_path=args.db,
        node_id=args.node_id,
        public_key=args.public_key,
        key_id=args.key_id,
    )
    print(
        "Device public key enrolled. Run Gateway --recover-device locally to issue its runtime session."
    )


if __name__ == "__main__":
    main()
