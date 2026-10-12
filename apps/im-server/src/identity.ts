import {
  createHash,
  createHmac,
  timingSafeEqual,
  randomBytes,
  randomInt,
  createPublicKey,
  generateKeyPairSync,
  diffieHellman,
  hkdfSync,
  createCipheriv,
} from "node:crypto";
import type { DatabaseSync, SQLInputValue } from "node:sqlite";
import type { FastifyRequest } from "fastify";
import { Worker } from "node:worker_threads";
import { createRequire } from "node:module";

type Row = Record<string, any>;
export type User = Row & {
  id: string;
  owner_id: string;
  membership_status: string;
  is_company_admin: boolean;
  owned_node_ids: string[];
};
export type RuntimeIdentity = {
  owner_id: string;
  node_id: string;
  node_epoch: number;
};
export class IdentityError extends Error {
  constructor(
    public statusCode: number,
    public detail: unknown,
    public retry_after?: number,
  ) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}
export const digest = (value: string) => createHash("sha256").update(value).digest("hex");
const secret = (size = 32) => randomBytes(size).toString("base64url");
const now = () => Math.floor(Date.now() / 1000);
const bcryptModule = createRequire(import.meta.url).resolve("bcryptjs");
const equal = (a: string, b: string) =>
  Buffer.byteLength(a) === Buffer.byteLength(b) && timingSafeEqual(Buffer.from(a), Buffer.from(b));
/** Match Python json.dumps(sort_keys=True, separators=(',', ':')) for device proofs. */
export function canonical(value: any): string {
  const sorted = (v: any): any =>
    Array.isArray(v)
      ? v.map(sorted)
      : v && typeof v === "object"
        ? Object.fromEntries(
            Object.keys(v)
              .sort()
              .map((k) => [k, sorted(v[k])]),
          )
        : v;
  return JSON.stringify(sorted(value)).replace(
    /[\u007f-\uffff]/g,
    (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"),
  );
}
export function bearer(request: Pick<FastifyRequest, "headers">): string {
  const match = /^Bearer\s+(.+)$/i.exec(request.headers.authorization ?? "");
  if (!match?.[1]?.trim()) throw new IdentityError(401, "missing or invalid authorization header");
  return match[1].trim();
}
const publicKey = (encoded: string) => {
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)) throw new IdentityError(409, "invalid device key");
  const raw = Buffer.from(encoded, "base64");
  if (raw.length !== 32) throw new IdentityError(409, "invalid device key");
  return createPublicKey({
    key: Buffer.concat([Buffer.from("302a300506032b656e032100", "hex"), raw]),
    format: "der",
    type: "spki",
  });
};

/** Own persisted identity, session rotation and device proof state. */
export class Identity {
  readonly refreshTtl = 7 * 24 * 60 * 60;
  private passwordWorkers = 0;
  constructor(
    readonly db: DatabaseSync,
    private jwtSecret: string,
  ) {
    if (!jwtSecret) throw new Error("jwt_secret must be non-empty");
  }
  get(sql: string, ...params: SQLInputValue[]): Row | undefined {
    return this.db.prepare(sql).get(...params) as Row | undefined;
  }
  all(sql: string, ...params: SQLInputValue[]): Row[] {
    return this.db.prepare(sql).all(...params) as Row[];
  }
  run(sql: string, ...params: SQLInputValue[]) {
    return this.db.prepare(sql).run(...params);
  }
  transaction<T>(fn: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }
  user(id: string): User | undefined {
    const row = this.get("SELECT * FROM users WHERE id=?", id);
    if (!row) return undefined;
    const owned = this.all(
      "SELECT node_id FROM nodes WHERE owner_id=? ORDER BY rowid",
      row.owner_id,
    ).map((n) => n.node_id);
    return {
      ...row,
      id: row.id,
      owner_id: row.owner_id,
      membership_status: row.membership_status,
      is_company_admin: Boolean(row.is_company_admin),
      owned_node_ids: owned,
      default_entry_node_id: owned.includes(row.default_entry_node_id)
        ? row.default_entry_node_id
        : (owned[0] ?? null),
    };
  }
  publicUser(user: User): Row {
    return Object.fromEntries(
      [
        "id",
        "username",
        "display_name",
        "owner_id",
        "locale",
        "default_entry_node_id",
        "owned_node_ids",
        "created_at",
        "membership_status",
        "is_company_admin",
      ].map((k) => [k, user[k]]),
    );
  }
  private async passwordWork<T>(
    operation: "hash" | "compare",
    password: string,
    hash?: string,
  ): Promise<T> {
    if (this.passwordWorkers >= 2) throw new IdentityError(429, "temporarily rate limited", 1);
    this.passwordWorkers++;
    try {
      return await new Promise<T>((resolve, reject) => {
        // Keep password CPU work outside the server event loop, with no unbounded queue.
        const worker = new Worker(
          `const {parentPort,workerData}=require('node:worker_threads'); const bcrypt=require(workerData.module); try { parentPort.postMessage({value:workerData.operation==='hash'?bcrypt.hashSync(workerData.password,12):bcrypt.compareSync(workerData.password,workerData.hash)}); } catch(error) { parentPort.postMessage({error:String(error)}); }`,
          {
            eval: true,
            workerData: { module: bcryptModule, operation, password, hash },
          },
        );
        worker.once("message", (result) =>
          result.error ? reject(new Error(result.error)) : resolve(result.value),
        );
        worker.once("error", reject);
        worker.once("exit", (code) => {
          if (code !== 0) reject(new Error("password worker failed"));
        });
      });
    } finally {
      this.passwordWorkers--;
    }
  }
  async register(username: string, password: string, displayName: string, locale = "en") {
    username = username.trim();
    displayName = displayName.trim();
    if (!username) throw new IdentityError(422, "username must be non-empty");
    if (username === "system" || username.startsWith("agent:") || username.startsWith("shadow:"))
      throw new IdentityError(422, "username uses a reserved runtime identity");
    if (!displayName) throw new IdentityError(422, "display_name must be non-empty");
    if ([...password].length < 8)
      throw new IdentityError(422, "password must be at least 8 characters");
    if (Buffer.byteLength(password) > 72)
      throw new IdentityError(422, "password must be at most 72 UTF-8 bytes");
    const hash = await this.passwordWork<string>("hash", password);
    const id =
      "u_" +
      Array.from({ length: 8 }, () => "abcdefghijklmnopqrstuvwxyz0123456789"[randomInt(36)]).join(
        "",
      );
    try {
      this.run(
        "INSERT INTO users(id,username,display_name,owner_id,password_hash,locale,created_at) VALUES(?,?,?,?,?,?,?)",
        id,
        username,
        displayName,
        id,
        hash,
        locale.trim() || "en",
        new Date().toISOString(),
      );
    } catch (error) {
      if (String(error).includes("users.username"))
        throw new IdentityError(409, "username already exists");
      throw error;
    }
    return this.issuePair(this.user(id)!);
  }
  async login(username: string, password: string) {
    const snapshot = this.get("SELECT * FROM users WHERE username=?", username.trim());
    const verified = await this.passwordWork<boolean>(
      "compare",
      password,
      snapshot?.password_hash || "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxaT4eLQiYxL6vO9eCzH8K9vAWe",
    );
    const fresh = snapshot ? this.user(snapshot.id) : undefined;
    if (
      Buffer.byteLength(password) > 72 ||
      !verified ||
      !fresh ||
      fresh.password_hash !== snapshot?.password_hash ||
      fresh.auth_epoch !== snapshot?.auth_epoch
    )
      throw new IdentityError(401, "invalid credentials");
    return this.issuePair(fresh);
  }
  private sign(payload: Row) {
    const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
    const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
    return `${header}.${body}.${createHmac("sha256", this.jwtSecret).update(`${header}.${body}`).digest("base64url")}`;
  }
  validSession(sid: string): Row | undefined {
    return this.get(
      "SELECT s.* FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.session_id=? AND s.revoked=0 AND s.expires_at>? AND s.epoch=u.auth_epoch AND u.password_hash IS NOT NULL",
      sid,
      now(),
    );
  }
  decode(token: string, type: "access" | "refresh"): Row {
    let payload: Row;
    try {
      const [header, body, signature, extra] = token.split(".");
      if (
        !header ||
        !body ||
        !signature ||
        extra !== undefined ||
        JSON.parse(Buffer.from(header, "base64url").toString()).alg !== "HS256" ||
        !equal(
          signature,
          createHmac("sha256", this.jwtSecret).update(`${header}.${body}`).digest("base64url"),
        )
      )
        throw Error();
      payload = JSON.parse(Buffer.from(body, "base64url").toString());
      if (
        typeof payload.exp !== "number" ||
        payload.exp <= now() ||
        (payload.nbf !== undefined && payload.nbf > now()) ||
        (payload.iat !== undefined && payload.iat > now()) ||
        payload.type !== type ||
        typeof payload.jti !== "string" ||
        typeof payload.sid !== "string" ||
        typeof payload.sub !== "string" ||
        !Number.isInteger(payload.epoch)
      )
        throw Error();
    } catch {
      throw new IdentityError(401, "invalid or expired token");
    }
    const session = this.validSession(payload.sid);
    if (
      !session ||
      session.user_id !== payload.sub ||
      session.epoch !== payload.epoch ||
      (type === "refresh" && !equal(session.refresh_hash, digest(payload.jti)))
    )
      throw new IdentityError(401, "session revoked or expired");
    return payload;
  }
  accessSession(token: string) {
    return this.decode(token, "access");
  }
  authenticateRequest(request: Pick<FastifyRequest, "headers">, requireActive = true): User {
    const user = this.user(this.accessSession(bearer(request)).sub)!;
    if (requireActive && user.membership_status !== "active")
      throw new IdentityError(403, {
        code: "company_membership_required",
        membership_status: user.membership_status,
      });
    return user;
  }
  private issuePair(user: User, sid?: string, oldJti?: string) {
    const exp = now() + this.refreshTtl,
      jti = randomBytes(24).toString("hex");
    if (sid) {
      if (
        this.run(
          "UPDATE auth_sessions SET refresh_hash=?,expires_at=? WHERE session_id=? AND refresh_hash=? AND revoked=0 AND expires_at>? AND epoch=(SELECT auth_epoch FROM users WHERE id=auth_sessions.user_id)",
          digest(jti),
          exp,
          sid,
          digest(oldJti!),
          now(),
        ).changes !== 1
      )
        throw new IdentityError(401, "refresh token already used");
    } else {
      sid = secret(24);
      this.run(
        "DELETE FROM auth_sessions WHERE session_id IN (SELECT session_id FROM auth_sessions WHERE expires_at<=? LIMIT 100)",
        now(),
      );
      this.run(
        "INSERT INTO auth_sessions(session_id,user_id,epoch,refresh_hash,expires_at) VALUES(?,?,?,?,?)",
        sid,
        user.id,
        user.auth_epoch,
        digest(jti),
        exp,
      );
    }
    const common = { sub: user.id, sid, epoch: user.auth_epoch, iat: now() };
    return {
      access_token: this.sign({
        ...common,
        type: "access",
        exp: now() + 900,
        jti: randomBytes(16).toString("hex"),
      }),
      refresh_token: this.sign({ ...common, type: "refresh", exp, jti }),
      user: this.publicUser(user),
    };
  }
  refresh(token: string) {
    const p = this.decode(token, "refresh");
    return this.issuePair(this.user(p.sub)!, p.sid, p.jti);
  }
  logout(token: string): string {
    const p = this.decode(token, "refresh");
    this.transaction(() => {
      this.run("UPDATE auth_sessions SET revoked=1 WHERE session_id=?", p.sid);
      this.run("DELETE FROM auth_ws_tickets WHERE session_id=?", p.sid);
    });
    return p.sid;
  }
  issueTicket(sid: string): string {
    const ticket = secret();
    this.run("DELETE FROM auth_ws_tickets WHERE expires_at<=?", now());
    if (
      this.run(
        "INSERT INTO auth_ws_tickets(ticket_hash,session_id,expires_at) SELECT ?,s.session_id,? FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.session_id=? AND s.revoked=0 AND s.epoch=u.auth_epoch AND s.expires_at>? AND u.membership_status='active'",
        digest(ticket),
        now() + 30,
        sid,
        now(),
      ).changes !== 1
    )
      throw new IdentityError(401, "inactive session");
    return ticket;
  }
  consumeTicket(ticket: string): Row | undefined {
    const row = this.get(
      "DELETE FROM auth_ws_tickets WHERE ticket_hash=? AND expires_at>? RETURNING session_id",
      digest(ticket),
      now(),
    );
    return row ? this.validSession(row.session_id) : undefined;
  }
  rateLimit(key: string, limit: number, window: number, consume = true) {
    const bucket = digest(key),
      time = now();
    this.run(
      "DELETE FROM auth_rate_limits WHERE bucket IN (SELECT bucket FROM auth_rate_limits WHERE expires_at<=? LIMIT 100)",
      time,
    );
    const row = this.get("SELECT count,expires_at FROM auth_rate_limits WHERE bucket=?", bucket);
    if (row && row.count >= limit && row.expires_at > time)
      throw new IdentityError(429, "temporarily rate limited", row.expires_at - time);
    if (consume)
      this.run(
        "INSERT INTO auth_rate_limits(bucket,count,expires_at) VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=CASE WHEN expires_at<=? THEN 1 ELSE count+1 END, expires_at=CASE WHEN expires_at<=? THEN excluded.expires_at ELSE expires_at END",
        bucket,
        time + window,
        time,
        time,
      );
  }
  clearLimit(key: string) {
    this.run("DELETE FROM auth_rate_limits WHERE bucket=?", digest(key));
  }
  initializeCompany(adminId: string, activeIds: string[] = []) {
    this.transaction(() => {
      const members = [...new Set([adminId, ...activeIds])].sort(),
        encoded = canonical(members);
      const existing = this.get("SELECT * FROM company_initialization WHERE singleton=1");
      if (existing) {
        if (existing.admin_id !== adminId || existing.active_ids !== encoded)
          throw new IdentityError(409, "company already initialized with a different member list");
        return;
      }
      for (const id of members)
        if (!this.user(id)?.password_hash)
          throw new IdentityError(409, "initial members must be existing human accounts");
      for (const id of members) {
        this.run(
          "UPDATE users SET membership_status='active',is_company_admin=? WHERE id=?",
          Number(id === adminId),
          id,
        );
        this.run(
          "INSERT INTO company_member_events(actor_id,user_id,action) VALUES('local_operator',?,'initialize')",
          id,
        );
      }
      this.run("INSERT INTO company_initialization VALUES(1,?,?)", adminId, encoded);
    });
  }
  transition(actorId: string, userId: string, action: string): User {
    return this.transaction(() => {
      const actor = this.user(actorId),
        target = this.user(userId);
      if (!actor?.is_company_admin || actor.membership_status !== "active")
        throw new IdentityError(403, "company administrator required");
      if (!target?.password_hash) throw new IdentityError(404, "member not found");
      let next: string;
      if (action === "approve") {
        if (target.membership_status === "suspended")
          throw new IdentityError(409, "suspended member cannot be approved");
        next = "active";
        this.run("UPDATE users SET membership_status='active' WHERE id=?", userId);
      } else if (action === "suspend") {
        if (target.membership_status === "pending")
          throw new IdentityError(409, "only active members can be suspended");
        if (
          target.membership_status === "active" &&
          target.is_company_admin &&
          this.get(
            "SELECT count(*) AS n FROM users WHERE membership_status='active' AND is_company_admin=1",
          )!.n <= 1
        )
          throw new IdentityError(409, "cannot suspend the last active administrator");
        next = "suspended";
        if (target.membership_status !== next) {
          this.run(
            "UPDATE users SET membership_status='suspended',auth_epoch=auth_epoch+1 WHERE id=?",
            userId,
          );
          this.run(
            "UPDATE node_binding_state SET node_epoch=node_epoch+1,runtime_token_hash=NULL WHERE owner_id=?",
            userId,
          );
        }
        this.run("UPDATE auth_sessions SET revoked=1 WHERE user_id=?", userId);
        this.run(
          "DELETE FROM auth_ws_tickets WHERE session_id IN (SELECT session_id FROM auth_sessions WHERE user_id=?)",
          userId,
        );
      } else throw new IdentityError(404, "unknown membership operation");
      if (target.membership_status !== next)
        this.run(
          "INSERT INTO company_member_events(actor_id,user_id,action) VALUES(?,?,?)",
          actorId,
          userId,
          action,
        );
      return this.user(userId)!;
    });
  }
  enrollDevice(nodeId: string, publicText: string, keyId: string) {
    publicKey(publicText);
    if (
      keyId !==
      "sha256:" + createHash("sha256").update(Buffer.from(publicText, "base64")).digest("hex")
    )
      throw new IdentityError(409, "key_id does not match the public key");
    this.transaction(() => {
      const node = this.get("SELECT owner_id FROM nodes WHERE node_id=?", nodeId);
      if (!node) throw new IdentityError(404, "node not found");
      const existing = this.get(
        "SELECT public_key FROM node_credential_keys WHERE node_id=?",
        nodeId,
      );
      if (existing && existing.public_key !== publicText)
        throw new IdentityError(
          409,
          "registered device key differs; key replacement is not supported",
        );
      this.run(
        "INSERT OR IGNORE INTO node_credential_keys VALUES (?,?,?,'X25519-HKDF-SHA256-AES-256-GCM',?,datetime('now'))",
        nodeId,
        node.owner_id || "",
        keyId,
        publicText,
      );
      this.run(
        "INSERT OR IGNORE INTO node_binding_state(node_id,node_epoch,owner_id) VALUES (?,0,?)",
        nodeId,
        node.owner_id || "",
      );
    });
  }
  authenticateRuntime(token: string): RuntimeIdentity | null {
    const row = this.get(
      "SELECT s.* FROM node_binding_state s JOIN nodes n ON n.node_id=s.node_id AND n.owner_id=s.owner_id JOIN users u ON u.owner_id=s.owner_id AND u.membership_status='active' WHERE s.runtime_token_hash=?",
      digest(token),
    );
    return row
      ? {
          owner_id: row.owner_id,
          node_id: row.node_id,
          node_epoch: row.node_epoch,
        }
      : null;
  }
  private operation(id: string, token: string): Row {
    const op = this.get("SELECT * FROM node_binding_operations WHERE operation_id=?", id);
    if (!op || op.expires_at <= Date.now() / 1000 || !equal(op.operation_token_hash, digest(token)))
      throw new IdentityError(409, "binding operation invalid or expired");
    return op;
  }
  private active(id: string): User {
    const user = this.user(id);
    if (!user || user.membership_status !== "active")
      throw new IdentityError(409, "receiving account must be active");
    return user;
  }
  private snapshot(nodeId: string): Row {
    return Object.fromEntries(
      [
        "agent_profiles",
        "channel_manifest_heads",
        "agent_channels",
        "agent_channel_removals",
        "agent_config_operations",
      ].map((table) => [
        table,
        this.all(`SELECT * FROM ${table} WHERE node_id=? ORDER BY rowid`, nodeId),
      ]),
    );
  }
  deviceStart(input: {
    node_id: string;
    node_name: string;
    public_key: string;
    key_id: string;
  }): Row {
    return this.transaction(() => {
      this.run("DELETE FROM node_binding_operations WHERE expires_at<?", Date.now() / 1000);
      const node = this.get("SELECT owner_id FROM nodes WHERE node_id=?", input.node_id),
        key = this.get("SELECT * FROM node_credential_keys WHERE node_id=?", input.node_id);
      if (node && !key) throw new IdentityError(409, "device requires offline local enrollment");
      const keyText = key?.public_key ?? input.public_key,
        keyId = key?.key_id ?? input.key_id;
      if (
        keyId !==
        "sha256:" + createHash("sha256").update(Buffer.from(keyText, "base64")).digest("hex")
      )
        throw new IdentityError(409, "invalid device key");
      const epoch =
        this.get("SELECT node_epoch FROM node_binding_state WHERE node_id=?", input.node_id)
          ?.node_epoch ?? 0;
      const op = secret(),
        token = secret(),
        browser = secret(),
        challenge = secret(),
        expires = Date.now() / 1000 + 900;
      const aad = {
        purpose: "device-binding",
        node_id: input.node_id,
        operation_id: op,
        epoch,
        expires_at: expires,
      };
      const ephemeral = generateKeyPairSync("x25519"),
        salt = randomBytes(16),
        nonce = randomBytes(12);
      const shared = diffieHellman({
        privateKey: ephemeral.privateKey,
        publicKey: publicKey(keyText),
      });
      const derived = hkdfSync(
        "sha256",
        shared,
        salt,
        Buffer.from("nano-multiagent/device-binding-v1"),
        32,
      );
      const cipher = createCipheriv("aes-256-gcm", Buffer.from(derived), nonce);
      cipher.setAAD(Buffer.from(canonical(aad)));
      const ciphertext = Buffer.concat([
        cipher.update(challenge),
        cipher.final(),
        cipher.getAuthTag(),
      ]);
      this.run(
        "INSERT INTO node_binding_operations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL)",
        op,
        input.node_id,
        input.node_name,
        node?.owner_id || "",
        epoch,
        keyId,
        keyText,
        digest(challenge),
        digest(token),
        digest(browser),
        expires,
        "awaiting_proof",
      );
      return {
        operation_id: op,
        operation_token: token,
        browser_token: browser,
        challenge: {
          aad,
          ephemeral_public_key: ephemeral.publicKey
            .export({ format: "der", type: "spki" })
            .subarray(-32)
            .toString("base64"),
          salt: salt.toString("base64"),
          nonce: nonce.toString("base64"),
          ciphertext: ciphertext.toString("base64"),
        },
      };
    });
  }
  deviceProve(id: string, token: string, challenge: string) {
    const op = this.operation(id, token);
    if (op.state === "cancelled") throw new IdentityError(409, "binding operation cancelled");
    if (!equal(op.challenge_hash, digest(challenge)))
      throw new IdentityError(409, "device proof invalid");
    if (op.state === "awaiting_proof")
      this.run(
        "UPDATE node_binding_operations SET state='awaiting_account' WHERE operation_id=?",
        id,
      );
    return { state: "awaiting_account" };
  }
  deviceBrowser(action: "inspect" | "accept" | "decline", browser: string, userId: string) {
    return this.transaction(() => {
      const user = this.active(userId),
        op = this.get(
          "SELECT * FROM node_binding_operations WHERE browser_token_hash=?",
          digest(browser),
        );
      if (!op || op.expires_at <= Date.now() / 1000)
        throw new IdentityError(409, "binding operation invalid or expired");
      if (op.target_user_id && op.target_user_id !== userId)
        throw new IdentityError(409, "receiving account already fixed");
      if (action === "decline") {
        if (op.state === "committed") throw new IdentityError(409, "binding cannot be cancelled");
        this.run(
          "UPDATE node_binding_operations SET state='cancelled' WHERE operation_id=?",
          op.operation_id,
        );
        return { state: "cancelled" };
      }
      if (!["awaiting_account", "awaiting_local_confirmation", "committed"].includes(op.state))
        throw new IdentityError(409, "binding operation invalid or expired");
      if (action === "accept" && op.state === "awaiting_account") {
        this.run(
          "UPDATE node_binding_operations SET target_user_id=?,target_owner=?,state='awaiting_local_confirmation' WHERE operation_id=?",
          userId,
          user.owner_id,
          op.operation_id,
        );
        op.state = "awaiting_local_confirmation";
      }
      return {
        node_id: op.node_id,
        node_name: op.node_name,
        agents: this.all("SELECT agent_id FROM agent_profiles WHERE node_id=?", op.node_id).map(
          (r) => r.agent_id,
        ),
        state: op.state,
      };
    });
  }
  deviceCancel(id: string, token: string) {
    const op = this.operation(id, token);
    if (op.state === "committed") throw new IdentityError(409, "binding already committed");
    this.run("UPDATE node_binding_operations SET state='cancelled' WHERE operation_id=?", id);
    return { state: "cancelled" };
  }
  devicePrepare(id: string, token: string): Row {
    return this.transaction(() => {
      const op = this.operation(id, token);
      if (["awaiting_proof", "cancelled"].includes(op.state))
        throw new IdentityError(409, "device proof required");
      if (op.state !== "awaiting_local_confirmation") return { state: op.state };
      const user = this.active(op.target_user_id),
        snapshot = this.snapshot(op.node_id),
        encoded = canonical(snapshot);
      this.run(
        "UPDATE node_binding_operations SET snapshot_json=? WHERE operation_id=?",
        encoded,
        id,
      );
      return {
        state: op.state,
        target_user_id: user.id,
        target_owner: user.owner_id,
        target_name: user.display_name,
        snapshot,
        confirmation: {
          operation_id: id,
          target_user_id: user.id,
          epoch: op.expected_epoch,
          snapshot_hash: digest(encoded),
        },
      };
    });
  }
  deviceCommit(id: string, token: string, proof: string, envelopes: Row) {
    return this.transaction(() => {
      const op = this.operation(id, token);
      if (op.state === "committed") return { state: "committed" };
      if (op.state !== "awaiting_local_confirmation" || !op.snapshot_json)
        throw new IdentityError(409, "local confirmation required");
      const user = this.active(op.target_user_id);
      const expected = createHmac("sha256", Buffer.from(op.challenge_hash, "hex"))
        .update(
          canonical({
            operation_id: id,
            target_user_id: user.id,
            epoch: op.expected_epoch,
            snapshot_hash: digest(op.snapshot_json),
          }),
        )
        .digest("hex");
      if (!equal(expected, proof)) throw new IdentityError(409, "local confirmation invalid");
      const node = this.get("SELECT owner_id FROM nodes WHERE node_id=?", op.node_id),
        state = this.get("SELECT node_epoch FROM node_binding_state WHERE node_id=?", op.node_id);
      if (
        (node?.owner_id || "") !== op.expected_owner ||
        (state?.node_epoch ?? 0) !== op.expected_epoch
      )
        throw new IdentityError(409, "node ownership changed");
      const snapshot = this.snapshot(op.node_id);
      if (canonical(snapshot) !== op.snapshot_json)
        throw new IdentityError(409, "node configuration changed; prepare again");
      if (
        snapshot.agent_config_operations.some((r: Row) =>
          ["pending", "gateway_applied"].includes(r.status),
        )
      )
        throw new IdentityError(409, "node configuration operation still pending");
      if (
        canonical(Object.keys(envelopes).sort()) !==
        canonical(snapshot.agent_channels.map((r: Row) => r.channel_id).sort())
      )
        throw new IdentityError(409, "complete channel ciphertext set required");
      for (const channel of snapshot.agent_channels) {
        const envelope = envelopes[channel.channel_id];
        if (
          !envelope ||
          typeof envelope !== "object" ||
          !["ciphertext", "nonce", "salt", "ephemeral_public_key"].every((k) => k in envelope)
        )
          throw new IdentityError(409, "invalid channel envelope");
        this.run(
          "UPDATE agent_channels SET credential_envelope_json=?,credential_revision=credential_revision+1,channel_revision=channel_revision+1 WHERE channel_id=?",
          canonical(envelope),
          channel.channel_id,
        );
      }
      this.run(
        "INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES(?,?,?,'offline') ON CONFLICT(node_id) DO UPDATE SET owner_id=excluded.owner_id,status='offline'",
        op.node_id,
        op.node_name,
        user.owner_id,
      );
      for (const table of [
        "agent_profiles",
        "channel_manifest_heads",
        "agent_channels",
        "agent_channel_removals",
        "node_credential_keys",
      ])
        this.run(`UPDATE ${table} SET owner_id=? WHERE node_id=?`, user.owner_id, op.node_id);
      this.run(
        "UPDATE channel_manifest_heads SET manifest_revision=manifest_revision+1 WHERE node_id=?",
        op.node_id,
      );
      this.run(
        "INSERT OR IGNORE INTO node_credential_keys VALUES(?,?,?,'X25519-HKDF-SHA256-AES-256-GCM',?,datetime('now'))",
        op.node_id,
        user.owner_id,
        op.key_id,
        op.public_key,
      );
      const runtime = secret(48);
      this.run(
        "INSERT INTO node_binding_state VALUES(?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET node_epoch=excluded.node_epoch,runtime_token_hash=excluded.runtime_token_hash,owner_id=excluded.owner_id",
        op.node_id,
        op.expected_epoch + 1,
        digest(runtime),
        user.owner_id,
      );
      this.run(
        "UPDATE node_binding_operations SET state='cancelled' WHERE node_id=? AND operation_id!=? AND state!='committed'",
        op.node_id,
        id,
      );
      this.run(
        "UPDATE node_binding_operations SET state='committed',runtime_token=? WHERE operation_id=?",
        runtime,
        id,
      );
      this.run(
        "UPDATE users SET default_entry_node_id=NULL WHERE default_entry_node_id=? AND owner_id!=?",
        op.node_id,
        user.owner_id,
      );
      this.run(
        "UPDATE users SET default_entry_node_id=COALESCE(default_entry_node_id,?) WHERE id=?",
        op.node_id,
        user.id,
      );
      return { state: "committed" };
    });
  }
  deviceRecover(id: string, token: string): Row {
    const op = this.operation(id, token);
    if (op.state !== "committed") throw new IdentityError(409, "binding not committed");
    const identity = this.authenticateRuntime(op.runtime_token);
    if (!identity) throw new IdentityError(409, "binding runtime revoked");
    return {
      ...identity,
      runtime_token: op.runtime_token,
      snapshot: this.snapshot(identity.node_id),
    };
  }
  deviceRecoverDevice(id: string, token: string) {
    return this.transaction(() => {
      const op = this.operation(id, token);
      if (op.state !== "awaiting_account")
        throw new IdentityError(409, "fresh device proof required");
      const row = this.get(
        "SELECT s.*,u.id AS user_id FROM node_binding_state s JOIN users u ON u.owner_id=s.owner_id AND u.membership_status='active' WHERE s.node_id=?",
        op.node_id,
      );
      if (!row || row.owner_id !== op.expected_owner || row.node_epoch !== op.expected_epoch)
        throw new IdentityError(409, "current device owner unavailable");
      const runtime = secret(48);
      this.run(
        "UPDATE node_binding_state SET node_epoch=node_epoch+1,runtime_token_hash=? WHERE node_id=?",
        digest(runtime),
        op.node_id,
      );
      this.run(
        "UPDATE node_binding_operations SET state='committed',target_user_id=?,target_owner=?,runtime_token=? WHERE operation_id=?",
        row.user_id,
        row.owner_id,
        runtime,
        id,
      );
      return { state: "committed" };
    });
  }
}
export const createIdentity = (db: DatabaseSync, jwtSecret: string) => new Identity(db, jwtSecret);
