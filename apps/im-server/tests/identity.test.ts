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
import { canonical, createIdentity, digest, type Identity } from "../src/identity.js";
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

  it("preserves pending registration, active membership gates, browser Origin and Cookie-only refresh", async () => {
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
    expect(created.json().user.membership_status).toBe("pending");
    expect(created.headers["set-cookie"]).toContain("HttpOnly; SameSite=Strict; Secure");
    const access = auth(created.json().access_token),
      cookie = String(created.headers["set-cookie"]).split(";")[0]!;
    expect((await app.inject({ url: "/im/v1/auth/me", headers: access })).statusCode).toBe(200);
    expect((await app.inject({ url: "/im/v1/me", headers: access })).statusCode).toBe(403);
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
    decipher.setAAD(Buffer.from(canonical(envelope.aad)));
    return Buffer.concat([
      decipher.update(ciphertext.subarray(0, -16)),
      decipher.final(),
    ]).toString();
  }
  const proof = (challenge: string, confirmation: any) =>
    createHmac("sha256", createHash("sha256").update(challenge).digest())
      .update(canonical(confirmation))
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
    expect(identity.authenticateRuntime(runtime.runtime_token)).toBeNull();
    expect(() => identity.deviceRecover(started.operation_id, started.operation_token)).toThrow();

    const transfer = identity.deviceStart({
      node_id: "new-node",
      node_name: "Device",
      ...key,
    });
    const transferChallenge = openChallenge(key, transfer.challenge);
    identity.deviceProve(transfer.operation_id, transfer.operation_token, transferChallenge);
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
    expect(identity.user("owner")!.owned_node_ids).toEqual([]);
    expect(identity.user("receiver")!.owned_node_ids).toEqual(["new-node"]);
    expect(identity.authenticateRuntime(recovered.runtime_token)).toBeNull();
    expect(
      identity.get("SELECT owner_id FROM channel_manifest_heads WHERE node_id='new-node'")!
        .owner_id,
    ).toBe("receiver");
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
