import {rejectDeletedExecution} from './agent-deletion.js';
import { requireLifecycle } from './agent-lifecycle.js';
import { canAccessSpace, agentAvailable } from "./identity.js";
import { createHash, randomUUID } from "node:crypto";
import { searchMessages } from "./message-search.js";
import type { FastifyInstance } from "fastify";
import {
  all,
  one,
  fail,
  body,
  params,
  query,
  type Row,
  type ImContext,
} from "./context.js";
import { conversationAccess, qualifiedUser } from "./conversation-access.js";
import { decodeWorkBatch, WorkEventError, type WorkAppendAck, type WorkSessionFields, formatLocalTime, projectChatReplyContext } from "@nano/product-contracts";
import type { Connection } from './gateway.js';
import { WorkRecords } from './work-records.js';
import type { WorkWindow } from './work-summaries.js';
import type { WorkCatalogFilter, WorkView } from './work-record-types.js';
/** Decode the wire batch before receipt checks or durable projection.
 * Args:
 *   input: Untrusted HTTP/WS body retaining the original event objects.
 * Returns:
 *   A validated batch, or the existing transport error shape.
 */
export function readWorkBatch(input: unknown) {
  try { return decodeWorkBatch(input); }
  catch (error) { if (error instanceof WorkEventError) fail(400, error.message); throw error; }
}
export class Work {
  private readonly progress = new WeakMap<Connection, { journal: string; produced: number; pending: boolean }>();

  /** Accept a completeness declaration only for the connection that received it.
   *
   * Args:
   *   connection: Registration active when the authenticated HTTP request began.
   *   journal: Durable source journal identity.
   *   produced: Highest locally committed product event sequence.
   *   pending: Whether product projection still has unprocessed source facts.
   */
  reportProgress(connection: Connection, journal: string, produced: number, pending: boolean): void {
    if (this.ctx.gateway.nodes.get(connection.node_id) === connection && this.ctx.gateway.valid(connection))
      this.progress.set(connection, { journal, produced, pending });
  }

  private recordSyncState(node: string): 'current' | 'catching_up' | 'unknown' {
    const connection = this.ctx.gateway.nodes.get(node);
    const report = connection && this.ctx.gateway.valid(connection) && this.progress.get(connection);
    if (!report) return 'unknown';
    const through = one(this.db, 'SELECT through_seq FROM agent_work_journals WHERE node_id=? AND journal_id=?', node, report.journal)?.through_seq ?? 0;
    if (through > report.produced) return 'unknown';
    return report.pending || through < report.produced ? 'catching_up' : 'current';
  }

  private readonly records: WorkRecords;
  constructor(readonly ctx: ImContext) { this.records = new WorkRecords(ctx.db); }
  get db() { return this.ctx.db; }
  register(root: string, session: string, node: string, payload: WorkSessionFields) {
    this.records.register(root, session, node, payload);
  }
  session(root: string, id: string) { return this.records.session(root, id); }
  catalog(root: string, after: string, limit: number, filter: WorkCatalogFilter) {
    return this.records.catalog(root, after, limit, filter);
  }
  items(root: string, session: string, turn: string, after = 0, limit = 100, afterRevision?: number, watermarked = false, preview = false) {
    return this.records.items(root, session, turn, after, limit, afterRevision, watermarked, preview);
  }
  item(root: string, session: string, turn: string, id: string) {
    return this.records.item(root, session, turn, id);
  }
  turns(root: string, session: string, before?: string, limit = 20, summary = false, separate = false) {
    const page = this.records.turns(root, session, before, limit, summary, separate);
    if (!separate) return page;
    const agent = one(this.db, "SELECT node_id FROM agent_profiles WHERE agent_id=?", root)!;
    return {...page, catalog: 'separate', revision: this.revision(root), ...this.connection(agent.node_id)};
  }
  revision(root: string) { return this.records.revision(root); }
  focus(root: string, messageId: string, separate = false) { return this.records.focus(root, messageId, separate); }
  append(node: string, input: unknown, historical = false): WorkAppendAck {
    const batch = readWorkBatch(input);
    const {ack, appliedRoots} = this.records.append(node, batch, historical);
    for (const root of appliedRoots) {
      const personal = one(this.db, "SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?", root);
      const space = one(this.db, "SELECT space_id FROM agent_profiles WHERE agent_id=?", root)!.space_id;
      const users = all(
        this.db,
        "SELECT * FROM users WHERE (personal_space_enabled=1 OR membership_status='active') AND password_hash IS NOT NULL",
      ).filter(u => (!personal || personal.owner_user_id === u.id) && canAccessSpace(u, space)).map((u) => u.id);
      this.ctx.gateway.broadcast(users, {
        op: "event",
        event_type: "agent.work.updated",
        data: { agent_id: root, revision: this.revision(root) },
      });
    }
    return ack;
  }
  private connection(node: string) {
    return {
      node_connection_state: this.ctx.gateway.isOnline(node) ? 'online' as const : 'offline' as const,
      record_sync_state: this.recordSyncState(node),
    };
  }
  view(root: string, before?: string, limit = 20, summary = false, messageId?: string, separate = false, combinedBefore?: number): WorkView {
    const {node_id, ...view} = this.records.view(root, before, limit, summary, messageId, separate, combinedBefore);
    const connection = this.connection(node_id);
    return {...view, ...connection,
      main_execution: connection.node_connection_state === 'offline' && ['running', 'waiting_permission'].includes(view.main_execution) ? 'unknown' : view.main_execution,
    };
  }
  /** Read activity without materializing the main timeline or catalog. */
  activity(root: string, node: string, after: string, limit: number) {
    const connection = this.connection(node);
    const main = this.records.mainSessionId(root);
    return {...connection, revision: this.revision(root), main_session_id: main,
      ...this.records.summaries.activity(root, main,
        connection.node_connection_state === 'online' && connection.record_sync_state === 'current', after, limit)};
  }

  /** Read the delegation window under the same Agent scope as Work records. */
  delegation(root: string, node: string, window: WorkWindow, until: string, after: string, limit: number) {
    const connection = this.connection(node);
    const main = this.records.mainSessionId(root);
    return {...connection, revision: this.revision(root), main_session_id: main,
      ...this.records.summaries.delegation(root, main, window, until, after, limit)};
  }

  query(c: Row, p: Row): Row {
    if (p.keywords !== undefined && (p.query !== undefined || p.keyword !== undefined)) fail(400, 'invalid_arguments');
    if (p.keywords !== undefined && (!Array.isArray(p.keywords) || p.keywords.some((v: unknown) => typeof v !== 'string'))) fail(400, 'invalid_arguments');
    const keywords: string[] | undefined = p.keywords === undefined ? undefined : [...new Set<string>(p.keywords.map((v: string) => v.trim().replace(/[A-Z]/g, letter => letter.toLowerCase())).filter(Boolean))];
    p={...p,query:p.keyword??p.query};
    const memory = p.memory_cutoff !== undefined;
    if (memory && (!['info', 'read', 'search'].includes(p.action) || typeof p.target !== 'string' || !p.target ||
      typeof p.memory_cutoff !== 'number' || !Number.isFinite(p.memory_cutoff) || typeof p.memory_after !== 'number' ||
      !Number.isFinite(p.memory_after) || p.memory_after > p.memory_cutoff)) fail(400, 'invalid_memory_range');
    if(p.message_id&&!p.target)p={...p,target:one(this.db,'SELECT conversation_id FROM messages WHERE id=?',p.message_id)?.conversation_id};
    const agent = one(
        this.db,
        "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND is_stale=0",
        p.agent_id,
        c.node_id,
      );
    if (!agent || !agentAvailable(this.db, agent)) fail(403, "scope_not_allowed");
    // Single-thread sessions live on their node, not in the global Work journal.
    // PA queries additionally intersect owner participation with current source access.
    if (agent.work_mode === "global") {
      const session = this.session(p.agent_id, p.session_id);
      if (session.node_id !== c.node_id || session.scope !== "global_main" || session.retired)
        fail(403, "scope_not_allowed");
    }
    const limit = p.limit ?? 20;
    if (
      !Number.isInteger(limit) ||
      limit < 1 ||
      limit > 50 ||
      !["list", "read", "search", "info", "describe", "resolve_target", "create", "join"].includes(p.action)
    )
      fail(400, "invalid_arguments");
    const personal = one(this.db,"SELECT * FROM personal_agent_bindings WHERE agent_id=?",p.agent_id);
    if(personal) this.ctx.personal!.authority(c,p);
    const s = this.ctx.messaging,
      uid = personal?.owner_user_id ?? s.agentUser(p.agent_id).id,
      sourceAllowed = (id:string) => !personal || this.ctx.personal!.sourceAllowed(personal,id);
    const scope = p.scope ?? "joined";
    if (!["joined", "public"].includes(scope)) fail(400, "invalid scope");
    // Targeted reads validate their own access; only discovery needs every chat.
    let listedConversations: Row[] | undefined;
    const conversations = () => listedConversations ??= personal ? this.ctx.personal!.sourceConversations(personal,scope).filter(r=>!r.excluded) : s.conversations(uid,scope);
    const viewerFor=(id:string)=>personal&&!conversationAccess(this.db,id,uid)?s.agentUser(p.agent_id).id:uid;
    const user = qualifiedUser(this.db,uid);
    if (!user) fail(403,"scope_not_allowed");
    if (p.action === "resolve_target") {
      if (typeof p.target !== "string" || !p.target.trim()) fail(400, "invalid_arguments");
      if(personal) {
        const target=p.target.replace(/^(conversation|user|agent):/, "");
        const matches=conversations().filter(r=>r.id===target || r.title===target || (r.type==="direct" && s.members(r.id).some(u=>u.id===target || u.display_name===target || u.username===`agent:${target}`)));
        return {target:matches.length===1?matches[0]!.id:null};
      }
      return { target: s.resolveTarget(p.agent_id, p.target, false) ?? null };
    }
    if (p.action === "create") {
      if (p.type && p.type !== "group") fail(400,"Only group creation is supported here");
      const created = s.createConversation({...qualifiedUser(this.db,s.agentUser(p.agent_id).id),kind:"agent"},{title:p.title,type:"group",visibility:p.visibility,participant_ids:p.participant_ids ?? []});
      return {target:created.id,name:created.title,conversation:created};
    }
    if (p.action === "join") {
      const joined = s.joinConversation(s.agentUser(p.agent_id).id,p.target);
      return {target:joined.id,name:joined.title,conversation:joined};
    }
    const members = (id: string) =>
      s.members(id).map((u) => ({
        id: u.id,
        name: u.display_name,
        kind: u.username.startsWith("agent:") ? "agent" : "user",
        ...(u.username.startsWith("agent:") ? { agent_id: u.username.slice(6) } : {}),
      }));
    if (p.action === "describe")
      return {
        conversations: (p.targets ?? []).filter((id:string)=>sourceAllowed(id)&&!!conversationAccess(this.db,id,viewerFor(id))).map((id:string)=>s.conversation(id,viewerFor(id)))
          .map((r: Row) => ({
            target: r.id,
            name: r.title,
            kind: r.type,
            channel: r.external_source ?? "web",
            participants: members(r.id),
          })),
      };
    const target = p.target && sourceAllowed(p.target) && conversationAccess(this.db,p.target,viewerFor(p.target)) ? s.conversation(p.target,viewerFor(p.target)) : undefined;
    if (p.sort !== undefined && !['relevance', 'recent'].includes(p.sort)) fail(400, 'invalid_arguments');
    if (p.sender_source_id && (!p.target || !target?.external_source || p.participant_id)) fail(400, 'invalid_arguments');
    if (p.around_message_id && (p.action !== 'read' || !p.target || p.message_id || p.query || p.keywords || p.before || p.after || p.participant_id || p.sender_source_id)) fail(400, 'invalid_arguments');
    if (p.action === "info") {
      if (!target) fail(404, "target_not_accessible");
      return {
        target: p.target,
        ...(memory ? { metadata_scope: 'current', history_cutoff: p.memory_cutoff } : {}),
        name: target.title,
        type: target.type,
        channel: target.external_source ?? "web",
        visibility:target.visibility,is_member:target.is_member,can_write:target.can_write,dissolved_at:target.dissolved_at,
        members: members(p.target).map((m) => ({
          user_id: m.id,
          name: m.name,
          type: m.kind,
          mention: `<mention type="user" target_id="${m.id}"/>`,
        })),
      };
    }
    const identity: Row = {
      agent: p.agent_id,
      action: p.action,
      target: p.target ?? null,
      query: p.query ?? null,
      participant_id: p.participant_id ?? null,
      message_id: p.message_id ?? null,
      before: p.before ?? null,
      after: p.after ?? null,
      scope: p.scope ?? "joined",
      ...(memory ? {memory_cutoff:p.memory_cutoff,memory_after:p.memory_after} : {}),
    };
    const newIdentity: Row = { ...identity, keywords: keywords ?? null, sort: p.action === 'search' ? p.sort ?? 'relevance' : null,
      sender_source_id: p.sender_source_id ?? null, around_message_id: p.around_message_id ?? null };
    let cursor: Row | undefined, snapshot: Row | undefined;
    if (p.cursor) {
      try {
        cursor = JSON.parse(Buffer.from(p.cursor, "base64url").toString());
        const r = one(
          this.db,
          "SELECT data FROM agent_work_query_snapshots WHERE snapshot_id=?",
          cursor!.snapshot,
        );
        if (!r) throw Error();
        snapshot = JSON.parse(r.data);
        if (!memory && snapshot!.memory_cutoff !== undefined) throw Error();
        if (snapshot!.version !== 2 && (p.keywords !== undefined || p.sort !== undefined || p.sender_source_id !== undefined || p.around_message_id !== undefined)) throw Error();
        if (
          !Number.isInteger(cursor!.offset) ||
          cursor!.offset < 0 ||
          !Number.isInteger(cursor!.part) ||
          cursor!.part < 0 ||
          Object.keys(snapshot!.version === 2 ? newIdentity : identity).some((k) => JSON.stringify(snapshot![k]) !== JSON.stringify((snapshot!.version === 2 ? newIdentity : identity)[k]))
        )
          throw Error();
      } catch {
        fail(400, "invalid_cursor");
      }
    }
    const next = (ids: string[], offset: number, part = 0) => {
      const id = cursor?.snapshot ?? randomUUID();
      if (!cursor)
        this.db
          .prepare("INSERT INTO agent_work_query_snapshots VALUES(?,?)")
          .run(id, JSON.stringify({ ...newIdentity, version: 2, ids }));
      return Buffer.from(JSON.stringify({ snapshot: id, offset, part })).toString("base64url");
    };
    if (p.action === "list") {
      const filtered = conversations().filter(
        (r) =>
          !p.query ||
          r.title.toLowerCase().includes(p.query.toLowerCase()) ||
          members(r.id).some((m) => m.name.toLowerCase().includes(p.query.toLowerCase())),
      );
      const ids: string[] = snapshot?.ids ?? filtered.map((r) => r.id),
        byId = new Map(filtered.map((r) => [r.id, r]));
      let offset = cursor?.offset ?? 0;
      const page = [];
      while (offset < ids.length && page.length < limit) {
        const r = byId.get(ids[offset++]!);
        if (r)
          page.push({
            target: r.id,
            name: r.title,
            kind: r.type,
            channel: r.external_source ?? "web",
            participants: members(r.id),
            visibility:r.visibility,is_member:r.is_member,can_write:r.can_write,
            latest_message_at: r.last_message_at,
            history_availability: "im_history",
          });
      }
      return {
        conversations: page,
        has_more: offset < ids.length,
        next_cursor: offset < ids.length ? next(ids, offset) : null,
      };
    }
    if (!target && (p.action !== "search" || p.target)) fail(404, "target_not_accessible");
    if (p.before_message_id && cursor) fail(400, "invalid_arguments");
    const targets = p.action === 'search' ? (target ? [target.id] : conversations().map(r=>r.id)) : [p.target];
    const terms = keywords ?? (typeof p.query === 'string' && p.query.trim() ? [p.query] : []);
    const matches = searchMessages(this.db, { targets, terms, action:p.action, sort:p.sort, around:p.around_message_id,
      messageId:p.message_id, before:p.before, after:p.after, participantId:p.participant_id, senderSourceId:p.sender_source_id,
      ...(memory ? {memoryRange:{after:new Date(p.memory_after).toISOString(),cutoff:new Date(p.memory_cutoff).toISOString()}} : {}) });
    const matchesById = new Map(matches.map(row => [row.id, row]));
    let currentIds: string[] = matches.map(row=>row.id);
    if (p.around_message_id) {
      const index = currentIds.indexOf(p.around_message_id);
      if (index < 0) fail(404, 'target_not_accessible');
      if (!snapshot) currentIds = currentIds.slice(Math.max(0,index-5),index+6).reverse();
    }
    if (p.before_message_id) {
      const index = currentIds.indexOf(p.before_message_id);
      if (index < 0) fail(404, 'target_not_accessible');
      currentIds = currentIds.slice(index+1);
    }
    const ids: string[] = snapshot?.ids ?? currentIds,
      available = new Set(currentIds);
    let offset = cursor?.offset ?? 0,
      part = cursor?.part ?? 0,
      budget = 24000,
      images = 0;
    const page = [];
    while (offset < ids.length && page.length < limit) {
      const id = ids[offset]!;
      if (!available.has(id)) {
        offset++;
        part = 0;
        continue;
      }
      const m = s.message(id);
      if (!m.content && !m.attachments.length && !m.interactive) { offset++; part=0; continue; }
      const messageConversation = one(this.db,"SELECT * FROM conversations WHERE id=?",m.conversation_id)!;
      const personalFacts=personal?this.ctx.personal!.sourceFacts(personal,m):undefined;
      const externalHuman = !!messageConversation.external_source && m.sender_type === 'user' && !!m.sender_source_id;
      const parts: Row[] = [];
      for (let i = 0; i < m.content.length; i += 24000)
        parts.push({ type: "text", text: m.content.slice(i, i + 24000) });
      parts.push(
        ...m.attachments.map((a: Row) => ({
          type: a.content_type?.startsWith("image/") ? "image" : "attachment",
          ...a,
        })),
      );
      // A UI-only message needs one result row for its interactive payload.
      const partCount = Math.max(1, parts.length);
      while (part < partCount && page.length < limit) {
        const content = parts[part],
          cost = content?.text?.length ?? 0;
        if (cost > budget || (content?.type === "image" && images >= 4)) break;
        budget -= cost;
        if (content?.type === "image") images++;
        if(personal && !memory) this.db.prepare("INSERT OR REPLACE INTO pa_source_reads VALUES(?,?,?,?)").run(personal.binding_id,m.id,m.conversation_id,this.ctx.personal!.policy(personal.binding_id).revision);
        page.push({
          message_id: m.id,
          ...(memory ? { created_at: m.created_at, content_hash: createHash('sha256').update(m.content).digest('hex'),
            delivery: personalFacts?.delivery ?? 'participant', version_scope: 'verified_at_cutoff' } : {}),
          ...(m.pa_agent_id?{pa_agent_id:m.pa_agent_id}:{}),
          sender: {
            ...(!externalHuman ? { id: m.sender_user_id } : {}),
            name: externalHuman ? matchesById.get(m.id)?.sender_display_name || m.sender_source_id : m.sender.display_name,
            ...(personalFacts ? {is_owner:personalFacts.is_owner} : {}),
            kind: externalHuman ? "external" : m.sender_type,
            ...(externalHuman
              ? {
                  channel: messageConversation.external_source,
                  source_id: m.sender_source_id,
                }
              : {}),
          },
          source_time: formatLocalTime(m.created_at, m.timezone ?? undefined),
          source: {
            channel: messageConversation.external_source ?? "web",
            conversation_id: m.conversation_id,
            reply_target: m.conversation_id,
            target: m.conversation_id,
            name: target?.title ?? conversations().find((chat: Row) => chat.id === m.conversation_id)?.title ?? s.conversation(m.conversation_id, viewerFor(m.conversation_id)).title,
            ...(personalFacts?{conversation_type:personalFacts.conversation_type,delivery:personalFacts.delivery}:{}),
            ...(personal ? {owner_can_read: !!conversationAccess(this.db, m.conversation_id, personal.owner_user_id)} : {}),
            url: `${this.ctx.publicUrl.replace(/\/$/, '')}/chat/${encodeURIComponent(m.conversation_id)}?message_id=${encodeURIComponent(m.id)}`,
          },
          ...(m.interactive ? {interactive:Object.fromEntries(Object.entries(m.interactive).filter(([key])=>key!=='format'&&key!=='catalog_version'))} : {}),
          ...(m.reply_to ? {reply_to:projectChatReplyContext(m.reply_to)} : {}),
          ...(m.interaction_reply ? {interaction_reply:m.interaction_reply} : {}),
          part_key: String(part),
          total_parts: partCount,
          content: content ? [content] : [],
          complete_message: partCount === 1,
        });
        part++;
      }
      if (part < partCount) break;
      offset++;
      part = 0;
    }
    return {
      target: p.target,
      name: target?.title,
      kind: target?.type,
      channel: target?.external_source ?? "web",
      messages: page,
      history_scope: "im_history",
      ...(memory ? { history_cutoff: p.memory_cutoff, history_after: p.memory_after,
        availability: 'Only versions with durable matching snapshots at the cutoff are included; later or unproven versions are unavailable.' } : {}),
      has_more: offset < ids.length,
      next_cursor: offset < ids.length ? next(ids, offset, part) : null,
    };
  }
}
export function registerWorkRoutes(app: FastifyInstance, ctx: ImContext) {
  const db = ctx.db,
    w = ctx.gateway.work;
  function profile(req: any, owner = false) {
    const user = ctx.identity.authenticateRequest(req),
      id = params(req).agent_id;
    const p = one(
      db,
      "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0 AND work_mode='global'",
      id,
    );
    const personal=one(db,"SELECT owner_user_id FROM personal_agent_bindings WHERE agent_id=?",id);
    if (!p || (owner && p.owner_id !== user.owner_id) || (personal && personal.owner_user_id!==user.id)) fail(404, "agent_not_accessible");
    ctx.identity.requireSpace(user, p.space_id);
    if (one(db,'SELECT 1 FROM agent_deletions WHERE agent_id=?',id)) fail(409,'agent_deletion_requested');
    return p;
  }
  function integer(value: unknown, fallback: number): number {
    if (value === undefined) return fallback;
    const n = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : NaN;
    if (!Number.isSafeInteger(n)) fail(400, 'invalid_arguments');
    return n;
  }
  const boundedLimit = (value: unknown, fallback: number, maximum: number) =>
    Math.min(maximum, Math.max(1, integer(value, fallback)));
  function readable(req: Parameters<typeof params>[0], session?: string) {
    const id = params(req).agent_id;
    rejectDeletedExecution(ctx, ctx.identity.authenticateRequest(req), id, session ? 'session' : 'agent', session ?? id);
    return profile(req).agent_id;
  }
  app.get("/im/v1/agents/:agent_id/work", (req) => {
    const q = query(req), agentId = params(req).agent_id;
    rejectDeletedExecution(ctx,ctx.identity.authenticateRequest(req),agentId,q.message_id ? 'message' : 'agent',q.message_id ?? agentId);
    const p = profile(req);
    const combined = q.timeline === 'combined';
    if (q.timeline !== undefined && (!combined || q.catalog !== 'separate' || q.before_turn !== undefined)) fail(400, 'invalid_arguments');
    const before = combined ? integer(q.before_seq, Number.MAX_SAFE_INTEGER) : undefined;
    return w.view(p.agent_id, q.before_turn, boundedLimit(q.limit, 20, 50), q.view === 'summary', q.message_id, q.catalog === 'separate', before);
  });
  app.get("/im/v1/agents/:agent_id/work/activity", (req) => {
    const q = query(req), root = readable(req);
    if (q.after_session !== undefined && typeof q.after_session !== 'string') fail(400, 'invalid_arguments');
    const node = one(db, 'SELECT node_id FROM agent_profiles WHERE agent_id=?', root)!.node_id;
    return w.activity(root, node, q.after_session ?? '', boundedLimit(q.limit, 12, 24));
  });
  app.get("/im/v1/agents/:agent_id/work/delegation", (req) => {
    const q = query(req), root = readable(req);
    const window = q.window ?? '3d';
    const now = Date.now();
    if ((window !== '3d' && window !== '2h') ||
      (q.after_session !== undefined && typeof q.after_session !== 'string')) fail(400, 'invalid_arguments');
    const time = q.until === undefined ? now : typeof q.until === 'string' ? Date.parse(q.until) : NaN;
    if (!Number.isFinite(time) || time > now || time < 0) fail(400, 'invalid_arguments');
    const node = one(db, 'SELECT node_id FROM agent_profiles WHERE agent_id=?', root)!.node_id;
    return w.delegation(root, node, window, new Date(time).toISOString(), q.after_session ?? '', boundedLimit(q.limit, 24, 24));
  });
  app.get("/im/v1/agents/:agent_id/work/focus", (req) => {
    const messageId = query(req).message_id, agentId = params(req).agent_id;
    const user = ctx.identity.authenticateRequest(req);
    if (typeof messageId !== "string" || !messageId) fail(400, "invalid_arguments");
    rejectDeletedExecution(ctx, user, agentId, 'message', messageId);
    return {focus: w.focus(profile(req).agent_id, messageId, query(req).catalog === 'separate')};
  });
  app.get("/im/v1/agents/:agent_id/work/sessions", (req) => {
    const q = query(req), root = readable(req);
    for (const field of ['after_session', 'parent_session_id', 'tool_call_id', 'child_agent_id'])
      if (q[field] !== undefined && (typeof q[field] !== 'string' || !q[field])) fail(400, 'invalid_arguments');
    if ((q.tool_call_id && !q.parent_session_id) || (q.parent_session_id && !q.tool_call_id && !q.child_agent_id)) fail(400, 'invalid_arguments');
    return w.catalog(root, q.after_session ?? '', boundedLimit(q.limit, 20, 50),
      {parent: q.parent_session_id, call: q.tool_call_id, agent: q.child_agent_id});
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id", (req) => {
    const id = params(req).session_id;
    return w.session(readable(req, id), id);
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id/turns", (req) => {
    const id = params(req).session_id, q = query(req);
    return w.turns(readable(req, id), id, q.before_turn, boundedLimit(q.limit, 20, 50), q.view === 'summary', q.catalog === 'separate');
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id/controls", (req) => {
    const id = params(req).session_id, q = query(req);
    return w.items(readable(req, id), id, '', integer(q.after_seq, 0), boundedLimit(q.limit, 20, 100));
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id/turns/:turn_id/items", (req) => {
    const p = params(req), q = query(req);
    const preview = q.view === 'preview';
    const watermarked = preview || q.catalog === 'separate';
    return w.items(readable(req, p.session_id), p.session_id, p.turn_id, integer(q.after_seq, 0),
      boundedLimit(q.limit, watermarked ? 20 : 100, preview ? 20 : 200),
      q.after_revision === undefined ? undefined : integer(q.after_revision, 0), watermarked, preview);
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id/turns/:turn_id/items/:item_id", (req) => {
    const p = params(req);
    return w.item(readable(req, p.session_id), p.session_id, p.turn_id, p.item_id);
  });
  app.post("/im/v1/agents/:agent_id/work/permissions/:request_id", async (req) => {
    const a = profile(req, true),
      id = params(req).request_id,
      b = body(req);
    const item = all(
      db,
      "SELECT i.*,s.node_id FROM agent_work_items i JOIN agent_work_sessions s USING(session_id) WHERE s.root_agent_id=? AND i.item_id=?",
      a.agent_id,
      `permission:${id}`,
    ).find((r) => {
      const p = JSON.parse(r.payload),
        t = one(
          db,
          "SELECT payload FROM agent_work_turns WHERE session_id=? AND turn_id=?",
          r.session_id,
          r.turn_id,
        );
      return (
        p.status === "pending" &&
        p.node_epoch ===
          (one(db, "SELECT node_epoch FROM node_binding_state WHERE node_id=?", r.node_id)
            ?.node_epoch ?? 0) &&
        t &&
        ["running", "waiting_permission", "unknown"].includes(JSON.parse(t.payload).status)
      );
    });
    if (!item) fail(409, "request_ended");
    requireLifecycle(db,a.agent_id,JSON.parse(item.payload).lifecycle_revision);
    if (!JSON.parse(item.payload).options?.some((o: Row) => o.id === b.decision))
      fail(409, "invalid_decision");
    const result = await ctx.gateway.request(a.node_id, "agent.work.permission", {
      request_id: id,
      root_agent_id: a.agent_id,
      lifecycle_revision:JSON.parse(item.payload).lifecycle_revision,
      session_id: item.session_id,
      decision: b.decision,
      reason: b.reason ?? "",
    });
    if (!result.ok) fail(409, result.error ?? "request_ended");
    return { ok: true, request_id: id };
  });
}
