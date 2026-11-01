import type { ScheduleDeletionIntent } from './schedule-deletions.js';
import type { ControlIntent } from './session-controls.js';
import { DatabaseSync } from 'node:sqlite';
import type { DeliveryState, RelayInput, RuntimeEvent, SessionBinding } from '@nano/product-contracts';
import { ToolReferences } from './tool-references.js';
import { AgentLifecycleAuthority } from './agent-lifecycle.js';

interface SystemContextInput {message_id:string;conversation_id:string;session_id:string|null;input_id:string;digest:string;state:'prepared'|'consumed'|'revoked';turn:number|null}

/** Node-owned durable handoff and delivery facts, independent of DSH storage. */
export class NodeStore {
  /** Read durable ingestion progress, independent of model consumption. */
  taskContextCursor(agentId:string):number { return (this.db.prepare('SELECT seq FROM task_context_cursors WHERE agent_id=?').get(agentId) as {seq:number}|undefined)?.seq??0; }
  /** Advance only after every original input or terminal reference was persisted. */
  advanceTaskContext(agentId:string,seq:number):void { this.db.prepare('INSERT INTO task_context_cursors VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET seq=max(seq,excluded.seq)').run(agentId,seq); }
  /** Persist a stable native identity without treating admission as consumption. */
  prepareSystemContext(agentId:string,messageId:string,conversationId:string,sessionId:string,digest:string):void {
    this.db.prepare("INSERT INTO system_context_inputs VALUES(?,?,?,?,?,?,'prepared',NULL) ON CONFLICT(agent_id,message_id) DO UPDATE SET session_id=excluded.session_id,digest=excluded.digest,turn=NULL WHERE state='prepared'").run(agentId,messageId,conversationId,sessionId,messageId,digest);
  }
  /** List product mappings for execution evidence repair, including terminal revocations. */
  systemContextInputs(agentId:string):SystemContextInput[] {
    return this.db.prepare('SELECT * FROM system_context_inputs WHERE agent_id=?').all(agentId) as unknown as SystemContextInput[];
  }
  /** Revocation is terminal and wins over delayed admission or evidence ACKs. */
  revokeSystemContext(agentId:string,messageId:string,conversationId:string):void {
    this.db.prepare("INSERT INTO system_context_inputs VALUES(?,?,?,NULL,?,'','revoked',NULL) ON CONFLICT(agent_id,message_id) DO UPDATE SET state=CASE WHEN state='consumed' THEN state ELSE 'revoked' END").run(agentId,messageId,conversationId,messageId);
  }
  /** Commit only the exact prepared content evidenced in an actual native step. */
  commitSystemContext(sessionId:string,inputId:string,digest:string,turn:number):boolean {
    return Number(this.db.prepare("UPDATE system_context_inputs SET state='consumed',turn=? WHERE session_id=? AND input_id=? AND digest=? AND state='prepared'").run(turn,sessionId,inputId,digest).changes)>0;
  }
  private readonly db: DatabaseSync;
  readonly toolReferences: ToolReferences;
  readonly lifecycle: AgentLifecycleAuthority;
  constructor(path: string, readonly ownerId: string) {
    this.db = new DatabaseSync(path);
    const migrateInputs=!this.db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='input_lifecycles'").get();
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA synchronous=FULL;
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS migration_relay_keys(idempotency_key TEXT PRIMARY KEY,expires_at REAL,seen_at REAL);
      CREATE TABLE IF NOT EXISTS node_owner (owner_id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS owner_timezone (owner_id TEXT PRIMARY KEY, timezone TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL, binding TEXT NOT NULL,
        UNIQUE(agent_id, conversation_id)
      );
      CREATE TABLE IF NOT EXISTS conversation_aliases(agent_id TEXT NOT NULL,alias TEXT NOT NULL,canonical TEXT NOT NULL,PRIMARY KEY(agent_id,alias));
      CREATE TABLE IF NOT EXISTS input_lifecycles(agent_id TEXT,message_id TEXT,revision INTEGER NOT NULL,PRIMARY KEY(agent_id,message_id));
      CREATE TABLE IF NOT EXISTS group_background (input_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, conversation_id TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS schedule_runs (input_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, schedule_id TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(session_id), requested_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS canonical_sessions (agent_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id));
      CREATE TABLE IF NOT EXISTS inputs (
        input_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id),
        relay_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
        accepted INTEGER NOT NULL DEFAULT 0, turn INTEGER, terminal TEXT,
        evidence_final INTEGER NOT NULL DEFAULT 0
      );
      CREATE TABLE IF NOT EXISTS runtime_events (
        session_id TEXT NOT NULL REFERENCES sessions(session_id), seq INTEGER NOT NULL,
        event TEXT NOT NULL, PRIMARY KEY(session_id,seq)
      );
      CREATE TABLE IF NOT EXISTS deliveries (
        operation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id),
        turn INTEGER NOT NULL, state TEXT NOT NULL, message_id TEXT, content TEXT NOT NULL DEFAULT '',
        UNIQUE(session_id,turn)
      );
      CREATE TABLE IF NOT EXISTS delivery_events (
        operation_id TEXT NOT NULL REFERENCES deliveries(operation_id), seq INTEGER NOT NULL,
        PRIMARY KEY(operation_id,seq)
      );
      CREATE TABLE IF NOT EXISTS schedule_deletions(operation_id TEXT PRIMARY KEY,intent TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS task_context_cursors(agent_id TEXT PRIMARY KEY,seq INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS system_context_inputs(agent_id TEXT,message_id TEXT,conversation_id TEXT,session_id TEXT,input_id TEXT,digest TEXT,state TEXT NOT NULL,turn INTEGER,PRIMARY KEY(agent_id,message_id),UNIQUE(session_id,input_id));
      CREATE TABLE IF NOT EXISTS control_intents(id TEXT PRIMARY KEY, intent TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS command_results (id TEXT PRIMARY KEY, result TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS input_receipts (input_id TEXT PRIMARY KEY REFERENCES inputs(input_id), status TEXT NOT NULL);
    `);
    this.db.prepare('INSERT INTO node_owner(owner_id) SELECT ? WHERE NOT EXISTS(SELECT 1 FROM node_owner)').run(ownerId);
    const owner = this.db.prepare('SELECT owner_id FROM node_owner').get() as { owner_id: string };
    if (owner.owner_id !== ownerId) { this.db.close(); throw new Error('Node state belongs to a different owner'); }
    // Historical terminal values include physical attempt ends, so upgrades must
    // leave every old input eligible for an authoritative lookup.
    if (!(this.db.prepare('PRAGMA table_info(inputs)').all() as { name: string }[]).some(column => column.name === 'evidence_final')) {
      this.db.exec('ALTER TABLE inputs ADD COLUMN evidence_final INTEGER NOT NULL DEFAULT 0');
    }
    this.db.exec('CREATE INDEX IF NOT EXISTS inputs_evidence_pending ON inputs(session_id,evidence_final)');
    this.toolReferences = new ToolReferences(this.db);
    this.lifecycle = new AgentLifecycleAuthority(this.db);
    if(!(this.db.prepare('PRAGMA table_info(group_background)').all() as {name:string}[]).some(c=>c.name==='cancelled'))this.db.exec('ALTER TABLE group_background ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0');
    if(migrateInputs)this.db.exec("INSERT OR IGNORE INTO input_lifecycles SELECT s.agent_id,json_extract(i.payload,'$.message.id'),coalesce(json_extract(i.payload,'$.lifecycle_revision'),1) FROM inputs i JOIN sessions s USING(session_id)");
    if(migrateInputs)this.db.exec("INSERT OR IGNORE INTO input_lifecycles SELECT agent_id,json_extract(payload,'$.message.id'),coalesce(json_extract(payload,'$.lifecycle_revision'),1) FROM group_background");
  }

  /** Preserve the original epoch even when transport retries omit their admission metadata. */
  admitInput(input: RelayInput): RelayInput {
    const previous=this.db.prepare('SELECT revision FROM input_lifecycles WHERE agent_id=? AND message_id=?').get(input.agent_id,input.message.id) as {revision:number}|undefined;
    const revision=previous?.revision ?? input.lifecycle_revision ?? this.lifecycle.assert(input.agent_id);
    this.lifecycle.assert(input.agent_id,revision);
    this.db.prepare('INSERT OR IGNORE INTO input_lifecycles VALUES(?,?,?)').run(input.agent_id,input.message.id,revision);
    return {...input,lifecycle_revision:revision};
  }
  /** Stamp outgoing requests at their actual dispatch boundary using the admitted epoch. */
  executionPayload(payload: Record<string,unknown>): Record<string,unknown> {
    const context=this.lifecycle.current();
    if(!context)return payload;
    const revision=this.lifecycle.assert(context.agentId,typeof payload.lifecycle_revision==='number'?payload.lifecycle_revision:context.revision);
    return {...payload,agent_id:payload.agent_id??context.agentId,lifecycle_revision:revision};
  }
  /** Cancel execution obligations while retaining raw input and delivery evidence. */
  cancelAgent(agentId: string): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare("UPDATE inputs SET terminal=?,evidence_final=1 WHERE session_id IN (SELECT session_id FROM sessions WHERE agent_id=?) AND evidence_final=0")
        .run(JSON.stringify({kind:'cancelled_by_disable'}),agentId);
      this.db.prepare("UPDATE deliveries SET state=CASE WHEN state IN ('sending','completing') THEN 'unknown' ELSE 'cancelled_by_disable' END WHERE session_id IN (SELECT session_id FROM sessions WHERE agent_id=?) AND state IN ('prepared','sending','completing')").run(agentId);
      this.db.prepare('UPDATE group_background SET cancelled=1 WHERE agent_id=?').run(agentId);
      this.db.prepare("UPDATE control_intents SET intent=json_set(intent,'$.delivered',json('true'),'$.text','cancelled_by_disable') WHERE json_extract(intent,'$.binding.agentId')=? AND coalesce(json_extract(intent,'$.delivered'),0)=0").run(agentId);
      this.db.exec('COMMIT');
    } catch(error) {this.db.exec('ROLLBACK');throw error;}
  }

  /** Read the account timezone cached for offline external input and Heartbeat. */
  get ownerTimezone(): string | undefined {
    return (this.db.prepare('SELECT timezone FROM owner_timezone WHERE owner_id=?').get(this.ownerId) as { timezone: string } | undefined)?.timezone;
  }
  /** Cache an IM-confirmed owner timezone without changing message snapshots. */
  setOwnerTimezone(timezone: string): void {
    this.db.prepare('INSERT INTO owner_timezone VALUES(?,?) ON CONFLICT(owner_id) DO UPDATE SET timezone=excluded.timezone WHERE timezone!=excluded.timezone').run(this.ownerId, timezone);
  }
  /** Preserve the old relay deduplication window without replaying retired execution. */
  priorRelay(key: string): boolean { return !!this.db.prepare('SELECT 1 FROM migration_relay_keys WHERE idempotency_key=? AND expires_at>?').get(key, Date.now()/1000); }
  /** Bind a product conversation once; runtime identity never comes from a model. */
  bind(binding: SessionBinding): SessionBinding {
    binding = { ...binding, conversationId: this.canonicalConversation(binding.agentId, binding.conversationId) };
    if (binding.ownerId !== this.ownerId) throw new Error('Session owner does not match node');
    this.db.prepare('INSERT OR IGNORE INTO sessions VALUES(?,?,?,?)').run(binding.sessionId, binding.agentId, binding.conversationId, JSON.stringify(binding));
    const actual = this.bindingFor(binding.agentId, binding.conversationId);
    if (!actual) throw new Error('Session identity already belongs to another conversation');
    return actual;
  }
  aliasConversation(agentId: string, alias: string, canonical: string): void {
    this.db.prepare('INSERT INTO conversation_aliases VALUES(?,?,?) ON CONFLICT(agent_id,alias) DO UPDATE SET canonical=excluded.canonical').run(agentId, alias, canonical);
  }
  /** Resolve a real IM conversation without inventing an external shadow.
   *
   * Args:
   *   agentId: Registered PA Agent identity.
   *   conversationId: Bound or explicitly selected conversation.
   *
   * Returns:
   *   IM ID, or undefined when the external conversation has not been mirrored.
   */
  imConversation(agentId: string, conversationId: string): string | undefined {
    if (conversationId.startsWith('global:') || conversationId.startsWith('owner:')) return;
    if (!conversationId.startsWith('external:')) return conversationId;
    return (this.db.prepare('SELECT alias FROM conversation_aliases WHERE agent_id=? AND canonical=?').get(agentId, conversationId) as { alias: string } | undefined)?.alias;
  }
  /** Resolve a persisted conversation alias before selecting its delivery transport.
   *
   * Args:
   *   agentId: Registered Agent identity.
   *   conversationId: Original or mirrored conversation target.
   * Returns:
   *   The persisted canonical target, or the unchanged target when unaliased.
   */
  canonicalConversation(agentId: string, conversationId: string): string {
    return (this.db.prepare('SELECT canonical FROM conversation_aliases WHERE agent_id=? AND alias=?').get(agentId, conversationId) as { canonical: string } | undefined)?.canonical ?? conversationId;
  }
  bindingFor(agentId: string, conversationId: string): SessionBinding | undefined {
    conversationId = this.canonicalConversation(agentId, conversationId);
    const row = this.db.prepare('SELECT binding FROM sessions WHERE agent_id=? AND conversation_id=?').get(agentId, conversationId) as { binding: string } | undefined;
    return row ? JSON.parse(row.binding) as SessionBinding : undefined;
  }
  bindings(): SessionBinding[] {
    return (this.db.prepare('SELECT binding FROM sessions').all() as { binding: string }[]).map(row => JSON.parse(row.binding) as SessionBinding);
  }

  canonical(agentId: string): SessionBinding | undefined {
    const row = this.db.prepare('SELECT s.binding FROM canonical_sessions c JOIN sessions s USING(session_id) WHERE c.agent_id=?').get(agentId) as { binding: string } | undefined;
    if (row) return JSON.parse(row.binding) as SessionBinding;
    const prior = this.db.prepare(`SELECT s.binding FROM inputs i JOIN sessions s USING(session_id)
      WHERE s.agent_id=? AND json_extract(i.payload,'$.metadata.conversation_type')='direct'
      AND json_extract(i.payload,'$.message.sender_type')='user' AND json_extract(i.payload,'$.message.sender_user_id')=? ORDER BY i.rowid LIMIT 1`).get(agentId, this.ownerId) as { binding: string } | undefined;
    if (!prior) return undefined;
    const binding = JSON.parse(prior.binding) as SessionBinding; this.markCanonical(binding); return binding;
  }
  markCanonical(binding: SessionBinding): void {
    this.db.prepare('INSERT OR IGNORE INTO canonical_sessions VALUES(?,?)').run(binding.agentId, binding.sessionId);
  }
  adoptConversation(binding: SessionBinding, conversationId: string): SessionBinding {
    const updated = { ...binding, conversationId };
    this.db.prepare('UPDATE sessions SET conversation_id=?,binding=? WHERE session_id=?').run(conversationId, JSON.stringify(updated), binding.sessionId);
    return updated;
  }

  /** Read only deletion-operation facts, never a substitute Schedule catalog. */
  scheduleDeletions():ScheduleDeletionIntent[]{return (this.db.prepare('SELECT intent FROM schedule_deletions ORDER BY rowid').all() as {intent:string}[]).map(row=>JSON.parse(row.intent));}
  /** Persist an intent or independent notification receipt before proceeding. */
  saveScheduleDeletion(intent:ScheduleDeletionIntent):void{this.db.prepare('INSERT INTO schedule_deletions VALUES(?,?) ON CONFLICT(operation_id) DO UPDATE SET intent=excluded.intent').run(intent.operationId,JSON.stringify(intent));}
  control(id: string): ControlIntent | undefined {
    const row = this.db.prepare('SELECT intent FROM control_intents WHERE id=?').get(id) as { intent: string } | undefined; return row ? JSON.parse(row.intent) : undefined;
  }
  controls(): ControlIntent[] { return (this.db.prepare('SELECT intent FROM control_intents ORDER BY rowid').all() as { intent: string }[]).map(row => JSON.parse(row.intent)); }
  saveControl(intent: ControlIntent) { this.db.prepare('INSERT INTO control_intents VALUES(?,?) ON CONFLICT(id) DO UPDATE SET intent=excluded.intent').run(intent.id, JSON.stringify(intent)); }
  command(id: string): string | undefined {
    return (this.db.prepare('SELECT result FROM command_results WHERE id=?').get(id) as { result: string } | undefined)?.result;
  }
  saveCommand(id: string, text: string): void { this.db.prepare('INSERT OR IGNORE INTO command_results VALUES(?,?)').run(id, text); }
  forgetCommand(id:string):void { this.db.prepare('DELETE FROM command_results WHERE id=?').run(id); }
  /** Replace only the active lookup; historical sessions retain their delivery target. */
  reset(binding: SessionBinding, next: SessionBinding, commandId: string): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('UPDATE sessions SET conversation_id=? WHERE session_id=?').run(`history:${binding.sessionId}`, binding.sessionId);
      this.bind(next);
      this.db.prepare('UPDATE canonical_sessions SET session_id=? WHERE agent_id=? AND session_id=?').run(next.sessionId, binding.agentId, binding.sessionId);
      this.saveCommand(commandId, '已开始新会话。'); this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }

  bufferGroup(input: RelayInput): void {
    input=this.admitInput(input);
    const id = `${input.agent_id}:${input.message.id}`;
    this.db.prepare('INSERT OR IGNORE INTO group_background(input_id,agent_id,conversation_id,payload) SELECT ?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM inputs WHERE input_id=?)').run(id, input.agent_id, input.conversation_id, JSON.stringify(input), id);
  }
  /** Transfer parked context into the durable handoff before dropping its buffer row. */
  takeGroup(binding: SessionBinding): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const rows = this.db.prepare('SELECT payload FROM group_background WHERE agent_id=? AND conversation_id=? AND cancelled=0 ORDER BY rowid').all(binding.agentId, binding.conversationId) as { payload: string }[];
      for (const row of rows) {
        const input = JSON.parse(row.payload) as RelayInput;
        this.receive(binding.sessionId, { ...input, metadata: { ...input.metadata, context_only: true } });
      }
      this.db.prepare('DELETE FROM group_background WHERE agent_id=? AND conversation_id=? AND cancelled=0').run(binding.agentId, binding.conversationId);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }

  /** Persist before runtime submission; duplicate transport messages share one input. */
  receive(sessionId: string, input: RelayInput): string {
    input=this.admitInput(input);
    const id = `${input.agent_id}:${input.message.id}`;
    this.db.prepare('INSERT OR IGNORE INTO inputs(input_id,session_id,relay_id,payload) VALUES(?,?,?,?)').run(id, sessionId, input.relay_task_id, JSON.stringify(input));
    return id;
  }
  accepted(inputId: string): void { this.db.prepare('UPDATE inputs SET accepted=1 WHERE input_id=?').run(inputId); }
  /** Persist lookup evidence atomically with its logical finality.
   *
   * Args:
   *   inputId: Durable runtime input identity.
   *   evidence: Authoritative session.lookup result.
   *   final: Whether logical completion was established; defaults to unresolved.
   */
  inputEvidence(inputId: string, evidence: { accepted: boolean; turn?: number; terminal?: unknown }, final = false): void {
    this.db.prepare('UPDATE inputs SET accepted=?,turn=coalesce(?,turn),terminal=?,evidence_final=? WHERE input_id=? AND terminal IS NOT ?').run(
      Number(evidence.accepted), evidence.turn ?? null, evidence.terminal === undefined ? null : JSON.stringify(evidence.terminal), Number(final), inputId, JSON.stringify({kind:'cancelled_by_disable'}),
    );
  }
  /** Select unresolved input identities without loading completed history payloads.
   *
   * Args:
   *   sessionId: Session whose durable evidence needs reconciliation.
   * Returns:
   *   Input IDs in admission order, including legacy rows not yet verified.
   */
  lookupInputIds(sessionId: string): string[] {
    return (this.db.prepare('SELECT input_id FROM inputs WHERE session_id=? AND evidence_final=0 ORDER BY rowid').all(sessionId) as { input_id: string }[]).map(row => row.input_id);
  }
  inputs(sessionId: string) {
    return (this.db.prepare('SELECT input_id,payload,accepted,turn,terminal FROM inputs WHERE session_id=? ORDER BY rowid').all(sessionId) as {
      input_id: string; payload: string; accepted: number; turn: number | null; terminal: string | null;
    }[]).map(row => ({ id: row.input_id, input: JSON.parse(row.payload) as RelayInput, accepted: !!row.accepted, turn: row.turn, terminal: row.terminal }));
  }
  inputForTurn(sessionId: string, turn: number) { return this.inputs(sessionId).find(input => input.turn === turn); }

  prepareScheduleRun(inputId: string, agentId: string, scheduleId: string, sessionId: string): void {
    this.db.prepare('INSERT OR IGNORE INTO schedule_runs VALUES(?,?,?,?,?)').run(inputId, agentId, scheduleId, sessionId, new Date().toISOString());
  }
  scheduleRuns(agentId: string, scheduleId: string, sessionId: string) {
    return this.db.prepare('SELECT input_id AS messageId,requested_at AS deliveredAt FROM schedule_runs WHERE agent_id=? AND schedule_id=? AND session_id=? ORDER BY requested_at DESC LIMIT 20').all(agentId, scheduleId, sessionId) as { messageId: string; deliveredAt: string }[];
  }

  /** Checkpoint only events returned by the runtime's persistence-barrier read. */
  recordEvents(sessionId: string, events: RuntimeEvent[]): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      for (const event of events) {
        this.db.prepare('INSERT OR IGNORE INTO runtime_events VALUES(?,?,?)').run(sessionId, event.seq, JSON.stringify(event));
        const messages = event.type === 'agent/inbox/spliced' ? event.data.inserted as RuntimeInput[]
          : event.type === 'user/message' ? [event.data as unknown as RuntimeInput] : [];
        for (const message of messages) this.runtimeInput(sessionId, message, event.type === 'agent/inbox/spliced');
        // A delayed physical attempt end cannot replace a final logical lookup.
        if (event.type === 'turn/end') this.db.prepare('UPDATE inputs SET terminal=? WHERE session_id=? AND turn=? AND evidence_final=0').run(JSON.stringify(event.data.reason), sessionId, Number(event.data.turn));
      }
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Native scheduled messages already exist in DSH; never submit them a second time. */
  private runtimeInput(sessionId: string, message: RuntimeInput, inserted: boolean): void {
    const source = message.source;
    if (source?.kind !== 'schedule' && !(source?.kind === 'nano-system' && ['heartbeat','task-execution','task-change'].includes(String(source.channel)))) return;
    const binding = this.bindings().find(binding => binding.sessionId === sessionId)!;
    // Schedule publishes its native insertion before the integration can stamp
    // the same message through public Inbox.replace. Do not bind that transient
    // unversioned representation to epoch 1 after a stop/enable transition.
    if (inserted && source.kind === 'schedule' && source.lifecycle_revision === undefined && (this.lifecycle.snapshot(binding.agentId)?.revision ?? 1) > 1) return;
    const input: RelayInput = {
      relay_task_id: `runtime:${sessionId}:${message.id}`, idempotency_key: message.id,
      agent_id: binding.agentId, conversation_id: binding.conversationId,lifecycle_revision:source.lifecycle_revision??1,
      metadata: { runtime_input_id: message.id, ...(source.kind==='nano-system'&&source.channel==='task-change'?{context_only:true}:{}), origin: source.kind === 'schedule' ? 'schedule' : ['task-execution','task-change'].includes(String(source.channel))?'task_execution':'heartbeat',
        ...(binding.conversationId.startsWith('external:') ? { external_reply: `runtime:${message.id}`, channel: 'feishu' } : {}),
      },
      message: { id: message.id, content: message.content.filter(part => part.type === 'text').map(part => part.text ?? '').join(''),
        sender_user_id: binding.agentId, sender_type: 'system', attachments: [] },
    };
    this.db.prepare('INSERT OR IGNORE INTO inputs(input_id,session_id,relay_id,payload,accepted) VALUES(?,?,?,?,1)').run(message.id, sessionId, input.relay_task_id, JSON.stringify(input));
  }
  events(sessionId: string, afterSeq = -1): RuntimeEvent[] {
    return (this.db.prepare('SELECT event FROM runtime_events WHERE session_id=? AND seq>? ORDER BY seq').all(sessionId,afterSeq) as { event: string }[]).map(row => JSON.parse(row.event) as RuntimeEvent);
  }
  cursor(sessionId: string): number {
    return (this.db.prepare('SELECT coalesce(max(seq),-1) AS seq FROM runtime_events WHERE session_id=?').get(sessionId) as { seq: number }).seq;
  }

  prepareDelivery(sessionId: string, turn: number): Delivery {
    const operationId = `nano:${sessionId}:${turn}`;
    this.db.prepare("INSERT OR IGNORE INTO deliveries(operation_id,session_id,turn,state) VALUES(?,?,?,'prepared')").run(operationId, sessionId, turn);
    return this.delivery(sessionId, turn)!;
  }
  delivery(sessionId: string, turn: number): Delivery | undefined {
    return this.db.prepare('SELECT operation_id AS operationId,state,message_id AS messageId,content FROM deliveries WHERE session_id=? AND turn=?').get(sessionId, turn) as Delivery | undefined;
  }
  activeDeliveries(sessionId: string): Delivery[] {
    return this.db.prepare("SELECT operation_id AS operationId,state,message_id AS messageId,content FROM deliveries WHERE session_id=? AND state='sending' AND message_id IS NOT NULL").all(sessionId) as unknown as Delivery[];
  }
  updateDelivery(operationId: string, state: DeliveryState, messageId: string | null, content: string): void {
    this.db.prepare('UPDATE deliveries SET state=?,message_id=?,content=? WHERE operation_id=?').run(state, messageId, content, operationId);
  }
  /** Retire the failed placeholder and reserve a distinct backup bubble atomically. */
  advanceFallbackDelivery(operationId: string, noticeId: string, marker: string): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.saveCommand(noticeId, 'delivered'); this.saveCommand(marker, 'converted-to-failure');
      this.updateDelivery(operationId, 'prepared', null, ''); this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  eventDelivered(operationId: string, seq: number): boolean {
    return !!this.db.prepare('SELECT 1 FROM delivery_events WHERE operation_id=? AND seq=?').get(operationId, seq);
  }
  confirmEvent(operationId: string, seq: number): void {
    this.db.prepare('INSERT OR IGNORE INTO delivery_events VALUES(?,?)').run(operationId, seq);
  }
  receipt(inputId: string): string | undefined {
    return (this.db.prepare('SELECT status FROM input_receipts WHERE input_id=?').get(inputId) as { status: string } | undefined)?.status;
  }
  confirmReceipt(inputId: string, status: string): void {
    this.db.prepare('INSERT INTO input_receipts VALUES(?,?) ON CONFLICT(input_id) DO UPDATE SET status=excluded.status').run(inputId, status);
  }
  close(): void { this.db.close(); }
}
export interface Delivery { operationId: string; state: DeliveryState; messageId: string | null; content: string }

interface RuntimeInput { id: string; content: { type: string; text?: string }[]; source?: { kind: string; channel?: string; lifecycle_revision?:number } }
