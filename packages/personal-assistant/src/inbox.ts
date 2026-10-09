import { DatabaseSync } from 'node:sqlite';
import { createHash, randomUUID } from 'node:crypto';
import type { RelayInput } from '@nano/product-contracts';

interface Entry { seq: number; agent_id: string; target: string; payload: string; attention: number; consumed: number }
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
      CREATE TABLE IF NOT EXISTS fragments(seq INTEGER,part INTEGER,PRIMARY KEY(seq,part));
      CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,data TEXT);
      CREATE TABLE IF NOT EXISTS reads(session_id TEXT,call_id TEXT,fragments TEXT,body TEXT,digest TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS wakes(agent_id TEXT PRIMARY KEY,watermark INTEGER);
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
  receive(input: RelayInput, attention: boolean): void {
    this.db.prepare('INSERT OR IGNORE INTO inbox(agent_id,target,message_id,payload,attention) VALUES(?,?,?,?,?)')
      .run(input.agent_id, input.conversation_id, input.message.id, JSON.stringify(input), Number(attention));
  }
  private entries(agent: string, target?: string): Entry[] {
    return this.db.prepare('SELECT * FROM inbox WHERE agent_id=? AND consumed=0 AND (? IS NULL OR target=?) ORDER BY seq').all(agent, target ?? null, target ?? null) as unknown as Entry[];
  }
  check(agent: string) {
    const sources = new Map<string, { target: string; name: string; unread: number; requires_attention: boolean }>();
    for (const row of this.entries(agent)) {
      const input = JSON.parse(row.payload) as RelayInput;
      const source = sources.get(row.target) ?? { target: row.target, name: (this.db.prepare('SELECT name FROM targets WHERE agent_id=? AND target=?').get(agent, row.target) as { name: string } | undefined)?.name ?? String(input.metadata.conversation_title ?? row.target), unread: 0, requires_attention: false };
      source.unread++; source.requires_attention ||= !!row.attention; sources.set(row.target, source);
    }
    return { sources: [...sources.values()] };
  }
  blocking(agent: string, target: string): boolean { return this.entries(agent, target).some(row => !!row.attention); }
  watermark(agent: string): number { return Number((this.db.prepare('SELECT coalesce(max(seq),0) AS seq FROM inbox WHERE agent_id=? AND attention=1').get(agent) as { seq: number }).seq); }
  wakePending(agent: string): number | undefined {
    const latest = this.watermark(agent);
    const admitted = (this.db.prepare('SELECT watermark FROM wakes WHERE agent_id=?').get(agent) as { watermark: number } | undefined)?.watermark ?? 0;
    return latest > admitted ? latest : undefined;
  }
  admitWake(agent: string, watermark: number): void { this.db.prepare('INSERT INTO wakes VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET watermark=max(watermark,excluded.watermark)').run(agent, watermark); }

  /** Cursor freezes fragments and membership; later messages remain a later read. */
  read(agent: string, session: string, call: string, args: { target: string; cursor?: string; limit?: number }): Record<string, unknown> {
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
        const count = this.parts(JSON.parse(row.payload) as RelayInput).length;
        return Array.from({ length: count }, (_, part) => ({ seq: row.seq, part }))
          .filter(fragment => !this.db.prepare('SELECT 1 FROM fragments WHERE seq=? AND part=?').get(fragment.seq, fragment.part));
      }) };
      this.db.prepare('INSERT INTO snapshots VALUES(?,?)').run(snapshotId, JSON.stringify(snapshot));
    }
    const selected = snapshot.fragments.slice(offset, offset + Math.min(4, Math.max(1, args.limit ?? 4)));
    const messages = selected.map(fragment => {
      const row = this.db.prepare('SELECT * FROM inbox WHERE seq=?').get(fragment.seq) as unknown as Entry;
      const input = JSON.parse(row.payload) as RelayInput;
      const parts = this.parts(input);
      return { id: input.message.id, target: row.target, sender: { id: input.message.sender_user_id, type: input.message.sender_type,
        name: input.metadata.sender_name ?? input.message.sender_user_id }, time: input.metadata.created_at ?? input.metadata.source_time ?? null,
        content: parts[fragment.part], ...(parts.length > 1 ? { partial: true, part: fragment.part + 1, parts: parts.length } : {}) };
    });
    const next = offset + selected.length;
    const body = { messages, ...(next < snapshot.fragments.length ? { next_cursor: Buffer.from(JSON.stringify({ id: snapshotId, offset: next })).toString('base64url') } : {}) };
    const text = JSON.stringify(body);
    this.db.prepare('INSERT INTO reads VALUES(?,?,?,?,?)').run(session, call, JSON.stringify(selected), text, hash(text));
    return body;
  }
  private parts(input: RelayInput): Record<string, unknown>[][] {
    const text = input.message.content;
    const result: Record<string, unknown>[][] = [];
    for (let start = 0; start < text.length || start === 0; start += 6000) result.push([{ type: 'text', text: text.slice(start, start + 6000) }]);
    for (const attachment of input.message.attachments) result.push([{ type: 'attachment', ...attachment }]);
    return result;
  }
  updateTarget(agent: string, target: string, name: string): void { this.db.prepare('INSERT INTO targets VALUES(?,?,?) ON CONFLICT(agent_id,target) DO UPDATE SET name=excluded.name').run(agent, target, name); }
  imageReferences(session: string, call: string): string[] {
    const row = this.db.prepare('SELECT body FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { body: string } | undefined;
    if (!row) throw new Error('No matching inbox read');
    const body = JSON.parse(row.body) as { messages: { content: { type: string; content_type?: string; url?: string }[] }[] };
    return body.messages.flatMap(message => message.content.filter(part => part.content_type?.startsWith('image/')).map(part => part.url!));
  }
  prepareRead(session: string, call: string, content: { type: string; text?: string }[]): void {
    const row = this.db.prepare('SELECT body FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { body: string } | undefined;
    if (!row || content[0]?.text !== row.body || content.filter(part => part.type === 'image').length !== this.imageReferences(session, call).length) throw new Error('Incomplete prepared inbox content');
    this.db.prepare('INSERT INTO read_content VALUES(?,?,?) ON CONFLICT(session_id,call_id) DO UPDATE SET digest=excluded.digest').run(session, call, hash(JSON.stringify(content)));
  }
  humanSources(session: string, turn: number): string[] {
    return (this.db.prepare(`SELECT i.message_id FROM inbox i JOIN ingestions g ON g.seq=i.seq
      WHERE g.session_id=? AND g.turn=? AND i.consumed=1 AND json_extract(i.payload,'$.message.sender_type')='user'`).all(session, turn) as { message_id: string }[]).map(row => row.message_id);
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
        const row = this.db.prepare('SELECT payload FROM inbox WHERE seq=?').get(fragment.seq) as { payload: string };
        const count = (this.db.prepare('SELECT count(*) AS n FROM fragments WHERE seq=?').get(fragment.seq) as { n: number }).n;
        if (count === this.parts(JSON.parse(row.payload) as RelayInput).length) {
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
