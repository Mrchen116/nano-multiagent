"""Local device proof, terminal confirmation and recoverable owner handoff."""

from __future__ import annotations

from base64 import b64decode
from dataclasses import replace
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time
import webbrowser

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from personal_assistant.channels.channel_credentials import (
    GatewayChannelKey,
    GatewayChannelKeyStore,
    GatewayChannelAad,
)
from personal_assistant.config.local_store import (
    load_local_config,
    save_sensitive_local_config,
)
from personal_assistant.gateway.im_http_transport import normalize_im_http_base_url


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def open_challenge(key: GatewayChannelKey, envelope: dict) -> str:
    """Decrypt only the binding-purpose envelope under its independent context."""
    private = serialization.load_pem_private_key(
        key.private_key_pem.encode(), password=None
    )
    shared = private.exchange(
        X25519PublicKey.from_public_bytes(
            b64decode(envelope["ephemeral_public_key"], validate=True)
        )
    )
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b64decode(envelope["salt"]),
        info=b"nano-multiagent/device-binding-v1",
    ).derive(shared)
    if envelope["aad"]["purpose"] != "device-binding":
        raise ValueError("invalid binding challenge purpose")
    return (
        AESGCM(derived)
        .decrypt(
            b64decode(envelope["nonce"]),
            b64decode(envelope["ciphertext"]),
            canonical(envelope["aad"]),
        )
        .decode()
    )


def confirmation_proof(challenge: str, confirmation: dict) -> str:
    """Bind terminal consent to the displayed recipient, epoch and revisions."""
    return hmac.new(
        hashlib.sha256(challenge.encode()).digest(),
        canonical(confirmation),
        hashlib.sha256,
    ).hexdigest()


def rewrap_channels(key: GatewayChannelKey, snapshot: dict, target_owner: str) -> dict:
    """Reseal credentials locally under the new owner and credential revision."""
    result = {}
    for row in snapshot["agent_channels"]:
        aad = GatewayChannelAad(
            owner_id=row["owner_id"],
            node_id=row["node_id"],
            agent_id=row["agent_id"],
            channel_id=row["channel_id"],
            provider=row["provider"],
            credential_revision=row["credential_revision"],
        )
        secret = key.open(envelope=json.loads(row["credential_envelope_json"]), aad=aad)
        result[row["channel_id"]] = key.seal(
            secret=secret,
            aad=replace(
                aad,
                owner_id=target_owner,
                credential_revision=aad.credential_revision + 1,
            ),
        )
    return result


def save_operation(path: Path, value: dict) -> None:
    """Persist the finite operation credential privately before any commit."""
    fd, name = tempfile.mkstemp(prefix=".binding-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install_handoff_cache(
    directory: Path, key: GatewayChannelKey, result: dict
) -> None:
    """Install the complete transferred encrypted manifest before reconnecting."""
    from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
    from personal_assistant.gateway.channel_manager import (
        ChannelManifest,
        ChannelGeneration,
        ManagedChannelSpec,
        ChannelRemovalIntent,
    )

    snapshot = result["snapshot"]
    heads = snapshot["channel_manifest_heads"]
    channels = tuple(
        ManagedChannelSpec(
            channel_id=r["channel_id"],
            agent_id=r["agent_id"],
            provider=r["provider"],
            enabled=bool(r["enabled"]),
            config=json.loads(r["config_json"]),
            credentials={},
            provider_runtime=json.loads(r["provider_runtime_json"]),
            generation=ChannelGeneration(
                r["provider_identity_fingerprint"],
                r["provider_identity_revision"],
                r["channel_revision"],
                r["credential_revision"],
            ),
            credential_envelope=json.loads(r["credential_envelope_json"]),
            credential_key_id=r["credential_key_id"],
        )
        for r in snapshot["agent_channels"]
    )
    removals = tuple(
        ChannelRemovalIntent(
            r["removal_token"],
            r["channel_id"],
            r["agent_id"],
            r["provider"],
            r["deletion_manifest_revision"],
        )
        for r in snapshot["agent_channel_removals"]
        if r["apply_state"] != "applied"
    )
    manifest = ChannelManifest(
        manifest_revision=heads[0]["manifest_revision"] if heads else 0,
        channels=channels,
        owner_id=result["owner_id"],
        node_id=result["node_id"],
        removals=removals,
    )
    ChannelManifestStore(
        directory / "channel-manifest-v1.json",
        node_id=result["node_id"],
        key_id=key.key_id,
    ).install_handoff(manifest)


def bind_local_device(
    config_path: str,
    *,
    auto_bind: bool = False,
    recover_device: bool = False,
    client: httpx.Client | None = None,
    confirm=input,
    open_browser=webbrowser.open,
) -> dict:
    """Complete or recover a handoff; caller stops/restarts the local runtime."""
    config = load_local_config(config_path)
    if config.im_service is None:
        raise ValueError("configure im_service before binding")
    key = GatewayChannelKeyStore(
        config.source_path.parent / "channel-credentials-v1.pem"
    ).load_or_create()
    recovery_path = config.source_path.parent / "device-binding-operation.json"
    owns_client = client is None
    client = client or httpx.Client(
        base_url=normalize_im_http_base_url(config.im_service.url),
        timeout=15,
        trust_env=False,
    )

    def post(action: str, payload: dict, *, browser: bool = False) -> dict:
        headers = (
            {"Authorization": f"Bearer {config.im_service.token}"} if browser else {}
        )
        response = client.post(
            "/im/v1/device-binding/" + action, json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()

    try:
        resuming = recovery_path.exists() and not recover_device
        if resuming:
            local = json.loads(recovery_path.read_text())
        else:
            local = post(
                "start",
                {
                    "node_id": config.node.node_id,
                    "node_name": config.node.node_id,
                    "public_key": key.public_key,
                    "key_id": key.key_id,
                },
            )
            local["challenge_response"] = open_challenge(key, local["challenge"])
            save_operation(recovery_path, local)
        operation = {k: local[k] for k in ("operation_id", "operation_token")}
        try:
            post("prove", {**operation, "challenge": local["challenge_response"]})
        except httpx.HTTPStatusError as exc:
            if not resuming or exc.response.status_code != 409:
                raise
            recovery_path.unlink()
            return bind_local_device(
                config_path,
                auto_bind=auto_bind,
                client=client,
                confirm=confirm,
                open_browser=open_browser,
            )
        if recover_device:
            post("recover-device", operation)
        state = post("prepare", operation)
        if state["state"] == "awaiting_account":
            if auto_bind:
                post("accept", {"browser_token": local["browser_token"]}, browser=True)
            else:
                print("Open this link and accept with the receiving active account:")
                print(local["bind_url"])
                open_browser(local["bind_url"])
            while state["state"] == "awaiting_account":
                time.sleep(2)
                state = post("prepare", operation)
        if state["state"] != "committed":
            print(
                f"Transfer this device to {state['target_name']} ({state['target_user_id']})"
            )
            print(
                "Agents: "
                + ", ".join(
                    sorted(
                        {r["agent_id"] for r in state["snapshot"]["agent_profiles"]}
                        | {a.agent_id for a in config.agents}
                    )
                )
            )
            if (
                not auto_bind
                and confirm(
                    "Type yes to confirm the complete device transfer: "
                ).strip()
                != "yes"
            ):
                post("cancel", operation)
                recovery_path.unlink()
                raise ValueError(
                    "local confirmation cancelled; device ownership unchanged"
                )
            envelopes = rewrap_channels(key, state["snapshot"], state["target_owner"])
            post(
                "commit",
                {
                    **operation,
                    "proof": confirmation_proof(
                        local["challenge_response"], state["confirmation"]
                    ),
                    "envelopes": envelopes,
                },
            )
        result = post("recover", operation)
        install_handoff_cache(config.source_path.parent, key, result)
        updated = replace(
            config,
            node=replace(config.node, user_id=result["owner_id"]),
            im_service=replace(
                config.im_service,
                token=result["runtime_token"],
                refresh_token=None,
                username=None,
                password=None,
            ),
        )
        save_sensitive_local_config(updated, config.source_path)
        recovery_path.unlink()
        return result
    finally:
        if owns_client:
            client.close()
