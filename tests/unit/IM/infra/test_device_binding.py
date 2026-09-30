from pathlib import Path
import pytest
from IM.infra.device_binding import DeviceBindingStore, migrate_device_binding
from IM.infra.db import connect, initialize_schema


def test_legacy_node_cannot_acquire_remote_key(tmp_path: Path):
    db = tmp_path / "im.db"
    c = connect(db)
    initialize_schema(c)
    migrate_device_binding(c)
    c.execute(
        "INSERT INTO nodes(node_id,node_name,owner_id) VALUES ('legacy','legacy','old')"
    )
    c.commit()
    store = DeviceBindingStore(db)
    with pytest.raises(ValueError, match="local enrollment"):
        store.start(
            node_id="legacy", node_name="legacy", public_key="untrusted", key_id="key"
        )


from personal_assistant.channels.channel_credentials import (
    GatewayChannelKeyStore,
    GatewayChannelAad,
)
from personal_assistant.gateway.device_binding import (
    open_challenge,
    confirmation_proof,
    rewrap_channels,
)
import json


def setup_store(tmp_path):
    db = tmp_path / "db"
    c = connect(db)
    initialize_schema(c)
    migrate_device_binding(c)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
    if "membership_status" not in cols:
        c.execute(
            "ALTER TABLE users ADD COLUMN membership_status TEXT DEFAULT 'pending'"
        )
    for uid in ("old", "new"):
        c.execute(
            "INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES (?,?,?,?,?,'active')",
            (uid, uid, uid, uid, "now"),
        )
    c.commit()
    return (
        DeviceBindingStore(db),
        c,
        GatewayChannelKeyStore(tmp_path / "key.pem").load_or_create(),
    )


def operation(store, key, owner="old"):
    local = store.start(
        node_id="node",
        node_name="Test device",
        public_key=key.public_key,
        key_id=key.key_id,
    )
    challenge = open_challenge(key, local["challenge"])
    auth = {k: local[k] for k in ("operation_id", "operation_token")}
    store.prove(**auth, challenge=challenge)
    store.accept(browser_token=local["browser_token"], user_id=owner)
    prepared = store.prepare(**auth)
    return auth, challenge, prepared, local


def finish(store, key, owner="old"):
    auth, challenge, prepared, local = operation(store, key, owner)
    store.commit(
        **auth,
        proof=confirmation_proof(challenge, prepared["confirmation"]),
        envelopes=rewrap_channels(key, prepared["snapshot"], owner),
    )
    return store.recover(**auth), auth


def test_local_proof_browser_does_not_commit_and_wrong_recipient_fails(tmp_path):
    store, c, key = setup_store(tmp_path)
    local = store.start(
        node_id="node", node_name="node", public_key=key.public_key, key_id=key.key_id
    )
    with pytest.raises(ValueError):
        store.accept(browser_token=local["browser_token"], user_id="old")
    auth = {k: local[k] for k in ("operation_id", "operation_token")}
    challenge = open_challenge(key, local["challenge"])
    store.prove(**auth, challenge=challenge)
    store.accept(browser_token=local["browser_token"], user_id="old")
    assert c.execute("SELECT * FROM nodes WHERE node_id='node'").fetchone() is None
    with pytest.raises(ValueError, match="already fixed"):
        store.accept(browser_token=local["browser_token"], user_id="new")
    p = store.prepare(**auth)
    p["confirmation"]["target_user_id"] = "new"
    with pytest.raises(ValueError, match="confirmation invalid"):
        store.commit(
            **auth, proof=confirmation_proof(challenge, p["confirmation"]), envelopes={}
        )


def test_suspended_owner_handoff_reseals_and_revokes_old_runtime(tmp_path):
    store, c, key = setup_store(tmp_path)
    first, _ = finish(store, key)
    old_aad = GatewayChannelAad(
        owner_id="old",
        node_id="node",
        agent_id="agent",
        channel_id="channel",
        provider="feishu",
        credential_revision=1,
    )
    envelope = key.seal(secret={"secret": "value"}, aad=old_aad)
    c.execute(
        "INSERT INTO agent_profiles(agent_id,node_id,owner_id,display_name,created_at,updated_at) VALUES ('agent','node','old','Agent','now','now')"
    )
    c.execute(
        "INSERT INTO agent_channels(channel_id,owner_id,agent_id,node_id,provider,enabled,config_json,provider_identity_fingerprint,provider_identity_revision,credential_envelope_json,credential_key_id,credential_revision,channel_revision,created_at,updated_at) VALUES ('channel','old','agent','node','feishu',1,'{}','fingerprint',1,?,?,1,1,'now','now')",
        (json.dumps(envelope), key.key_id),
    )
    c.execute(
        "INSERT INTO channel_manifest_heads(node_id,owner_id,manifest_revision,applied_manifest_revision,updated_at) VALUES ('node','old',5,5,'now')"
    )
    c.execute(
        "INSERT INTO agent_channel_removals(channel_id,removal_token,owner_id,agent_id,node_id,provider,display_config_json,deleted_channel_revision,deletion_manifest_revision,apply_state,expires_at,created_at,updated_at) VALUES ('removed','removal-token','old','agent','node','feishu','{}',3,5,'pending','future','now','now')"
    )
    c.execute("UPDATE users SET membership_status='suspended' WHERE id='old'")
    c.commit()
    result, auth = finish(store, key, "new")
    assert result["node_epoch"] == 2
    assert store.authenticate_runtime(first["runtime_token"]) is None
    assert store.authenticate_runtime(result["runtime_token"]) == ("new", "node", 2)
    row = c.execute(
        "SELECT * FROM agent_channels WHERE channel_id='channel'"
    ).fetchone()
    assert row["owner_id"] == "new" and row["credential_revision"] == 2
    new_aad = GatewayChannelAad(
        owner_id="new",
        node_id="node",
        agent_id="agent",
        channel_id="channel",
        provider="feishu",
        credential_revision=2,
    )
    assert key.open(
        envelope=json.loads(row["credential_envelope_json"]), aad=new_aad
    ) == {"secret": "value"}
    assert store.recover(**auth) == result
    assert c.execute(
        "SELECT owner_id,manifest_revision FROM channel_manifest_heads WHERE node_id='node'"
    ).fetchone()[:] == ("new", 6)
    assert c.execute(
        "SELECT owner_id,apply_state FROM agent_channel_removals WHERE channel_id='removed'"
    ).fetchone()[:] == ("new", "pending")
    from personal_assistant.gateway.device_binding import install_handoff_cache
    from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore

    install_handoff_cache(tmp_path, key, result)
    cached = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json", node_id="node", key_id=key.key_id
    ).load_manifest()
    assert cached.owner_id == "new" and cached.manifest_revision == 6
    assert key.open(envelope=cached.channels[0].credential_envelope, aad=new_aad) == {
        "secret": "value"
    }


def test_revisions_and_target_suspend_abort_without_partial_transfer(tmp_path):
    store, c, key = setup_store(tmp_path)
    finish(store, key)
    auth, challenge, p, _ = operation(store, key, "new")
    c.execute(
        "INSERT INTO agent_profiles(agent_id,node_id,owner_id,display_name,created_at,updated_at) VALUES ('agent','node','old','Agent','now','now')"
    )
    c.commit()
    with pytest.raises(ValueError, match="configuration changed"):
        store.commit(
            **auth, proof=confirmation_proof(challenge, p["confirmation"]), envelopes={}
        )
    p = store.prepare(**auth)
    c.execute("UPDATE users SET membership_status='suspended' WHERE id='new'")
    c.commit()
    with pytest.raises(ValueError, match="must be active"):
        store.commit(
            **auth, proof=confirmation_proof(challenge, p["confirmation"]), envelopes={}
        )
    assert (
        c.execute("SELECT owner_id FROM nodes WHERE node_id='node'").fetchone()[0]
        == "old"
    )


def test_private_key_recovery_without_browser_and_key_cannot_change(tmp_path):
    store, c, key = setup_store(tmp_path)
    first, _ = finish(store, key)
    other = GatewayChannelKeyStore(tmp_path / "other.pem").load_or_create()
    local = store.start(
        node_id="node",
        node_name="node",
        public_key=other.public_key,
        key_id=other.key_id,
    )
    with pytest.raises(Exception):
        open_challenge(other, local["challenge"])
    challenge = open_challenge(key, local["challenge"])
    auth = {k: local[k] for k in ("operation_id", "operation_token")}
    store.prove(**auth, challenge=challenge)
    store.recover_device(**auth)
    result = store.recover(**auth)
    assert result["owner_id"] == "old" and result["node_epoch"] == 2
    assert store.authenticate_runtime(first["runtime_token"]) is None
    assert (
        c.execute(
            "SELECT public_key FROM node_credential_keys WHERE node_id='node'"
        ).fetchone()[0]
        == key.public_key
    )


def test_cli_recovers_committed_interruption_and_persists_private_config(
    tmp_path, monkeypatch
):
    import httpx
    from personal_assistant.gateway.device_binding import bind_local_device
    from personal_assistant.config.local_store import load_local_config

    store, c, key = setup_store(tmp_path)
    (tmp_path / "workspace").mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(
        """node:
  node_id: node
agents:
  - agent_id: agent
    workspace_root: """
        + str(tmp_path / "workspace")
        + """
llm:
  default_model: test:model
  providers:
    - name: openai_compat
      base_url: http://localhost:4000
      models:
        - name: test:model
im_service:
  url: http://im.test
  token: browser-token
"""
    )
    committed = False

    def transport(req):
        nonlocal committed
        body = json.loads(req.content)
        action = req.url.path.rsplit("/", 1)[1]
        if action == "accept":
            body["user_id"] = "old"
        result = getattr(store, action)(**body)
        if action == "start":
            result["bind_url"] = (
                "http://im.test/bind/confirm#token=" + result["browser_token"]
            )
        if action == "recover" and not committed:
            committed = True
            raise httpx.ConnectError("interrupted after central commit")
        return httpx.Response(200, json=result)

    client = httpx.Client(
        base_url="http://im.test", transport=httpx.MockTransport(transport)
    )
    with pytest.raises(httpx.ConnectError):
        bind_local_device(str(config), auto_bind=True, client=client)
    recovery = tmp_path / "device-binding-operation.json"
    assert recovery.exists() and recovery.stat().st_mode & 0o777 == 0o600
    result = bind_local_device(str(config), auto_bind=True, client=client)
    assert not recovery.exists()
    saved = load_local_config(config)
    assert saved.node.user_id == "old"
    assert saved.im_service.token == result["runtime_token"]
    assert config.stat().st_mode & 0o777 == 0o600
    assert store.authenticate_runtime(saved.im_service.token) == ("old", "node", 1)


@pytest.mark.asyncio
async def test_machine_http_requires_live_same_epoch_registration(tmp_path):
    from types import SimpleNamespace
    from IM.ws.gateway.sessions import GatewaySessions, GatewayAuthorizationError
    from IM.infra.gateway_persistence import GatewayNodePersistence

    store, c, key = setup_store(tmp_path)
    result, _ = finish(store, key)
    sessions = GatewaySessions(
        im_user_url="http://im.test", node_persistence=GatewayNodePersistence(c)
    )
    assert await sessions.authenticate_access_token(result["runtime_token"]) is None

    class Socket:
        state = SimpleNamespace(
            authenticated_node_id="node", authenticated_node_epoch=1
        )

        async def close(self, code):
            pass

    socket = Socket()
    ack = await sessions.register(
        websocket=socket,
        payload={"node_id": "node", "agents": []},
        authenticated_owner_id="old",
    )
    assert await sessions.authenticate_access_token(result["runtime_token"]) is not None
    finish(store, key, "new")
    assert await sessions.authenticate_access_token(result["runtime_token"]) is None
    assert (
        await sessions.authenticate_access_token(ack["payload"]["gateway_access_token"])
        is None
    )
    with pytest.raises(GatewayAuthorizationError):
        await sessions.authorize(
            websocket=socket, payload={"node_id": "node"}, authenticated_owner_id="old"
        )


def test_offline_local_enrollment_allows_proven_runtime_recovery(tmp_path):
    from IM.cli.enroll_device import enroll_device

    store, c, key = setup_store(tmp_path)
    c.execute(
        "INSERT INTO nodes(node_id,node_name,owner_id) VALUES ('node','Local','old')"
    )
    c.commit()
    db = tmp_path / "db"
    # The maintenance host imports only public material, without the device file.
    (tmp_path / "key.pem").unlink()
    with pytest.raises(ValueError, match="key_id"):
        enroll_device(
            db_path=db, node_id="node", public_key=key.public_key, key_id="sha256:wrong"
        )
    enroll_device(
        db_path=db, node_id="node", public_key=key.public_key, key_id=key.key_id
    )
    local = store.start(
        node_id="node", node_name="node", public_key=key.public_key, key_id=key.key_id
    )
    auth = {k: local[k] for k in ("operation_id", "operation_token")}
    store.prove(**auth, challenge=open_challenge(key, local["challenge"]))
    store.recover_device(**auth)
    assert store.recover(**auth)["owner_id"] == "old"


def test_cancellation_and_expiry_never_change_owner(tmp_path):
    store, c, key = setup_store(tmp_path)
    finish(store, key)
    auth, challenge, prepared, local = operation(store, key, "new")
    store.decline(browser_token=local["browser_token"], user_id="new")
    with pytest.raises(ValueError, match="local confirmation required"):
        store.commit(
            **auth,
            proof=confirmation_proof(challenge, prepared["confirmation"]),
            envelopes={},
        )
    assert (
        c.execute("SELECT owner_id FROM nodes WHERE node_id='node'").fetchone()[0]
        == "old"
    )
    c.execute("UPDATE node_binding_operations SET expires_at=0")
    c.commit()
    with pytest.raises(ValueError, match="expired"):
        store.prepare(**auth)
