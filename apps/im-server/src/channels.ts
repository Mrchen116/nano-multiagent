import {
  createCipheriv,
  createHash,
  createPublicKey,
  diffieHellman,
  generateKeyPairSync,
  hkdfSync,
  randomBytes,
  randomUUID,
} from "node:crypto";
import type { FastifyInstance } from "fastify";
import type { DatabaseSync } from "node:sqlite";
import {
  all,
  one,
  transaction,
  fail,
  now,
  body,
  params,
  query,
  type ImContext,
  type Row,
} from "./context.js";
import { canonicalJson } from "./task-graphs.js";

/** Seal a Gateway-only secret in the Python-compatible X25519 envelope. */
export function sealChannelSecret(publicKey: string, secret: Row, aad: Row): Row {
  const recipient = createPublicKey({
    key: {
      kty: "OKP",
      crv: "X25519",
      x: Buffer.from(publicKey, "base64").toString("base64url"),
    },
    format: "jwk",
  });
  const ephemeral = generateKeyPairSync("x25519"),
    salt = randomBytes(16),
    nonce = randomBytes(12);
  const key = Buffer.from(
    hkdfSync(
      "sha256",
      diffieHellman({ privateKey: ephemeral.privateKey, publicKey: recipient }),
      salt,
      Buffer.from("nano-multiagent/channel-envelope-v1"),
      32,
    ),
  );
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  cipher.setAAD(Buffer.from(canonicalJson(aad)));
  const ciphertext = Buffer.concat([
    cipher.update(canonicalJson(secret)),
    cipher.final(),
    cipher.getAuthTag(),
  ]);
  return {
    version: 1,
    algorithm: "X25519-HKDF-SHA256-AES-256-GCM",
    ephemeral_public_key: Buffer.from(
      ephemeral.publicKey.export({ format: "jwk" }).x!,
      "base64url",
    ).toString("base64"),
    salt: salt.toString("base64"),
    nonce: nonce.toString("base64"),
    ciphertext: ciphertext.toString("base64"),
  };
}
function channelError(code: string, status = 422, current?: Row): never {
  fail(status, { code, ...(current ? { current } : {}) });
}
const joined = `SELECT ac.*,s.observed_revision,s.connection_state,s.diagnostics_state,s.status_code,s.status_message,s.checks_json,s.received_at,n.status AS node_status,h.manifest_revision AS head_manifest_revision,h.applied_manifest_revision,h.last_apply_error_json FROM agent_channels ac LEFT JOIN agent_channel_status s ON s.channel_id=ac.channel_id LEFT JOIN nodes n ON n.node_id=ac.node_id LEFT JOIN channel_manifest_heads h ON h.node_id=ac.node_id`;
function config(provider: string, input: Row): Row {
  if (provider !== "feishu") channelError("channel_provider_unsupported");
  if (!input || typeof input.app_id !== "string" || !input.app_id.trim())
    channelError("channel_config_invalid");
  return { app_id: input.app_id.trim() };
}
function fingerprint(provider: string, c: Row) {
  return createHash("sha256").update(`${provider}\0${c.app_id}`).digest("hex");
}
function removalView(r: Row) {
  return {
    resource_type: "removal",
    channel_id: r.channel_id,
    provider: r.provider,
    display_config: JSON.parse(r.display_config_json),
    deletion_manifest_revision: r.deletion_manifest_revision,
    apply_state: r.apply_state,
    apply_error:
      r.apply_error_code || r.apply_error_message
        ? {
            code: r.apply_error_code || "channel_removal_failed",
            message: r.apply_error_message || "Removal could not be applied",
          }
        : null,
    created_at: r.created_at,
  };
}
function view(r: Row): Row {
  let sync = "pending",
    error = null,
    observed = null;
  const first = r.last_apply_error_json
    ? JSON.parse(r.last_apply_error_json).find((x: unknown) => x && typeof x === "object")
    : null;
  if (first) {
    error = {
      code: first.error_code || "channel_apply_failed",
      message: first.error_message || "Channel configuration could not be applied.",
    };
    sync = "failed";
  }
  if (r.observed_revision != null) {
    observed = {
      observed_revision: r.observed_revision,
      connection_state: r.connection_state,
      diagnostics_state: r.diagnostics_state,
      status_code: r.status_code,
      status_message: r.status_message,
      checks: JSON.parse(r.checks_json),
      status_updated_at: r.received_at,
      status_stale: r.node_status !== "online",
    };
    if (
      !error &&
      (r.applied_manifest_revision ?? 0) >= (r.head_manifest_revision ?? 0) &&
      r.observed_revision >= r.channel_revision
    )
      sync = r.connection_state === "failed" ? "failed" : "applied";
  }
  return {
    channel_id: r.channel_id,
    provider: r.provider,
    enabled: !!r.enabled,
    config: JSON.parse(r.config_json),
    secret_configured: !!r.credential_envelope_json,
    channel_revision: r.channel_revision,
    sync_state: sync,
    apply_error: error,
    observed,
    updated_at: r.updated_at,
  };
}
/** Own the desired manifest, secret-free projections and runtime receipt CAS. */
export class ChannelService {
  constructor(private db: DatabaseSync) {}
  private agent(owner: string, agent: string) {
    const p = one(
      this.db,
      "SELECT node_id FROM agent_profiles WHERE agent_id=? AND owner_id=?",
      agent,
      owner,
    );
    if (!p?.node_id) channelError("channel_not_found", 404);
    return p.node_id as string;
  }
  private key(owner: string, node: string) {
    const k = one(
      this.db,
      "SELECT * FROM node_credential_keys WHERE node_id=? AND owner_id=?",
      node,
      owner,
    );
    if (!k) channelError("channel_credential_key_unavailable", 409);
    return k;
  }
  private row(owner: string, agent: string, channel: string) {
    const r = one(
      this.db,
      `${joined} WHERE ac.channel_id=? AND ac.owner_id=? AND ac.agent_id=?`,
      channel,
      owner,
      agent,
    );
    if (!r) channelError("channel_not_found", 404);
    return r;
  }
  private advance(owner: string, node: string) {
    this.db
      .prepare(
        "INSERT INTO channel_manifest_heads(node_id,owner_id,manifest_revision,applied_manifest_revision,initialized_at,updated_at) VALUES(?,?,0,0,?,?) ON CONFLICT(node_id) DO NOTHING",
      )
      .run(node, owner, now(), now());
    this.db
      .prepare(
        "UPDATE channel_manifest_heads SET manifest_revision=manifest_revision+1,last_apply_error_json=NULL,updated_at=? WHERE node_id=? AND owner_id=?",
      )
      .run(now(), node, owner);
  }
  list(owner: string, agent: string): Row[] {
    this.agent(owner, agent);
    return [
      ...all(
        this.db,
        `${joined} WHERE ac.owner_id=? AND ac.agent_id=? ORDER BY ac.created_at,ac.channel_id`,
        owner,
        agent,
      ).map(view),
      ...all(
        this.db,
        "SELECT * FROM agent_channel_removals WHERE owner_id=? AND agent_id=? AND apply_state!='applied' ORDER BY created_at,channel_id",
        owner,
        agent,
      ).map(removalView),
    ];
  }
  manifest(node: string): Row | null {
    const h = one(this.db, "SELECT * FROM channel_manifest_heads WHERE node_id=?", node);
    if (!h) return null;
    return {
      owner_id: h.owner_id,
      node_id: node,
      manifest_revision: h.manifest_revision,
      channels: all(
        this.db,
        "SELECT * FROM agent_channels WHERE node_id=? AND owner_id=? ORDER BY created_at,channel_id",
        node,
        h.owner_id,
      ).map((r) => ({
        ...Object.fromEntries(
          [
            "channel_id",
            "agent_id",
            "node_id",
            "provider",
            "provider_identity_fingerprint",
            "provider_identity_revision",
            "credential_key_id",
            "credential_revision",
            "channel_revision",
          ].map((k) => [k, r[k]]),
        ),
        enabled: !!r.enabled,
        config: JSON.parse(r.config_json),
        provider_runtime: JSON.parse(r.provider_runtime_json),
        credential_envelope: JSON.parse(r.credential_envelope_json),
      })),
      removals: all(
        this.db,
        "SELECT removal_token,channel_id,agent_id,provider,deletion_manifest_revision FROM agent_channel_removals WHERE node_id=? AND owner_id=? AND apply_state!='applied' ORDER BY created_at,channel_id",
        node,
        h.owner_id,
      ),
    };
  }
  create(owner: string, agent: string, input: Row) {
    return transaction(this.db, () => {
      const node = this.agent(owner, agent),
        key = this.key(owner, node),
        c = config(input.provider, input.config);
      if (
        input.credentials?.mode !== "replace" ||
        typeof input.credentials.app_secret !== "string" ||
        !input.credentials.app_secret.trim()
      )
        channelError("channel_credentials_required");
      if (
        one(
          this.db,
          "SELECT 1 FROM agent_channel_removals WHERE owner_id=? AND agent_id=? AND provider=? AND apply_state!='applied'",
          owner,
          agent,
          input.provider,
        )
      )
        channelError("channel_deletion_pending", 409);
      if (
        one(
          this.db,
          "SELECT 1 FROM agent_channels WHERE owner_id=? AND agent_id=? AND provider=?",
          owner,
          agent,
          input.provider,
        )
      )
        channelError("channel_provider_already_exists", 409);
      const id = `ch_${randomUUID().replaceAll("-", "")}`,
        stamp = now();
      const envelope = sealChannelSecret(
        key.public_key,
        { app_secret: input.credentials.app_secret },
        {
          owner_id: owner,
          node_id: node,
          agent_id: agent,
          channel_id: id,
          provider: input.provider,
          credential_revision: 1,
        },
      );
      this.db
        .prepare(
          "INSERT INTO agent_channels(channel_id,owner_id,agent_id,node_id,provider,enabled,config_json,provider_identity_fingerprint,provider_identity_revision,provider_runtime_json,credential_envelope_json,credential_key_id,credential_revision,channel_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,1,'{}',?,?,1,1,?,?)",
        )
        .run(
          id,
          owner,
          agent,
          node,
          input.provider,
          input.enabled === false ? 0 : 1,
          canonicalJson(c),
          fingerprint(input.provider, c),
          canonicalJson(envelope),
          key.key_id,
          stamp,
          stamp,
        );
      this.advance(owner, node);
      return {
        resource: view(this.row(owner, agent, id)),
        manifest: this.manifest(node)!,
      };
    });
  }
  update(owner: string, agent: string, id: string, input: Row) {
    return transaction(this.db, () => {
      const r = this.row(owner, agent, id);
      if (r.channel_revision !== input.channel_revision)
        channelError("channel_revision_conflict", 409, view(r));
      const c = config(r.provider, input.config),
        changed = c.app_id !== JSON.parse(r.config_json).app_id,
        mode = input.credentials?.mode;
      if (!["keep", "replace"].includes(mode) || (changed && mode !== "replace"))
        channelError("channel_credentials_required");
      if (typeof input.enabled !== "boolean") channelError("channel_config_invalid");
      let envelope = r.credential_envelope_json,
        keyId = r.credential_key_id,
        credentialRevision = r.credential_revision;
      if (mode === "replace") {
        if (
          typeof input.credentials.app_secret !== "string" ||
          !input.credentials.app_secret.trim()
        )
          channelError("channel_credentials_required");
        const k = this.key(owner, r.node_id);
        credentialRevision++;
        keyId = k.key_id;
        envelope = canonicalJson(
          sealChannelSecret(
            k.public_key,
            { app_secret: input.credentials.app_secret },
            {
              owner_id: owner,
              node_id: r.node_id,
              agent_id: agent,
              channel_id: id,
              provider: r.provider,
              credential_revision: credentialRevision,
            },
          ),
        );
      }
      this.db
        .prepare(
          "UPDATE agent_channels SET enabled=?,config_json=?,provider_identity_fingerprint=?,provider_identity_revision=?,provider_runtime_json=?,credential_envelope_json=?,credential_key_id=?,credential_revision=?,channel_revision=?,updated_at=? WHERE channel_id=?",
        )
        .run(
          +input.enabled,
          canonicalJson(c),
          changed ? fingerprint(r.provider, c) : r.provider_identity_fingerprint,
          r.provider_identity_revision + +changed,
          changed ? "{}" : r.provider_runtime_json,
          envelope,
          keyId,
          credentialRevision,
          r.channel_revision + 1,
          now(),
          id,
        );
      this.advance(owner, r.node_id);
      return {
        resource: view(this.row(owner, agent, id)),
        manifest: this.manifest(r.node_id)!,
      };
    });
  }
  delete(owner: string, agent: string, id: string, revision: number) {
    return transaction(this.db, () => {
      const r = this.row(owner, agent, id);
      if (r.channel_revision !== revision) channelError("channel_revision_conflict", 409, view(r));
      this.db.prepare("DELETE FROM agent_channels WHERE channel_id=?").run(id);
      this.advance(owner, r.node_id);
      const h = this.manifest(r.node_id)!;
      this.db
        .prepare(
          "INSERT INTO agent_channel_removals(channel_id,removal_token,owner_id,agent_id,node_id,provider,display_config_json,deleted_channel_revision,deletion_manifest_revision,apply_state,expires_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?,?)",
        )
        .run(
          id,
          `rm_${randomUUID().replaceAll("-", "")}`,
          owner,
          agent,
          r.node_id,
          r.provider,
          canonicalJson({
            app_id_suffix: JSON.parse(r.config_json).app_id.slice(-5),
          }),
          revision,
          h.manifest_revision,
          new Date(Date.now() + 7 * 86400000).toISOString(),
          now(),
          now(),
        );
      return {
        resource: removalView(
          one(this.db, "SELECT * FROM agent_channel_removals WHERE channel_id=?", id)!,
        ),
        manifest: this.manifest(r.node_id)!,
      };
    });
  }
  reconnect(owner: string, agent: string, id: string) {
    const r = this.row(owner, agent, id);
    return {
      resource: view(r),
      node_id: r.node_id,
      channel_revision: r.channel_revision,
    };
  }
  retry(owner: string, agent: string, id: string) {
    this.agent(owner, agent);
    const r = one(
      this.db,
      "SELECT * FROM agent_channel_removals WHERE channel_id=? AND owner_id=? AND agent_id=? AND apply_state!='applied'",
      id,
      owner,
      agent,
    );
    if (!r) channelError("channel_not_found", 404);
    return { resource: removalView(r), manifest: this.manifest(r.node_id)! };
  }
  initialize(node: string) {
    return transaction(this.db, () => {
      const n = one(this.db, "SELECT owner_id FROM nodes WHERE node_id=?", node);
      if (!n?.owner_id) return { state: "waiting_for_owner", manifest: null };
      const h = one(this.db, "SELECT * FROM channel_manifest_heads WHERE node_id=?", node);
      if (!h) {
        this.db
          .prepare(
            "INSERT INTO channel_manifest_heads(node_id,owner_id,manifest_revision,applied_manifest_revision,initialized_at,updated_at) VALUES(?,?,0,0,NULL,?)",
          )
          .run(node, n.owner_id, now());
        return { state: "bootstrap_required", manifest: null };
      }
      if (!h.initialized_at && h.manifest_revision === 0)
        return { state: "bootstrap_required", manifest: null };
      if (!h.initialized_at)
        this.db
          .prepare(
            "UPDATE channel_manifest_heads SET initialized_at=?,updated_at=? WHERE node_id=?",
          )
          .run(now(), now(), node);
      return { state: "initialized", manifest: this.manifest(node) };
    });
  }
  bootstrap(node: string, items: unknown) {
    return transaction(this.db, () => {
      if (!Array.isArray(items)) channelError("channel_bootstrap_invalid");
      const owner = one(this.db, "SELECT owner_id FROM nodes WHERE node_id=?", node)?.owner_id;
      if (!owner) channelError("channel_not_found", 404);
      const k = this.key(owner, node),
        h = one(this.db, "SELECT * FROM channel_manifest_heads WHERE node_id=?", node);
      if (h?.initialized_at)
        return { state: "already_initialized", manifest: this.manifest(node)! };
      this.db.prepare("DELETE FROM agent_channels WHERE owner_id=? AND node_id=?").run(owner, node);
      const seen = new Set();
      for (const r of items) {
        if (
          !r ||
          !r.channel_id ||
          !r.agent_id ||
          r.provider !== "feishu" ||
          r.credential_key_id !== k.key_id ||
          !r.credential_envelope ||
          !Object.keys(r.credential_envelope).length ||
          seen.has(`${r.agent_id}:${r.provider}`)
        )
          channelError("channel_bootstrap_invalid");
        seen.add(`${r.agent_id}:${r.provider}`);
        if (this.agent(owner, r.agent_id) !== node) channelError("channel_not_found", 404);
        const c = config(r.provider, r.config),
          runtime = Object.fromEntries(
            Object.entries(r.provider_runtime ?? {}).filter(([, v]) => typeof v === "string"),
          );
        this.db
          .prepare(
            "INSERT INTO agent_channels(channel_id,owner_id,agent_id,node_id,provider,enabled,config_json,provider_identity_fingerprint,provider_identity_revision,provider_runtime_json,credential_envelope_json,credential_key_id,credential_revision,channel_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,1,?,?,?,1,1,?,?)",
          )
          .run(
            r.channel_id,
            owner,
            r.agent_id,
            node,
            r.provider,
            r.enabled === false ? 0 : 1,
            canonicalJson(c),
            fingerprint(r.provider, c),
            canonicalJson(runtime),
            canonicalJson(r.credential_envelope),
            k.key_id,
            now(),
            now(),
          );
      }
      this.db
        .prepare(
          "INSERT INTO channel_manifest_heads(node_id,owner_id,manifest_revision,applied_manifest_revision,initialized_at,updated_at) VALUES(?,?,1,0,?,?) ON CONFLICT(node_id) DO UPDATE SET owner_id=excluded.owner_id,manifest_revision=1,initialized_at=excluded.initialized_at,updated_at=excluded.updated_at",
        )
        .run(node, owner, now(), now());
      return { state: "initialized", manifest: this.manifest(node)! };
    });
  }
  pruneAppliedRemovals(): number {
    return Number(
      this.db
        .prepare(
          "DELETE FROM agent_channel_removals WHERE apply_state='applied' AND expires_at<=? AND EXISTS(SELECT 1 FROM channel_manifest_heads h WHERE h.node_id=agent_channel_removals.node_id AND h.owner_id=agent_channel_removals.owner_id AND h.applied_manifest_revision>=agent_channel_removals.deletion_manifest_revision)",
        )
        .run(now()).changes,
    );
  }
  recordStatus(p: Row): Row {
    return transaction(this.db, () => {
      const r = one(
        this.db,
        "SELECT ac.*,n.owner_id AS node_owner_id FROM agent_channels ac LEFT JOIN nodes n ON n.node_id=ac.node_id WHERE ac.channel_id=? AND ac.node_id=?",
        p.channel_id,
        p.node_id,
      );
      if (!r) return { outcome: "terminal_channel_removed" };
      if (r.owner_id !== r.node_owner_id) return { outcome: "fatal_owner_mismatch" };
      if (r.channel_revision !== p.channel_revision) return { outcome: "terminal_stale_revision" };
      const current = one(
        this.db,
        "SELECT * FROM agent_channel_status WHERE channel_id=?",
        p.channel_id,
      );
      if (
        !current || current.runtime_incarnation !== p.runtime_incarnation
          ? !(p.instance_started === true && p.status_sequence === 1)
          : p.status_sequence <= current.status_sequence
      )
        return { outcome: "already_current" };
      this.db
        .prepare(
          "INSERT INTO agent_channel_status(channel_id,node_id,observed_revision,runtime_incarnation,status_sequence,connection_state,diagnostics_state,status_code,status_message,checks_json,received_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET node_id=excluded.node_id,observed_revision=excluded.observed_revision,runtime_incarnation=excluded.runtime_incarnation,status_sequence=excluded.status_sequence,connection_state=excluded.connection_state,diagnostics_state=excluded.diagnostics_state,status_code=excluded.status_code,status_message=excluded.status_message,checks_json=excluded.checks_json,received_at=excluded.received_at",
        )
        .run(
          p.channel_id,
          p.node_id,
          p.channel_revision,
          p.runtime_incarnation,
          p.status_sequence,
          p.connection_state || "failed",
          p.diagnostics_state || "unknown",
          p.status_code ?? null,
          p.status_message ?? null,
          canonicalJson(Array.isArray(p.checks) ? p.checks : []),
          now(),
        );
      return {
        outcome: "accepted",
        owner_id: r.owner_id,
        agent_id: r.agent_id,
        channel_id: p.channel_id,
      };
    });
  }
  recordProviderMetadata(p: Row) {
    return transaction(this.db, () => {
      const r = one(
        this.db,
        "SELECT * FROM agent_channels WHERE channel_id=? AND node_id=?",
        p.channel_id,
        p.node_id,
      );
      if (!r) return "terminal_channel_removed";
      if (
        [
          "provider_identity_fingerprint",
          "provider_identity_revision",
          "channel_revision",
          "credential_revision",
        ].some((k) => r[k] !== p[k])
      )
        return "terminal_stale_revision";
      const runtime = JSON.parse(r.provider_runtime_json);
      let changed = false;
      for (const key of ["owner_open_id", "bot_open_id"]) {
        const value = p.provider_runtime_patch?.[key];
        if (typeof value === "string" && value.trim() && !runtime[key]) {
          runtime[key] = value.trim();
          changed = true;
        }
      }
      if (changed)
        this.db
          .prepare("UPDATE agent_channels SET provider_runtime_json=? WHERE channel_id=?")
          .run(canonicalJson(runtime), p.channel_id);
      return changed ? "accepted" : "already_current";
    });
  }
  recordReconcile(p: Row) {
    return transaction(this.db, () => {
      const h = one(this.db, "SELECT * FROM channel_manifest_heads WHERE node_id=?", p.node_id);
      if (!h) channelError("channel_not_found", 404);
      if (p.manifest_revision > h.manifest_revision) channelError("channel_manifest_future", 409);
      if (p.outcome === "applied")
        this.db
          .prepare(
            "UPDATE channel_manifest_heads SET applied_manifest_revision=MAX(applied_manifest_revision,?),last_apply_error_json=CASE WHEN manifest_revision=? THEN NULL ELSE last_apply_error_json END,applied_at=?,updated_at=? WHERE node_id=?",
          )
          .run(p.manifest_revision, p.manifest_revision, now(), now(), p.node_id);
      else if (p.outcome === "retryable_failed")
        this.db
          .prepare(
            "UPDATE channel_manifest_heads SET last_apply_error_json=CASE WHEN manifest_revision=? THEN ? ELSE last_apply_error_json END,updated_at=? WHERE node_id=?",
          )
          .run(p.manifest_revision, canonicalJson(p.failures ?? []), now(), p.node_id);
      else if (p.outcome !== "stale") channelError("channel_reconcile_result_invalid");
      const acks: Row[] = [];
      for (const item of p.removal_outcomes ?? []) {
        if (!item?.removal_token || !item.channel_id) continue;
        const r = one(
          this.db,
          "SELECT * FROM agent_channel_removals WHERE removal_token=? AND channel_id=? AND node_id=?",
          item.removal_token,
          item.channel_id,
          p.node_id,
        );
        let outcome = "fatal_unknown";
        if (!r) {
          const active = one(
            this.db,
            "SELECT 1 FROM agent_channels WHERE channel_id=? AND node_id=?",
            item.channel_id,
            p.node_id,
          );
          if (
            !active &&
            item.deletion_manifest_revision > 0 &&
            Math.max(
              h.applied_manifest_revision,
              p.outcome === "applied" ? p.manifest_revision : 0,
            ) >= item.deletion_manifest_revision
          )
            outcome = "already_applied_by_head";
        } else if (p.manifest_revision >= r.deletion_manifest_revision) {
          if (r.apply_state === "applied") outcome = "already_applied";
          else if (["applied", "already_absent"].includes(item.outcome)) {
            this.db
              .prepare(
                "UPDATE agent_channel_removals SET apply_state='applied',apply_error_code=NULL,apply_error_message=NULL,applied_at=?,updated_at=? WHERE removal_token=?",
              )
              .run(now(), now(), item.removal_token);
            this.db
              .prepare("DELETE FROM agent_channel_status WHERE channel_id=?")
              .run(item.channel_id);
            outcome = "accepted";
          } else if (item.outcome === "failed") {
            this.db
              .prepare(
                "UPDATE agent_channel_removals SET apply_state='failed',apply_error_code=?,apply_error_message=?,updated_at=? WHERE removal_token=?",
              )
              .run(item.error_code ?? null, item.error_message ?? null, now(), item.removal_token);
            outcome = "accepted";
          }
        }
        acks.push({ removal_token: item.removal_token, outcome });
      }
      return {
        head_outcome: p.outcome === "stale" ? "already_applied" : "accepted",
        removal_token_outcomes: acks,
      };
    });
  }
}
export function registerChannelRoutes(app: FastifyInstance, ctx: ImContext) {
  const service = new ChannelService(ctx.db),
    push = (manifest: Row) =>
      ctx.gateway.send(manifest.node_id, {
        type: "channel.reconcile",
        payload: { ...manifest, request_id: randomUUID().replaceAll("-", "") },
      });
  app.get("/im/v1/agents/:agent_id/channels", async (req) =>
    service.list((await ctx.identity.authenticateRequest(req)).owner_id, params(req).agent_id),
  );
  app.post("/im/v1/agents/:agent_id/channels", async (req, reply) => {
    const result = service.create(
      (await ctx.identity.authenticateRequest(req)).owner_id,
      params(req).agent_id,
      body(req),
    );
    push(result.manifest);
    return reply.code(201).send(result.resource);
  });
  app.patch("/im/v1/agents/:agent_id/channels/:channel_id", async (req) => {
    const p = params(req),
      result = service.update(
        (await ctx.identity.authenticateRequest(req)).owner_id,
        p.agent_id,
        p.channel_id,
        body(req),
      );
    push(result.manifest);
    return result.resource;
  });
  app.delete("/im/v1/agents/:agent_id/channels/:channel_id", async (req) => {
    const p = params(req),
      revision = Number(query(req).channel_revision);
    if (!Number.isInteger(revision) || revision < 1) channelError("channel_revision_invalid");
    const result = service.delete(
      (await ctx.identity.authenticateRequest(req)).owner_id,
      p.agent_id,
      p.channel_id,
      revision,
    );
    push(result.manifest);
    return result.resource;
  });
  app.post("/im/v1/agents/:agent_id/channels/:channel_id/actions/reconnect", async (req) => {
    const p = params(req),
      r = service.reconnect(
        (await ctx.identity.authenticateRequest(req)).owner_id,
        p.agent_id,
        p.channel_id,
      );
    if (
      !ctx.gateway.send(r.node_id, {
        type: "channel.reconnect",
        payload: {
          channel_id: p.channel_id,
          channel_revision: r.channel_revision,
        },
      })
    )
      channelError("channel_node_offline", 409);
    return r.resource;
  });
  app.post("/im/v1/agents/:agent_id/channel-removals/:channel_id/actions/retry", async (req) => {
    const p = params(req),
      r = service.retry(
        (await ctx.identity.authenticateRequest(req)).owner_id,
        p.agent_id,
        p.channel_id,
      );
    if (!push(r.manifest)) channelError("channel_node_offline", 409);
    return r.resource;
  });
}
