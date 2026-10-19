import { defaultSpace, canAccessSpace, canActorAccess, agentAvailable, canContactPersonalAgent } from "./identity.js";
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
import { conversationAccess, qualifiedUser } from "./conversation-access.js";
import { validateTimeZone, type InteractionContext } from "@nano/product-contracts";
import { Interactions } from './interactions.js';
/** Derive human approval badges from the durable request/decision identity. */
export function withHumanApproval(call: Row, permissions: Row[]): Row {
  const decision = permissions.findLast(item => item.call_id === call.id && item.status === "resolved" && item.decided_by)?.decision;
  if (!["allow_once", "deny"].includes(decision)) return call;
  return {...call, approval: decision === "allow_once" ? "user_allow" : "user_deny", ...(decision === "deny" ? {reason: "denied"} : {})};
}

export class Messaging {
  readonly interactions: Interactions;
  constructor(readonly ctx: ImContext) { this.interactions = new Interactions(ctx); }
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
    return { ...u!, owner_id: a.owner_id, space_id: a.space_id };
  }
  actor(u: Row): Row {
    return {
      type: u.username.startsWith("agent:") ? "agent" : "user",
      id: u.username.startsWith("agent:") ? u.username.slice(6) : u.id,
      display_name: u.display_name,
      user_id: u.id,
      is_stale: u.is_stale ? true : null,
      ...(u.username.startsWith("agent:") && one(this.db,"SELECT 1 FROM personal_agent_bindings WHERE agent_id=?",u.username.slice(6)) ? {role:"personal"} : {}),
    };
  }
  members(id: string): Row[] {
    return all(
      this.db,
      `SELECT u.*,ap.is_stale FROM conversation_participants cp JOIN users u ON u.id=cp.user_id LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id WHERE cp.conversation_id=? ORDER BY cp.rowid`,
      id,
    );
  }
  /** Resolve the same XML mention format used by Web and native clients. */
  mentionedAgents(conversationId: string, content: string): string[] {
    const targets = new Set([...content.matchAll(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g)].map(match => match[1]));
    return this.members(conversationId).filter(user => user.username.startsWith("agent:") && targets.has(user.id)).map(user => user.username.slice(6));
  }
  access(principal: Row, id: string, agentId?: string, mode: "read" | "write" = "read"): Row {
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
      const personal=agentId?one(this.db,"SELECT * FROM personal_agent_bindings WHERE agent_id=?",agentId):undefined;
      if(personal) {
        this.ctx.personal!.authority(principal,{agent_id:agentId});
        if(mode==="write" && id!==personal.conversation_id)fail(403,"personal_reviewed_delivery_required");
        if(!this.ctx.personal!.sourceAllowed(personal,id,mode))fail(404,"conversation_id not found");
        return this.ctx.personal!.sourceAccess(personal,id,mode)!;
      }
      if (!agent || agent.space_id !== c.space_id || !agentAvailable(this.db, agent)) fail(404, "conversation_id not found");
      uid = this.agentUser(agentId!).id;
    }
    if (principal.kind !== "gateway") this.ctx.identity.requireSpace(principal, c.space_id);
    const access = conversationAccess(this.db,id,uid);
    if (!access || (mode === "write" && !access.is_member)) fail(404,"conversation_id not found");
    if (mode === "write" && access.dissolved_at) fail(409,{code:"conversation_dissolved",message:"This conversation is read-only after dissolution"});
    return access;
  }

  conversation(id: string, userId: string): Row {
    const c = one(this.db, "SELECT * FROM conversations WHERE id=?", id)!;
    const access = conversationAccess(this.db,id,userId);
    if (!access) fail(404,"conversation_id not found");
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
          "space_id",
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
      visibility:c.visibility, dissolved_at:c.dissolved_at,
      is_member:access.is_member,can_write:access.can_write,can_join:access.can_join,can_change_visibility:access.can_change_visibility,
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
      last_message_system_notice: c.last_message_at ? JSON.parse(one(this.db,
        "SELECT system_notice_json FROM messages WHERE conversation_id=? AND created_at=? ORDER BY rowid DESC LIMIT 1",
        id, c.last_message_at,
      )?.system_notice_json ?? "null") : null,
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
  conversations(userId: string, scope = "joined"): Row[] {
    if (!["joined","public"].includes(scope)) fail(400,"invalid scope");
    if (!qualifiedUser(this.db,userId)) fail(403,"account access required");
    if (scope === "public") return all(this.db,"SELECT id FROM conversations WHERE space_id='company:default' AND type='group' AND visibility='public' AND dissolved_at IS NULL ORDER BY COALESCE(last_message_at,created_at) DESC").filter(c=>conversationAccess(this.db,c.id,userId)).map(c=>this.conversation(c.id,userId));
    return all(
      this.db,
      "SELECT c.id FROM conversations c JOIN conversation_participants p ON p.conversation_id=c.id WHERE p.user_id=? AND c.dissolved_at IS NULL ORDER BY p.is_pinned DESC, COALESCE(c.last_message_at,c.created_at) DESC",
      userId,
    ).filter(c => {
      const scope = one(this.db, "SELECT space_id FROM conversations WHERE id=?", c.id)!.space_id;
      return canActorAccess(this.db, userId, scope);
    }).map((c) => this.conversation(c.id, userId));
  }
  resolveParticipants(principal: Row, actors: Row[], ids: string[] = [], group = true, space?: string): string[] {
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
      if (!u) fail(404, "participant not found");
      const profile = u.username.startsWith("agent:")
        ? one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=?", u.username.slice(6)) : undefined;
      const visible = profile ? (canAccessSpace(principal, profile.space_id) || canContactPersonalAgent(this.db,principal,profile)) && agentAvailable(this.db, profile)
        : u.id === principal.id || (principal.membership_status === "active" && u.membership_status === "active");
      if (!visible || (space && !canActorAccess(this.db, id, space))) fail(404, "participant not found");
      if (group && u.username.startsWith("agent:") && !one(this.db,
        "SELECT 1 FROM agent_profiles WHERE agent_id=? AND owner_id=? AND is_stale=0", u.username.slice(6), principal.owner_id))
        fail(404, "agent not accessible");
    }
    return result;
  }
  createConversation(p: Row, b: Row, force = false, inheritedSpace?: string): Row {
    if (!b.title?.trim() || !["direct", "group"].includes(b.type))
      fail(422, "title and valid type required");
    const ids = this.resolveParticipants(
      p,
      b.participants ?? [],
      b.participant_ids ?? [],
      b.type === "group",
    );
    if (!ids.length && b.type !== "group") fail(422, "participants required");
    if (b.visibility !== undefined && !["public","private"].includes(b.visibility)) fail(422,"invalid visibility");
    if (p.kind === "agent" && ids.some(id=>id !== p.id && one(this.db,"SELECT username FROM users WHERE id=?",id)?.username.startsWith("agent:")))
      fail(403,"An Agent can add only itself, not other Agents");
    if(b.type==='direct' && ids.filter(id=>id!==p.id).length===1) {
      const canonical=one(this.db,"SELECT b.* FROM personal_agent_bindings b JOIN users u ON u.username='agent:'||b.agent_id WHERE b.owner_user_id=? AND u.id=? AND b.status='active'",p.id,ids.find(id=>id!==p.id)!);
      if(canonical)return this.conversation(canonical.conversation_id,p.id);
    }
    const profiles = ids.map(id => one(this.db, "SELECT ap.* FROM agent_profiles ap JOIN users u ON u.username='agent:'||ap.agent_id WHERE u.id=?", id)).filter(Boolean);
    const contactingPersonal=profiles.some(profile=>!!profile && profile.owner_id!==p.owner_id && canContactPersonalAgent(this.db,p,profile));
    // An owner may invite their PA into a colleague group without moving its private assets into that group.
    const sharedPersonalGroup=b.type==='group' && profiles.some(profile=>!!profile && canContactPersonalAgent(this.db,p,profile)
      && ids.some(id=>!canActorAccess(this.db,id,profile.space_id)));
    const space = inheritedSpace ?? (contactingPersonal || sharedPersonalGroup ? "company:default" : profiles[0]?.space_id ?? (ids.some(id => id !== p.id) && !profiles.length ? "company:default" : defaultSpace(p)));
    this.ctx.identity.requireSpace(p, space);
    if (ids.some(id => !canActorAccess(this.db, id, space))) fail(404, "participant not found");
    if (!ids.includes(p.id)) ids.unshift(p.id);
    if (b.type === "direct" && ids.length !== 2)
      fail(400, "direct conversation requires two participants");
    const key = b.type === "direct" && !force ? `${space}|${[...ids].sort().join("|")}` : null;
    const existing = key
      ? one(this.db, "SELECT id FROM conversations WHERE space_id=? AND (direct_key=? OR direct_key=?)", space, key, [...ids].sort().join("|"))
      : null;
    if (existing) return this.conversation(existing.id, p.id);
    const id = chatId("c_");
    transaction(this.db, () => {
      this.db
        .prepare(
          "INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at,space_id,visibility) VALUES(?,?,?,?,?,?,?,?,?)",
        )
        .run(id, b.title.trim(), b.type, p.owner_id, p.id, key, now(), space, b.type === "group" && space === "company:default" ? b.visibility ?? "public" : "private");
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
          "timezone",
          "elapsed_ms",
          "kernel_message_id",
        ].map((key) => [key, m[key]]),
      ),
      sender: {
        ...this.actor(u),
        type: m.sender_type,
        display_name: m.sender_display_name ?? u.display_name,
      },
      ...(this.ctx.updates ? {update_wait: this.ctx.updates.messageWait(id)} : {}),
    };
    const delegation = one(this.db,"SELECT * FROM pa_delegated_messages WHERE message_id=?",id);
    if(delegation) result.delegation={agent_id:delegation.agent_id,authorized_by:delegation.authorized_by,display_name:delegation.display_name,label:`${one(this.db,"SELECT display_name FROM users WHERE id=?",delegation.authorized_by)?.display_name??delegation.display_name}的 PA · 代为发送`};
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
    result.tool_calls = result.tool_calls.map((call: Row) => withHumanApproval(call, result.permission_requests));
    for (const key of ["token_usage", "system_notice", "interaction_reply"])
      result[key] = JSON.parse(m[`${key}_json`] ?? "null");
    const interactive = this.interactions.message(id);
    if (interactive) result.interactive = interactive;
    const replyDraft=this.ctx.personal?.replyDraft(id);
    if(replyDraft)result.reply_draft=replyDraft;
    for (const key of Object.keys(result)) if (key.endsWith("_json")) delete result[key];
    Object.defineProperties(result, {
      awaiting_permission_at: { value: m.awaiting_permission_at },
      sender_source_id: { value: m.sender_source_id },
    });
    return result;
  }
  event(id: string, messageId: string | null, type: string, data: Row, status = "completed", publish = true): Row {
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
    if (publish) this.ctx.gateway.broadcast(
      this.members(id).map((u) => u.id),
      frame,
    );
    for(const b of all(this.db,"SELECT DISTINCT b.* FROM personal_agent_bindings b JOIN pa_source_events e ON e.binding_id=b.binding_id JOIN pa_policies p ON p.binding_id=b.binding_id WHERE e.source_event_id=?",frame.event_id)) this.ctx.personal?.wake(b);
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
    if ((extra.interactive || extra.reply_draft) && !this.db.isTransaction)
      return transaction(this.db, () => this.insertMessage(cId, sender, type, content, attachments, key, status, extra));
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
    const at = extra.created_at ?? now();
    this.db
      .prepare(
        `INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,attachments_json,delivery_status,created_at,caller_idempotency_key,sender_display_name,sender_source_id,timezone) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)`,
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
        extra.timezone ?? null,
      );
    this.db
      .prepare("UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?")
      .run(content.trim().slice(0, 120) || attachments[0]?.file_name || "", at, cId);
    this.db
      .prepare(
        "UPDATE conversation_participants SET unread_count=unread_count+1 WHERE conversation_id=? AND user_id!=?",
      )
      .run(cId, sender);
    if (extra.system_notice) this.db.prepare("UPDATE messages SET system_notice_json=? WHERE id=?").run(JSON.stringify(extra.system_notice),id);
    if (extra.interactive) {
      if (type !== 'agent') fail(403, 'Only Agent messages may contain interactive replies');
      this.interactions.record(id, cId, sender, extra.interactive);
    }
    if (extra.reply_draft) {
      if(!this.ctx.personal)fail(422,'invalid_reply_draft');
      this.ctx.personal.recordReplyDraft(id,extra.reply_draft);
    }
    if (extra.interaction_reply) this.db.prepare('UPDATE messages SET interaction_reply_json=? WHERE id=?').run(JSON.stringify(extra.interaction_reply), id);
    const m = this.message(id);
    this.event(cId, id, "message.created", { ...m, message_id: id }, status, extra.publish !== false);
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
  /** Authenticate private provider ingestion separately from outward message delivery. */
  incomingExternalSource(principal:Row,id:string,agentId:string):Row {
    if(principal.kind!=='gateway')fail(403,'gateway_credential_required');
    const binding=this.ctx.personal!.authority(principal,{agent_id:agentId});
    const c=one(this.db,'SELECT * FROM conversations WHERE id=? AND config_agent_id=? AND owner_id=?',id,agentId,binding.owner_id);
    const channel=c?all(this.db,'SELECT * FROM agent_channels WHERE agent_id=? AND node_id=? AND owner_id=? AND provider=? AND enabled=1',agentId,binding.node_id,binding.owner_id,c.external_source)
      .find(row=>String(c.external_chat_id).startsWith(`${row.provider}:${JSON.parse(row.config_json).app_id}:${c.type==='group'?'group':'dm'}:`)):undefined;
    if(!c||!channel||!this.ctx.personal!.sourceAllowed(binding,id))fail(403,'incoming_source_not_verified');
    return {...c,owner_user_id:binding.owner_user_id};
  }
  /** Mirror authenticated provider input only into its private owner/Agent shadow. */
  incomingExternal(req:FastifyRequest):Row {
    const p=this.principal(req),id=params(req).conversation_id,b=body(req),agentId=query(req).agent_id;
    const c=this.incomingExternalSource(p,id,agentId);
    if(typeof b.sender_source_id!=='string'||!b.sender_source_id||typeof b.content!=='string')fail(422,'incoming_source_required');
    if(c.type==='direct'&&!c.external_chat_id.endsWith(`:dm:${b.sender_source_id}`))fail(403,'incoming_actor_mismatch');
    const attachments=b.attachments??[];
    if(!Array.isArray(attachments)||attachments.length>5)fail(422,'invalid_attachments');
    const key=req.headers['idempotency-key'];if(typeof key!=='string'||!key.startsWith('shadow:'))fail(422,'incoming_receipt_required');
    const old=one(this.db,'SELECT id FROM messages WHERE conversation_id=? AND caller_idempotency_key=?',id,key);if(old)return this.message(old.id);
    const content=this.validateReferences(p,id,b.content,agentId);
    const safeAttachments=attachments.map((a:Row)=>({url:this.validateReferences(p,id,a.url,agentId),content_type:a.content_type,file_name:a.file_name}));
    return this.insertMessage(id,c.owner_user_id,'user',content,safeAttachments,key,'completed',{
      sender_source_id:b.sender_source_id,sender_display_name:b.sender_display_name,created_at:b.created_at,timezone:b.timezone,
    });
  }
  async sendMessage(req: FastifyRequest): Promise<Row> {
    const p = this.principal(req),
      b = body(req),
      q = query(req),
      id = params(req).conversation_id,
      c = this.access(p, id, q.agent_id, "write");
    let sender = p.id,
      type = "user";
    if (p.kind === "gateway") {
      if(one(this.db,"SELECT 1 FROM personal_agent_bindings WHERE agent_id=?",q.agent_id) && (b.sender?.type??b.sender_type)!=="agent")fail(403,"owner_identity_cannot_be_delegated");
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
    if (b.interaction_contexts !== undefined && c.type !== 'direct') fail(422, 'Private interaction background is only supported in direct chats');
    if (c.type === 'group' && b.interaction_reply && !b.interaction_reply.action_id && !b.interaction_reply.event)
      fail(422, 'Group interaction state requires an explicit card action');
    if (b.interaction_reply !== undefined) return this.sendInteraction(p, id, b, req);
    if (b.interactive !== undefined && (p.kind !== 'gateway' || type !== 'agent')) fail(403, 'Only Agent messages may contain interactive replies');
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
    if (b.interaction_contexts !== undefined && !key) fail(422, 'Idempotency-Key required for private interaction background');
    const contexts = b.interaction_contexts === undefined ? [] : this.interactions.contexts(p, id, b.interaction_contexts);
    // Retries and history retain the timezone captured by the original send.
    const timezone = p.kind === "gateway" ? b.timezone ?? null
      : b.timezone === undefined ? one(this.db, "SELECT timezone FROM users WHERE id=?", p.id)?.timezone ?? null
      : this.updateUserTimezone(p.id, b.timezone);
    const agents = b.suppress_relay ? [] : this.relayAgents(id);
    // Freeze private background with its message; publish only after both are durable.
    const {m,relays} = transaction(this.db, () => {
      const m = this.insertMessage(id,sender,type,b.content ?? "",attachments,key,
        agents.length ? "pending" : "completed",{ ...(p.kind === "gateway" ? b : {}), timezone, publish:false });
      return {m,relays:this.enqueueRelays(m,key,agents,contexts)};
    });
    const delivered = this.publishMessages([m]);
    if (!b.suppress_relay) {
      if (relays.length && !delivered) fail(503,"target_node_id is not connected");
      const wait = this.ctx.updates?.messageWait(m.id);
      if (wait) this.event(m.conversation_id, m.id, 'node.update_wait_changed', {update_wait: wait}, 'pending');
    }
    return this.message(m.id);
  }
  private sendInteraction(p: Row, id: string, b: Row, req: FastifyRequest): Row {
    if (b.attachments?.length) fail(422, 'Send attachments in a separate message');
    const rawKey = req.headers['idempotency-key'];
    const key = rawKey ? `interaction:${p.id}:${String(rawKey)}` : null;
    const prepared = this.interactions.prepare(p, id, b, key);
    if (prepared.existing) return this.message(prepared.existing);
    // Preserve handwritten text exactly, including reference syntax and whitespace.
    const content = this.validateReferences(p, id, prepared.content);
    const timezone = b.timezone === undefined ? one(this.db, 'SELECT timezone FROM users WHERE id=?', p.id)?.timezone ?? null : this.updateUserTimezone(p.id, b.timezone);
    const message = transaction(this.db, () => {
      const m = this.insertMessage(id, p.id, 'user', content, [], key, 'pending', { timezone, interaction_reply: prepared.snapshot, publish: false });
      this.interactions.submit(p.id, m.id, prepared);
      this.enqueueRelays(m, key);
      return m;
    });
    this.publishMessages([message]);
    return this.message(message.id);
  }
  /** Save a foreground client's timezone and notify this user's connected Gateways.
   *
   * Args:
   *   userId: Authenticated human account, never a client-selected target.
   *   value: System timezone reported by the browser or native app.
   * Returns:
   *   The saved timezone; unchanged values do not write or broadcast.
   */
  updateUserTimezone(userId: string, value: unknown): string {
    let timezone: string;
    try { timezone = validateTimeZone(value); } catch { fail(422, "invalid timezone"); }
    const previous = one(this.db, "SELECT timezone FROM users WHERE id=?", userId)?.timezone;
    if (previous !== timezone) {
      this.db.prepare("UPDATE users SET timezone=? WHERE id=?").run(timezone, userId);
      for (const node of all(this.db, "SELECT node_id FROM nodes WHERE owner_id=?", userId))
        this.ctx.gateway.send(node.node_id, { type: "user.timezone", payload: { timezone } });
    }
    return timezone;
  }
  /** Persist a task event inside the caller's graph transaction; never publish early. */
  persistTaskNotice(id: string, sender: string, content: string, metadata: Row): Row {
    const m = this.insertMessage(id,sender,"system",content,[],null,"completed",{system_notice:metadata,publish:false});
    this.enqueueRelays(m);
    return m;
  }
  private relayAgents(id: string): Row[] {
    return this.members(id).filter(u=>u.username.startsWith("agent:") && conversationAccess(this.db,id,u.id)?.can_write)
      .map(u=>one(this.db,"SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0",u.username.slice(6))).filter(Boolean) as Row[];
  }
  private enqueueRelays(m: Row, key: string | null = null, agents = this.relayAgents(m.conversation_id), contexts: InteractionContext[] = []): Row[] {
    const c = one(this.db,"SELECT * FROM conversations WHERE id=?",m.conversation_id)!;
    const relays: Row[] = [];
    for (const a of agents) {
      const background = contexts.filter(context => context.agent_id === a.agent_id);
      const id = randomUUID().replaceAll("-",""), relayKey = `${key ?? m.id}:${a.agent_id}`;
      const payload = {relay_task_id:id,idempotency_key:relayKey,conversation_id:c.id,agent_id:a.agent_id,
        message:m,sender:m.sender,participants:this.members(c.id).map(u=>this.actor(u)),metadata:{
          conversation_type:c.type,mentioned_agent_ids:[...new Set([...this.mentionedAgents(c.id,m.content), ...(m.interaction_reply ? [m.interaction_reply.agent_id] : [])])],participant_agent_ids:agents.map(a=>a.agent_id),
          config_profile_version:a.profile_version,node_epoch:one(this.db,"SELECT node_epoch FROM node_binding_state WHERE node_id=?",a.node_id)?.node_epoch ?? 0,
          ...(background.length ? {interaction_contexts:background} : {}),
          ...(c.external_source ? {external_source:c.external_source,external_chat_id:c.external_chat_id,trigger_source:"im"} : {})}};
      this.db.prepare("INSERT INTO relay_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)").run(id,m.id,c.id,a.node_id,JSON.stringify(payload),relayKey,"queued",null,null,now(),now());
      relays.push({relay_task_id:id,target_node_id:a.node_id,payload_json:JSON.stringify(payload),conversation_id:c.id});
    }
    return relays;
  }
  /** Queue other direct-chat Agents in the same transaction as a reviewed PA message. */
  queueDirectAgentRelays(message:Row):void {
    if(one(this.db,'SELECT type FROM conversations WHERE id=?',message.conversation_id)?.type!=='direct')return;
    this.enqueueRelays(message,null,this.relayAgents(message.conversation_id).filter(agent=>`agent:${agent.agent_id}`!==one(this.db,'SELECT username FROM users WHERE id=?',message.sender_user_id)?.username));
  }
  /** Recheck membership and lifecycle before either immediate or reconnect delivery. */
  relayEligible(task: Row): boolean {
    const payload = JSON.parse(task.payload_json), agent = one(this.db,"SELECT a.node_id,u.id FROM agent_profiles a JOIN users u ON u.username='agent:'||a.agent_id WHERE a.agent_id=? AND a.is_stale=0",payload.agent_id);
    const epoch = one(this.db, 'SELECT node_epoch FROM node_binding_state WHERE node_id=?', task.target_node_id)?.node_epoch ?? 0;
    if (payload.metadata?.node_epoch !== undefined && payload.metadata.node_epoch !== epoch) return false;
    return !!agent && agent.node_id===task.target_node_id && !!conversationAccess(this.db,task.conversation_id,agent.id)?.can_write;
  }
  deliverRelays(relays: Row[]): boolean {
    let sent = false;
    for (const task of relays) {
      if (!this.relayEligible(task)) {
        this.db.prepare("UPDATE relay_tasks SET status='cancelled',updated_at=? WHERE relay_task_id=?").run(now(),task.relay_task_id);
        continue;
      }
      if (this.ctx.updates?.acceptingQueue(task.target_node_id)) {
        sent = true;
        continue;
      }
      if (this.ctx.gateway.send(task.target_node_id,{type:"relay.message",payload:JSON.parse(task.payload_json)})) {
        this.db.prepare("UPDATE relay_tasks SET status='sent',updated_at=? WHERE relay_task_id=?").run(now(),task.relay_task_id);
        sent = true;
      }
    }
    return sent;
  }
  /** Publish committed system messages and attempt their already durable relay rows. */
  publishMessages(messages: Row[]) {
    let delivered = false;
    for (const m of messages) {
      const e = one(this.db,"SELECT * FROM conversation_events WHERE message_id=? AND event_type='message.created'",m.id)!;
      const data = JSON.parse(e.payload_json);
      this.ctx.gateway.broadcast(this.members(m.conversation_id).map(u=>u.id),{op:"event",event_id:e.event_id,conversation_id:m.conversation_id,message_id:m.id,event_type:e.event_type,delivery_status:e.delivery_status,created_at:e.created_at,data:{...data,...this.message(m.id),message_id:m.id,event_id:e.event_id}});
      delivered = this.deliverRelays(all(this.db,"SELECT * FROM relay_tasks WHERE message_id=? AND status='queued'",m.id)) || delivered;
    }
    return delivered;
  }
  /** Join only the caller, without changing invitation authority for other Agents. */
  joinConversation(userId: string, id: string): Row {
    const c = conversationAccess(this.db,id,userId);
    if (!c || c.type !== "group" || c.visibility !== "public") fail(404,"conversation_id not found");
    if (c.dissolved_at) fail(409,{code:"conversation_dissolved",message:"This conversation has been dissolved"});
    this.db.prepare("INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES(?,?)").run(id,userId);
    this.membership(id,this.members(id).map(u=>u.id));
    return this.conversation(id,userId);
  }
  /** Freeze group history and close unfinished records without generating task notices. */
  dissolveConversation(userId: string, id: string) {
    const c = conversationAccess(this.db,id,userId);
    if (!c?.can_write) fail(404,"conversation_id not found");
    if (c.creator_id !== userId) fail(403,"only creator can delete group");
    transaction(this.db,()=>{
      const at = now();
      this.db.prepare("UPDATE conversations SET dissolved_at=? WHERE id=?").run(at,id);
      for (const row of all(this.db,"SELECT * FROM task_graphs WHERE conversation_id=?",id)) {
        const d=JSON.parse(row.document_json);
        for (const n of d.nodes) if (!["done","closed"].includes(n.status)) {n.status="closed";n.updated_at=at;}
        for (const n of d.nodes) {
          if (n.selected_candidate_id && d.nodes.some((candidate: Row)=>candidate.id===n.selected_candidate_id && candidate.status==="closed")) n.selected_candidate_id=null;
        }
        d.revision++; d.updated_at=at;
        this.db.prepare("UPDATE task_graphs SET document_json=?,revision=?,updated_at=? WHERE graph_id=?").run(JSON.stringify(d),d.revision,at,row.graph_id);
      }
      this.db.prepare("UPDATE relay_tasks SET status='cancelled',updated_at=? WHERE conversation_id=? AND status IN ('queued','sent','accepted')").run(at,id);
    });
    this.membership(id,this.members(id).map(u=>u.id));
  }
  /** Resolve an authorized send target.
   *
   * Args:
   *   agentId: Sending Agent identity used for membership and space checks.
   *   target: Conversation, user or Agent address accepted by message delivery.
   *   create: False for lookup without creating an empty direct conversation.
   *
   * Returns:
   *   Authorized conversation ID, or undefined for a new direct target in lookup mode.
   *
   * Side Effects:
   *   Creates a direct conversation only in the default delivery mode.
   */
  resolveTarget(agentId: string, target: string): string;
  resolveTarget(agentId: string, target: string, create: false): string | undefined;
  resolveTarget(agentId: string, target: string, create = true): string | undefined {
    const a = this.agentUser(agentId);
    const personal=one(this.db,'SELECT * FROM personal_agent_bindings WHERE agent_id=?',agentId);
    if(personal && [personal.owner_id,personal.owner_user_id,`user:${personal.owner_user_id}`,`user:${personal.owner_id}`,personal.conversation_id,`conversation:${personal.conversation_id}`].includes(target))return personal.conversation_id;
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
      if (!canActorAccess(this.db, a.id, one(this.db, "SELECT space_id FROM conversations WHERE id=?", c.id)!.space_id)) fail(404, "target not accessible");
      return c.id;
    }
    const uid = target.replace(/^(?:user|agent):/, "");
    const u = one(this.db, "SELECT * FROM users WHERE id=? OR username=?", uid, `agent:${uid}`);
    if (!u || !canActorAccess(this.db, a.id, a.space_id) || !canActorAccess(this.db, u.id, a.space_id))
      fail(404, "target not accessible");
    const pairKey = [a.id, u.id].sort().join("|");
    const key = `${a.space_id}|${pairKey}`;
    const old = one(this.db, "SELECT id FROM conversations WHERE space_id=? AND (direct_key=? OR direct_key=?)", a.space_id, key, pairKey);
    if (old) return old.id;
    if (!create) return;
    const id = chatId("c_");
    this.db
      .prepare(
        "INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at,space_id) VALUES(?,?,?,?,?,?,?,?)",
      )
      .run(id, u.display_name, "direct", a.owner_id, a.id, key, now(), a.space_id);
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
  const contactRows = (viewer: Row) =>
    all(
      db,
      "SELECT u.id AS user_id,CASE WHEN ap.agent_id IS NULL THEN 'human' ELSE 'agent' END AS kind,COALESCE(ap.display_name,u.display_name) AS display_name,ap.agent_id,ap.owner_id,ap.space_id,owner.display_name AS owner_display_name,COALESCE(NULLIF(n.alias,''),n.node_name) AS node_name,COALESCE(n.status,'offline') AS status,ap.work_mode FROM users u LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id LEFT JOIN users owner ON owner.id=ap.owner_id LEFT JOIN nodes n ON n.node_id=ap.node_id WHERE (u.password_hash IS NOT NULL AND u.password_hash!='' AND ap.agent_id IS NULL) OR (ap.agent_id IS NOT NULL AND ap.is_stale=0) ORDER BY u.id",
    ).filter(r => {
      if (r.kind === "human") {
        const target = one(db, "SELECT * FROM users WHERE id=?", r.user_id)!;
        return target.id === viewer.id || (viewer.membership_status === "active" && target.membership_status === "active");
      }
      const profile = one(db, "SELECT * FROM agent_profiles WHERE agent_id=?", r.agent_id)!;
      return (canAccessSpace(viewer, profile.space_id)||canContactPersonalAgent(db,viewer,profile)) && agentAvailable(db, profile);
    }).map((r) =>
      r.kind === "human" ? { user_id: r.user_id, kind: r.kind, display_name: r.display_name } : one(db,"SELECT 1 FROM personal_agent_bindings WHERE agent_id=?",r.agent_id) ? {user_id:r.user_id,kind:r.kind,display_name:r.display_name,agent_id:r.agent_id,owner_id:r.owner_id,owner_display_name:r.owner_display_name,role:"personal",status:r.status} : r,
    );
  app.get("/im/v1/contacts", (req) => {
    const viewer = ctx.identity.authenticateRequest(req);
    const q = query(req);
    if (q.kind && !["human", "agent"].includes(q.kind)) fail(400, "invalid kind");
    const rows = contactRows(viewer).filter(
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
    const viewer = ctx.identity.authenticateRequest(req);
    const r = contactRows(viewer).find((r) => r.user_id === params(req).user_id);
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
    return { items: s.conversations(uid,query(req).scope ?? "joined") };
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
  app.post("/im/v1/conversations/:conversation_id/join",req=>{
    const p=ctx.identity.authenticateRequest(req);
    return s.joinConversation(p.id,params(req).conversation_id);
  });
  app.patch("/im/v1/conversations/:conversation_id", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      b = body(req);
    const c = s.access(p, id, undefined, "write");
    if (b.visibility !== undefined) {
      if (!c.can_change_visibility) fail(403,"Only a joined company administrator can change visibility");
      if (!["public","private"].includes(b.visibility)) fail(400,"invalid visibility");
    }
    if (b.title !== undefined) {
      if (!b.title.trim()) fail(400, "title must be non-empty");
      db.prepare("UPDATE conversations SET title=?,title_is_custom=1 WHERE id=?").run(
        b.title.trim(),
        id,
      );
    }
    if (b.visibility !== undefined) db.prepare("UPDATE conversations SET visibility=? WHERE id=?").run(b.visibility,id);
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
      c = s.access(p, id, undefined, "write");
    if (c.type === "group" && c.creator_id !== p.id) fail(403, "only creator can delete group");
    const recipients = s.members(id).map((u) => u.id);
    if (c.type === "group") s.dissolveConversation(p.id,id);
    else db.prepare("DELETE FROM conversations WHERE id=?").run(id);
    s.membership(id, recipients);
    reply.code(204).send();
  });
  app.post("/im/v1/conversations/:conversation_id/participants", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      c = s.access(p, id, undefined, "write");
    if (c.type !== "group") fail(400, "group required");
    const ids = s.resolveParticipants(p, body(req).participants ?? [], [], true, c.space_id);
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
      c = s.access(p, id, undefined, "write");
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
  app.get('/im/v1/conversations/:conversation_id/messages/:message_id/interaction-state', req => s.interactions.readDraft(req));
  app.put('/im/v1/conversations/:conversation_id/messages/:message_id/interaction-state', req => s.interactions.writeDraft(req));
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
