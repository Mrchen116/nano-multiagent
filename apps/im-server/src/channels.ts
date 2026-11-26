import { requireSettingsNodeOnline } from "./agent-settings.js";
import { agentAvailable } from "./identity.js";
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
import { sortedJsonUtf8 } from '@nano/product-contracts/serialization';

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
  cipher.setAAD(Buffer.from(sortedJsonUtf8(aad)));
  const ciphertext = Buffer.concat([
    cipher.update(sortedJsonUtf8(secret)),
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
  if (provider === "feishu") {
    if (!input || typeof input.app_id !== "string" || !input.app_id.trim())
      channelError("channel_config_invalid");
    return { app_id: input.app_id.trim() };
  }
  if (provider === "wechat") {
    if (
      !input ||
      typeof input.bot_id !== "string" ||
      !input.bot_id.trim() ||
      typeof input.owner_user_id !== "string" ||
      !input.owner_user_id.trim() ||
      typeof input.base_url !== "string" ||
      !input.base_url.trim()
    )
      channelError("channel_config_invalid");
    return {
      bot_id: input.bot_id.trim(),
      owner_user_id: input.owner_user_id.trim(),
      base_url: input.base_url.trim(),
    };
  }
  channelError("channel_provider_unsupported");
}
function fingerprint(provider: string, c: Row) {
  if (provider === "wechat") {
    return createHash("sha256")
      .update(`wechat\0${c.bot_id}\0${c.owner_user_id}`)
      .digest("hex");
  }
  return createHash("sha256").update(`${provider}\0${c.app_id}`).digest("hex");
}
function removalDisplayConfig(provider: string, c: Row): Row {
  if (provider === "wechat") {
    return {
      bot_id_suffix: String(c.bot_id ?? "").slice(-6),
      owner_user_id_suffix: String(c.owner_user_id ?? "").slice(-4),
    };
  }
  return { app_id_suffix: String(c.app_id ?? "").slice(-5) };
}

/** Resolves the bound owner's external platform user ID from persisted channel columns. */
export function externalChannelOwnerId(row: Row): string | undefined {
  if (row.provider === "wechat") {
    const owner = JSON.parse(row.config_json).owner_user_id;
    return typeof owner === "string" && owner ? owner : undefined;
  }
  if (row.provider === "feishu") {
    const owner = JSON.parse(row.provider_runtime_json).owner_open_id;
    return typeof owner === "string" && owner ? owner : undefined;
  }
  return undefined;
}

/** Verifies whether an `agent_channels` row owns a persisted shadow `conversations` record. */
export function matchesExternalChannel(row: Row, chat: Row): boolean {
  if (row.provider !== chat.external_source) return false;
  const cfg = JSON.parse(row.config_json);
  if (row.provider === "feishu") {
    return (
      typeof cfg.app_id === "string" &&
      Boolean(cfg.app_id) &&
      String(chat.external_chat_id).startsWith(
        `feishu:${cfg.app_id}:${chat.type === "group" ? "group" : "dm"}:`,
      )
    );
  }
  if (row.provider === "wechat") {
    return (
      chat.type === "direct" &&
      typeof cfg.bot_id === "string" &&
      Boolean(cfg.bot_id) &&
      typeof cfg.owner_user_id === "string" &&
      Boolean(cfg.owner_user_id) &&
      chat.external_chat_id === `wechat:${cfg.bot_id}:dm:${cfg.owner_user_id}`
    );
  }
  return false;
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
      "SELECT * FROM agent_profiles WHERE agent_id=? AND owner_id=?",
      agent,
      owner,
    );
    if (!p?.node_id || !agentAvailable(this.db, p)) channelError("channel_not_found", 404);
    if (one(this.db,'SELECT 1 FROM agent_deletions WHERE agent_id=?',agent)) channelError('agent_deletion_requested',409);
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
    this.agent(owner, agent);
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
      if (input?.provider === "wechat")
        channelError("channel_interactive_setup_required", 422);
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
          sortedJsonUtf8(c),
          fingerprint(input.provider, c),
          sortedJsonUtf8(envelope),
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
        serializedConfig = sortedJsonUtf8(c),
        changed = serializedConfig !== r.config_json,
        mode = input.credentials?.mode;
      if (r.provider === "wechat" && (mode !== "keep" || changed))
        channelError("channel_interactive_setup_required", 422);
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
        envelope = sortedJsonUtf8(
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
          sortedJsonUtf8(c),
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
          sortedJsonUtf8(
            removalDisplayConfig(r.provider, JSON.parse(r.config_json)),
          ),
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
          !["feishu", "wechat"].includes(r.provider) ||
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
            sortedJsonUtf8(c),
            fingerprint(r.provider, c),
            sortedJsonUtf8(runtime),
            sortedJsonUtf8(r.credential_envelope),
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
          sortedJsonUtf8(Array.isArray(p.checks) ? p.checks : []),
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
          .run(sortedJsonUtf8(runtime), p.channel_id);
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
          .run(p.manifest_revision, sortedJsonUtf8(p.failures ?? []), now(), p.node_id);
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
  preflightWeChatSetup(
    owner: string,
    agent: string,
    editingChannelId?: string,
    expectedRevision?: number,
  ): string {
    const node = this.agent(owner, agent);
    this.key(owner, node);
    if (
      one(
        this.db,
        "SELECT 1 FROM agent_channel_removals WHERE owner_id=? AND agent_id=? AND provider='wechat' AND apply_state!='applied'",
        owner,
        agent,
      )
    )
      channelError("channel_deletion_pending", 409);
    if (editingChannelId) {
      const r = this.row(owner, agent, editingChannelId);
      if (r.provider !== "wechat") channelError("channel_provider_unsupported");
      if (expectedRevision !== undefined && r.channel_revision !== expectedRevision)
        channelError("channel_revision_conflict", 409, view(r));
    } else if (
      one(
        this.db,
        "SELECT 1 FROM agent_channels WHERE owner_id=? AND agent_id=? AND provider='wechat'",
        owner,
        agent,
      )
    ) {
      channelError("channel_provider_already_exists", 409);
    }
    return node;
  }
  completeWeChatSetup(
    owner: string,
    agent: string,
    binding: { bot_token: string; bot_id: string; owner_user_id: string; base_url: string },
    editingChannelId?: string,
    expectedRevision?: number,
  ) {
    return transaction(this.db, () => {
      const node = this.preflightWeChatSetup(owner, agent, editingChannelId, expectedRevision);
      const k = this.key(owner, node);
      const c = config("wechat", {
        bot_id: binding.bot_id,
        owner_user_id: binding.owner_user_id,
        base_url: binding.base_url,
      });
      const serializedConfig = sortedJsonUtf8(c);
      const nextFp = fingerprint("wechat", c);
      if (editingChannelId) {
        const r = this.row(owner, agent, editingChannelId);
        const identityChanged = serializedConfig !== r.config_json;
        const nextCredRev = r.credential_revision + 1;
        const envelope = sealChannelSecret(
          k.public_key,
          { bot_token: binding.bot_token },
          {
            owner_id: owner,
            node_id: r.node_id,
            agent_id: agent,
            channel_id: editingChannelId,
            provider: "wechat",
            credential_revision: nextCredRev,
          },
        );
        this.db
          .prepare(
            "UPDATE agent_channels SET enabled=1,config_json=?,provider_identity_fingerprint=?,provider_identity_revision=?,provider_runtime_json='{}',credential_envelope_json=?,credential_key_id=?,credential_revision=?,channel_revision=?,updated_at=? WHERE channel_id=?",
          )
          .run(
            serializedConfig,
            nextFp,
            r.provider_identity_revision + +identityChanged,
            sortedJsonUtf8(envelope),
            k.key_id,
            nextCredRev,
            r.channel_revision + 1,
            now(),
            editingChannelId,
          );
        this.advance(owner, r.node_id);
        return {
          resource: view(this.row(owner, agent, editingChannelId)),
          manifest: this.manifest(r.node_id)!,
        };
      }
      const id = `ch_${randomUUID().replaceAll("-", "")}`,
        stamp = now();
      const envelope = sealChannelSecret(
        k.public_key,
        { bot_token: binding.bot_token },
        {
          owner_id: owner,
          node_id: node,
          agent_id: agent,
          channel_id: id,
          provider: "wechat",
          credential_revision: 1,
        },
      );
      this.db
        .prepare(
          "INSERT INTO agent_channels(channel_id,owner_id,agent_id,node_id,provider,enabled,config_json,provider_identity_fingerprint,provider_identity_revision,provider_runtime_json,credential_envelope_json,credential_key_id,credential_revision,channel_revision,created_at,updated_at) VALUES(?,?,?,?,'wechat',1,?,?,1,'{}',?,?,1,1,?,?)",
        )
        .run(
          id,
          owner,
          agent,
          node,
          serializedConfig,
          nextFp,
          sortedJsonUtf8(envelope),
          k.key_id,
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
}
export function registerChannelRoutes(app: FastifyInstance, ctx: ImContext) {
  const service = new ChannelService(ctx.db),
    push = (manifest: Row) =>
      ctx.gateway.send(manifest.node_id, {
        type: "channel.reconcile",
        payload: { ...manifest, request_id: randomUUID().replaceAll("-", "") },
      });
  const writable = (req: import('fastify').FastifyRequest, removal = false) => {
    const owner = ctx.identity.authenticateRequest(req).owner_id, p = params(req);
    const resources = service.list(owner,p.agent_id);
    if (p.channel_id && !resources.some(resource => resource.channel_id === p.channel_id && (resource.resource_type === 'removal') === removal))
      channelError('channel_not_found',404);
    const profile = one(ctx.db,'SELECT * FROM agent_profiles WHERE agent_id=? AND owner_id=?',p.agent_id,owner)!;
    requireSettingsNodeOnline(ctx,profile);
    return owner;
  };
  app.get("/im/v1/agents/:agent_id/channels", async (req) =>
    service.list((await ctx.identity.authenticateRequest(req)).owner_id, params(req).agent_id),
  );
  app.post("/im/v1/agents/:agent_id/channels", async (req, reply) => {
    const result = service.create(
      writable(req),
      params(req).agent_id,
      body(req),
    );
    push(result.manifest);
    return reply.code(201).send(result.resource);
  });
  app.patch("/im/v1/agents/:agent_id/channels/:channel_id", async (req) => {
    const p = params(req),
      result = service.update(
        writable(req),
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
      writable(req),
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
        writable(req),
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
        writable(req,true),
        p.agent_id,
        p.channel_id,
      );
    if (!push(r.manifest)) channelError("channel_node_offline", 409);
    return r.resource;
  });
  const wechatSetups = new Map<
    string,
    { owner: string; agentId: string; editingChannelId?: string; channelRevision?: number; committed?: Row }
  >();
  app.post("/im/v1/agents/:agent_id/channels/wechat/setup", async (req) => {
    const owner = writable(req),
      agentId = params(req).agent_id,
      b = body(req) ?? {},
      action = b.action;
    if (!["start", "status", "verify_code", "cancel"].includes(action))
      channelError("channel_config_invalid");
    const editingChannelId =
      typeof b.editing_channel_id === "string" && b.editing_channel_id.trim()
        ? b.editing_channel_id.trim()
        : undefined;
    const channelRevision =
      b.channel_revision !== undefined ? Number(b.channel_revision) : undefined;
    if (channelRevision !== undefined && (!Number.isInteger(channelRevision) || channelRevision < 1))
      channelError("channel_revision_invalid");

    if (action === "start") {
      const nodeId = service.preflightWeChatSetup(owner, agentId, editingChannelId, channelRevision);
      const reply = await ctx.gateway.request(nodeId, "node.wechat.setup.request", {
        action: "start",
        agent_id: agentId,
        ...(editingChannelId ? { editing_channel_id: editingChannelId } : {}),
      });
      if (reply.setup_id) {
        wechatSetups.set(reply.setup_id, { owner, agentId, editingChannelId, channelRevision });
      }
      if (reply.state === "confirmed" && reply.binding) {
        const committed = service.completeWeChatSetup(owner, agentId, reply.binding, editingChannelId, channelRevision);
        push(committed.manifest);
        if (reply.setup_id) wechatSetups.set(reply.setup_id, { owner, agentId, committed: committed.resource });
        return { setup_id: reply.setup_id, state: "confirmed", channel: committed.resource };
      }
      const { binding: _neverEcho, ...safe } = reply;
      return safe;
    }

    const setupId = typeof b.setup_id === "string" && b.setup_id.trim() ? b.setup_id.trim() : "";
    if (!setupId) channelError("channel_config_invalid");
    const tracked = wechatSetups.get(setupId);
    if (tracked && (tracked.owner !== owner || tracked.agentId !== agentId))
      channelError("channel_not_found", 404);
    if (tracked?.committed && (action === "status" || action === "verify_code")) {
      return { setup_id: setupId, state: "confirmed", channel: tracked.committed };
    }
    const profile = one(ctx.db, "SELECT node_id FROM agent_profiles WHERE agent_id=? AND owner_id=?", agentId, owner);
    if (!profile?.node_id) channelError("channel_not_found", 404);

    let rpcPayload: Parameters<typeof ctx.gateway.request<"node.wechat.setup.request">>[2];
    if (action === "verify_code") {
      const code = typeof b.code === "string" ? b.code.trim() : "";
      if (!/^\d{1,12}$/.test(code)) channelError("channel_verify_code_invalid", 422);
      rpcPayload = { action: "verify_code", agent_id: agentId, setup_id: setupId, code };
    } else if (action === "cancel") {
      rpcPayload = { action: "cancel", agent_id: agentId, setup_id: setupId };
    } else {
      rpcPayload = { action: "status", agent_id: agentId, setup_id: setupId };
    }

    const reply = await ctx.gateway.request(profile.node_id, "node.wechat.setup.request", rpcPayload);
    if (action === "cancel") wechatSetups.delete(setupId);
    if (reply.state === "confirmed" && reply.binding) {
      const effectiveEditId = editingChannelId ?? tracked?.editingChannelId;
      const effectiveRev = channelRevision ?? tracked?.channelRevision;
      const committed = service.completeWeChatSetup(owner, agentId, reply.binding, effectiveEditId, effectiveRev);
      push(committed.manifest);
      wechatSetups.set(setupId, { owner, agentId, committed: committed.resource });
      return { setup_id: setupId, state: "confirmed", channel: committed.resource };
    }
    const { binding: _neverEcho, ...safe } = reply;
    return safe;
  });
}
