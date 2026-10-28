import { afterEach, describe, expect, it } from "vitest";
import Fastify, { type FastifyInstance } from "fastify";
import {
  createHash,
  createHmac,
  createDecipheriv,
  createPublicKey,
  diffieHellman,
  generateKeyPairSync,
  hkdfSync,
} from "node:crypto";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { openDatabase } from "../src/db.js";
import { serializeIdentityJson, createIdentity, digest, canActorAccess, canAccessSpace, type Identity } from "../src/identity.js";
import { registerIdentityRoutes } from "../src/identity-routes.js";
import type { ImContext } from "../src/context.js";

// Created with Python bcrypt.hashpw, not with the implementation under test.
const legacyHash = "$2b$12$EF/L52c0/DOIAIzztg.vLeo3btIdIuVbW5/M3UBiyztqi7ZLIfTUW";
const legacyRefresh =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsInNpZCI6InB5dGhvbi1zZXNzaW9uIiwiZXBvY2giOjAsImlhdCI6MTcwMDAwMDAwMCwiZXhwIjo0MTAyNDQ0ODAwLCJqdGkiOiJweXRob24tcmVmcmVzaCIsInR5cGUiOiJyZWZyZXNoIn0.uN2Ay187pl7YpiLAVPOibK0qAdQ29AkDTtXv8ymzvss";
const cleanups: (() => void | Promise<void>)[] = [];
afterEach(async () => {
  for (const close of cleanups.splice(0)) await close();
});
function fixture(path = ":memory:") {
  const db = openDatabase(path),
    identity = createIdentity(db, "migration-test-secret");
  cleanups.push(() => db.close());
  return { db, identity };
}
function human(identity: Identity, id: string, admin = false, status = "active") {
  identity.run(
    "INSERT INTO users(id,username,display_name,owner_id,password_hash,membership_status,is_company_admin,created_at) VALUES(?,?,?,?,?,?,?,?)",
    id,
    id,
    id,
    id,
    legacyHash,
    status,
    Number(admin),
    "2026-01-01T00:00:00+00:00",
  );
}
async function server(identity: Identity) {
  const app = Fastify();
  app.setErrorHandler((error: any, _request, reply) => {
    if (error.retry_after) reply.header("Retry-After", error.retry_after);
    reply.code(error.statusCode ?? 500).send({
      detail: error.detail ?? error.message,
      ...(error.retry_after ? { retry_after: error.retry_after } : {}),
    });
  });
  registerIdentityRoutes(app, {
    identity,
    db: identity.db,
    publicUrl: "https://im.example.test",
    gateway: {
      closeSession() {},
      closeUser() {},
      revokeOwner() {},
      revokeNode() {},
    },
  } as unknown as ImContext);
  await app.ready();
  cleanups.unshift(() => app.close());
  return app;
}
const auth = (token: string) => ({ authorization: `Bearer ${token}` });
async function post(
  app: FastifyInstance,
  url: string,
  payload: any,
  headers: Record<string, string> = {},
) {
  return app.inject({ method: "POST", url, payload, headers });
}

describe("durable identity compatibility", () => {
  it("reads Python bcrypt users, rotates refresh once across restart, and revokes access at logout", async () => {
    const dir = mkdtempSync(join(tmpdir(), "im-identity-"));
    cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
    const { identity } = fixture(join(dir, "im.db"));
    human(identity, "alice");
    identity.run(
      "INSERT INTO auth_sessions(session_id,user_id,epoch,refresh_hash,expires_at) VALUES('python-session','alice',0,?,4102444800)",
      digest("python-refresh"),
    );
    const migrated = identity.refresh(legacyRefresh);
    expect(migrated.user.id).toBe("alice");
    expect(() => identity.refresh(legacyRefresh)).toThrow();
    const login = await identity.login("alice", "old-password");
    expect(login.user).not.toHaveProperty("password_hash");
    const replacement = identity.refresh(login.refresh_token);
    expect(() => identity.refresh(login.refresh_token)).toThrow();
    const restarted = fixture(join(dir, "im.db")).identity;
    expect(() => restarted.refresh(login.refresh_token)).toThrow();
    expect(restarted.accessSession(replacement.access_token).sub).toBe("alice");
    const ticket = restarted.issueTicket(restarted.accessSession(replacement.access_token).sid);
    expect(restarted.consumeTicket(ticket)?.user_id).toBe("alice");
    expect(restarted.consumeTicket(ticket)).toBeUndefined();
    restarted.logout(replacement.refresh_token);
    expect(() => identity.accessSession(login.access_token)).toThrow();
    expect(() => identity.refresh(replacement.refresh_token)).toThrow();
  });

  it("preserves browser Origin and Cookie-only refresh while new accounts can use their personal space", async () => {
    const { identity } = fixture(),
      app = await server(identity);
    const payload = {
      username: "new-human",
      password: "password-123",
      display_name: "人类",
    };
    const refused = await post(app, "/im/v1/auth/register", payload, {
      "x-im-session": "browser",
      origin: "https://im.example.test.evil",
    });
    expect(refused.statusCode).toBe(403);
    expect(identity.get("SELECT * FROM users WHERE username=?", payload.username)).toBeUndefined();
    const headers = {
      "x-im-session": "browser",
      origin: "https://im.example.test",
    };
    const created = await post(app, "/im/v1/auth/register", payload, headers);
    expect(created.statusCode).toBe(201);
    expect(created.json()).not.toHaveProperty("refresh_token");
    expect(created.json().user.membership_status).toBe("none");
    expect(created.json().user.account_status).toBe("active");
    expect(created.headers["set-cookie"]).toContain("HttpOnly; SameSite=Strict; Secure");
    const access = auth(created.json().access_token),
      cookie = String(created.headers["set-cookie"]).split(";")[0]!;
    expect((await app.inject({ url: "/im/v1/auth/me", headers: access })).statusCode).toBe(200);
    expect((await app.inject({ url: "/im/v1/me", headers: access })).statusCode).toBe(200);
    expect((await post(app, "/im/v1/auth/refresh", {}, { cookie })).statusCode).toBe(422);
    expect(
      (
        await post(
          app,
          "/im/v1/auth/refresh",
          { refresh_token: "explicit" },
          { ...headers, cookie },
        )
      ).statusCode,
    ).toBe(422);
    const refreshed = await post(app, "/im/v1/auth/refresh", {}, { ...headers, cookie });
    expect(refreshed.statusCode).toBe(200);
    expect((await post(app, "/im/v1/auth/refresh", {}, { ...headers, cookie })).statusCode).toBe(
      401,
    );
    expect(
      (
        await post(
          app,
          "/im/v1/auth/logout",
          {},
          {
            ...headers,
            cookie: String(refreshed.headers["set-cookie"]).split(";")[0]!,
          },
        )
      ).statusCode,
    ).toBe(200);
    expect((await app.inject({ url: "/im/v1/auth/me", headers: access })).statusCode).toBe(401);
  });

  it("rejects reserved and oversized passwords without creating humans and limits without extending cooldown", async () => {
    const { identity } = fixture();
    await expect(identity.register(" agent:root ", "password", "Agent")).rejects.toMatchObject({
      statusCode: 422,
    });
    await expect(identity.register("human", "密".repeat(25), "Human")).rejects.toMatchObject({
      statusCode: 422,
    });
    expect(identity.get("SELECT count(*) AS n FROM users")!.n).toBe(0);
    identity.rateLimit("source", 1, 60);
    const expires = identity.get(
      "SELECT expires_at FROM auth_rate_limits WHERE bucket=?",
      digest("source"),
    )!.expires_at;
    expect(() => identity.rateLimit("source", 1, 60)).toThrow();
    expect(
      identity.get("SELECT expires_at FROM auth_rate_limits WHERE bucket=?", digest("source"))!
        .expires_at,
    ).toBe(expires);
  });

  it("does not block account reads while bounded password computations run", async () => {
    const { identity } = fixture();
    human(identity, "alice");
    const pair = await identity.login("alice", "old-password");
    let completed = false;
    const first = identity.login("alice", "old-password").then(() => {
      completed = true;
    });
    const second = identity.login("alice", "old-password");
    await expect(identity.login("alice", "old-password")).rejects.toMatchObject({
      statusCode: 429,
    });
    await new Promise((resolve) => setImmediate(resolve));
    expect(identity.authenticateRequest({ headers: auth(pair.access_token) }).id).toBe("alice");
    expect(completed).toBe(false);
    await Promise.all([first, second]);
  });

  it("requires explicit company bootstrap and suspends sessions and node epochs without deleting content", async () => {
    const { identity } = fixture();
    human(identity, "admin", false, "pending");
    human(identity, "member", false, "pending");
    const pending = await identity.login("member", "old-password");
    expect(() => identity.authenticateRequest({headers: auth(pending.access_token)})).toThrow();
    identity.initializeCompany("admin", ["member"]);
    identity.initializeCompany("admin", ["member"]);
    expect(() => identity.initializeCompany("member", ["admin"])).toThrow();
    const pair = await identity.login("member", "old-password");
    identity.run(
      "INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES('node','Device','member','offline')",
    );
    identity.run("INSERT INTO node_binding_state VALUES('node',1,?,'member')", digest("runtime"));
    expect(identity.authenticateRuntime("runtime")?.node_id).toBe("node");
    expect(() => identity.transition("member", "admin", "suspend")).toThrow();
    identity.transition("admin", "member", "suspend");
    expect(() => identity.accessSession(pair.access_token)).toThrow();
    expect(identity.authenticateRuntime("runtime")).toBeNull();
    expect(identity.get("SELECT owner_id FROM nodes WHERE node_id='node'")!.owner_id).toBe(
      "member",
    );
    expect(() => identity.transition("admin", "member", "approve")).toThrow();
    expect(() => identity.transition("admin", "admin", "suspend")).toThrow();
  });
});

describe("device possession and ownership transfer", () => {
  const deviceKey = () => {
    const key = generateKeyPairSync("x25519"),
      raw = key.publicKey.export({ type: "spki", format: "der" }).subarray(-32);
    return {
      key,
      public_key: raw.toString("base64"),
      key_id: "sha256:" + createHash("sha256").update(raw).digest("hex"),
    };
  };
  function openChallenge(key: ReturnType<typeof deviceKey>, envelope: any): string {
    const pub = createPublicKey({
      key: Buffer.concat([
        Buffer.from("302a300506032b656e032100", "hex"),
        Buffer.from(envelope.ephemeral_public_key, "base64"),
      ]),
      type: "spki",
      format: "der",
    });
    const shared = diffieHellman({
      privateKey: key.key.privateKey,
      publicKey: pub,
    });
    const aesKey = hkdfSync(
      "sha256",
      shared,
      Buffer.from(envelope.salt, "base64"),
      Buffer.from("nano-multiagent/device-binding-v1"),
      32,
    );
    const decipher = createDecipheriv(
      "aes-256-gcm",
      Buffer.from(aesKey),
      Buffer.from(envelope.nonce, "base64"),
    );
    const ciphertext = Buffer.from(envelope.ciphertext, "base64");
    decipher.setAuthTag(ciphertext.subarray(-16));
    decipher.setAAD(Buffer.from(serializeIdentityJson(envelope.aad)));
    return Buffer.concat([
      decipher.update(ciphertext.subarray(0, -16)),
      decipher.final(),
    ]).toString();
  }
  const proof = (challenge: string, confirmation: any) =>
    createHmac("sha256", createHash("sha256").update(challenge).digest())
      .update(serializeIdentityJson(confirmation))
      .digest("hex");

  it("completes encrypted proof and local commit, rejects stale snapshots, and recovers with a new node epoch", async () => {
    const { identity } = fixture();
    human(identity, "owner");
    human(identity, "receiver");
    const key = deviceKey(),
      started = identity.deviceStart({
        node_id: "new-node",
        node_name: "我的设备",
        ...key,
      });
    expect(() => identity.deviceBrowser("accept", started.browser_token, "owner")).toThrow();
    const challenge = openChallenge(key, started.challenge);
    identity.deviceProve(started.operation_id, started.operation_token, challenge);
    identity.deviceBrowser("accept", started.browser_token, "owner");
    expect(() => identity.deviceBrowser("accept", started.browser_token, "receiver")).toThrow();
    expect(identity.get("SELECT * FROM nodes WHERE node_id='new-node'")).toBeUndefined();
    const prepared = identity.devicePrepare(started.operation_id, started.operation_token);
    expect(() =>
      identity.deviceCommit(started.operation_id, started.operation_token, "wrong", {}),
    ).toThrow();
    identity.deviceCommit(
      started.operation_id,
      started.operation_token,
      proof(challenge, prepared.confirmation),
      {},
    );
    const runtime = identity.deviceRecover(started.operation_id, started.operation_token);
    expect(identity.authenticateRuntime(runtime.runtime_token)).toMatchObject({
      node_id: "new-node",
      node_epoch: 1,
      owner_id: "owner",
    });
    expect(identity.user("owner")!.default_entry_node_id).toBe("new-node");

    identity.run("INSERT INTO personal_agent_bindings VALUES('pa-binding','owner','owner','pa-test','new-node',1,'pa-chat','Assistant','create','active',NULL,datetime('now'))");
    const recover = identity.deviceStart({
      node_id: "new-node",
      node_name: "Device",
      ...key,
    });
    identity.deviceProve(
      recover.operation_id,
      recover.operation_token,
      openChallenge(key, recover.challenge),
    );
    identity.deviceRecoverDevice(recover.operation_id, recover.operation_token);
    const recovered = identity.deviceRecover(recover.operation_id, recover.operation_token);
    expect(recovered.node_epoch).toBe(2);
    expect(recovered.snapshot.personal_agent_bindings).toMatchObject([{binding_id:'pa-binding',node_epoch:2}]);
    expect(identity.authenticateRuntime(runtime.runtime_token)).toBeNull();
    expect(() => identity.deviceRecover(started.operation_id, started.operation_token)).toThrow();

    // The explicit device handoff carries private Agent execution history, not
    // the old owner's conversations or task graphs.
    identity.run("UPDATE users SET personal_space_enabled=1 WHERE id='owner'");
    identity.run("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,space_id,created_at,updated_at) VALUES('private','owner','new-node','Private','personal:owner','then','then')");
    identity.run("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('agent-private','agent:private','Private','owner','then')");
    identity.run("INSERT INTO conversations(id,title,owner_id,space_id,created_at) VALUES('private-chat','Private','owner','personal:owner','then')");
    identity.run("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('private-chat','agent-private')");
    identity.run("INSERT INTO task_graphs(graph_id,owner_id,space_id,conversation_id,root_title,revision,document_json,created_at,updated_at,updated_by) VALUES('private-task','owner','personal:owner','private-chat','Private',1,'{}','then','then','owner')");
    identity.run("INSERT INTO agent_work_sessions VALUES('work-history','private','new-node','global_main',NULL,'{}')");
    expect(canActorAccess(identity.db, 'agent-private', 'personal:owner')).toBe(true);
    const transfer = identity.deviceStart({
      node_id: "new-node",
      node_name: "Device",
      ...key,
    });
    const transferChallenge = openChallenge(key, transfer.challenge);
    identity.deviceProve(transfer.operation_id, transfer.operation_token, transferChallenge);
    expect(identity.deviceBrowser("inspect", transfer.browser_token, "receiver")).toMatchObject({is_transfer: true, history_transferred: true});
    identity.deviceBrowser("accept", transfer.browser_token, "receiver");
    let ready = identity.devicePrepare(transfer.operation_id, transfer.operation_token);
    identity.run(
      "INSERT INTO channel_manifest_heads(owner_id,node_id,manifest_revision,updated_at) VALUES('owner','new-node',1,'2026-01-01T00:00:00Z')",
    );
    expect(() =>
      identity.deviceCommit(
        transfer.operation_id,
        transfer.operation_token,
        proof(transferChallenge, ready.confirmation),
        {},
      ),
    ).toThrow("node configuration changed");
    ready = identity.devicePrepare(transfer.operation_id, transfer.operation_token);
    identity.deviceCommit(
      transfer.operation_id,
      transfer.operation_token,
      proof(transferChallenge, ready.confirmation),
      {},
    );
    expect(identity.get("SELECT owner_id,space_id FROM agent_profiles WHERE agent_id='private'")).toEqual({owner_id: 'receiver', space_id: 'personal:receiver'});
    expect(identity.user('receiver')!.personal_space_enabled).toBe(true);
    expect(canAccessSpace(identity.user('owner'), 'personal:receiver')).toBe(false);
    expect(canAccessSpace(identity.user('receiver'), 'personal:receiver')).toBe(true);
    expect(canActorAccess(identity.db, 'agent-private', 'personal:owner')).toBe(false);
    expect(identity.get("SELECT session_id FROM agent_work_sessions WHERE root_agent_id='private'")?.session_id).toBe('work-history');
    expect(identity.get("SELECT space_id FROM conversations WHERE id='private-chat'")?.space_id).toBe('personal:owner');
    expect(identity.get("SELECT space_id FROM task_graphs WHERE graph_id='private-task'")?.space_id).toBe('personal:owner');
    expect(identity.user("owner")!.owned_node_ids).toEqual([]);
    expect(identity.user("receiver")!.owned_node_ids).toEqual(["new-node"]);
    expect(identity.authenticateRuntime(recovered.runtime_token)).toBeNull();
    expect(
      identity.get("SELECT owner_id FROM channel_manifest_heads WHERE node_id='new-node'")!
        .owner_id,
    ).toBe("receiver");
  });

  it("requires company approval before handing over a device containing company Agents", () => {
    const { identity } = fixture();
    human(identity, "owner");
    human(identity, "personal", false, "none");
    identity.run("UPDATE users SET personal_space_enabled=1 WHERE id='personal'");
    identity.run("INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES('company-device','Company','owner','offline')");
    identity.run("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,created_at,updated_at) VALUES('company-agent','owner','company-device','Company','then','then')");
    const key = deviceKey();
    identity.enrollDevice('company-device', key.public_key, key.key_id);
    const operation = identity.deviceStart({node_id: 'company-device', node_name: 'Company', ...key});
    identity.deviceProve(operation.operation_id, operation.operation_token, openChallenge(key, operation.challenge));
    expect(() => identity.deviceBrowser('accept', operation.browser_token, 'personal')).toThrow('active company recipient');
    expect(identity.get("SELECT owner_id FROM nodes WHERE node_id='company-device'")?.owner_id).toBe('owner');
    identity.run("UPDATE users SET membership_status='active' WHERE id='personal'");
    expect(identity.deviceBrowser('accept', operation.browser_token, 'personal').state).toBe('awaiting_local_confirmation');
  });

  it("does not transfer a computer that has held personal assistant data to another owner", () => {
    const {identity}=fixture();human(identity,'owner');human(identity,'receiver');
    identity.run("INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES('pa-device','Private','owner','offline')");
    identity.run("INSERT INTO pa_node_residencies VALUES('pa-device','owner')");
    const key=deviceKey();identity.enrollDevice('pa-device',key.public_key,key.key_id);
    const operation=identity.deviceStart({node_id:'pa-device',node_name:'Private',...key});
    identity.deviceProve(operation.operation_id,operation.operation_token,openChallenge(key,operation.challenge));
    expect(()=>identity.deviceBrowser('accept',operation.browser_token,'receiver')).toThrow('personal assistant data');
    expect(identity.get("SELECT owner_id FROM nodes WHERE node_id='pa-device'")?.owner_id).toBe('owner');
    expect(identity.deviceBrowser('accept',operation.browser_token,'owner').state).toBe('awaiting_local_confirmation');
  });

  it("requires local enrollment of existing nodes and keeps the enrolled key immutable", () => {
    const { identity } = fixture();
    human(identity, "owner");
    identity.run(
      "INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES('existing','Device','owner','offline')",
    );
    const key = deviceKey(),
      other = deviceKey();
    expect(() =>
      identity.deviceStart({
        node_id: "existing",
        node_name: "Device",
        ...key,
      }),
    ).toThrow("offline local enrollment");
    identity.enrollDevice("existing", key.public_key, key.key_id);
    expect(() => identity.enrollDevice("existing", other.public_key, other.key_id)).toThrow(
      "key replacement",
    );
    const start = identity.deviceStart({
      node_id: "existing",
      node_name: "Device",
      ...other,
    });
    expect(() => openChallenge(other, start.challenge)).toThrow();
    expect(openChallenge(key, start.challenge)).toBeTypeOf("string");
  });
});

// Fixed snapshot/proof bytes from a34af8473, including DEL and nested Unicode.
it('preserves identity snapshot bytes across serializer ownership changes', () => {
  expect(serializeIdentityJson({"z":"\u4e2d\u6587\ud83d\ude00\u007f\u0080\u2028\ud800","a":{"b":2,"a":1},"arr":[{"z":"e\u0301","a":null},false,0],"keys":{"2":2,"10":10,"\u00e9":1,"e":2,"\u4e2d":3,"\ud83d\ude00":4,"\ue000":5}})).toBe("{\"a\":{\"a\":1,\"b\":2},\"arr\":[{\"a\":null,\"z\":\"e\\u0301\"},false,0],\"keys\":{\"2\":2,\"10\":10,\"e\":2,\"\\u00e9\":1,\"\\u4e2d\":3,\"\\ud83d\\ude00\":4,\"\\ue000\":5},\"z\":\"\\u4e2d\\u6587\\ud83d\\ude00\\u007f\\u0080\\u2028\\ud800\"}");
});
