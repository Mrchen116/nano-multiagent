import { randomUUID } from "node:crypto";
import type { FastifyInstance, FastifyRequest } from "fastify";
import {
  all,
  one,
  now,
  chatId,
  fail,
  body,
  params,
  query,
  transaction,
  type Row,
  type ImContext,
} from "./context.js";
export class Messaging {
  constructor(readonly ctx: ImContext) {}
  get db() {
    return this.ctx.db;
  }
  principal(req: FastifyRequest): Row {
    const token = (req.headers.authorization ?? "").replace(/^Bearer\s+/i, "");
    const gateway = this.ctx.gateway.authenticate(token);
    return gateway ? { ...gateway, kind: "gateway" } : this.ctx.identity.authenticateRequest(req);
  }
  agentUser(agentId: string): Row {
    const a = one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0", agentId);
    if (!a) fail(404, "agent not found");
    let u = one(this.db, "SELECT * FROM users WHERE username=?", `agent:${agentId}`);
    if (!u) {
      const id = chatId("u_");
      this.db
        .prepare(
          `INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES(?,?,?,?,?,'active')`,
        )
        .run(id, `agent:${agentId}`, a.display_name, a.owner_id, now());
      u = one(this.db, "SELECT * FROM users WHERE id=?", id);
    }
    return u!;
  }
  actor(u: Row): Row {
    return {
      type: u.username.startsWith("agent:") ? "agent" : "user",
      id: u.username.startsWith("agent:") ? u.username.slice(6) : u.id,
      display_name: u.display_name,
      user_id: u.id,
      is_stale: u.is_stale ? true : null,
    };
  }
  members(id: string): Row[] {
    return all(
      this.db,
      `SELECT u.*,ap.is_stale FROM conversation_participants cp JOIN users u ON u.id=cp.user_id LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id WHERE cp.conversation_id=? ORDER BY cp.rowid`,
      id,
    );
  }
  access(principal: Row, id: string, agentId?: string): Row {
    const c = one(this.db, "SELECT * FROM conversations WHERE id=?", id);
    if (!c) fail(404, "conversation_id not found");
    let uid = principal.id;
    if (principal.kind === "gateway") {
      const agent = agentId
        ? one(
            this.db,
            "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND owner_id=? AND is_stale=0",
            agentId,
            principal.node_id,
            principal.owner_id,
          )
        : undefined;
      if (!agent) fail(404, "conversation_id not found");
      uid = this.agentUser(agentId!).id;
    }
    if (
      !one(
        this.db,
        "SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?",
        id,
        uid,
      )
    )
      fail(404, "conversation_id not found");
    return c;
  }
  conversation(id: string, userId: string): Row {
    const c = one(this.db, "SELECT * FROM conversations WHERE id=?", id)!;
    const members = this.members(id);
    const prefs =
      one(
        this.db,
        "SELECT * FROM conversation_participants WHERE conversation_id=? AND user_id=?",
        id,
        userId,
      ) ?? {};
    const agents = members.filter((u) => u.username.startsWith("agent:"));
    return {
      ...Object.fromEntries(
        [
          "id",
          "title",
          "type",
          "owner_id",
          "creator_id",
          "last_message_preview",
          "last_message_at",
          "config_agent_id",
          "config_profile_version",
          "external_source",
          "external_chat_id",
          "created_at",
        ].map((key) => [key, c[key]]),
      ),
      participants: members.map((u) => this.actor(u)),
      participant_ids: members.map((u) => u.id),
      direct_kind:
        c.type === "direct"
          ? agents.length === 2
            ? "agent-agent"
            : agents.length
              ? "user-agent"
              : "user-user"
          : null,
      is_pinned: !!prefs.is_pinned,
      is_muted: !!prefs.is_muted,
      unread_count: prefs.unread_count ?? 0,
      run_state: one(
        this.db,
        "SELECT 1 FROM messages WHERE conversation_id=? AND delivery_status='running'",
        id,
      )
        ? "running"
        : "idle",
      source_agent_id:
        c.config_agent_id ?? (agents.length === 1 ? (agents[0]?.username.slice(6) ?? null) : null),
      source_node_id:
        c.config_agent_id || agents.length === 1
          ? (one(
              this.db,
              "SELECT node_id FROM agent_profiles WHERE agent_id=?",
              c.config_agent_id ?? agents[0]!.username.slice(6),
            )?.node_id ?? null)
          : null,
    };
  }
  conversations(userId: string): Row[] {
    return all(
      this.db,
      "SELECT c.id FROM conversations c JOIN conversation_participants p ON p.conversation_id=c.id WHERE p.user_id=? ORDER BY p.is_pinned DESC, COALESCE(c.last_message_at,c.created_at) DESC",
      userId,
    ).map((c) => this.conversation(c.id, userId));
  }
  resolveParticipants(principal: Row, actors: Row[], ids: string[] = [], group = true): string[] {
    let result = ids.map((id) =>
      id.startsWith("agent:") ? this.agentUser(id.slice(6)).id : id.replace(/^user:/, ""),
    );
    for (const a of actors) {
      if (a.type === "agent") {
        const profile = one(
          this.db,
          "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0",
          a.id,
        );
        if (!profile || (group && profile.owner_id !== principal.owner_id))
          fail(404, "agent not accessible");
        result.push(this.agentUser(a.id).id);
      } else if (a.type === "user") result.push(a.id);
      else fail(400, "invalid actor type");
    }
    result = [...new Set(result)];
    for (const id of result) {
      const u = one(this.db, "SELECT * FROM users WHERE id=?", id);
      if (!u || (!u.username.startsWith("agent:") && u.membership_status !== "active"))
        fail(400, "participant not found");
      if (group && u.username.startsWith("agent:") && u.owner_id !== principal.owner_id)
        fail(404, "agent not accessible");
    }
    return result;
  }
  createConversation(p: Row, b: Row, force = false): Row {
    if (!b.title?.trim() || !["direct", "group"].includes(b.type))
      fail(422, "title and valid type required");
    const ids = this.resolveParticipants(
      p,
      b.participants ?? [],
      b.participant_ids ?? [],
      b.type === "group",
    );
    if (!ids.length) fail(422, "participants required");
    if (!ids.includes(p.id)) ids.unshift(p.id);
    if (b.type === "direct" && ids.length !== 2)
      fail(400, "direct conversation requires two participants");
    const key = b.type === "direct" && !force ? [...ids].sort().join("|") : null;
    const existing = key
      ? one(this.db, "SELECT id FROM conversations WHERE direct_key=?", key)
      : null;
    if (existing) return this.conversation(existing.id, p.id);
    const id = chatId("c_");
    transaction(this.db, () => {
      this.db
        .prepare(
          "INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at) VALUES(?,?,?,?,?,?,?)",
        )
        .run(id, b.title.trim(), b.type, p.owner_id, p.id, key, now());
      for (const uid of ids)
        this.db
          .prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)")
          .run(id, uid);
      const profiles = ids
        .map((uid) =>
          one(
            this.db,
            "SELECT ap.agent_id,ap.profile_version FROM agent_profiles ap JOIN users u ON u.username='agent:'||ap.agent_id WHERE u.id=?",
            uid,
          ),
        )
        .filter(Boolean);
      if (profiles.length === 1)
        this.db
          .prepare("UPDATE conversations SET config_agent_id=?,config_profile_version=? WHERE id=?")
          .run(profiles[0]!.agent_id, profiles[0]!.profile_version, id);
    });
    this.membership(id, ids);
    return this.conversation(id, p.id);
  }
  membership(id: string, recipients: string[]) {
    this.ctx.gateway.broadcast(recipients, {
      op: "event",
      event_type: "conversation.membership_changed",
      data: { conversation_id: id },
    });
  }
  message(id: string): Row {
    const m = one(this.db, "SELECT * FROM messages WHERE id=?", id);
    if (!m) fail(404, "message not found");
    const u = one(this.db, "SELECT * FROM users WHERE id=?", m.sender_user_id)!;
    const result: Row = {
      ...Object.fromEntries(
        [
          "id",
          "conversation_id",
          "sender_user_id",
          "sender_type",
          "content",
          "delivery_status",
          "created_at",
          "elapsed_ms",
          "kernel_message_id",
        ].map((key) => [key, m[key]]),
      ),
      sender: {
        ...this.actor(u),
        type: m.sender_type,
        display_name: m.sender_display_name ?? u.display_name,
      },
    };
    for (const key of [
      "attachments",
      "tool_calls",
      "thinking",
      "background_returns",
      "reply_process",
      "permission_requests",
    ])
      result[key] = JSON.parse(
        m[key === "permission_requests" ? "permission_request_json" : `${key}_json`] ?? "[]",
      );
    for (const key of ["token_usage", "system_notice"])
      result[key] = JSON.parse(m[`${key}_json`] ?? "null");
    for (const key of Object.keys(result)) if (key.endsWith("_json")) delete result[key];
    Object.defineProperties(result, {
      awaiting_permission_at: { value: m.awaiting_permission_at },
      sender_source_id: { value: m.sender_source_id },
    });
    return result;
  }
  event(id: string, messageId: string | null, type: string, data: Row, status = "completed"): Row {
    const at = now();
    const payload = {
      created_at: at,
      delivery_status: status,
      conversation_id: id,
      ...(messageId ? { message_id: messageId } : {}),
      ...data,
    };
    const result = this.db
      .prepare(
        "INSERT INTO conversation_events(conversation_id,message_id,event_type,delivery_status,payload_json,created_at) VALUES(?,?,?,?,?,?)",
      )
      .run(id, messageId, type, status, JSON.stringify(payload), at);
    const frame = {
      op: "event",
      event_id: Number(result.lastInsertRowid),
      conversation_id: id,
      message_id: messageId,
      event_type: type,
      delivery_status: status,
      created_at: at,
      data: { ...payload, event_id: Number(result.lastInsertRowid) },
    };
    this.ctx.gateway.broadcast(
      this.members(id).map((u) => u.id),
      frame,
    );
    return frame;
  }
  insertMessage(
    cId: string,
    sender: string,
    type: string,
    content: string,
    attachments: Row[] = [],
    key: string | null = null,
    status = "completed",
    extra: Row = {},
  ): Row {
    const old = key
      ? one(
          this.db,
          "SELECT id FROM messages WHERE conversation_id=? AND caller_idempotency_key=?",
          cId,
          key,
        )
      : undefined;
    if (old) return this.message(old.id);
    const id = randomUUID().replaceAll("-", "");
    const at = now();
    this.db
      .prepare(
        `INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,attachments_json,delivery_status,created_at,caller_idempotency_key,sender_display_name,sender_source_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)`,
      )
      .run(
        id,
        cId,
        sender,
        type,
        content,
        JSON.stringify(attachments),
        status,
        at,
        key,
        extra.sender_display_name ?? null,
        extra.sender_source_id ?? null,
      );
    this.db
      .prepare("UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?")
      .run(content.trim().slice(0, 120) || attachments[0]?.file_name || "", at, cId);
    this.db
      .prepare(
        "UPDATE conversation_participants SET unread_count=unread_count+1 WHERE conversation_id=? AND user_id!=?",
      )
      .run(cId, sender);
    const m = this.message(id);
    this.event(cId, id, "message.created", { ...m, message_id: id }, status);
    return m;
  }
  copyReferences(source: string, target: string, value: string): string {
    return value.replace(
      /\/im\/v1\/conversations\/([^/\s]+)\/(images|attachments)\/([\w-]+)/g,
      (match, cId, kind, imageId) => {
        if (cId !== source || source === target) return match;
        const old = one(
          this.db,
          "SELECT * FROM message_images WHERE conversation_id=? AND image_id=?",
          source,
          imageId,
        );
        if (!old) fail(404, "resource not found");
        const key = `fork:${source}:${imageId}`;
        let resource = one(
          this.db,
          "SELECT * FROM message_images WHERE conversation_id=? AND source_key=?",
          target,
          key,
        );
        if (!resource) {
          const id = randomUUID().replaceAll("-", "");
          this.db
            .prepare("INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)")
            .run(
              id,
              target,
              key,
              old.sha256,
              old.content_type,
              old.file_name,
              old.byte_size,
              old.storage_name,
            );
          resource = { image_id: id };
        }
        return `/im/v1/conversations/${target}/${kind}/${resource.image_id}`;
      },
    );
  }
  validateReferences(p: Row, cId: string, value: string, agentId?: string): string {
    return value.replace(
      /(?:(https?:\/\/[^\s/]+))?(\/im\/v1\/conversations\/([^/\s]+)\/(?:images|attachments)\/([\w-]+))/g,
      (match, origin, path, source, image) => {
        if (origin && new URL(origin).origin !== new URL(this.ctx.publicUrl).origin) return match;
        this.access(p, source, agentId);
        if (
          !one(
            this.db,
            "SELECT 1 FROM message_images WHERE conversation_id=? AND image_id=?",
            source,
            image,
          )
        )
          fail(404, "resource not found");
        return source === cId ? match : this.copyReferences(source, cId, path);
      },
    );
  }
  async sendMessage(req: FastifyRequest): Promise<Row> {
    const p = this.principal(req),
      b = body(req),
      q = query(req),
      id = params(req).conversation_id,
      c = this.access(p, id, q.agent_id);
    let sender = p.id,
      type = "user";
    if (p.kind === "gateway") {
      sender =
        b.sender?.type === "agent" || b.sender_type === "agent"
          ? this.agentUser(q.agent_id).id
          : p.owner_id;
      type = b.sender?.type ?? b.sender_type ?? "user";
    } else if (
      (b.sender?.id ?? b.sender_user_id) !== p.id ||
      (b.sender?.type ?? b.sender_type ?? "user") !== "user"
    )
      fail(403, "sender does not match authenticated user");
    if (typeof b.content !== "string" && b.content !== undefined) fail(422, "invalid content");
    const attachments = b.attachments ?? [];
    if (attachments.length > 5) fail(400, "too many attachments");
    if (!b.content?.trim() && !attachments.length)
      fail(400, "message content or attachments required");
    b.content = this.validateReferences(p, id, b.content ?? "", q.agent_id);
    for (const a of attachments) a.url = this.validateReferences(p, id, a.url, q.agent_id);
    const key = (req.headers["idempotency-key"] as string) ?? null;
    const old = key
      ? one(
          this.db,
          "SELECT id FROM messages WHERE conversation_id=? AND caller_idempotency_key=?",
          id,
          key,
        )
      : undefined;
    if (old) return this.message(old.id);
    const agents = this.members(id)
      .filter((u) => u.username.startsWith("agent:"))
      .map((u) =>
        one(
          this.db,
          "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0",
          u.username.slice(6),
        ),
      )
      .filter(Boolean) as Row[];
    const targetAgents = b.suppress_relay ? [] : agents;
    const m = this.insertMessage(
      id,
      sender,
      type,
      b.content ?? "",
      attachments,
      key,
      targetAgents.length ? "pending" : "completed",
      p.kind === "gateway" ? b : {},
    );
    if (targetAgents.length) {
      let sent = false;
      for (const a of targetAgents) {
        const relayId = randomUUID().replaceAll("-", ""),
          relayKey = `${key ?? m.id}:${a.agent_id}`;
        const payload = {
          relay_task_id: relayId,
          idempotency_key: relayKey,
          conversation_id: id,
          agent_id: a.agent_id,
          message: m,
          sender: m.sender,
          participants: this.conversation(id, sender).participants,
          metadata: {
            conversation_type: c.type,
            mentioned_agent_ids: agents
              .filter((a) => m.content.includes(`<@${this.agentUser(a.agent_id).id}>`))
              .map((a) => a.agent_id),
            participant_agent_ids: agents.map((a) => a.agent_id),
            config_profile_version: a.profile_version,
            node_epoch:
              one(this.db, "SELECT node_epoch FROM node_binding_state WHERE node_id=?", a.node_id)
                ?.node_epoch ?? 0,
            ...(c.external_source
              ? {
                  external_source: c.external_source,
                  external_chat_id: c.external_chat_id,
                  trigger_source: "im",
                }
              : {}),
          },
        };
        this.db
          .prepare("INSERT INTO relay_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)")
          .run(
            relayId,
            m.id,
            id,
            a.node_id,
            JSON.stringify(payload),
            relayKey,
            "queued",
            null,
            null,
            now(),
            now(),
          );
        if (this.ctx.gateway.send(a.node_id, { type: "relay.message", payload })) {
          sent = true;
          this.db
            .prepare("UPDATE relay_tasks SET status='sent' WHERE relay_task_id=?")
            .run(relayId);
        } else
          this.event(
            id,
            m.id,
            "relay.failed",
            {
              relay_task_id: relayId,
              target_node_id: a.node_id,
              reason: "node_disconnected",
            },
            "failed",
          );
      }
      if (!sent) fail(503, "target_node_id is not connected");
    }
    return m;
  }
  resolveTarget(agentId: string, target: string): string {
    const a = this.agentUser(agentId);
    const c = one(
      this.db,
      "SELECT id FROM conversations WHERE id=?",
      target.replace(/^conversation:/, ""),
    );
    if (c) {
      if (
        !one(
          this.db,
          "SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?",
          c.id,
          a.id,
        )
      )
        fail(404, "target not accessible");
      return c.id;
    }
    const uid = target.replace(/^(?:user|agent):/, "");
    const u = one(this.db, "SELECT * FROM users WHERE id=? OR username=?", uid, `agent:${uid}`);
    if (!u || (!u.username.startsWith("agent:") && u.membership_status !== "active"))
      fail(404, "target not accessible");
    const key = [a.id, u.id].sort().join("|");
    const old = one(this.db, "SELECT id FROM conversations WHERE direct_key=?", key);
    if (old) return old.id;
    const id = chatId("c_");
    this.db
      .prepare(
        "INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at) VALUES(?,?,?,?,?,?,?)",
      )
      .run(id, u.display_name, "direct", a.owner_id, a.id, key, now());
    for (const member of [a.id, u.id])
      this.db
        .prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)")
        .run(id, member);
    return id;
  }
}
export function registerMessagingRoutes(app: FastifyInstance, ctx: ImContext) {
  const s = ctx.messaging,
    db = ctx.db;
  const contactRows = () =>
    all(
      db,
      "SELECT u.id AS user_id,CASE WHEN ap.agent_id IS NULL THEN 'human' ELSE 'agent' END AS kind,COALESCE(ap.display_name,u.display_name) AS display_name,ap.agent_id,ap.owner_id,owner.display_name AS owner_display_name,COALESCE(NULLIF(n.alias,''),n.node_name) AS node_name,COALESCE(n.status,'offline') AS status,ap.work_mode FROM users u LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id LEFT JOIN users owner ON owner.id=ap.owner_id LEFT JOIN nodes n ON n.node_id=ap.node_id WHERE (u.password_hash IS NOT NULL AND u.password_hash!='' AND ap.agent_id IS NULL) OR (ap.agent_id IS NOT NULL AND ap.is_stale=0) ORDER BY u.id",
    ).map((r) =>
      r.kind === "human" ? { user_id: r.user_id, kind: r.kind, display_name: r.display_name } : r,
    );
  app.get("/im/v1/contacts", (req) => {
    ctx.identity.authenticateRequest(req);
    const q = query(req);
    if (q.kind && !["human", "agent"].includes(q.kind)) fail(400, "invalid kind");
    const rows = contactRows().filter(
      (r) =>
        (!q.cursor || r.user_id > q.cursor) &&
        (!q.kind || r.kind === q.kind) &&
        (!q.q ||
          [r.display_name, r.user_id, r.agent_id ?? ""].some((x) =>
            x.toLowerCase().includes(q.q.trim().toLowerCase()),
          )),
    );
    return {
      items: rows.slice(0, 50),
      next_cursor: rows.length > 50 ? rows[49]!.user_id : null,
    };
  });
  app.get("/im/v1/contacts/:user_id", (req) => {
    ctx.identity.authenticateRequest(req);
    const r = contactRows().find((r) => r.user_id === params(req).user_id);
    if (!r) fail(404, "contact not found");
    return r;
  });
  app.post("/im/v1/conversations", (req, reply) => {
    const p = ctx.identity.authenticateRequest(req);
    reply.code(201);
    return s.createConversation(p, body(req));
  });
  app.get("/im/v1/conversations", (req) => {
    const p = s.principal(req);
    const uid = p.kind === "gateway" ? s.agentUser(query(req).agent_id).id : p.id;
    if (p.kind === "gateway") {
      const a = one(db, "SELECT node_id FROM agent_profiles WHERE agent_id=?", query(req).agent_id);
      if (a?.node_id !== p.node_id) fail(404, "agent not found");
    }
    return { items: s.conversations(uid) };
  });
  app.get("/im/v1/sync", (req) => {
    const p = ctx.identity.authenticateRequest(req);
    return {
      items: s.conversations(p.id),
      max_event_id: one(db, "SELECT COALESCE(MAX(event_id),0) AS n FROM conversation_events")!.n,
    };
  });
  app.get("/im/v1/conversations/:conversation_id", (req) => {
    const p = s.principal(req),
      id = params(req).conversation_id;
    s.access(p, id, query(req).agent_id);
    return s.conversation(id, p.id ?? s.agentUser(query(req).agent_id).id);
  });
  app.patch("/im/v1/conversations/:conversation_id", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      b = body(req);
    s.access(p, id);
    if (b.title !== undefined) {
      if (!b.title.trim()) fail(400, "title must be non-empty");
      db.prepare("UPDATE conversations SET title=?,title_is_custom=1 WHERE id=?").run(
        b.title.trim(),
        id,
      );
    }
    for (const key of ["is_pinned", "is_muted"])
      if (b[key] !== undefined)
        db.prepare(
          `UPDATE conversation_participants SET ${key}=? WHERE conversation_id=? AND user_id=?`,
        ).run(b[key] ? 1 : 0, id, p.id);
    s.membership(
      id,
      s.members(id).map((u) => u.id),
    );
    return s.conversation(id, p.id);
  });
  app.delete("/im/v1/conversations/:conversation_id", (req, reply) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      c = s.access(p, id);
    if (c.type === "group" && c.creator_id !== p.id) fail(403, "only creator can delete group");
    const recipients = s.members(id).map((u) => u.id);
    db.prepare("DELETE FROM conversations WHERE id=?").run(id);
    s.membership(id, recipients);
    reply.code(204).send();
  });
  app.post("/im/v1/conversations/:conversation_id/participants", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      c = s.access(p, id);
    if (c.type !== "group") fail(400, "group required");
    const ids = s.resolveParticipants(p, body(req).participants ?? []);
    if (!ids.length) fail(400, "participants required");
    for (const uid of ids)
      db.prepare(
        "INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES(?,?)",
      ).run(id, uid);
    s.membership(
      id,
      s.members(id).map((u) => u.id),
    );
    return s.conversation(id, p.id);
  });
  app.delete("/im/v1/conversations/:conversation_id/participants/:user_id", (req, reply) => {
    const p = ctx.identity.authenticateRequest(req),
      { conversation_id: id, user_id: uid } = params(req),
      c = s.access(p, id);
    if (c.type !== "group" || uid === c.creator_id) fail(403, "creator cannot be removed");
    const recipients = s.members(id).map((u) => u.id);
    db.prepare("DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?").run(
      id,
      uid,
    );
    s.membership(id, recipients);
    reply.code(204).send();
  });
  app.post("/im/v1/conversations/:conversation_id/read", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id;
    s.access(p, id);
    const m = one(
      db,
      "SELECT rowid FROM messages WHERE id=? AND conversation_id=?",
      body(req).last_read_message_id,
      id,
    );
    if (!m) fail(400, "message not found");
    db.prepare(
      "UPDATE conversation_participants SET last_read_message_id=?,unread_count=(SELECT COUNT(*) FROM messages WHERE conversation_id=? AND rowid>? AND sender_user_id!=?) WHERE conversation_id=? AND user_id=?",
    ).run(body(req).last_read_message_id, id, m.rowid, p.id, id, p.id);
    return s.conversation(id, p.id);
  });
  app.post("/im/v1/conversations/:conversation_id/messages", async (req, reply) => {
    reply.code(201);
    return s.sendMessage(req);
  });
  app.get("/im/v1/conversations/:conversation_id/messages", (req) => {
    const p = s.principal(req),
      id = params(req).conversation_id,
      q = query(req);
    s.access(p, id, q.agent_id);
    const limit = Math.min(100, Math.max(1, Number(q.limit ?? 50)));
    const before = q.before_message_id
      ? one(
          db,
          "SELECT rowid FROM messages WHERE id=? AND conversation_id=?",
          q.before_message_id,
          id,
        )?.rowid
      : undefined;
    const rows = all(
      db,
      "SELECT id,rowid FROM messages WHERE conversation_id=? AND rowid<? ORDER BY rowid DESC LIMIT ?",
      id,
      before ?? Number.MAX_SAFE_INTEGER,
      limit + 1,
    );
    const more = rows.length > limit;
    const page = rows.slice(0, limit).reverse();
    const items: Row[] = [];
    for (const row of page) {
      for (const b of all(
        db,
        "SELECT * FROM agent_config_boundaries WHERE conversation_id=? AND before_message_id=?",
        id,
        row.id,
      ))
        items.push({
          type: "agent_config_changed",
          id: b.boundary_id,
          conversation_id: id,
          agent_id: b.agent_id,
          before_message_id: row.id,
          applied_at: b.applied_at,
        });
      items.push({ type: "message", message: s.message(row.id) });
    }
    return { items, next_before_message_id: more ? page[0]!.id : null };
  });
}
