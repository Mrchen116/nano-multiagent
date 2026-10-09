import { DatabaseSync } from 'node:sqlite';
import type { DeliveryState, RelayInput, RuntimeEvent, SessionBinding } from '@nano/product-contracts';

/** Node-owned durable handoff and delivery facts, independent of DSH storage. */
export class NodeStore {
  private readonly db: DatabaseSync;
  constructor(path: string, readonly ownerId: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA synchronous=FULL;
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS node_owner (owner_id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL, binding TEXT NOT NULL,
        UNIQUE(agent_id, conversation_id)
      );
      CREATE TABLE IF NOT EXISTS conversation_aliases(agent_id TEXT NOT NULL,alias TEXT NOT NULL,canonical TEXT NOT NULL,PRIMARY KEY(agent_id,alias));
      CREATE TABLE IF NOT EXISTS group_background (input_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, conversation_id TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS schedule_runs (input_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, schedule_id TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(session_id), requested_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS canonical_sessions (agent_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id));
      CREATE TABLE IF NOT EXISTS inputs (
        input_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id),
        relay_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
        accepted INTEGER NOT NULL DEFAULT 0, turn INTEGER, terminal TEXT
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
      CREATE TABLE IF NOT EXISTS input_receipts (input_id TEXT PRIMARY KEY REFERENCES inputs(input_id), status TEXT NOT NULL);
    `);
    this.db.prepare('INSERT INTO node_owner(owner_id) SELECT ? WHERE NOT EXISTS(SELECT 1 FROM node_owner)').run(ownerId);
    const owner = this.db.prepare('SELECT owner_id FROM node_owner').get() as { owner_id: string };
    if (owner.owner_id !== ownerId) { this.db.close(); throw new Error('Node state belongs to a different owner'); }
  }

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
  private canonicalConversation(agentId: string, conversationId: string): string {
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

  bufferGroup(input: RelayInput): void {
    const id = `${input.agent_id}:${input.message.id}`;
    this.db.prepare('INSERT OR IGNORE INTO group_background SELECT ?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM inputs WHERE input_id=?)').run(id, input.agent_id, input.conversation_id, JSON.stringify(input), id);
  }
  /** Transfer parked context into the durable handoff before dropping its buffer row. */
  takeGroup(binding: SessionBinding): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const rows = this.db.prepare('SELECT payload FROM group_background WHERE agent_id=? AND conversation_id=? ORDER BY rowid').all(binding.agentId, binding.conversationId) as { payload: string }[];
      for (const row of rows) {
        const input = JSON.parse(row.payload) as RelayInput;
        this.receive(binding.sessionId, { ...input, metadata: { ...input.metadata, context_only: true } });
      }
      this.db.prepare('DELETE FROM group_background WHERE agent_id=? AND conversation_id=?').run(binding.agentId, binding.conversationId);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }

  /** Persist before runtime submission; duplicate transport messages share one input. */
  receive(sessionId: string, input: RelayInput): string {
    const id = `${input.agent_id}:${input.message.id}`;
    this.db.prepare('INSERT OR IGNORE INTO inputs(input_id,session_id,relay_id,payload) VALUES(?,?,?,?)').run(id, sessionId, input.relay_task_id, JSON.stringify(input));
    return id;
  }
  accepted(inputId: string): void { this.db.prepare('UPDATE inputs SET accepted=1 WHERE input_id=?').run(inputId); }
  inputEvidence(inputId: string, evidence: { accepted: boolean; turn?: number; terminal?: unknown }): void {
    this.db.prepare('UPDATE inputs SET accepted=?,turn=coalesce(?,turn),terminal=coalesce(?,terminal) WHERE input_id=?').run(
      Number(evidence.accepted), evidence.turn ?? null, evidence.terminal === undefined ? null : JSON.stringify(evidence.terminal), inputId,
    );
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
        for (const message of messages) this.runtimeInput(sessionId, message);
        if (event.type === 'turn/end') this.db.prepare('UPDATE inputs SET terminal=? WHERE session_id=? AND turn=?').run(JSON.stringify(event.data.reason), sessionId, Number(event.data.turn));
      }
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Native scheduled messages already exist in DSH; never submit them a second time. */
  private runtimeInput(sessionId: string, message: RuntimeInput): void {
    const source = message.source;
    if (source?.kind !== 'schedule' && !(source?.kind === 'nano-system' && source.channel === 'heartbeat')) return;
    const binding = this.bindings().find(binding => binding.sessionId === sessionId)!;
    const input: RelayInput = {
      relay_task_id: `runtime:${sessionId}:${message.id}`, idempotency_key: message.id,
      agent_id: binding.agentId, conversation_id: binding.conversationId,
      metadata: { runtime_input_id: message.id, origin: source.kind === 'schedule' ? 'schedule' : 'heartbeat',
        ...(binding.conversationId.startsWith('external:') ? { external_reply: `runtime:${message.id}`, channel: 'feishu' } : {}),
      },
      message: { id: message.id, content: message.content.filter(part => part.type === 'text').map(part => part.text ?? '').join(''),
        sender_user_id: binding.agentId, sender_type: 'system', attachments: [] },
    };
    this.db.prepare('INSERT OR IGNORE INTO inputs(input_id,session_id,relay_id,payload,accepted) VALUES(?,?,?,?,1)').run(message.id, sessionId, input.relay_task_id, JSON.stringify(input));
  }
  events(sessionId: string): RuntimeEvent[] {
    return (this.db.prepare('SELECT event FROM runtime_events WHERE session_id=? ORDER BY seq').all(sessionId) as { event: string }[]).map(row => JSON.parse(row.event) as RuntimeEvent);
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
  updateDelivery(operationId: string, state: DeliveryState, messageId: string | null, content: string): void {
    this.db.prepare('UPDATE deliveries SET state=?,message_id=?,content=? WHERE operation_id=?').run(state, messageId, content, operationId);
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

interface RuntimeInput { id: string; content: { type: string; text?: string }[]; source?: { kind: string; channel?: string } }
