import { DatabaseSync } from 'node:sqlite';
import { createHash, randomUUID } from 'node:crypto';
import type { RelayInput } from '@nano/product-contracts';
import { formatLocalTime, withInteractionContext } from '@nano/product-contracts';

interface Entry { seq: number; agent_id: string; target: string; payload: string; attention: number; consumed: number }
interface Background { last_notified_at: number | null; due_at: number | null; notified_through_seq: number; submitting_through_seq: number | null }
interface Fragment { seq: number; part: number }
interface Snapshot { agent: string; target: string; fragments: Fragment[] }
const hash = (value: string) => createHash('sha256').update(value).digest('hex');

/** Durable cross-chat inbox; a read does not itself advance consumption. */
export class InboxStore {
  readonly journalId: string;
  private readonly db: DatabaseSync;
  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS inbox(seq INTEGER PRIMARY KEY,agent_id TEXT,target TEXT,message_id TEXT,payload TEXT,attention INTEGER,consumed INTEGER DEFAULT 0,UNIQUE(agent_id,message_id));
      CREATE TABLE IF NOT EXISTS imported_parts(seq INTEGER,part INTEGER,body TEXT,PRIMARY KEY(seq,part));
      CREATE TABLE IF NOT EXISTS fragments(seq INTEGER,part INTEGER,PRIMARY KEY(seq,part));
      CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,data TEXT);
      CREATE TABLE IF NOT EXISTS reads(session_id TEXT,call_id TEXT,fragments TEXT,body TEXT,digest TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS wakes(agent_id TEXT PRIMARY KEY,watermark INTEGER);
      CREATE TABLE IF NOT EXISTS background_wakes(agent_id TEXT PRIMARY KEY,last_notified_at INTEGER,due_at INTEGER,notified_through_seq INTEGER DEFAULT 0,submitting_through_seq INTEGER);
      CREATE TABLE IF NOT EXISTS journal(seq INTEGER PRIMARY KEY,event_id TEXT UNIQUE,event TEXT);
      CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS read_content(session_id TEXT,call_id TEXT,digest TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS targets(agent_id TEXT,target TEXT,name TEXT,PRIMARY KEY(agent_id,target));
      CREATE TABLE IF NOT EXISTS ingestions(seq INTEGER PRIMARY KEY,session_id TEXT,turn INTEGER);
      CREATE TABLE IF NOT EXISTS receipts(seq INTEGER PRIMARY KEY,status TEXT);
      CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,target TEXT,body TEXT,state TEXT,result TEXT);
    `);
    this.db.prepare('INSERT OR IGNORE INTO metadata VALUES(?,?)').run('journal', randomUUID());
    this.journalId = (this.db.prepare('SELECT value FROM metadata WHERE key=?').get('journal') as { value: string }).value;
  }
  /** Persist an input and its first background deadline together.
   * Args:
   *   now: Node reception time in UTC milliseconds, independent of message time.
   */
  receive(input: RelayInput, attention: boolean, now = Date.now()): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      // Source removal must not reuse an accepted or in-flight notification identity.
      this.db.prepare(`INSERT OR IGNORE INTO inbox(seq,agent_id,target,message_id,payload,attention) VALUES((SELECT max(
        coalesce((SELECT max(seq) FROM inbox),0),coalesce((SELECT max(watermark) FROM wakes),0),
        coalesce((SELECT max(notified_through_seq) FROM background_wakes),0),coalesce((SELECT max(submitting_through_seq) FROM background_wakes),0))+1),?,?,?,?,?)`)
        .run(input.agent_id, input.conversation_id, input.message.id, JSON.stringify(input), Number(attention));
      if (input.metadata.personal_delivery === 'observer') this.trackBackground(input.agent_id, now);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  private trackBackground(agent: string, now: number): void {
    // Old, already notified inputs must not become new background wakes after upgrade.
    this.db.prepare('INSERT OR IGNORE INTO background_wakes(agent_id,notified_through_seq) VALUES(?,coalesce((SELECT watermark FROM wakes WHERE agent_id=?),0))').run(agent,agent);
    this.background(agent, now);
  }
  /** Return unread legacy PA inputs that still require authenticated source facts. */
  unclassified(agent: string): RelayInput[] {
    return this.entries(agent).map(row => JSON.parse(row.payload) as RelayInput).filter(input => input.metadata.personal_delivery === undefined);
  }
  /** Replace legacy admission facts without changing saved tool results or consumption. */
  classify(input: RelayInput, attention: boolean): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('UPDATE inbox SET payload=?,attention=? WHERE agent_id=? AND message_id=?').run(JSON.stringify(input),Number(attention),input.agent_id,input.message.id);
      if (input.metadata.personal_delivery === 'observer') this.trackBackground(input.agent_id, Date.now());
      this.db.exec('COMMIT');
    } catch(error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Return one pending background boundary, dropping deadlines for consumed inputs.
   * Args:
   *   now: Node UTC milliseconds used only to establish a missing deadline.
   * Returns:
   *   A durable deadline and watermark; pending identities survive uncertain ACKs.
   */
  background(agent: string, now = Date.now()): {dueAt: number; watermark: number; pending: boolean; unread: boolean} | undefined {
    const row=this.db.prepare('SELECT * FROM background_wakes WHERE agent_id=?').get(agent) as unknown as Background | undefined;
    if (!row) return;
    const newest=this.db.prepare("SELECT max(seq) seq FROM inbox WHERE agent_id=? AND consumed=0 AND seq>? AND json_extract(payload,'$.metadata.personal_delivery')='observer'").get(agent,row.notified_through_seq) as {seq:number|null};
    if (newest.seq === null && row.submitting_through_seq === null) {
      this.db.prepare('UPDATE background_wakes SET due_at=NULL WHERE agent_id=?').run(agent); return;
    }
    const dueAt=row.due_at ?? (row.last_notified_at === null ? now+600000 : Math.max(now,row.last_notified_at+600000));
    if (row.due_at === null) this.db.prepare('UPDATE background_wakes SET due_at=? WHERE agent_id=?').run(dueAt,agent);
    return {dueAt,watermark:row.submitting_through_seq ?? newest.seq!,pending:row.submitting_through_seq !== null,unread:newest.seq !== null};
  }
  /** Reserve a stable batch identity before the runtime may accept it. */
  prepareBackground(agent: string, watermark: number): void {
    this.db.prepare('UPDATE background_wakes SET submitting_through_seq=coalesce(submitting_through_seq,?) WHERE agent_id=?').run(watermark,agent);
  }
  /** Settle a notification, or discard a proven-unaccepted empty batch.
   * Args:
   *   notified: False only when runtime lookup proves an empty batch was not accepted.
   * Side Effects:
   *   Advances notification identity, never message consumption.
   */
  admitBackground(agent: string, watermark: number, now=Date.now(), notified=true): void {
    this.db.prepare(`UPDATE background_wakes SET notified_through_seq=max(notified_through_seq,?),
      last_notified_at=CASE WHEN ? THEN ? ELSE last_notified_at END,due_at=NULL,submitting_through_seq=NULL WHERE agent_id=?`)
      .run(watermark,Number(notified),now,agent);
    this.background(agent,now);
  }
  /** Remove a revoked source from future reads and frozen page caches. */
  revokeSource(agent: string, target: string): void {
    const rows = this.db.prepare('SELECT seq FROM inbox WHERE agent_id=? AND target=?').all(agent,target) as {seq:number}[];
    for(const {seq} of rows) {
      this.db.prepare('DELETE FROM imported_parts WHERE seq=?').run(seq);
      this.db.prepare('DELETE FROM fragments WHERE seq=?').run(seq);
    }
    this.db.prepare('DELETE FROM inbox WHERE agent_id=? AND target=?').run(agent,target);
    this.db.prepare("DELETE FROM snapshots WHERE json_extract(data,'$.agent')=? AND json_extract(data,'$.target')=?").run(agent,target);
    this.db.prepare("DELETE FROM reads WHERE json_extract(body,'$.target')=?").run(target);
    this.db.prepare('DELETE FROM targets WHERE agent_id=? AND target=?').run(agent,target);
  }
  private entries(agent: string, target?: string): Entry[] {
    return this.db.prepare('SELECT * FROM inbox WHERE agent_id=? AND consumed=0 AND (? IS NULL OR target=?) ORDER BY seq').all(agent, target ?? null, target ?? null) as unknown as Entry[];
  }
  /** List unread sources; personal projection omits host scheduling state. */
  check(agent: string, personal = false) {
    const sources = new Map<string, { target: string; name: string; unread: number; requires_attention?: boolean; conversation_type?: string; delivery?: string }>();
    for (const row of this.entries(agent)) {
      const input = JSON.parse(row.payload) as RelayInput;
      const source = sources.get(row.target) ?? { target: row.target, name: this.targetName(agent,row.target,input), unread: 0,
        ...(personal ? {conversation_type:String(input.metadata.conversation_type),delivery:String(input.metadata.personal_delivery)} : {requires_attention:false}) };
      source.unread++; if (!personal) source.requires_attention ||= !!row.attention; sources.set(row.target, source);
    }
    return { sources: [...sources.values()] };
  }
  private targetName(agent: string, target: string, input: RelayInput): string {
    return (this.db.prepare('SELECT name FROM targets WHERE agent_id=? AND target=?').get(agent,target) as {name:string}|undefined)?.name ?? String(input.metadata.conversation_title ?? target);
  }
  blocking(agent: string, target: string): boolean { return this.entries(agent, target).some(row => !!row.attention); }
  watermark(agent: string): number { return Number((this.db.prepare('SELECT coalesce(max(seq),0) AS seq FROM inbox WHERE agent_id=? AND attention=1').get(agent) as { seq: number }).seq); }
  wakePending(agent: string): number | undefined {
    const latest = this.watermark(agent);
    const admitted = (this.db.prepare('SELECT watermark FROM wakes WHERE agent_id=?').get(agent) as { watermark: number } | undefined)?.watermark ?? 0;
    return latest > admitted ? latest : undefined;
  }
  admitWake(agent: string, watermark: number): void { this.db.prepare('INSERT INTO wakes VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET watermark=max(watermark,excluded.watermark)').run(agent, watermark); }

  /** Freeze fragments and persist the exact page admitted to the model.
   *
   * Args:
   *   agent: Trusted product Agent identity.
   *   session: Execution session receiving this page.
   *   call: Durable tool call identity; retries replay its saved body.
   *   args: Canonical target and cursor; later messages remain a later read.
   *   present: Optional model projection, applied before saving the consumption evidence.
   * Returns:
   *   Saved page; only this exact content can commit its fragments as consumed.
   */
  read(agent: string, session: string, call: string, args: { target: string; cursor?: string; limit?: number }, present: (body: Record<string, unknown>) => Record<string, unknown> = body => body): Record<string, unknown> {
    const prior = this.db.prepare('SELECT body FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { body: string } | undefined;
    if (prior) return JSON.parse(prior.body) as Record<string, unknown>;
    let snapshot: Snapshot;
    let snapshotId: string;
    let offset = 0;
    if (args.cursor) {
      const cursor = JSON.parse(Buffer.from(args.cursor, 'base64url').toString()) as { id: string; offset: number };
      const saved = this.db.prepare('SELECT data FROM snapshots WHERE id=?').get(cursor.id) as { data: string } | undefined;
      if (!saved || !Number.isSafeInteger(cursor.offset) || cursor.offset < 0) throw new Error('Invalid inbox cursor');
      snapshot = JSON.parse(saved.data) as Snapshot;
      if (snapshot.agent !== agent || snapshot.target !== args.target) throw new Error('Inbox cursor scope mismatch');
      snapshotId = cursor.id; offset = cursor.offset;
    } else {
      snapshotId = randomUUID();
      snapshot = { agent, target: args.target, fragments: this.entries(agent, args.target).flatMap(row => {
        const count = this.parts(JSON.parse(row.payload) as RelayInput, row.seq).length;
        return Array.from({ length: count }, (_, part) => ({ seq: row.seq, part }))
          .filter(fragment => !this.db.prepare('SELECT 1 FROM fragments WHERE seq=? AND part=?').get(fragment.seq, fragment.part));
      }) };
      this.db.prepare('INSERT INTO snapshots VALUES(?,?)').run(snapshotId, JSON.stringify(snapshot));
    }
    let selected = snapshot.fragments.slice(offset, offset + Math.min(4, Math.max(1, args.limit ?? 4)));
    const sourceInput = (seq: number) => JSON.parse((this.db.prepare('SELECT payload FROM inbox WHERE seq=?').get(seq) as {payload:string}).payload) as RelayInput;
    const first = selected.length ? sourceInput(selected[0]!.seq) : undefined;
    const personal = first?.metadata.personal_delivery !== undefined;
    if (personal) {
      // A page shares source context; stop at a historical relationship boundary.
      const context = (input: RelayInput) => JSON.stringify([input.metadata.personal_delivery,input.metadata.conversation_type,input.metadata.channel]);
      const boundary = selected.findIndex(fragment => context(sourceInput(fragment.seq)) !== context(first!));
      if (boundary !== -1) selected = selected.slice(0,boundary);
    }
    const messages = selected.map(fragment => {
      const row = this.db.prepare('SELECT * FROM inbox WHERE seq=?').get(fragment.seq) as unknown as Entry;
      const input = JSON.parse(row.payload) as RelayInput;
      const parts = this.parts(input, row.seq);
      const instant = input.message.created_at ?? input.metadata.created_at ?? input.metadata.source_time
        ?? (input.metadata.source_timestamp ? Number(input.metadata.source_timestamp) : undefined);
      return { id: input.message.id, sender: { id: input.message.sender_user_id, type: input.message.sender_type,
        name: input.message.sender?.display_name ?? input.metadata.sender_display_name ?? input.metadata.sender_name ?? input.message.sender_user_id,
        ...(personal ? {is_owner:input.metadata.personal_is_owner === true} : {}) }, time: instant === undefined ? null : formatLocalTime(instant as string | number, input.message.timezone),
        ...(!personal && input.metadata.channel ? {channel:input.metadata.channel} : {}),
        ...(input.metadata.personal_actor_risk ? {actor_risk:personal ? this.actorRisk(input) : input.metadata.personal_actor_risk} : {}),
        content: parts[fragment.part], ...(parts.length > 1 ? { partial: true, part: fragment.part + 1, parts: parts.length } : {}) };
    });
    const next = offset + selected.length;
    const body = present({ target: args.target,
      ...(personal ? {name:this.targetName(agent,args.target,first!),conversation_type:first!.metadata.conversation_type,delivery:first!.metadata.personal_delivery,channel:first!.metadata.channel} : {}), messages, ...(next < snapshot.fragments.length ? { next_cursor: Buffer.from(JSON.stringify({ id: snapshotId, offset: next })).toString('base64url') } : {}) });
    const text = JSON.stringify(body);
    this.db.prepare('INSERT INTO reads VALUES(?,?,?,?,?)').run(session, call, JSON.stringify(selected), text, hash(text));
    return body;
  }
  private actorRisk(input: RelayInput): Record<string, unknown> {
    const risk=input.metadata.personal_actor_risk as Record<string,unknown>;
    return {status:risk.status,reason:risk.reason};
  }
  private parts(input: RelayInput, seq?: number): Record<string, unknown>[][] {
    if (seq !== undefined) {
      const imported = this.db.prepare('SELECT body FROM imported_parts WHERE seq=? ORDER BY part').all(seq) as {body: string}[];
      if (imported.length) return imported.map(row => JSON.parse(row.body) as Record<string, unknown>[]);
    }
    const text = withInteractionContext(input.message.content, input.message.interaction_reply, input.metadata.interaction_contexts);
    const result: Record<string, unknown>[][] = [];
    for (let start = 0; start < text.length || start === 0; start += 6000) result.push([{ type: 'text', text: text.slice(start, start + 6000) }]);
    for (const attachment of input.message.attachments) result.push([{ type: 'attachment', ...attachment }]);
    return result;
  }
  updateTarget(agent: string, target: string, name: string): void { this.db.prepare('INSERT INTO targets VALUES(?,?,?) ON CONFLICT(agent_id,target) DO UPDATE SET name=excluded.name').run(agent, target, name); }
  imageReferences(session: string, call: string): string[] {
    return this.imageSources(session, call).map(source => source.url);
  }
  /** Read image provenance from the saved tool page, including legacy per-message targets.
   *
   * Args:
   *   session: Execution session owning the read.
   *   call: Durable Inbox read call.
   * Returns:
   *   Image sources; compact conversation references still need host resolution.
   * Raises:
   *   Error: There is no matching saved Inbox read.
   */
  imageSources(session: string, call: string): { kind: 'chat'; conversationId: string; messageId: string; url: string }[] {
    const row = this.db.prepare('SELECT body FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { body: string } | undefined;
    if (!row) throw new Error('No matching inbox read');
    const body = JSON.parse(row.body) as { target: string; messages: { id: string; target?: string; content: { type: string; content_type?: string; url?: string }[] }[] };
    return body.messages.flatMap(message => message.content.filter(part => part.content_type?.startsWith('image/')).map(part => ({
      kind: 'chat' as const, conversationId: message.target ?? body.target, messageId: message.id, url: part.url!,
    })));
  }
  prepareRead(session: string, call: string, content: { type: string; text?: string }[]): void {
    const row = this.db.prepare('SELECT body FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { body: string } | undefined;
    if (!row || content[0]?.text !== row.body || content.filter(part => part.type === 'image').length !== this.imageReferences(session, call).length) throw new Error('Incomplete prepared inbox content');
    this.db.prepare('INSERT INTO read_content VALUES(?,?,?) ON CONFLICT(session_id,call_id) DO UPDATE SET digest=excluded.digest').run(session, call, hash(JSON.stringify(content)));
  }
  reviewTargets(session: string, turn: number): string[] {
    return (this.db.prepare('SELECT DISTINCT i.target FROM inbox i JOIN ingestions g ON g.seq=i.seq WHERE g.session_id=? AND g.turn=? AND i.consumed=1').all(session, turn) as { target: string }[]).map(row => row.target);
  }
  completedInputs(session: string, turn: number): { seq: number; input: RelayInput }[] {
    return (this.db.prepare('SELECT i.seq,i.payload FROM inbox i JOIN ingestions g ON g.seq=i.seq LEFT JOIN receipts r ON r.seq=i.seq WHERE g.session_id=? AND g.turn=? AND r.seq IS NULL').all(session, turn) as { seq: number; payload: string }[]).map(row => ({ seq: row.seq, input: JSON.parse(row.payload) as RelayInput }));
  }
  confirmReceipt(seq: number, status: string): void { this.db.prepare('INSERT OR REPLACE INTO receipts VALUES(?,?)').run(seq, status); }
  /** Match the exact committed tool body, never a summary, truncation, or failed call. */
  commitRead(session: string, call: string, content: { type: string; text?: string }[], isError: boolean, turn?: number): boolean {
    const read = this.db.prepare('SELECT fragments,digest FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { fragments: string; digest: string } | undefined;
    if (!read || isError) return false;
    const prepared = this.db.prepare('SELECT digest FROM read_content WHERE session_id=? AND call_id=?').get(session, call) as { digest: string } | undefined;
    if (prepared ? prepared.digest !== hash(JSON.stringify(content)) : this.imageReferences(session, call).length > 0 || read.digest !== hash(content.filter(block => block.type === 'text').map(block => block.text ?? '').join(''))) return false;
    const fragments = JSON.parse(read.fragments) as Fragment[];
    this.db.exec('BEGIN IMMEDIATE');
    try {
      for (const fragment of fragments) {
        this.db.prepare('INSERT OR IGNORE INTO fragments VALUES(?,?)').run(fragment.seq, fragment.part);
        const row = this.db.prepare('SELECT seq,payload FROM inbox WHERE seq=?').get(fragment.seq) as { seq: number; payload: string };
        const count = (this.db.prepare('SELECT count(*) AS n FROM fragments WHERE seq=?').get(fragment.seq) as { n: number }).n;
        if (count === this.parts(JSON.parse(row.payload) as RelayInput, row.seq).length) {
          this.db.prepare('UPDATE inbox SET consumed=1 WHERE seq=?').run(fragment.seq);
          if (turn !== undefined) this.db.prepare('INSERT OR IGNORE INTO ingestions VALUES(?,?,?)').run(fragment.seq, session, turn);
        }
      }
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
    return true;
  }
  append(event: Record<string, unknown> & { event_id: string }): void {
    if (this.db.prepare('SELECT 1 FROM journal WHERE event_id=?').get(event.event_id)) return;
    const seq = (this.db.prepare('SELECT coalesce(max(seq),0)+1 AS seq FROM journal').get() as { seq: number }).seq;
    this.db.prepare('INSERT INTO journal VALUES(?,?,?)').run(seq, event.event_id, JSON.stringify({ ...event, seq }));
  }
  journal(after: number): Record<string, unknown>[] { return (this.db.prepare('SELECT event FROM journal WHERE seq>? ORDER BY seq LIMIT 100').all(after) as { event: string }[]).map(row => JSON.parse(row.event) as Record<string, unknown>); }
  get throughSeq(): number { return Number((this.db.prepare('SELECT value FROM metadata WHERE key=?').get('through') as { value: string } | undefined)?.value ?? 0); }
  acknowledge(seq: number): void { this.db.prepare('INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run('through', String(seq)); }
  publication(id: string): { target: string; body: string; state: string; result: string | null } | undefined { return this.db.prepare('SELECT target,body,state,result FROM publications WHERE id=?').get(id) as { target: string; body: string; state: string; result: string | null } | undefined; }
  preparePublication(id: string, target: string, body: string): void { this.db.prepare("INSERT OR IGNORE INTO publications VALUES(?,?,?,'prepared',NULL)").run(id, target, body); }
  settlePublication(id: string, state: string, result?: unknown): void { this.db.prepare('UPDATE publications SET state=?,result=? WHERE id=?').run(state, result === undefined ? null : JSON.stringify(result), id); }
  close(): void { this.db.close(); }
}
