import { randomBytes } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';

type ObjectValue = Record<string, unknown>;

/** Hard upper bound for every atomic identifier an Agent must pass into tool arguments. */
export const MAX_AGENT_ID_LENGTH = 8;

const SUPPORTED_METHODS = new Set([
  'inbox', 'conversations', 'read_messages', 'search_messages', 'threads',
  'send_message', 'send_user_message', 'send_message.context', 'send_user_message.context',
  'task_graph', 'personal_sources',
]);

/** Split a unified conversation or thread target (`<chat>` or `<chat>:<root>`) without breaking prefixed targets. */
export function splitThreadTarget(raw: string): { base: string; root?: string } {
  if (!raw || raw.startsWith('external:') || raw.startsWith('user:') || raw.startsWith('agent:')) return { base: raw };
  const prefix = raw.startsWith('conversation:') ? 'conversation:' : '';
  const body = raw.slice(prefix.length);
  if (body.startsWith('external:')) return { base: raw };
  const index = body.indexOf(':');
  if (index <= 0) return { base: raw };
  const root = body.slice(index + 1);
  return { base: prefix + body.slice(0, index), root: root || undefined };
}

/** Combine a base conversation target and optional thread root message ID into one unified target. */
export function joinThreadTarget(base: string, root?: string): string {
  return root ? `${base}:${root}` : base;
}

/** Store durable <= 8-char model references without replacing the product's access checks.
 *
 * Args:
 *   db: Owner-bound Node database; mappings share its backup and lifetime.
 */
export class ToolReferences {
  constructor(private readonly db: DatabaseSync) {
    db.exec(`CREATE TABLE IF NOT EXISTS tool_references (
      reference TEXT PRIMARY KEY, agent_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL,
      UNIQUE(agent_id,kind,value)
    )`);
  }

  private reference(agent: string, kind: string, value: string, prefix: string, preferred?: string): string {
    const existing = this.db.prepare('SELECT reference FROM tool_references WHERE agent_id=? AND kind=? AND value=?').get(agent, kind, value) as { reference: string } | undefined;
    if (existing) return existing.reference;
    const randomLen = Math.max(1, Math.floor((MAX_AGENT_ID_LENGTH - prefix.length) / 2));
    let candidate = preferred;
    while (true) {
      const reference = candidate ?? (prefix + randomBytes(randomLen).toString('hex').slice(0, MAX_AGENT_ID_LENGTH - prefix.length));
      candidate = undefined;
      const inserted = this.db.prepare('INSERT OR IGNORE INTO tool_references VALUES(?,?,?,?)').run(reference, agent, kind, value);
      if (inserted.changes) return reference;
      const raced = this.db.prepare('SELECT reference FROM tool_references WHERE agent_id=? AND kind=? AND value=?').get(agent, kind, value) as { reference: string } | undefined;
      if (raced) return raced.reference;
    }
  }

  private resolve(agent: string, kind: string, reference: string): string {
    const row = this.db.prepare('SELECT value FROM tool_references WHERE reference=? AND agent_id=? AND kind=?').get(reference, agent, kind) as { value: string } | undefined;
    if (!row) throw new Error('Unknown tool reference or reference outside this Agent/tool scope');
    return row.value;
  }

  private resolveOptional(agent: string, kind: string, reference: string): string | undefined {
    const row = this.db.prepare('SELECT value FROM tool_references WHERE reference=? AND agent_id=? AND kind=?').get(reference, agent, kind) as { value: string } | undefined;
    return row?.value;
  }

  /** Compact any conversation ID longer than 8 chars (and all external IDs) to <= 8 chars. */
  conversationRef(agent: string, value: string): string {
    const clean = value.replace(/^conversation:/, '');
    if (clean.startsWith('external:')) return this.reference(agent, 'conversation', clean, 'f_');
    if (clean.length > MAX_AGENT_ID_LENGTH) return this.reference(agent, 'conversation', clean, 'c_');
    return clean;
  }

  /** Compact any message ID longer than 8 chars to an 8-char hex reference, preferring its hex prefix. */
  messageRef(agent: string, value: string): string {
    if (!value || value.length <= MAX_AGENT_ID_LENGTH) return value;
    const preferred = /^[0-9a-f]{8}/i.test(value) ? value.slice(0, MAX_AGENT_ID_LENGTH).toLowerCase() : undefined;
    return this.reference(agent, 'message', value, '', preferred);
  }

  /** Compact any user ID longer than 8 chars to an 8-char `u_xxxxxx` reference. */
  userRef(agent: string, value: string): string {
    if (!value || value.length <= MAX_AGENT_ID_LENGTH) return value;
    return this.reference(agent, 'user', value, 'u_');
  }

  /** Compact any external sender source_id longer than 8 chars to an 8-char `s_xxxxxx` reference. */
  senderSourceRef(agent: string, value: string): string {
    if (!value || value.length <= MAX_AGENT_ID_LENGTH) return value;
    return this.reference(agent, 'sender_source', value, 's_');
  }

  /** Compact any screenshot operation_id longer than 8 chars to an 8-char `r_xxxxxx` reference. */
  operationRef(agent: string, value: string): string {
    if (!value || value.length <= MAX_AGENT_ID_LENGTH) return value;
    return this.reference(agent, 'operation', value, 'r_');
  }

  /** Compact any PA incident_ref longer than 8 chars to an 8-char `i_xxxxxx` reference. */
  incidentRef(agent: string, value: string): string {
    if (!value || value.length <= MAX_AGENT_ID_LENGTH) return value;
    return this.reference(agent, 'incident', value, 'i_');
  }

  /** Split a canonical target that may be an external conversation ID joined with a thread root ID. */
  splitResolvedTarget(agent: string, value: string): { base: string; root?: string } {
    if (value.startsWith('external:') || value.startsWith('conversation:external:')) {
      const prefix = value.startsWith('conversation:') ? 'conversation:' : '';
      const body = value.slice(prefix.length);
      const lastColon = body.lastIndexOf(':');
      if (lastColon > 'external:'.length) {
        const candidateBase = body.slice(0, lastColon);
        const candidateRoot = body.slice(lastColon + 1);
        const knownConv = this.db.prepare("SELECT 1 FROM tool_references WHERE agent_id=? AND kind='conversation' AND value=?").get(agent, candidateBase);
        const looksLikeMessageId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(candidateRoot)
          || /^[0-9a-f]{32}$/i.test(candidateRoot)
          || !!this.db.prepare("SELECT 1 FROM tool_references WHERE agent_id=? AND kind='message' AND value=?").get(agent, candidateRoot);
        if (knownConv || looksLikeMessageId) {
          return { base: prefix + candidateBase, root: candidateRoot };
        }
      }
    }
    return splitThreadTarget(value);
  }

  /** Project a conversation or unified thread target (`<chat>` or `<chat>:<root>`) to <= 8-char atomic parts. */
  targetRef(agent: string, value: unknown, hint?: { base?: unknown; root?: unknown }): unknown {
    if (typeof value !== 'string') return value;
    const hintBase = typeof hint?.base === 'string' && hint.base ? hint.base : undefined;
    const hintRoot = typeof hint?.root === 'string' && hint.root ? hint.root : undefined;
    if (hintBase && value.startsWith(`${hintBase}:`)) {
      const root = value.slice(hintBase.length + 1);
      return root ? joinThreadTarget(this.conversationRef(agent, hintBase), this.messageRef(agent, root)) : this.conversationRef(agent, hintBase);
    }
    if (hintRoot && value.endsWith(`:${hintRoot}`)) {
      const base = value.slice(0, -(hintRoot.length + 1));
      if (base) return joinThreadTarget(this.conversationRef(agent, base), this.messageRef(agent, hintRoot));
    }
    const { base, root } = this.splitResolvedTarget(agent, value);
    const shortBase = this.conversationRef(agent, base);
    return root ? joinThreadTarget(shortBase, this.messageRef(agent, root)) : shortBase;
  }

  /** Resolve a short message ID reference back to its canonical IM message ID when mapped. */
  resolveMessageId(agent: string, value: string): string {
    return this.resolveOptional(agent, 'message', value) ?? value;
  }

  /** Resolve a short user ID reference back to its canonical IM user ID when mapped. */
  resolveUserId(agent: string, value: string): string {
    return this.resolveOptional(agent, 'user', value) ?? value;
  }

  /** Resolve short `<mention type="user" target_id="..."/>` references in outgoing message text. */
  resolveMentions(agent: string, text: string): string {
    return text.replace(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g,
      (full, targetId: string) => {
        const resolved = this.resolveOptional(agent, 'user', targetId);
        return resolved ? `<mention type="user" target_id="${resolved}"/>` : full;
      });
  }

  /** Resolve a short conversation or thread target while continuing to accept saved full routing IDs.
   *
   * Args:
   *   agent: Trusted product Agent identity, not a model-supplied scope.
   *   target: Tool target (`c_xxx`, `c_xxx:root`, `f_xxx`, `current`, `current:root`, etc.).
   * Returns:
   *   Canonical routing target; ordinary short IM IDs pass through.
   * Raises:
   *   Error: A compact external reference is unknown or belongs to another Agent.
   */
  resolveTarget(agent: string, target: string): string {
    const { base, root } = splitThreadTarget(target);
    const prefix = base.startsWith('conversation:') ? 'conversation:' : base.startsWith('user:') ? 'user:' : '';
    const value = base.slice(prefix.length);
    let resolvedBase: string;
    if (value.startsWith('f_') || value.startsWith('c_f_')) {
      resolvedBase = this.resolve(agent, 'conversation', value);
    } else if (prefix === 'user:') {
      resolvedBase = this.resolveOptional(agent, 'user', value) ?? value;
    } else {
      resolvedBase = this.resolveOptional(agent, 'conversation', value)
        ?? this.resolveOptional(agent, 'user', value)
        ?? value;
    }
    const resolvedRoot = root ? this.resolveMessageId(agent, root) : undefined;
    return joinThreadTarget(prefix + resolvedBase, resolvedRoot);
  }

  /** Decode routing and ID fields without changing user content or native DSH IDs.
   *
   * Args:
   *   agent: Trusted product Agent identity.
   *   method: Product method; cursor references are isolated by method.
   *   args: Model arguments, retained without mutation.
   * Returns:
   *   Arguments for the existing authoritative handler and its access checks.
   * Raises:
   *   Error: A compact reference is unknown or outside this scope.
   */
  arguments(agent: string, method: string, args: ObjectValue): ObjectValue {
    if (!SUPPORTED_METHODS.has(method)) return args;
    const next: ObjectValue = { ...args };
    if (typeof args.target === 'string') next.target = this.resolveTarget(agent, args.target);
    if (typeof args.conversation_id === 'string') next.conversation_id = this.resolveTarget(agent, args.conversation_id);
    if (typeof args.cursor === 'string' && args.cursor.startsWith('p_')) next.cursor = this.resolve(agent, `cursor:${method}`, args.cursor);
    for (const field of ['message_id', 'reply_to_message_id', 'around_message_id', 'before_message_id', 'thread_root_message_id', 'source_message_id']) {
      if (typeof args[field] === 'string') next[field] = this.resolveMessageId(agent, args[field] as string);
    }
    if (typeof args.participant_id === 'string') next.participant_id = this.resolveUserId(agent, args.participant_id);
    if (Array.isArray(args.participant_ids)) {
      next.participant_ids = args.participant_ids.map(item =>
        typeof item === 'string' && !item.startsWith('agent:') ? this.resolveUserId(agent, item) : item);
    }
    if (typeof args.sender_source_id === 'string' && args.sender_source_id.startsWith('s_')) {
      next.sender_source_id = this.resolve(agent, 'sender_source', args.sender_source_id);
    }
    if (typeof args.receipt_of === 'string' && args.receipt_of.startsWith('r_')) {
      next.receipt_of = this.resolve(agent, 'operation', args.receipt_of);
    }
    if (typeof args.incident_ref === 'string' && args.incident_ref.startsWith('i_')) {
      next.incident_ref = this.resolve(agent, 'incident', args.incident_ref);
    }
    if ((method === 'send_message' || method === 'send_user_message') && typeof args.text === 'string') {
      next.text = this.resolveMentions(agent, args.text);
    }
    if (args.interactive && typeof args.interactive === 'object' && !Array.isArray(args.interactive)) {
      const interactive = args.interactive as ObjectValue;
      if (typeof interactive.supersedes_message_id === 'string') {
        next.interactive = { ...interactive, supersedes_message_id: this.resolveMessageId(agent, interactive.supersedes_message_id) };
      }
    }
    return next;
  }

  private projectSender(agent: string, sender: unknown): unknown {
    if (!sender || typeof sender !== 'object' || Array.isArray(sender)) return sender;
    const obj = { ...sender as ObjectValue };
    if (typeof obj.id === 'string') obj.id = this.userRef(agent, obj.id);
    if (typeof obj.source_id === 'string') obj.source_id = this.senderSourceRef(agent, obj.source_id);
    return obj;
  }

  private projectReplyTo(agent: string, replyTo: unknown): unknown {
    if (!replyTo || typeof replyTo !== 'object' || Array.isArray(replyTo)) return replyTo;
    const obj = { ...replyTo as ObjectValue };
    if (typeof obj.message_id === 'string') obj.message_id = this.messageRef(agent, obj.message_id);
    if (obj.sender) obj.sender = this.projectSender(agent, obj.sender);
    return obj;
  }

  private projectMessageRecord(agent: string, raw: ObjectValue): ObjectValue {
    const out: ObjectValue = { ...raw };
    if (typeof out.message_id === 'string') out.message_id = this.messageRef(agent, out.message_id);
    if (typeof out.id === 'string') out.id = this.messageRef(agent, out.id);
    if (out.sender) out.sender = this.projectSender(agent, out.sender);
    if (out.reply_to) out.reply_to = this.projectReplyTo(agent, out.reply_to);
    if (out.source && typeof out.source === 'object' && !Array.isArray(out.source)) {
      const src = { ...out.source as ObjectValue };
      const rawConvId = typeof src.conversation_id === 'string' ? src.conversation_id : undefined;
      if ('target' in src) src.target = this.targetRef(agent, src.target, { base: rawConvId });
      if ('reply_target' in src) src.reply_target = this.targetRef(agent, src.reply_target, { base: rawConvId });
      if (rawConvId !== undefined) src.conversation_id = this.conversationRef(agent, rawConvId);
      out.source = src;
    }
    if (out.thread && typeof out.thread === 'object' && !Array.isArray(out.thread)) {
      const thread = { ...out.thread as ObjectValue };
      const rawRoot = typeof thread.root_message_id === 'string' ? thread.root_message_id : undefined;
      if ('target' in thread) thread.target = this.targetRef(agent, thread.target, { root: rawRoot });
      if (rawRoot !== undefined) thread.root_message_id = this.messageRef(agent, rawRoot);
      if (Array.isArray(thread.earlier_replies)) {
        thread.earlier_replies = thread.earlier_replies.map(item =>
          item && typeof item === 'object' ? { ...item as ObjectValue, ...(typeof (item as ObjectValue).id === 'string' ? { id: this.messageRef(agent, (item as ObjectValue).id as string) } : {}) } : item);
      }
      out.thread = thread;
    }
    return out;
  }

  /** Project a PA security incident or personal event payload so every agent-facing ID is <= 8 chars. */
  projectIncidentPayload(agent: string, item: ObjectValue): ObjectValue {
    const out: ObjectValue = { ...item };
    if (typeof out.incident_ref === 'string') out.incident_ref = this.incidentRef(agent, out.incident_ref);
    if (typeof out.incident_id === 'string') out.incident_id = this.incidentRef(agent, out.incident_id);
    if (typeof out.owner_target === 'string') out.owner_target = this.targetRef(agent, out.owner_target);
    if (typeof out.peer_target === 'string') out.peer_target = this.targetRef(agent, out.peer_target);
    if (typeof out.conversation_id === 'string') out.conversation_id = this.conversationRef(agent, out.conversation_id);
    if (typeof out.source_message_id === 'string') out.source_message_id = this.messageRef(agent, out.source_message_id);
    if (typeof out.owner_notice_message_id === 'string') out.owner_notice_message_id = this.messageRef(agent, out.owner_notice_message_id);
    if (typeof out.peer_notice_message_id === 'string') out.peer_notice_message_id = this.messageRef(agent, out.peer_notice_message_id);
    if (typeof out.actor_id === 'string') out.actor_id = this.userRef(agent, out.actor_id);
    if (out.conversation && typeof out.conversation === 'object' && !Array.isArray(out.conversation)) {
      const conv = { ...out.conversation as ObjectValue };
      if (typeof conv.id === 'string') conv.id = this.conversationRef(agent, conv.id);
      out.conversation = conv;
    }
    return out;
  }

  private projectThreadContext(agent: string, value: unknown): unknown {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
    const ctx = { ...value as ObjectValue };
    const rawRoot = typeof ctx.root_message_id === 'string' ? ctx.root_message_id : undefined;
    if ('target' in ctx) ctx.target = this.targetRef(agent, ctx.target, { root: rawRoot });
    if (rawRoot !== undefined) ctx.root_message_id = this.messageRef(agent, rawRoot);
    if (Array.isArray(ctx.earlier_replies)) {
      ctx.earlier_replies = ctx.earlier_replies.map(item =>
        item && typeof item === 'object' ? { ...item as ObjectValue, ...(typeof (item as ObjectValue).id === 'string' ? { id: this.messageRef(agent, (item as ObjectValue).id as string) } : {}) } : item);
    }
    return ctx;
  }

  /** Present compact <= 8-char references without changing canonical delivery or query records.
   *
   * Args:
   *   agent: Trusted product Agent identity.
   *   method: Product method whose known response fields are projected.
   *   value: Canonical result; user content and unknown methods pass through.
   * Returns:
   *   Model-visible result with stable <= 8-char references and duplicate send targets removed.
   * Side Effects:
   *   Persists new mappings before returning them to the model.
   */
  result(agent: string, method: string, value: unknown, action?: string): unknown {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
    const body = { ...value } as ObjectValue;
    const cursor = (object: ObjectValue): ObjectValue => ({ ...object,
      ...(typeof object.next_cursor === 'string' ? { next_cursor: this.reference(agent, `cursor:${method}`, object.next_cursor, 'p_') } : {}),
    });
    const projectParticipant = (item: unknown): unknown => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
      const obj = { ...item as ObjectValue };
      if (typeof obj.id === 'string') obj.id = this.userRef(agent, obj.id);
      if (typeof obj.user_id === 'string') {
        const shortId = this.userRef(agent, obj.user_id);
        obj.user_id = shortId;
        if (typeof obj.mention === 'string') obj.mention = `<mention type="user" target_id="${shortId}"/>`;
      }
      return obj;
    };
    const conversation = (object: ObjectValue): ObjectValue => {
      const rawParent = typeof object.parent_target === 'string' ? object.parent_target : undefined;
      const out: ObjectValue = {
        ...object,
        ...('target' in object ? { target: this.targetRef(agent, object.target, { base: rawParent }) } : {}),
        ...('parent_target' in object ? { parent_target: this.targetRef(agent, object.parent_target) } : {}),
        ...('id' in object ? { id: this.targetRef(agent, object.id, { base: rawParent }) } : {}),
      };
      if (Array.isArray(out.members)) out.members = out.members.map(projectParticipant);
      if (Array.isArray(out.participants)) out.participants = out.participants.map(projectParticipant);
      return out;
    };
    if (method === 'inbox') {
      const rawRootHint = body.thread_context && typeof body.thread_context === 'object' && !Array.isArray(body.thread_context)
        ? (body.thread_context as ObjectValue).root_message_id : undefined;
      const rawParentHint = typeof body.parent_target === 'string' ? body.parent_target : undefined;
      if (Array.isArray(body.sources)) body.sources = body.sources.map(source => conversation(source as ObjectValue));
      if (Array.isArray(body.messages)) body.messages = (body.messages as ObjectValue[]).map(msg => this.projectMessageRecord(agent, msg));
      if (body.thread_context) body.thread_context = this.projectThreadContext(agent, body.thread_context);
      if (Array.isArray(body.review_failures)) {
        body.review_failures = (body.review_failures as ObjectValue[]).map(item => ({
          ...item,
          ...(typeof item.message_id === 'string' ? { message_id: this.messageRef(agent, item.message_id) } : {}),
          ...(typeof item.conversation_id === 'string' ? { conversation_id: this.conversationRef(agent, item.conversation_id) } : {}),
        }));
      }
      if (Array.isArray(body.security_incidents)) {
        body.security_incidents = (body.security_incidents as ObjectValue[]).map(item => this.projectIncidentPayload(agent, item));
      }
      if (typeof body.incident_ref === 'string') body.incident_ref = this.incidentRef(agent, body.incident_ref);
      if (typeof body.incident_id === 'string') body.incident_id = this.incidentRef(agent, body.incident_id);
      if (typeof body.message_id === 'string') body.message_id = this.messageRef(agent, body.message_id);
      if ('target' in body) body.target = this.targetRef(agent, body.target, { base: rawParentHint, root: rawRootHint });
      if ('parent_target' in body) body.parent_target = this.targetRef(agent, body.parent_target);
      return cursor(body);
    }
    if (method === 'threads') {
      if (Array.isArray(body.threads)) {
        body.threads = (body.threads as ObjectValue[]).map(item => {
          const rawParent = typeof item.parent_target === 'string' ? item.parent_target : undefined;
          const rawRoot = typeof item.root_message_id === 'string' ? item.root_message_id : undefined;
          return {
            ...item,
            ...('target' in item ? { target: this.targetRef(agent, item.target, { base: rawParent, root: rawRoot }) } : {}),
            ...('parent_target' in item ? { parent_target: this.targetRef(agent, item.parent_target) } : {}),
            ...(rawRoot !== undefined ? { root_message_id: this.messageRef(agent, rawRoot) } : {}),
          };
        });
      }
      const result = cursor(conversation(body));
      if (action === 'list') {
        delete result.has_more;
        if (!result.next_cursor) delete result.next_cursor;
      }
      return result;
    }
    if (method === 'conversations' || method === 'read_messages' || method === 'search_messages') {
      if (Array.isArray(body.conversations)) body.conversations = body.conversations.map(item => conversation(item as ObjectValue));
      if (body.conversation && typeof body.conversation === 'object' && !Array.isArray(body.conversation)) {
        const nested = conversation(body.conversation as ObjectValue);
        if (typeof nested.creator_id === 'string') nested.creator_id = this.userRef(agent, nested.creator_id);
        if (typeof nested.owner_id === 'string') nested.owner_id = this.userRef(agent, nested.owner_id);
        if (Array.isArray(nested.participant_ids)) {
          nested.participant_ids = nested.participant_ids.map(item => typeof item === 'string' ? this.userRef(agent, item) : item);
        }
        body.conversation = nested;
      }
      const result = cursor(conversation(body));
      if (result.id === result.target) delete result.id;
      const isMessagesMethod = method === 'read_messages' || method === 'search_messages' || ['read', 'search'].includes(action ?? '');
      if (isMessagesMethod || action === 'list') {
        delete result.has_more;
        if (!result.next_cursor) delete result.next_cursor;
      }
      if (result.thread_root && typeof result.thread_root === 'object' && !Array.isArray(result.thread_root)) {
        result.thread_root = this.projectMessageRecord(agent, result.thread_root as ObjectValue);
      }
      if (isMessagesMethod && Array.isArray(result.messages)) {
        const messages: ObjectValue[] = [];
        for (const raw of result.messages as ObjectValue[]) {
          const projected = this.projectMessageRecord(agent, raw);
          if (typeof projected.part_key !== 'string') { messages.push(projected); continue; }
          const index = Number(projected.part_key) + 1;
          const total = Number(projected.total_parts);
          const previous = messages.at(-1);
          const partial = previous?.partial as { first_part?: number; last_part?: number; total_parts?: number } | undefined;
          if (previous && previous.message_id === projected.message_id && partial?.last_part === index - 1 && partial.total_parts === total && JSON.stringify(previous.source) === JSON.stringify(projected.source)) {
            previous.content = [...previous.content as unknown[], ...projected.content as unknown[]];
            partial.last_part = index;
            if (partial.first_part === 1 && partial.last_part === total) delete previous.partial;
            continue;
          }
          const { part_key: _part, total_parts: _total, complete_message: complete, ...message } = projected;
          const isKnown = Number.isInteger(index) && Number.isInteger(total) && total >= index;
          messages.push({ ...message,
            ...(isKnown && !(index === 1 && total === 1) ? { partial: { first_part: index, last_part: index, total_parts: total } }
              : !isKnown && !complete ? { partial: { status: 'unknown' } } : {}) });
        }
        result.messages = messages;
      }
      return result;
    }
    if (method === 'personal_sources') {
      if (Array.isArray(body.items)) {
        body.items = (body.items as ObjectValue[]).map(item => {
          const out: ObjectValue = {
            ...item,
            ...(typeof item.id === 'string' ? { id: this.conversationRef(agent, item.id) } : {}),
            ...(typeof item.creator_id === 'string' ? { creator_id: this.userRef(agent, item.creator_id) } : {}),
            ...(typeof item.owner_id === 'string' ? { owner_id: this.userRef(agent, item.owner_id) } : {}),
          };
          if (Array.isArray(out.participants)) out.participants = out.participants.map(projectParticipant);
          if (Array.isArray(out.participant_ids)) out.participant_ids = out.participant_ids.map(pid => typeof pid === 'string' ? this.userRef(agent, pid) : pid);
          return out;
        });
      }
      if (body.policy && typeof body.policy === 'object' && !Array.isArray(body.policy)) {
        const policy = { ...body.policy as ObjectValue };
        if (Array.isArray(policy.excluded_conversation_ids)) {
          policy.excluded_conversation_ids = policy.excluded_conversation_ids.map(id =>
            typeof id === 'string' ? this.conversationRef(agent, id) : id);
        }
        body.policy = policy;
      }
      return body;
    }
    if (method === 'task_graph' && body.result && typeof body.result === 'object') return { ...body, result: cursor(body.result as ObjectValue) };
    if (method === 'send_message' || method === 'send_user_message') {
      if ('target' in body) body.target = this.targetRef(agent, body.target);
      if ('conversation_id' in body) body.conversation_id = this.conversationRef(agent, String(body.conversation_id));
      if (typeof body.target === 'string' && splitThreadTarget(body.target.replace(/^conversation:/, '')).base === body.conversation_id) delete body.conversation_id;
      if (typeof body.message_id === 'string') body.message_id = this.messageRef(agent, body.message_id);
      if (typeof body.operation_id === 'string') body.operation_id = this.operationRef(agent, body.operation_id);
      if (Array.isArray(body.inbox_targets)) body.inbox_targets = body.inbox_targets.map(target => this.targetRef(agent, target));
      return body;
    }
    return value;
  }
}
