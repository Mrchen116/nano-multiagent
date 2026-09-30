"""Device-key proof and atomic whole-node ownership transfer.

Operation credentials authorize only this finite handoff; they are never company
sessions. Channel ciphertext is opened and resealed exclusively by the device.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from contextlib import closing
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from IM.infra.db import connect

CONTEXT = b"nano-multiagent/device-binding-v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def migrate_device_binding(connection: sqlite3.Connection) -> None:
    """Create operation state without granting legacy nodes device authority."""
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS node_binding_state (
            node_id TEXT PRIMARY KEY, node_epoch INTEGER NOT NULL DEFAULT 0,
            runtime_token_hash TEXT, owner_id TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS node_binding_operations (
            operation_id TEXT PRIMARY KEY, node_id TEXT NOT NULL,
            node_name TEXT NOT NULL, expected_owner TEXT NOT NULL,
            expected_epoch INTEGER NOT NULL, key_id TEXT NOT NULL,
            public_key TEXT NOT NULL, challenge_hash TEXT NOT NULL,
            operation_token_hash TEXT NOT NULL, browser_token_hash TEXT NOT NULL,
            expires_at REAL NOT NULL, state TEXT NOT NULL,
            target_user_id TEXT, target_owner TEXT, snapshot_json TEXT,
            runtime_token TEXT
        );
    """)


class DeviceBindingStore:
    """Serialize local proof, browser acceptance and revision-checked commit."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def start(
        self, *, node_id: str, node_name: str, public_key: str, key_id: str
    ) -> dict:
        """Seal a short-lived challenge to the immutable registered device key."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            c.execute(
                "DELETE FROM node_binding_operations WHERE expires_at < ?",
                (time.time(),),
            )
            node = c.execute(
                "SELECT owner_id FROM nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            key = c.execute(
                "SELECT * FROM node_credential_keys WHERE node_id=?", (node_id,)
            ).fetchone()
            if node is not None and key is None:
                raise ValueError("device requires offline local enrollment")
            if key is not None:
                public_key, key_id = key["public_key"], key["key_id"]
            raw_key = b64decode(public_key, validate=True)
            if key_id != "sha256:" + hashlib.sha256(raw_key).hexdigest():
                raise ValueError("invalid device key")
            state = c.execute(
                "SELECT node_epoch FROM node_binding_state WHERE node_id=?", (node_id,)
            ).fetchone()
            epoch = state["node_epoch"] if state else 0
            op, token, browser, challenge = (
                secrets.token_urlsafe(32) for _ in range(4)
            )
            expires = time.time() + 900
            aad = {
                "purpose": "device-binding",
                "node_id": node_id,
                "operation_id": op,
                "epoch": epoch,
                "expires_at": expires,
            }
            ephemeral = X25519PrivateKey.generate()
            salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
            shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(raw_key))
            derived = HKDF(
                algorithm=hashes.SHA256(), length=32, salt=salt, info=CONTEXT
            ).derive(shared)
            envelope = {
                "aad": aad,
                "ephemeral_public_key": b64encode(
                    ephemeral.public_key().public_bytes(
                        serialization.Encoding.Raw, serialization.PublicFormat.Raw
                    )
                ).decode(),
                "salt": b64encode(salt).decode(),
                "nonce": b64encode(nonce).decode(),
                "ciphertext": b64encode(
                    AESGCM(derived).encrypt(nonce, challenge.encode(), canonical(aad))
                ).decode(),
            }
            c.execute(
                """INSERT INTO node_binding_operations VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL)""",
                (
                    op,
                    node_id,
                    node_name,
                    str(node["owner_id"] or "") if node else "",
                    epoch,
                    key_id,
                    public_key,
                    digest(challenge),
                    digest(token),
                    digest(browser),
                    expires,
                    "awaiting_proof",
                ),
            )
            return {
                "operation_id": op,
                "operation_token": token,
                "browser_token": browser,
                "challenge": envelope,
            }

    def _operation(self, c: sqlite3.Connection, op: str, token: str) -> sqlite3.Row:
        row = c.execute(
            "SELECT * FROM node_binding_operations WHERE operation_id=?", (op,)
        ).fetchone()
        if (
            row is None
            or row["expires_at"] <= time.time()
            or not hmac.compare_digest(row["operation_token_hash"], digest(token))
        ):
            raise ValueError("binding operation invalid or expired")
        return row

    def prove(self, *, operation_id: str, operation_token: str, challenge: str) -> dict:
        """Unlock browser acceptance only after the device decrypts its challenge."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            op = self._operation(c, operation_id, operation_token)
            if op["state"] == "cancelled":
                raise ValueError("binding operation cancelled")
            if not hmac.compare_digest(op["challenge_hash"], digest(challenge)):
                raise ValueError("device proof invalid")
            if op["state"] == "awaiting_proof":
                c.execute(
                    "UPDATE node_binding_operations SET state='awaiting_account' WHERE operation_id=?",
                    (operation_id,),
                )
            return {"state": "awaiting_account"}

    @staticmethod
    def _active(c: sqlite3.Connection, user_id: str) -> sqlite3.Row:
        user = c.execute(
            "SELECT * FROM users WHERE id=? AND membership_status='active'", (user_id,)
        ).fetchone()
        if user is None:
            raise ValueError("receiving account must be active")
        return user

    def inspect(self, *, browser_token: str, user_id: str) -> dict:
        """Show the complete device impact before browser acceptance."""
        with closing(connect(self._db_path)) as c:
            self._active(c, user_id)
            op = c.execute(
                "SELECT * FROM node_binding_operations WHERE browser_token_hash=?",
                (digest(browser_token),),
            ).fetchone()
            if (
                op is None
                or op["expires_at"] <= time.time()
                or op["state"] in ("awaiting_proof", "cancelled")
            ):
                raise ValueError("binding operation invalid or expired")
            if op["target_user_id"] and op["target_user_id"] != user_id:
                raise ValueError("receiving account already fixed")
            agents = [
                r["agent_id"]
                for r in c.execute(
                    "SELECT agent_id FROM agent_profiles WHERE node_id=?",
                    (op["node_id"],),
                )
            ]
            return {
                "node_id": op["node_id"],
                "node_name": op["node_name"],
                "agents": agents,
                "state": op["state"],
            }

    def decline(self, *, browser_token: str, user_id: str) -> dict:
        """Cancel an uncommitted browser acceptance without touching ownership."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            self._active(c, user_id)
            op = c.execute(
                "SELECT * FROM node_binding_operations WHERE browser_token_hash=?",
                (digest(browser_token),),
            ).fetchone()
            if (
                op is None
                or op["expires_at"] <= time.time()
                or op["state"] == "committed"
                or (op["target_user_id"] and op["target_user_id"] != user_id)
            ):
                raise ValueError("binding cannot be cancelled")
            c.execute(
                "UPDATE node_binding_operations SET state='cancelled' WHERE operation_id=?",
                (op["operation_id"],),
            )
            return {"state": "cancelled"}

    def cancel(self, *, operation_id: str, operation_token: str) -> dict:
        """Cancel a local operation, preserving the current node owner."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            op = self._operation(c, operation_id, operation_token)
            if op["state"] == "committed":
                raise ValueError("binding already committed")
            c.execute(
                "UPDATE node_binding_operations SET state='cancelled' WHERE operation_id=?",
                (operation_id,),
            )
            return {"state": "cancelled"}

    def accept(self, *, browser_token: str, user_id: str) -> dict:
        """Fix the active receiving account without transferring ownership."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            user = self._active(c, user_id)
            op = c.execute(
                "SELECT * FROM node_binding_operations WHERE browser_token_hash=?",
                (digest(browser_token),),
            ).fetchone()
            if (
                op is None
                or op["expires_at"] <= time.time()
                or op["state"]
                not in ("awaiting_account", "awaiting_local_confirmation", "committed")
            ):
                raise ValueError("binding operation invalid or expired")
            if op["target_user_id"] and op["target_user_id"] != user_id:
                raise ValueError("receiving account already fixed")
            if op["state"] == "awaiting_account":
                c.execute(
                    "UPDATE node_binding_operations SET target_user_id=?,target_owner=?,state='awaiting_local_confirmation' WHERE operation_id=?",
                    (user_id, user["owner_id"], op["operation_id"]),
                )
            agents = [
                r["agent_id"]
                for r in c.execute(
                    "SELECT agent_id FROM agent_profiles WHERE node_id=?",
                    (op["node_id"],),
                )
            ]
            return {
                "node_id": op["node_id"],
                "node_name": op["node_name"],
                "agents": agents,
                "state": "committed"
                if op["state"] == "committed"
                else "awaiting_local_confirmation",
            }

    @staticmethod
    def _snapshot(c: sqlite3.Connection, node_id: str) -> dict:
        tables = (
            "agent_profiles",
            "channel_manifest_heads",
            "agent_channels",
            "agent_channel_removals",
            "agent_config_operations",
        )
        return {
            table: [
                dict(r)
                for r in c.execute(
                    f"SELECT * FROM {table} WHERE node_id=? ORDER BY rowid", (node_id,)
                )
            ]
            for table in tables
        }

    def prepare(self, *, operation_id: str, operation_token: str) -> dict:
        """Return only the proven device's handoff material and target identity."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            op = self._operation(c, operation_id, operation_token)
            if op["state"] in ("awaiting_proof", "cancelled"):
                raise ValueError("device proof required")
            if op["state"] != "awaiting_local_confirmation":
                return {"state": op["state"]}
            user = self._active(c, op["target_user_id"])
            snapshot = self._snapshot(c, op["node_id"])
            encoded = canonical(snapshot).decode()
            c.execute(
                "UPDATE node_binding_operations SET snapshot_json=? WHERE operation_id=?",
                (encoded, operation_id),
            )
            return {
                "state": op["state"],
                "target_user_id": user["id"],
                "target_owner": user["owner_id"],
                "target_name": user["display_name"],
                "snapshot": snapshot,
                "confirmation": {
                    "operation_id": operation_id,
                    "target_user_id": user["id"],
                    "epoch": op["expected_epoch"],
                    "snapshot_hash": digest(encoded),
                },
            }

    def commit(
        self, *, operation_id: str, operation_token: str, proof: str, envelopes: dict
    ) -> dict:
        """Atomically transfer all current configuration and revoke the old epoch."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            op = self._operation(c, operation_id, operation_token)
            if op["state"] == "committed":
                return {"state": "committed"}
            if op["state"] != "awaiting_local_confirmation" or not op["snapshot_json"]:
                raise ValueError("local confirmation required")
            user = self._active(c, op["target_user_id"])
            confirmation = {
                "operation_id": operation_id,
                "target_user_id": user["id"],
                "epoch": op["expected_epoch"],
                "snapshot_hash": digest(op["snapshot_json"]),
            }
            expected = hmac.new(
                bytes.fromhex(op["challenge_hash"]),
                canonical(confirmation),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, proof):
                raise ValueError("local confirmation invalid")
            node = c.execute(
                "SELECT owner_id FROM nodes WHERE node_id=?", (op["node_id"],)
            ).fetchone()
            state = c.execute(
                "SELECT node_epoch FROM node_binding_state WHERE node_id=?",
                (op["node_id"],),
            ).fetchone()
            if (str(node["owner_id"] or "") if node else "") != op[
                "expected_owner"
            ] or (state["node_epoch"] if state else 0) != op["expected_epoch"]:
                raise ValueError("node ownership changed")
            snapshot = self._snapshot(c, op["node_id"])
            if canonical(snapshot).decode() != op["snapshot_json"]:
                raise ValueError("node configuration changed; prepare again")
            if any(
                r["status"] in ("pending", "gateway_applied")
                for r in snapshot["agent_config_operations"]
            ):
                raise ValueError("node configuration operation still pending")
            channels = snapshot["agent_channels"]
            if set(envelopes) != {r["channel_id"] for r in channels}:
                raise ValueError("complete channel ciphertext set required")
            for row in channels:
                envelope = envelopes[row["channel_id"]]
                if not isinstance(envelope, dict) or not all(
                    k in envelope
                    for k in ("ciphertext", "nonce", "salt", "ephemeral_public_key")
                ):
                    raise ValueError("invalid channel envelope")
                c.execute(
                    "UPDATE agent_channels SET credential_envelope_json=?,credential_revision=credential_revision+1,channel_revision=channel_revision+1 WHERE channel_id=?",
                    (canonical(envelope).decode(), row["channel_id"]),
                )
            owner, node_id = user["owner_id"], op["node_id"]
            c.execute(
                "INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES (?,?,?,'offline') ON CONFLICT(node_id) DO UPDATE SET owner_id=excluded.owner_id,status='offline'",
                (node_id, op["node_name"], owner),
            )
            for table in (
                "agent_profiles",
                "channel_manifest_heads",
                "agent_channels",
                "agent_channel_removals",
                "node_credential_keys",
            ):
                c.execute(
                    f"UPDATE {table} SET owner_id=? WHERE node_id=?", (owner, node_id)
                )
            c.execute(
                "UPDATE channel_manifest_heads SET manifest_revision=manifest_revision+1 WHERE node_id=?",
                (node_id,),
            )
            c.execute(
                "INSERT OR IGNORE INTO node_credential_keys VALUES (?,?,?,'X25519-HKDF-SHA256-AES-256-GCM',?,datetime('now'))",
                (node_id, owner, op["key_id"], op["public_key"]),
            )
            runtime = secrets.token_urlsafe(48)
            c.execute(
                "INSERT INTO node_binding_state VALUES (?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET node_epoch=excluded.node_epoch,runtime_token_hash=excluded.runtime_token_hash,owner_id=excluded.owner_id",
                (node_id, op["expected_epoch"] + 1, digest(runtime), owner),
            )
            c.execute(
                "UPDATE node_binding_operations SET state='cancelled' WHERE node_id=? AND operation_id!=? AND state!='committed'",
                (node_id, operation_id),
            )
            c.execute(
                "UPDATE node_binding_operations SET state='committed',runtime_token=? WHERE operation_id=?",
                (runtime, operation_id),
            )
            c.execute(
                "UPDATE users SET default_entry_node_id=NULL WHERE default_entry_node_id=? AND owner_id!=?",
                (node_id, owner),
            )
            c.execute(
                "UPDATE users SET default_entry_node_id=COALESCE(default_entry_node_id,?) WHERE id=?",
                (node_id, user["id"]),
            )
            return {"state": "committed"}

    def recover(self, *, operation_id: str, operation_token: str) -> dict:
        """Recover only this committed result, after checking its current epoch."""
        with closing(connect(self._db_path)) as c:
            op = self._operation(c, operation_id, operation_token)
            if op["state"] != "committed":
                raise ValueError("binding not committed")
            identity = self.authenticate_runtime(op["runtime_token"])
            if identity is None:
                raise ValueError("binding runtime revoked")
            owner, node, epoch = identity
            return {
                "owner_id": owner,
                "node_id": node,
                "node_epoch": epoch,
                "runtime_token": op["runtime_token"],
                "snapshot": self._snapshot(c, node),
            }

    def recover_device(self, *, operation_id: str, operation_token: str) -> dict:
        """Reissue the current owner's node session after fresh local-key proof."""
        with closing(connect(self._db_path)) as c, c:
            c.execute("BEGIN IMMEDIATE")
            op = self._operation(c, operation_id, operation_token)
            if op["state"] != "awaiting_account":
                raise ValueError("fresh device proof required")
            row = c.execute(
                "SELECT s.*,u.id AS user_id FROM node_binding_state s JOIN users u ON u.owner_id=s.owner_id AND u.membership_status='active' WHERE s.node_id=?",
                (op["node_id"],),
            ).fetchone()
            if (
                row is None
                or row["owner_id"] != op["expected_owner"]
                or row["node_epoch"] != op["expected_epoch"]
            ):
                raise ValueError("current device owner unavailable")
            runtime = secrets.token_urlsafe(48)
            c.execute(
                "UPDATE node_binding_state SET node_epoch=node_epoch+1,runtime_token_hash=? WHERE node_id=?",
                (digest(runtime), op["node_id"]),
            )
            c.execute(
                "UPDATE node_binding_operations SET state='committed',target_user_id=?,target_owner=?,runtime_token=? WHERE operation_id=?",
                (row["user_id"], row["owner_id"], runtime, operation_id),
            )
            return {"state": "committed"}

    def authenticate_runtime(self, token: str) -> tuple[str, str, int] | None:
        """Resolve a node-scoped runtime token only for its current active owner."""
        with closing(connect(self._db_path)) as c:
            row = c.execute(
                """SELECT s.* FROM node_binding_state s JOIN nodes n ON n.node_id=s.node_id AND n.owner_id=s.owner_id
                JOIN users u ON u.owner_id=s.owner_id AND u.membership_status='active'
                WHERE s.runtime_token_hash=?""",
                (digest(token),),
            ).fetchone()
            return (row["owner_id"], row["node_id"], row["node_epoch"]) if row else None
