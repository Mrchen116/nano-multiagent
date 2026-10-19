import type { FastifyRequest } from 'fastify';
import { canonicalJson, interactiveResponse, type InteractionSnapshot } from '@nano/product-contracts';
import { body, fail, one, params, transaction, type ImContext, type Row } from './context.js';
import { agentAvailable } from './identity.js';
import { interactionState, validateInteractiveSource, type InteractiveSchema } from './interactive-source.js';

/** Own immutable UI records, private drafts, and viewer-specific submission identity. */
export class Interactions {
  constructor(private readonly ctx: ImContext) {}
  private get db() { return this.ctx.db; }
  private source(id: string, cid: string): Row {
    const source = one(this.db, 'SELECT i.*,m.content,m.sender_user_id,u.username FROM message_interactive i JOIN messages m ON m.id=i.message_id JOIN users u ON u.id=m.sender_user_id WHERE i.message_id=? AND m.conversation_id=?', id, cid);
    if (!source) fail(404, 'interactive message not found');
    return source;
  }
  private writable(source: Row): void {
    if (source.superseded_by || source.read_only) fail(409, { code: 'interaction_read_only', message: 'This reply has been replaced or is copied history' });
  }
  private state(source: Row, value: unknown) {
    try { return interactionState(JSON.parse(source.registry_json) as InteractiveSchema, value); }
    catch (error) { fail(422, String((error as Error).message)); }
  }
  /** Project only public data; registry and drafts never enter message broadcasts. */
  message(id: string): Row | undefined {
    const row = one(this.db, 'SELECT * FROM message_interactive WHERE message_id=?', id);
    return row ? { format: row.format, catalog_version: row.catalog_version, source: row.source,
      ...(row.supersedes_message_id ? { supersedes_message_id: row.supersedes_message_id } : {}),
      ...(row.superseded_by ? { superseded_by: row.superseded_by } : {}), ...(row.read_only ? { read_only: true } : {}) } : undefined;
  }
  /** Save validated source inside the same transaction as its Agent message. */
  record(id: string, cid: string, sender: string, input: unknown): void {
    let value, registry;
    try { value = interactiveResponse(input); if (!value) return; registry = validateInteractiveSource(value.source); }
    catch (error) { fail(422, String((error as Error).message)); }
    if (!one(this.db, "SELECT 1 FROM users WHERE id=? AND username LIKE 'agent:%'", sender)) fail(403, 'Only an Agent can publish interactive replies');
    if (value.supersedes_message_id) {
      const old = this.source(value.supersedes_message_id, cid);
      if (old.sender_user_id !== sender || old.read_only || old.superseded_by) fail(409, 'Only the same Agent can replace its current reply');
      this.db.prepare('UPDATE message_interactive SET superseded_by=? WHERE message_id=?').run(id, value.supersedes_message_id);
    }
    this.db.prepare('INSERT INTO message_interactive(message_id,format,catalog_version,source,registry_json,supersedes_message_id) VALUES(?,?,?,?,?,?)')
      .run(id, value.format, value.catalog_version, value.source, JSON.stringify(registry), value.supersedes_message_id ?? null);
  }
  /** Read only the authenticated viewer's draft after ordinary conversation access. */
  readDraft(req: FastifyRequest): Row {
    const p = this.ctx.messaging.principal(req), { conversation_id: cid, message_id: mid } = params(req);
    if (p.kind === 'gateway' || p.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    this.ctx.messaging.access(p, cid); this.source(mid, cid);
    const row = one(this.db, 'SELECT * FROM interaction_drafts WHERE source_message_id=? AND user_id=?', mid, p.id);
    return { updated_at: row?.updated_at ?? null, draft_revision: row?.draft_revision ?? 0, state: JSON.parse(row?.state_json ?? '{}'), submission_message_id: row?.submission_message_id ?? null };
  }
  /** Compare-and-swap a private draft; an existing submission makes it read-only. */
  writeDraft(req: FastifyRequest): Row {
    const p = this.ctx.messaging.principal(req), { conversation_id: cid, message_id: mid } = params(req), b = body(req);
    if (p.kind === 'gateway' || p.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    this.ctx.messaging.access(p, cid, undefined, 'write');
    const source = this.source(mid, cid); this.writable(source);
    const {state} = this.state(source, b.state);
    if (!Number.isSafeInteger(b.expected_draft_revision) || b.expected_draft_revision < 0) fail(422, 'expected_draft_revision required');
    transaction(this.db, () => {
      this.db.prepare('INSERT OR IGNORE INTO interaction_drafts(source_message_id,user_id) VALUES(?,?)').run(mid, p.id);
      const changed = this.db.prepare('UPDATE interaction_drafts SET draft_revision=draft_revision+1,state_json=?,updated_at=? WHERE source_message_id=? AND user_id=? AND draft_revision=? AND submission_message_id IS NULL')
        .run(canonicalJson(state), new Date().toISOString(), mid, p.id, b.expected_draft_revision).changes;
      if (!changed) fail(409, { code: 'interaction_draft_conflict', message: 'The draft changed on another device or was already submitted' });
    });
    return this.readDraft(req);
  }
  /** Resolve a browser choice using saved source and identity, before creating its message. */
  prepare(user: Row, cid: string, request: Row, key: string | null): { existing?: string; content: string; semantic: string; snapshot: InteractionSnapshot } {
    const input = request.interaction_reply;
    if (!input || typeof input !== 'object' || typeof input.source_message_id !== 'string' || input.action_id !== undefined && typeof input.action_id !== 'string') fail(422, 'Invalid interaction reply');
    if (user.kind === 'gateway' || user.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    if (input.action_id && request.content) fail(422, 'Use either a button or handwritten content');
    const source = this.source(input.source_message_id, cid);
    const registry = JSON.parse(source.registry_json) as InteractiveSchema;
    const {state, fields} = this.state(source, input.state);
    const label = input.action_id ? registry.actions[input.action_id] : undefined;
    if (input.action_id !== undefined && (!input.action_id || !Object.hasOwn(registry.actions, input.action_id))) fail(422, 'Unknown continuation action');
    const content = input.action_id ? label! : request.content;
    if (typeof content !== 'string' || !content.trim()) fail(422, 'Handwritten content required');
    const semantic = canonicalJson({source_message_id: source.message_id, action_id: input.action_id ?? null, typed_content: input.action_id ? '' : content, canonical_state: state});
    const previous = one(this.db, 'SELECT * FROM interaction_submissions WHERE source_message_id=? AND user_id=?', source.message_id, user.id)
      ?? (key ? one(this.db, 'SELECT s.* FROM interaction_submissions s JOIN messages m ON m.id=s.message_id WHERE m.conversation_id=? AND m.caller_idempotency_key=?', cid, key) : undefined);
    const snapshot: InteractionSnapshot = { source_message_id: source.message_id, source_summary: source.content, agent_id: source.username.slice(6),
      ...(input.action_id ? {action_id: input.action_id, action_label: label} : {}), state, fields };
    if (previous) {
      if (previous.semantic_json !== semantic) fail(409, { code: 'interaction_already_submitted', message: 'This reply was already submitted with different content', submission_message_id: previous.message_id });
      return { existing: previous.message_id, content, semantic, snapshot };
    }
    this.writable(source);
    const agent = one(this.db, 'SELECT * FROM agent_profiles WHERE agent_id=?', snapshot.agent_id);
    if (!agentAvailable(this.db, agent) || !one(this.db, 'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?', cid, source.sender_user_id)) fail(409, 'The source Agent is no longer available in this conversation');
    return { content, semantic, snapshot };
  }
  /** Commit a choice identity and its private submitted state with the public message. */
  submit(user: string, message: string, prepared: ReturnType<Interactions['prepare']>): void {
    const source = prepared.snapshot.source_message_id;
    this.db.prepare('INSERT INTO interaction_submissions VALUES(?,?,?,?)').run(source, user, message, prepared.semantic);
    this.db.prepare('INSERT INTO interaction_drafts(source_message_id,user_id,draft_revision,state_json,submission_message_id) VALUES(?,?,1,?,?) ON CONFLICT(source_message_id,user_id) DO UPDATE SET draft_revision=draft_revision+1,state_json=excluded.state_json,submission_message_id=excluded.submission_message_id')
      .run(source, user, canonicalJson(prepared.snapshot.state), message);
  }
  /** Copy public history only; no private drafts or active continuation survives a fork. */
  copy(ids: Map<string, string>): void {
    for (const [oldId, newId] of ids) {
      const old = one(this.db, 'SELECT * FROM message_interactive WHERE message_id=?', oldId);
      if (old) this.db.prepare('INSERT INTO message_interactive VALUES(?,?,?,?,?,?,?,1)').run(newId, old.format, old.catalog_version, old.source, old.registry_json,
        ids.get(old.supersedes_message_id) ?? null, ids.get(old.superseded_by) ?? null);
      const reply = one(this.db, 'SELECT interaction_reply_json FROM messages WHERE id=?', newId)?.interaction_reply_json;
      if (reply) {
        const snapshot = JSON.parse(reply);
        snapshot.source_message_id = ids.get(snapshot.source_message_id) ?? null;
        this.db.prepare('UPDATE messages SET interaction_reply_json=? WHERE id=?').run(JSON.stringify(snapshot), newId);
      }
    }
  }
}
