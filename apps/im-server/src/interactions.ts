import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { mergeStatements } from '@openuidev/lang-core';
import type { FastifyRequest } from 'fastify';
import { interactiveResponse, type InteractionDraftField, type InteractionSnapshot, type InteractionContext, type MessageInteractive } from '@nano/product-contracts';
import { body, fail, now, one, params, transaction, type ImContext, type Row } from './context.js';
import { agentAvailable } from './identity.js';
import { conversationAccess } from './conversation-access.js';
import { InteractiveSourceError, interactionState, validateInteractiveSource, type InteractiveSchema } from './interactive-source.js';

/** Own immutable UI records, private drafts, and viewer-specific submission identity. */
export class Interactions {
  constructor(private readonly ctx: ImContext) {}
  private get db() { return this.ctx.db; }
  /** Resolve the executor from controlled provenance independently of the public author. */
  source(id: string, cid: string): Row {
    const source = one(this.db, `SELECT i.*,m.content,m.sender_user_id,u.username,
      COALESCE(e.id,CASE WHEN u.username LIKE 'agent:%' THEN u.id END) executor_user_id,
      COALESCE(d.agent_id,CASE WHEN u.username LIKE 'agent:%' THEN substr(u.username,7) END) executor_agent_id
      FROM message_interactive i JOIN messages m ON m.id=i.message_id JOIN users u ON u.id=m.sender_user_id
      LEFT JOIN pa_delegated_messages d ON d.message_id=m.id AND d.representation_operation_id IS NOT NULL
      LEFT JOIN users e ON e.username='agent:'||d.agent_id
      WHERE i.message_id=? AND m.conversation_id=?`, id, cid);
    if (!source) fail(404, 'interactive message not found');
    return source;
  }
  private available(source:Row,cid:string):boolean {
    return !source.read_only&&!source.superseded_by&&agentAvailable(this.db,one(this.db,'SELECT * FROM agent_profiles WHERE agent_id=?',source.executor_agent_id))
      && !!conversationAccess(this.db,cid,source.executor_user_id)?.can_write;
  }
  private writable(source: Row): void {
    if (source.superseded_by || source.read_only) fail(409, { code: 'interaction_read_only', message: 'This reply has been replaced or is copied history' });
  }
  private state(source: Row, value: unknown) {
    try { return interactionState({source:source.source, actions:JSON.parse(source.registry_json).actions}, value); }
    catch (error) { fail(422, String((error as Error).message)); }
  }
  /** Project only public data; registry and drafts never enter message broadcasts. */
  message(id: string): MessageInteractive | undefined {
    const row = one(this.db, 'SELECT * FROM message_interactive WHERE message_id=?', id);
    return row ? { format: row.format, catalog_version: row.catalog_version, source: row.source,
      ...(row.supersedes_message_id ? { supersedes_message_id: row.supersedes_message_id } : {}),
      ...(row.superseded_by ? { superseded_by: row.superseded_by } : {}), ...(row.read_only ? { read_only: true } : {}) } : undefined;
  }
  publication(id: string): unknown {
    const row = one(this.db, 'SELECT publication_json FROM message_interactive WHERE message_id=?', id);
    return row?.publication_json ? JSON.parse(row.publication_json) : interactiveResponse(this.message(id));
  }
  /** Resolve a saved private draft into the one background a send may carry.
   *
   * Args:
   *   user: Authenticated human; the derivation already passed conversation checks.
   *   cid: Conversation containing the source message.
   *   sourceMessageId: Draft owner row selected by the derivation query.
   *   stateJson: That row's saved state.
   * Returns:
   *   Background for private delivery to the source Agent, or null when the card stopped
   *   being interactive. A stale draft is client-written history and must never veto a
   *   user's message, so invalid state degrades to "no background" instead of failing.
   */
  background(user: Row, cid: string, sourceMessageId: string, stateJson: string): InteractionContext | null {
    if (user.kind === 'gateway' || user.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    const source = this.source(sourceMessageId, cid);
    if (source.read_only || source.superseded_by) return null;
    let state, fields;
    try { ({state, fields} = interactionState({source:source.source, actions:JSON.parse(source.registry_json).actions}, JSON.parse(stateJson))); }
    catch { return null; }
    return {source_message_id:source.message_id, source_summary:source.content.slice(0,160), agent_id:source.executor_agent_id, state, fields};
  }
  /** Save validated source inside the same transaction as its Agent message. */
  record(id: string, cid: string, sender: string, input: unknown): void {
    let value, registry;
    try { value = interactiveResponse(input); if (!value) return; }
    catch (error) { fail(422, String((error as Error).message)); }
    if (!one(this.db, "SELECT 1 FROM users WHERE id=? AND username LIKE 'agent:%'", sender)) fail(403, 'Only an Agent can publish interactive replies');
    const publication = sortedJsonAscii(value);
    if (value.supersedes_message_id) {
      const old = this.source(value.supersedes_message_id, cid);
      if (old.executor_user_id !== sender || old.read_only || old.superseded_by) fail(409, 'Only the same Agent can replace its current reply');
      if (value.source_mode === 'patch') value = {...value, source: mergeStatements(old.source, value.source)};
      this.db.prepare('UPDATE message_interactive SET superseded_by=? WHERE message_id=?').run(id, old.message_id);
    }
    try { registry = validateInteractiveSource(value.source); }
    catch (error) { fail(422, error instanceof InteractiveSourceError ? error.detail : (error as Error).message); }
    const {searchText, previewTitle, ...actionRegistry} = registry;
    this.db.prepare('INSERT INTO message_interactive(message_id,format,catalog_version,source,registry_json,search_text,preview_title,supersedes_message_id,publication_json) VALUES(?,?,?,?,?,?,?,?,?)')
      .run(id, value.format, value.catalog_version, value.source, JSON.stringify(actionRegistry), searchText, previewTitle, value.supersedes_message_id ?? null, publication);
  }
  /** Read only the authenticated viewer's draft after ordinary conversation access. */
  readDraft(req: FastifyRequest): Row {
    const p = this.ctx.messaging.principal(req), { conversation_id: cid, message_id: mid } = params(req);
    if (p.kind === 'gateway' || p.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    this.ctx.messaging.access(p, cid); const source=this.source(mid, cid);
    const row = one(this.db, 'SELECT * FROM interaction_drafts WHERE source_message_id=? AND user_id=?', mid, p.id);
    const state = JSON.parse(row?.state_json ?? '{}');
    // Labels for the cross-device 409 comparison; the same evaluation that labels the
    // saved state, so both columns speak one vocabulary. A draft written against an older
    // program degrades to no labels rather than failing the read.
    let fields: InteractionDraftField[] = [];
    try { fields = interactionState({source:source.source, actions:JSON.parse(source.registry_json).actions}, state, {withOptions:true}).fields; }
    catch { fields = []; }
    return { read_only:!!source.read_only, superseded_by:source.superseded_by??null, can_interact:this.available(source,cid)&&!!conversationAccess(this.db,cid,p.id)?.can_write, updated_at: row?.updated_at ?? null, draft_revision: row?.draft_revision ?? 0, state, submission_message_id: row?.submission_message_id ?? null, fields };
  }
  /** Compare-and-swap private local state independently of earlier requests. */
  writeDraft(req: FastifyRequest): Row {
    const p = this.ctx.messaging.principal(req), { conversation_id: cid, message_id: mid } = params(req), b = body(req);
    if (p.kind === 'gateway' || p.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    this.ctx.messaging.access(p, cid, undefined, 'write');
    const source = this.source(mid, cid); this.writable(source);
    const {state} = this.state(source, b.state);
    if (!Number.isSafeInteger(b.expected_draft_revision) || b.expected_draft_revision < 0) fail(422, 'expected_draft_revision required');
    transaction(this.db, () => {
      this.db.prepare('INSERT OR IGNORE INTO interaction_drafts(source_message_id,user_id) VALUES(?,?)').run(mid, p.id);
      const changed = this.db.prepare('UPDATE interaction_drafts SET draft_revision=draft_revision+1,state_json=?,updated_at=?,submission_message_id=NULL WHERE source_message_id=? AND user_id=? AND draft_revision=?')
        .run(sortedJsonAscii(state), now(), mid, p.id, b.expected_draft_revision).changes;
      if (!changed) fail(409, { code: 'interaction_draft_conflict', message: 'The draft changed on another device' });
    });
    return this.readDraft(req);
  }
  /** Resolve a browser choice using saved source and identity, before creating its message. */
  prepare(user: Row, cid: string, request: Row, key: string | null): { existing?: string; content: string; semantic: string; snapshot: InteractionSnapshot } {
    const input = request.interaction_reply;
    if (!input || typeof input !== 'object' || typeof input.source_message_id !== 'string' || input.action_id !== undefined && typeof input.action_id !== 'string') fail(422, 'Invalid interaction reply');
    if (user.kind === 'gateway' || user.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    if (!key) fail(422, 'Idempotency-Key required for interaction');
    if ((input.action_id || input.event) && request.content) fail(422, 'Use either a button or handwritten content');
    const source = this.source(input.source_message_id, cid);
    const registry = JSON.parse(source.registry_json) as InteractiveSchema;
    const {state, fields} = this.state(source, input.state);
    const label = input.action_id ? registry.actions[input.action_id] : undefined;
    if (input.action_id !== undefined && (!input.action_id || !Object.hasOwn(registry.actions, input.action_id))) fail(422, 'Unknown continuation action');
    const event = input.event;
    if (event !== undefined && (!event || event.type !== 'continue_conversation' || typeof event.message !== 'string'
      || event.label !== undefined && typeof event.label !== 'string' || event.form_name !== undefined && typeof event.form_name !== 'string'
      || input.action_id || Buffer.byteLength(JSON.stringify(event), 'utf8') > 16384)) fail(422, 'Invalid native interaction event');
    const nativeEvent = event ? {type:'continue_conversation' as const,message:event.message,
      ...(event.context !== undefined ? {context:event.context} : {}), ...(event.label ? {label:event.label} : {}), ...(event.form_name ? {form_name:event.form_name} : {})} : undefined;
    const content = input.action_id ? label! : nativeEvent ? nativeEvent.label || '发送到聊天' : request.content;
    if (typeof content !== 'string' || !content.trim()) fail(422, 'Handwritten content required');
    const semantic = sortedJsonAscii({source_message_id: source.message_id, action_id: input.action_id ?? null, typed_content: input.action_id || nativeEvent ? '' : content, canonical_state: state, ...(nativeEvent ? {event:nativeEvent} : {})});
    const previous = one(this.db, 'SELECT s.* FROM interaction_submissions s JOIN messages m ON m.id=s.message_id WHERE m.conversation_id=? AND m.caller_idempotency_key=?', cid, key);
    const snapshot: InteractionSnapshot = { source_message_id: source.message_id, source_summary: source.content, agent_id: source.executor_agent_id,
      ...(input.action_id ? {action_id: input.action_id, action_label: label} : {}), ...(nativeEvent ? {event:nativeEvent,action_label:content} : {}), state, fields };
    if (previous) {
      if (previous.semantic_json !== semantic) fail(409, { code: 'interaction_already_submitted', message: 'This request key was already used with different content', submission_message_id: previous.message_id });
      return { existing: previous.message_id, content, semantic, snapshot };
    }
    this.writable(source);
    if (!this.available(source,cid)) fail(409, 'The source Agent is no longer available in this conversation');
    return { content, semantic, snapshot };
  }
  /** Commit a choice identity and its private submitted state with the public message. */
  submit(user: string, message: string, prepared: ReturnType<Interactions['prepare']>): void {
    const source = prepared.snapshot.source_message_id;
    this.db.prepare('INSERT INTO interaction_submissions VALUES(?,?,?,?)').run(source, user, message, prepared.semantic);
    this.db.prepare('INSERT INTO interaction_drafts(source_message_id,user_id,draft_revision,state_json,submission_message_id) VALUES(?,?,1,?,?) ON CONFLICT(source_message_id,user_id) DO UPDATE SET draft_revision=draft_revision+1,state_json=excluded.state_json,submission_message_id=excluded.submission_message_id')
      .run(source, user, sortedJsonAscii(prepared.snapshot.state), message);
  }
  /** Copy public history only; no private drafts or active continuation survives a fork. */
  copy(ids: Map<string, string>): void {
    for (const [oldId, newId] of ids) {
      const old = one(this.db, 'SELECT * FROM message_interactive WHERE message_id=?', oldId);
      if (old) this.db.prepare('INSERT INTO message_interactive(message_id,format,catalog_version,source,registry_json,search_text,preview_title,supersedes_message_id,superseded_by,read_only) VALUES(?,?,?,?,?,?,?,?,?,1)').run(newId, old.format, old.catalog_version, old.source, old.registry_json, old.search_text, old.preview_title,
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
