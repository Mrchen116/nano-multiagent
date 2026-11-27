import { sourceInstant } from './attention.js';
import { InboxReviews } from './inbox-review.js';
import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { DatabaseSync } from 'node:sqlite';
import type { WorkCheckpoint } from './work-projection.js';
import { createHash, randomUUID } from 'node:crypto';
import { CHAT_BACKGROUND_DELAY_MS, cliWorkerRuntimes, decodeWorkEvent, workRedactedType } from '@nano/product-contracts';
import type { WorkReadyCut, WorkDraft, WorkJournalEvent, RelayInput, WorkRedactionManifest, RuntimeEvent } from '@nano/product-contracts';
import { formatLocalTime, isRasterImageMime, projectChatReplyContext, withInteractionContext } from '@nano/product-contracts';
import { joinThreadTarget, splitThreadTarget } from './tool-references.js';

interface Entry { seq: number; agent_id: string; target: string; payload: string; attention: number; consumed: number }
interface Source { target: string; parent_target?: string; name: string; unread: number; mentions: number; conversation_type: string;
  latest_message_at: string | null; requires_attention?: boolean; delivery?: string; addressed_to?: 'owner'|'agent'|'both' }
export interface InboxRestriction {sessionId:string; inputId?:string; toolCallId?:string; content?:{type:'text';text:string}[]; retainImageIndices?:number[]}

function inputTarget(input: RelayInput): string {
  const root = typeof input.metadata.thread_root_message_id === 'string' && input.metadata.thread_root_message_id
    ? input.metadata.thread_root_message_id : undefined;
  return joinThreadTarget(input.conversation_id, root);
}

interface Fragment { seq: number; part: number }
interface Snapshot { agent: string; target: string; fragments: Fragment[] }
export const MAX_INBOX_READ_ENTRIES = 20;
export const MAX_INBOX_READ_CHARS = 8_000;
export const MAX_INBOX_READ_IMAGES = 4;
const hash = (value: string) => createHash('sha256').update(value).digest('hex');

/** Durable cross-chat inbox; a read does not itself advance consumption. */
export class InboxStore {
  readonly journalId: string;
  readonly reviews: InboxReviews;
  // A restart must re-confirm the main execution before exposing partial readiness.
  private readonly childOnlyRecovery = new Set<string>();
  private readonly db: DatabaseSync;
  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS inbox(seq INTEGER PRIMARY KEY,agent_id TEXT,target TEXT,message_id TEXT,payload TEXT,attention INTEGER,consumed INTEGER DEFAULT 0,UNIQUE(agent_id,message_id));
      CREATE INDEX IF NOT EXISTS inbox_topics ON inbox(agent_id,target) WHERE json_extract(payload,'$.metadata.thread_root_message_id') IS NOT NULL;
      CREATE INDEX IF NOT EXISTS inbox_blocking_target ON inbox(agent_id,target) WHERE consumed=0 AND attention=1;
      CREATE TABLE IF NOT EXISTS imported_parts(seq INTEGER,part INTEGER,body TEXT,PRIMARY KEY(seq,part));
      CREATE TABLE IF NOT EXISTS fragments(seq INTEGER,part INTEGER,PRIMARY KEY(seq,part));
      CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,data TEXT);
      CREATE TABLE IF NOT EXISTS reads(session_id TEXT,call_id TEXT,fragments TEXT,body TEXT,digest TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS query_reads(session_id TEXT,call_id TEXT,fragments TEXT,digest TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS wakes(agent_id TEXT PRIMARY KEY,watermark INTEGER);
      CREATE TABLE IF NOT EXISTS inbox_notifications(session_id TEXT,input_id TEXT,agent_id TEXT,seqs TEXT,summary TEXT,delivered INTEGER DEFAULT 0,PRIMARY KEY(session_id,input_id));
      CREATE TABLE IF NOT EXISTS inbox_schedule(ord INTEGER PRIMARY KEY,seq INTEGER UNIQUE NOT NULL,agent_id TEXT NOT NULL,due_at INTEGER NOT NULL,notified INTEGER NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS inbox_schedule_pending ON inbox_schedule(agent_id,due_at) WHERE notified=0;
      CREATE TABLE IF NOT EXISTS inbox_batch(agent_id TEXT PRIMARY KEY,watermark INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS inbox_checks(session_id TEXT,call_id TEXT,agent_id TEXT,seqs TEXT,body TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS scope_revisions(agent_id TEXT,session_id TEXT,key TEXT,edit TEXT,coverage TEXT,settled INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(agent_id,session_id,key));
      CREATE TABLE IF NOT EXISTS scope_cancelled(agent_id TEXT,message_id TEXT,PRIMARY KEY(agent_id,message_id));
      CREATE TABLE IF NOT EXISTS journal(seq INTEGER PRIMARY KEY,event_id TEXT UNIQUE,event TEXT);
      CREATE INDEX IF NOT EXISTS journal_root_agent ON journal(json_extract(event,'$.root_agent_id'));
      CREATE TABLE IF NOT EXISTS inbox_deleted_agents(agent_id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS inbox_deleted_sessions(session_id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS work_checkpoints(session_id TEXT PRIMARY KEY,root_session_id TEXT NOT NULL,checkpoint TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS work_checkpoint_roots ON work_checkpoints(root_session_id);
      CREATE TABLE IF NOT EXISTS work_open_events(session_id TEXT NOT NULL,seq INTEGER NOT NULL,event TEXT NOT NULL,PRIMARY KEY(session_id,seq));
      CREATE TABLE IF NOT EXISTS work_waiting_facts(session_id TEXT NOT NULL,seq INTEGER NOT NULL,event_id TEXT NOT NULL,event TEXT NOT NULL,PRIMARY KEY(session_id,seq,event_id));
      CREATE TABLE IF NOT EXISTS work_recovery(root_session_id TEXT PRIMARY KEY,pending INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS read_content(session_id TEXT,call_id TEXT,digest TEXT,PRIMARY KEY(session_id,call_id));
      CREATE TABLE IF NOT EXISTS targets(agent_id TEXT,target TEXT,name TEXT,PRIMARY KEY(agent_id,target));
      CREATE TABLE IF NOT EXISTS ingestions(seq INTEGER PRIMARY KEY,session_id TEXT,turn INTEGER);
      CREATE TABLE IF NOT EXISTS receipts(seq INTEGER PRIMARY KEY,status TEXT);
      CREATE TABLE IF NOT EXISTS relay_receipts(id TEXT PRIMARY KEY,agent_id TEXT,message_id TEXT,input TEXT,status TEXT,confirmed INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS relay_controls(agent_id TEXT,message_id TEXT,input TEXT,done INTEGER DEFAULT 0,PRIMARY KEY(agent_id,message_id));
      CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,target TEXT,body TEXT,state TEXT,result TEXT);
      CREATE TABLE IF NOT EXISTS inbox_seen_threads(session_id TEXT NOT NULL,target TEXT NOT NULL,PRIMARY KEY(session_id,target));
    `);
    if (!(this.db.prepare('PRAGMA table_info(relay_receipts)').all() as {name:string}[]).some(c=>c.name==='read_pending'))
      this.db.exec('ALTER TABLE relay_receipts ADD COLUMN read_pending INTEGER NOT NULL DEFAULT 0');
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS relay_receipts_message ON relay_receipts(agent_id,message_id);
      CREATE INDEX IF NOT EXISTS relay_receipts_pending ON relay_receipts(confirmed)
        WHERE confirmed>=0 AND (confirmed=0 OR read_pending=1);
    `);
    this.reviews = new InboxReviews(this.db);
    const publicationColumns = (this.db.prepare('PRAGMA table_info(publications)').all() as {name:string}[]).map(column => column.name);
    if (!publicationColumns.includes('agent_id')) this.db.exec('ALTER TABLE publications ADD COLUMN agent_id TEXT');
    if (!publicationColumns.includes('source')) this.db.exec('ALTER TABLE publications ADD COLUMN source TEXT');
    this.db.prepare('INSERT OR IGNORE INTO metadata VALUES(?,?)').run('journal', randomUUID());
    this.journalId = (this.db.prepare('SELECT value FROM metadata WHERE key=?').get('journal') as { value: string }).value;
  }
  /** Read immutable admission data before deciding whether a transport duplicate is current. */
  input(agentId:string,messageId:string):RelayInput|undefined {
    const row=this.db.prepare('SELECT payload FROM inbox WHERE agent_id=? AND message_id=?').get(agentId,messageId) as {payload:string}|undefined;
    return row?JSON.parse(row.payload) as RelayInput:undefined;
  }
  skipped(input:RelayInput):boolean {
    return !!this.db.prepare('SELECT 1 FROM scope_cancelled WHERE agent_id=? AND message_id=?').get(input.agent_id,input.message.id);
  }
  /** Clear stale `owner_internal` snapshot metadata on unconsumed entries when an external member joins a group. */
  markConversationExternal(agent:string,conversationId:string):void {
    const base=splitThreadTarget(conversationId).base;
    const rows=this.db.prepare('SELECT seq,payload FROM inbox WHERE agent_id=? AND consumed=0 AND (target=? OR target LIKE ?)').all(agent,base,`${base}:%`) as {seq:number;payload:string}[];
    const update=this.db.prepare('UPDATE inbox SET payload=? WHERE seq=?');
    for(const row of rows) {
      const parsed=JSON.parse(row.payload) as RelayInput;
      if(parsed.metadata?.owner_internal===true) {
        parsed.metadata.owner_internal=false;
        update.run(JSON.stringify(parsed),row.seq);
      }
    }
  }
  /** Complete a scope-filtered relay without creating an Inbox item or a delivery badge. */
  skip(input:RelayInput):void {
    this.db.prepare('INSERT OR IGNORE INTO scope_cancelled VALUES(?,?)').run(input.agent_id,input.message.id);
    this.db.prepare('UPDATE inbox SET consumed=1,review_event_delivered=1 WHERE agent_id=? AND message_id=?').run(input.agent_id,input.message.id);
    this.finishControl(input);
    if(!input.metadata.pa_observation) {
      const prior=this.db.prepare('SELECT status FROM relay_receipts WHERE agent_id=? AND message_id=? LIMIT 1').get(input.agent_id,input.message.id);
      this.settleRelay(input,String(prior?.status??'skipped'));
    }
  }
  releaseBatch(agent:string,watermark:number):void {
    this.db.prepare('DELETE FROM inbox_batch WHERE agent_id=? AND watermark=?').run(agent,watermark);
  }
  /** Keep the exact source membership of an Inbox check until native request admission. */
  saveCheck(agent:string,session:string,call:string,body:Record<string,unknown>):void {
    this.db.prepare('INSERT OR REPLACE INTO inbox_checks VALUES(?,?,?,?,?)')
      .run(session,call,agent,JSON.stringify(this.entries(agent).map(row=>row.seq)),JSON.stringify(body));
  }

  /** Retire excluded rows and prepare durable native edits for unsent notices and tool results.
   *
   * Args:
   *   allowed: Current owner-only routing decision for an original message.
   *   render: Model-facing rendering using this Agent's stable conversation references.
   * Returns:
   *   Idempotent edits. The native runtime owns the final already-sent boundary.
   */
  restrict(agent:string,allowed:(input:RelayInput)=>boolean,personal:boolean,timezone:string|undefined,
    render:(snapshot:ReturnType<InboxStore['check']>,notice:boolean)=>string):InboxRestriction[] {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const rows=this.db.prepare('SELECT * FROM inbox WHERE agent_id=?').all(agent) as unknown as Entry[];
      const keep=new Map<number,Entry>();
      for(const row of rows) {
        const input=JSON.parse(row.payload) as RelayInput;
        if(allowed(input)){keep.set(row.seq,row);continue;}
        this.db.prepare('INSERT OR IGNORE INTO scope_cancelled VALUES(?,?)').run(agent,input.message.id);
        this.db.prepare(`UPDATE inbox SET consumed=1,review_event_delivered=1,
          review_state=CASE WHEN review_state IN ('pending','reviewing') THEN 'rejected' ELSE review_state END,
          review_error_code=CASE WHEN review_state IN ('pending','reviewing') THEN 'collaboration_scope_restricted' ELSE review_error_code END,
          review_reason=CASE WHEN review_state IN ('pending','reviewing') THEN 'Retired by collaboration scope' ELSE review_reason END
          WHERE seq=?`).run(row.seq);
        this.finishControl(input);
      }
      const save=(key:string,edit:InboxRestriction,coverage:unknown)=>this.db.prepare(
        'INSERT OR IGNORE INTO scope_revisions(agent_id,session_id,key,edit,coverage) VALUES(?,?,?,?,?)')
        .run(agent,edit.sessionId,key,JSON.stringify(edit),JSON.stringify(coverage));
      for(const notice of [true,false]) {
        const table=notice?'inbox_notifications':'inbox_checks', id=notice?'input_id':'call_id';
        const snapshots=this.db.prepare(`SELECT session_id,${id} id,seqs FROM ${table} WHERE agent_id=?`).all(agent) as {session_id:string;id:string;seqs:string}[];
        for(const item of snapshots) {
          const seqs=JSON.parse(item.seqs) as number[];
          const visible=seqs.flatMap(seq=>keep.has(seq)?[keep.get(seq)!]:[]);
          if(visible.length===seqs.length)continue;
          const text=render(this.check(agent,personal,timezone,visible),notice);
          const edit:InboxRestriction={sessionId:item.session_id,...(notice?{inputId:item.id}:{toolCallId:item.id}),
            ...(visible.length?{content:[{type:'text',text}]}:{})};
          save((notice?'input:':'tool:')+item.id,edit,visible.map(row=>row.seq));
        }
      }
      const pages=this.db.prepare(`SELECT * FROM reads WHERE EXISTS(SELECT 1 FROM json_each(reads.fragments) part
        JOIN inbox i ON i.seq=json_extract(part.value,'$.seq') WHERE i.agent_id=?)`).all(agent) as unknown as {session_id:string;call_id:string;fragments:string;body:string}[];
      for(const page of pages) {
        const original=JSON.parse(page.fragments) as Fragment[];
        const fragments=original.filter(fragment=>keep.has(fragment.seq));
        if(fragments.length===original.length)continue;
        const body=JSON.parse(page.body) as {messages:{content:{content_type?:string}[]}[];next_cursor?:string};
        let imageIndex=0;
        const retainImageIndices:number[]=[];
        for(const [index,message] of body.messages.entries())for(const part of message.content) {
          if(!isRasterImageMime(part.content_type))continue;
          if(keep.has(original[index]!.seq))retainImageIndices.push(imageIndex);
          imageIndex++;
        }
        const visible=fragments.length?{...body,messages:body.messages.filter((_,index)=>keep.has(original[index]!.seq))}:{messages:[]};
        const text=JSON.stringify(visible);
        save('tool:'+page.call_id,{sessionId:page.session_id,toolCallId:page.call_id,...(fragments.length?{content:[{type:'text',text}]}:{}),
          ...(retainImageIndices.length?{retainImageIndices}:{})},fragments);
      }
      this.db.prepare(`DELETE FROM query_reads WHERE EXISTS(SELECT 1 FROM json_each(query_reads.fragments) part
        JOIN inbox i ON i.seq=json_extract(part.value,'$.seq')
        JOIN scope_cancelled c ON c.agent_id=i.agent_id AND c.message_id=i.message_id
        WHERE i.agent_id=?)`).run(agent);
      this.db.exec('COMMIT');
    } catch(error){this.db.exec('ROLLBACK');throw error;}
    return this.db.prepare('SELECT edit FROM scope_revisions WHERE agent_id=?').all(agent).map(row=>JSON.parse(String(row.edit)) as InboxRestriction);
  }
  /** Reconcile native scope edits with receipt coverage after the provider handoff is known. */
  confirmRestricted(agent:string,withdrawn:readonly {sessionId:string;inputId?:string;toolCallId?:string}[]):void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      for(const {sessionId,inputId,toolCallId} of withdrawn) {
        const key=inputId?'input:'+inputId:'tool:'+toolCallId;
        const row=this.db.prepare('SELECT edit,coverage FROM scope_revisions WHERE agent_id=? AND session_id=? AND key=? AND settled=0')
          .get(agent,sessionId,key) as {edit:string;coverage:string}|undefined;
        if(!row)continue;
        const edit=JSON.parse(row.edit) as InboxRestriction;
        const text=edit.content?.[0]?.text;
        if(inputId)this.db.prepare('UPDATE inbox_notifications SET seqs=?,summary=? WHERE session_id=? AND input_id=?')
          .run(row.coverage,text??'',sessionId,inputId);
        else if(toolCallId){
          const body=text??'{"messages":[]}';
          this.db.prepare('UPDATE reads SET fragments=?,body=?,digest=? WHERE session_id=? AND call_id=?')
            .run(row.coverage,body,hash(body),sessionId,toolCallId);
          const prior=this.db.prepare('SELECT digest FROM read_content WHERE session_id=? AND call_id=?').get(sessionId,toolCallId);
          if(prior && String(prior.digest).startsWith('[') && edit.retainImageIndices?.length){
            const blocks=JSON.parse(String(prior.digest)) as string[];
            const retained=[hash(JSON.stringify({type:'text',text:body})),...edit.retainImageIndices.map(index=>blocks[index+1])];
            this.db.prepare('UPDATE read_content SET digest=? WHERE session_id=? AND call_id=?').run(JSON.stringify(retained),sessionId,toolCallId);
          }else this.db.prepare('DELETE FROM read_content WHERE session_id=? AND call_id=?').run(sessionId,toolCallId);
        }
      }
      this.db.prepare('UPDATE scope_revisions SET settled=1 WHERE agent_id=?').run(agent);
      // An already handed-off notice or read can acquire its delivery evidence after the setting was saved.
      this.db.prepare(`UPDATE relay_receipts SET status='skipped',confirmed=0
        WHERE agent_id=? AND status='accepted' AND message_id IN
        (SELECT i.message_id FROM inbox i JOIN scope_cancelled c USING(agent_id,message_id) WHERE i.agent_id=?
         AND NOT EXISTS(SELECT 1 FROM inbox_notifications n,json_each(n.seqs) s WHERE n.agent_id=i.agent_id AND s.value=i.seq)
         AND NOT EXISTS(SELECT 1 FROM reads r,json_each(r.fragments) f WHERE json_extract(f.value,'$.seq')=i.seq))`).run(agent,agent);
      this.db.exec('COMMIT');
    }catch(error){this.db.exec('ROLLBACK');throw error;}
  }
  private restrictedRead(session:string,call:string):string|undefined {
    const row=this.db.prepare('SELECT edit FROM scope_revisions WHERE session_id=? AND key=?').get(session,'tool:'+call);
    if(row)return (JSON.parse(String(row.edit)) as InboxRestriction).content?.[0]?.text??'{"messages":[]}';
  }
  /** Retire pending execution without deleting raw inbox, journal, receipts or ACK cursors. */
  cancelAgent(agentId: string, sessionIds: string[] = []): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('UPDATE inbox SET consumed=1,review_event_delivered=1 WHERE agent_id=?').run(agentId);
      this.admitWake(agentId,this.watermark(agentId));
      this.db.prepare('DELETE FROM inbox_batch WHERE agent_id=?').run(agentId);
      this.db.prepare('UPDATE relay_controls SET done=1 WHERE agent_id=?').run(agentId);
      this.db.prepare("UPDATE publications SET state=CASE WHEN state='sending' THEN 'unknown' ELSE 'cancelled_by_disable' END WHERE agent_id=? AND state IN ('prepared','sending')").run(agentId);
      for(const session of sessionIds)this.db.prepare("UPDATE publications SET state=CASE WHEN state='sending' THEN 'unknown' ELSE 'cancelled_by_disable' END WHERE agent_id IS NULL AND substr(id,1,?)=? AND state IN ('prepared','sending')").run(session.length+1,`${session}:`);
      this.db.exec('COMMIT');
    } catch(error) {this.db.exec('ROLLBACK');throw error;}
  }
  /** Freeze the stopped Agent's journal contribution and return its exact positions. */
  deletionWork(agentId: string): WorkRedactionManifest {
    this.db.prepare('INSERT OR IGNORE INTO inbox_deleted_agents VALUES(?)').run(agentId);
    const entries = this.db.prepare("SELECT seq,event_id FROM journal WHERE json_extract(event,'$.root_agent_id')=? ORDER BY seq").all(agentId) as WorkRedactionManifest['entries'];
    return { journal_id: this.journalId, entries };
  }

  /** Return native Work identities observed before the target journal is redacted. */
  deletionSessionIds(agentId: string): string[] {
    const placeholders = cliWorkerRuntimes.map(() => '?').join(',');
    const rows = this.db.prepare(`SELECT json_extract(event,'$.session_id') id FROM journal
      WHERE json_extract(event,'$.root_agent_id')=? AND json_extract(event,'$.type')!=?
      UNION SELECT json_extract(event,'$.payload.child_session_id') id FROM journal
      WHERE json_extract(event,'$.root_agent_id')=? AND json_extract(event,'$.type')='session_linked'
      EXCEPT SELECT json_extract(event,'$.session_id') id FROM journal
      WHERE json_extract(event,'$.root_agent_id')=? AND json_extract(event,'$.type')='worker_state'
        AND json_extract(event,'$.payload.runtime') IN (${placeholders})`)
      .all(agentId, workRedactedType, agentId, agentId, ...cliWorkerRuntimes);
    return rows.flatMap(({ id }) => typeof id === 'string' && id ? [id] : []);
  }

  /** Remove private Inbox data after the center has recorded every redaction receipt.
   * Args:
   *   agentId: Permanently retired Agent whose journal contribution was frozen.
   *   sessionIds: Proven execution identities owned by this Agent.
   */
  purgeAgent(agentId: string, sessionIds: readonly string[]): void {
    if (!this.deletedAgent(agentId)) throw new Error('Agent journal was not frozen for deletion');
    this.db.exec('BEGIN IMMEDIATE');
    try {
      // Preserve sequence high water even when the removed rows were the newest input.
      this.db.prepare(`INSERT INTO metadata(key,value) VALUES('inbox_sequence',max(
        coalesce((SELECT max(seq) FROM inbox),0),coalesce((SELECT max(watermark) FROM wakes),0),
        coalesce((SELECT max(ord) FROM inbox_schedule),0),coalesce((SELECT max(watermark) FROM inbox_batch),0)))
        ON CONFLICT(key) DO UPDATE SET value=max(CAST(metadata.value AS INTEGER),CAST(excluded.value AS INTEGER))`).run();
      const ownedRead = `EXISTS(SELECT 1 FROM json_each(reads.fragments) part JOIN inbox i ON i.seq=json_extract(part.value,'$.seq') WHERE i.agent_id=?)`;
      const ownedQueryRead = `EXISTS(SELECT 1 FROM json_each(query_reads.fragments) part JOIN inbox i ON i.seq=json_extract(part.value,'$.seq') WHERE i.agent_id=?)`;
      this.db.prepare(`DELETE FROM read_content WHERE (session_id,call_id) IN (SELECT session_id,call_id FROM reads WHERE ${ownedRead})`).run(agentId);
      this.db.prepare(`DELETE FROM reads WHERE ${ownedRead}`).run(agentId);
      this.db.prepare(`DELETE FROM query_reads WHERE ${ownedQueryRead}`).run(agentId);
      for (const table of ['imported_parts', 'fragments', 'ingestions', 'receipts']) {
        this.db.prepare(`DELETE FROM ${table} WHERE seq IN (SELECT seq FROM inbox WHERE agent_id=?)`).run(agentId);
      }
      this.db.prepare("DELETE FROM snapshots WHERE json_extract(data,'$.agent')=?").run(agentId);
      for (const table of ['inbox', 'targets', 'wakes', 'inbox_schedule', 'inbox_batch', 'inbox_checks', 'scope_revisions', 'scope_cancelled', 'inbox_notifications', 'relay_receipts', 'relay_controls', 'publications']) {
        this.db.prepare(`DELETE FROM ${table} WHERE agent_id=?`).run(agentId);
      }
      for (const sessionId of sessionIds) {
        this.db.prepare('INSERT OR IGNORE INTO inbox_deleted_sessions VALUES(?)').run(sessionId);
        for (const table of ['reads', 'query_reads', 'read_content', 'ingestions', 'work_waiting_facts', 'inbox_seen_threads']) this.db.prepare(`DELETE FROM ${table} WHERE session_id=?`).run(sessionId);
        this.db.prepare('DELETE FROM work_open_events WHERE session_id IN (SELECT session_id FROM work_checkpoints WHERE session_id=? OR root_session_id=?)').run(sessionId, sessionId);
        this.db.prepare('DELETE FROM work_checkpoints WHERE session_id=? OR root_session_id=?').run(sessionId, sessionId);
        this.db.prepare('DELETE FROM work_recovery WHERE root_session_id=?').run(sessionId);
        this.db.prepare('DELETE FROM publications WHERE agent_id IS NULL AND substr(id,1,?)=?').run(sessionId.length + 1, `${sessionId}:`);
      }
      this.db.prepare(`UPDATE journal SET event=json_object('seq',seq,'event_id',event_id,'root_agent_id',?,
        'session_id','redacted','type',?,'payload',json('{}')) WHERE json_extract(event,'$.root_agent_id')=?
        AND json_extract(event,'$.type')!=?`).run(agentId, workRedactedType, agentId, workRedactedType);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }

  private deletedAgent(agentId: string): boolean {
    return !!this.db.prepare('SELECT 1 FROM inbox_deleted_agents WHERE agent_id=?').get(agentId);
  }

  private deletedSession(sessionId: string): boolean {
    return !!this.db.prepare('SELECT 1 FROM inbox_deleted_sessions WHERE session_id=?').get(sessionId);
  }
  /** Persist an input and its first background deadline together.
   * Args:
   *   now: Node reception time in UTC milliseconds, independent of message time.
   */
  receive(input: RelayInput, attention: boolean, now = Date.now(), high = attention): void {
    if (this.deletedAgent(input.agent_id) || this.skipped(input)) return;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      // Source removal must not reuse an accepted or in-flight notification identity.
      this.db.prepare(`INSERT OR IGNORE INTO inbox(seq,agent_id,target,message_id,payload,attention) VALUES((SELECT max(
        coalesce((SELECT max(seq) FROM inbox),0),coalesce((SELECT max(watermark) FROM wakes),0),
        coalesce((SELECT max(ord) FROM inbox_schedule),0),coalesce((SELECT max(watermark) FROM inbox_batch),0),
        coalesce((SELECT CAST(value AS INTEGER) FROM metadata WHERE key='inbox_sequence'),0))+1),?,?,?,?,?)`)
        .run(input.agent_id, inputTarget(input), input.message.id, JSON.stringify(input), Number(attention));
      this.reviews.initialize(input);
      this.schedule(input, high, now);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Atomically accept an input, its receipt obligation, and any control intent.
   * Args:
   *   input: Authenticated relay envelope from the current node connection.
   *   attention: Whether this already classified input needs a model notification.
   *   control: Keep commands out of the model Inbox and recover them separately.
   */
  acceptRelay(input: RelayInput, attention: boolean, control = false, high = attention): void {
    if (this.deletedAgent(input.agent_id) || this.skipped(input)) return;
    const identity = (value: RelayInput) => sortedJsonAscii({agent:value.agent_id,target:value.conversation_id,message:value.message});
    const coreIdentity = (value: RelayInput) => sortedJsonAscii({
      agent: value.agent_id, target: value.conversation_id, id: value.message.id,
      sender_type: value.message.sender_type, content: value.message.content,
    });
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const previous = this.db.prepare('SELECT payload FROM inbox WHERE agent_id=? AND message_id=?').get(input.agent_id,input.message.id) as {payload:string}|undefined;
      if (previous) {
        const prevInput = JSON.parse(previous.payload) as RelayInput;
        if (prevInput.metadata.pa_observation === true && !input.metadata.pa_observation) {
          if (coreIdentity(prevInput) !== coreIdentity(input)) throw new Error('Relay input identity conflict');
          const mergedMetadata = prevInput.metadata.personal_unclassified === true
            ? { ...prevInput.metadata, ...input.metadata }
            : { ...input.metadata, ...prevInput.metadata };
          const merged: RelayInput = { ...input, metadata: mergedMetadata };
          delete merged.metadata.pa_observation;
          if (prevInput.metadata.personal_unclassified !== true) delete merged.metadata.personal_unclassified;
          const keepConsumed = prevInput.metadata.personal_unclassified !== true && prevInput.metadata.personal_is_owner !== true;
          this.db.prepare('UPDATE inbox SET target=?,payload=?,consumed=CASE WHEN ? THEN 1 ELSE consumed END WHERE agent_id=? AND message_id=?')
            .run(inputTarget(merged), JSON.stringify(merged), Number(control && !keepConsumed), input.agent_id, input.message.id);
        } else if (!prevInput.metadata.pa_observation && input.metadata.pa_observation === true) {
          if (coreIdentity(prevInput) !== coreIdentity(input)) throw new Error('Relay input identity conflict');
        } else if (identity(prevInput) !== identity(input)) {
          throw new Error('Relay input identity conflict');
        }
      }
      const receipt = this.db.prepare('SELECT input FROM relay_receipts WHERE id=?').get(input.relay_task_id) as {input:string}|undefined;
      if (receipt && identity(JSON.parse(receipt.input)) !== identity(input)) throw new Error('Relay receipt identity conflict');
      if (!previous) {
        this.db.prepare(`INSERT INTO inbox(seq,agent_id,target,message_id,payload,attention,consumed) VALUES((SELECT max(
          coalesce((SELECT max(seq) FROM inbox),0),coalesce((SELECT max(watermark) FROM wakes),0),
          coalesce((SELECT max(ord) FROM inbox_schedule),0),coalesce((SELECT max(watermark) FROM inbox_batch),0),
          coalesce((SELECT CAST(value AS INTEGER) FROM metadata WHERE key='inbox_sequence'),0))+1),?,?,?,?,?,?)`)
          .run(input.agent_id,inputTarget(input),input.message.id,JSON.stringify(input),Number(attention),Number(control));

      }
      this.reviews.initialize(input);
      if(!control)this.schedule(input,high,Date.now());
      this.db.prepare(`INSERT OR IGNORE INTO relay_receipts(id,agent_id,message_id,input,status,read_pending) VALUES(?,?,?,?,
        coalesce((SELECT status FROM relay_receipts WHERE agent_id=? AND message_id=? LIMIT 1),'accepted'),
        coalesce((SELECT min(read_pending,1) FROM relay_receipts WHERE agent_id=? AND message_id=? LIMIT 1),0))`)
        .run(input.relay_task_id,input.agent_id,input.message.id,JSON.stringify(input),input.agent_id,input.message.id,input.agent_id,input.message.id);
      // An identical redelivery requests the last durable receipt again.
      this.db.prepare('UPDATE relay_receipts SET confirmed=0 WHERE id=?').run(input.relay_task_id);
      if (control) this.db.prepare('INSERT OR IGNORE INTO relay_controls(agent_id,message_id,input) VALUES(?,?,?)').run(input.agent_id,input.message.id,JSON.stringify(input));
      this.db.exec('COMMIT');
    } catch(error) {this.db.exec('ROLLBACK');throw error;}
  }
  /** Return bounded receipt obligations without depending on runtime availability. */
  pendingRelays(channel?: 'im' | 'feishu', deferred: readonly string[] = []): {input:RelayInput;status:string}[] {
    return (this.db.prepare(`
      SELECT input, CASE WHEN confirmed=0 THEN status ELSE 'read' END AS status
      FROM relay_receipts WHERE confirmed>=0 AND (confirmed=0 OR read_pending=1)
        AND (? IS NULL OR (id LIKE 'external:%')=?)
        AND id NOT IN (SELECT value FROM json_each(?))
      ORDER BY confirmed, rowid LIMIT 100
    `).all(channel ?? null, Number(channel === 'feishu'), JSON.stringify(deferred)) as {input:string;status:string}[])
      .map(row=>({input:JSON.parse(row.input) as RelayInput,status:row.status}));
  }
  /** Derive read badges from durable ingestions, outside the Inbox read transaction.
   * Args:
   *   calls: Committed Inbox tool calls to project, or undefined for restart catch-up.
   */
  projectReadReceipts(calls?: { sessionId: string; callId: string }[]): void {
    const scope = calls ? `
      FROM json_each(?) call
      JOIN (SELECT session_id, call_id, fragments FROM reads UNION ALL SELECT session_id, call_id, fragments FROM query_reads) r
        ON r.session_id=json_extract(call.value,'$.sessionId') AND r.call_id=json_extract(call.value,'$.callId')
      JOIN json_each(r.fragments) part
      JOIN ingestions g ON g.seq=json_extract(part.value,'$.seq')
    ` : 'FROM ingestions g';
    this.db.prepare(`
      UPDATE relay_receipts SET read_pending=1
      WHERE read_pending=0 AND confirmed>=0 AND status!='skipped' AND json_extract(input,'$.metadata.agent_receipt')=1
        AND (agent_id,message_id) IN (SELECT i.agent_id,i.message_id ${scope} JOIN inbox i ON i.seq=g.seq)
    `).run(...(calls ? [JSON.stringify(calls)] : []));
  }
  /** Identify pre-upgrade unread messages requiring a new, attributable model notification. */
  legacyReceiptWake(agentId: string): number | undefined {
    const row = this.db.prepare('SELECT value FROM metadata WHERE key=?').get(`receipt-recovery:${agentId}`) as {value:string}|undefined;
    return row ? Number(row.value) : undefined;
  }
  private confirmLegacyReceiptWake(agentId: string): void {
    this.db.prepare('DELETE FROM metadata WHERE key=?').run(`receipt-recovery:${agentId}`);
  }
  /** Freeze exactly the unread inputs represented by one native Inbox notification. */
  notification(agentId: string, sessionId: string, inputId: string, render: (snapshot: ReturnType<InboxStore['check']>) => string, personal = false, timezone?:string, watermark?:number): string {
    const prior = this.db.prepare('SELECT summary FROM inbox_notifications WHERE session_id=? AND input_id=?').get(sessionId,inputId) as {summary:string}|undefined;
    if (prior) return prior.summary;
    const seqs = this.entries(agentId).map(row => row.seq);
    const summary = render(this.check(agentId, personal, timezone));
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('INSERT INTO inbox_notifications(session_id,input_id,agent_id,seqs,summary) VALUES(?,?,?,?,?)')
        .run(sessionId,inputId,agentId,JSON.stringify(seqs),summary);
      if(watermark!==undefined)this.db.prepare('INSERT OR REPLACE INTO inbox_batch VALUES(?,?)').run(agentId,watermark);
      this.db.exec('COMMIT');
    } catch(error){this.db.exec('ROLLBACK');throw error;}
    return summary;
  }
  /** Discard a snapshot only after the runtime proves it was not admitted. */
  discardNotification(sessionId: string, inputId: string): void {
    this.db.prepare('DELETE FROM inbox_notifications WHERE session_id=? AND input_id=? AND delivered=0').run(sessionId,inputId);
  }
  /** Project durable model-response evidence onto the notification's frozen inputs. */
  deliverNotifications(agentId: string, sessionId: string, inputIds: string[]): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      for (const inputId of inputIds) {
        if(this.db.prepare("SELECT 1 FROM scope_revisions WHERE agent_id=? AND session_id=? AND key=? AND settled=0")
          .get(agentId,sessionId,'input:'+inputId))throw new Error('Inbox receipt is awaiting native scope reconciliation');
        const notice = this.db.prepare('SELECT seqs FROM inbox_notifications WHERE agent_id=? AND session_id=? AND input_id=? AND delivered=0')
          .get(agentId,sessionId,inputId) as {seqs:string}|undefined;
        if (!notice) continue;
        this.db.prepare(`UPDATE relay_receipts SET status='sent',confirmed=0 WHERE agent_id=? AND status='accepted'
          AND message_id IN (SELECT message_id FROM inbox WHERE agent_id=? AND seq IN (SELECT value FROM json_each(?)))`)
          .run(agentId,agentId,notice.seqs);
        this.db.prepare('UPDATE inbox_notifications SET delivered=1 WHERE session_id=? AND input_id=?').run(sessionId,inputId);

      }
      const legacy = this.legacyReceiptWake(agentId);
      if (legacy !== undefined && !this.db.prepare(`SELECT 1 FROM inbox i JOIN relay_receipts r ON r.agent_id=i.agent_id AND r.message_id=i.message_id
        WHERE i.agent_id=? AND i.seq<=? AND i.consumed=0 AND r.status='accepted' LIMIT 1`).get(agentId,legacy)) this.confirmLegacyReceiptWake(agentId);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Enqueue a native session's receipt without adding the message to the Global Inbox. */
  queueNativeReceipt(input: RelayInput, read: boolean): void {
    this.db.prepare('INSERT OR IGNORE INTO relay_receipts(id,agent_id,message_id,input,status,read_pending) VALUES(?,?,?,?,?,?)')
      .run(input.relay_task_id,input.agent_id,input.message.id,JSON.stringify(input),'sent',Number(read));
    if (read) this.db.prepare('UPDATE relay_receipts SET read_pending=1 WHERE id=? AND read_pending=0').run(input.relay_task_id);
  }
  /** Advance all relay identities for a message without regressing a terminal receipt. */
  settleRelay(input: RelayInput, status: string): void {
    if (this.deletedAgent(input.agent_id)) return;
    this.db.prepare('INSERT OR IGNORE INTO relay_receipts(id,agent_id,message_id,input,status) VALUES(?,?,?,?,?)').run(input.relay_task_id,input.agent_id,input.message.id,JSON.stringify(input),status);
    this.db.prepare("UPDATE relay_receipts SET status=?,confirmed=0 WHERE agent_id=? AND message_id=? AND status NOT IN ('completed','failed','skipped') AND (? != 'accepted' OR status='accepted')")
      .run(status,input.agent_id,input.message.id,status);
  }
  /** Settle any recorded Web relay receipts for a message settled asynchronously in batch review. */
  settleMessageRelays(agentId: string, messageId: string, status: string): void {
    if (this.deletedAgent(agentId)) return;
    this.db.prepare("UPDATE relay_receipts SET status=?,confirmed=0 WHERE agent_id=? AND message_id=? AND status NOT IN ('completed','failed','skipped')")
      .run(status, agentId, messageId);
  }
  /** Close a revoked obligation without recording a remote acceptance. */
  rejectRelay(id:string):void {this.db.prepare('UPDATE relay_receipts SET confirmed=-1 WHERE id=?').run(id);}
  confirmRelay(id: string, status: string): void {
    if (status === 'read') this.db.prepare('UPDATE relay_receipts SET read_pending=2 WHERE id=?').run(id);
    else this.db.prepare('UPDATE relay_receipts SET confirmed=1 WHERE id=? AND status=?').run(id,status);
  }
  pendingControls(): RelayInput[] {return (this.db.prepare('SELECT input FROM relay_controls WHERE done=0 ORDER BY rowid').all() as {input:string}[]).map(row=>JSON.parse(row.input) as RelayInput);}
  /** Return a source-authorized ordinary PA message to the Inbox after command classification. */
  demoteControl(input:RelayInput):void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('UPDATE inbox SET consumed=0 WHERE agent_id=? AND message_id=?').run(input.agent_id,input.message.id);
      this.finishControl(input);this.db.exec('COMMIT');
    } catch(error) {this.db.exec('ROLLBACK');throw error;}
  }
  finishControl(input:RelayInput):void {this.db.prepare('UPDATE relay_controls SET done=1 WHERE agent_id=? AND message_id=?').run(input.agent_id,input.message.id);}
  /** Record that an authenticated owner command was executed so dual delivery neither repeats it nor leaves an unread wake. */
  markControlHandled(input: RelayInput): void {
    delete input.metadata.personal_unclassified;
    input.metadata.personal_control_handled = true;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const row = this.db.prepare('SELECT seq,payload FROM inbox WHERE agent_id=? AND message_id=?').get(input.agent_id, input.message.id) as { seq: number; payload: string } | undefined;
      if (row) {
        const existing = JSON.parse(row.payload) as RelayInput;
        const merged: RelayInput = !existing.metadata.pa_observation && input.metadata.pa_observation === true
          ? { ...existing, metadata: { ...existing.metadata, ...input.metadata } }
          : input;
        delete merged.metadata.personal_unclassified;
        if (!existing.metadata.pa_observation) delete merged.metadata.pa_observation;
        merged.metadata.personal_control_handled = true;
        this.db.prepare('UPDATE inbox SET target=?,payload=?,consumed=1 WHERE seq=?').run(inputTarget(merged), JSON.stringify(merged), row.seq);
        this.db.prepare('DELETE FROM inbox_schedule WHERE seq=?').run(row.seq);
      }
      this.db.prepare('UPDATE relay_controls SET done=1 WHERE agent_id=? AND message_id=?').run(input.agent_id, input.message.id);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  private schedule(input:RelayInput, high:boolean, now:number):void {
    this.scheduleAt(input, high ? 0 : now + CHAT_BACKGROUND_DELAY_MS);
  }
  private scheduleAt(input:RelayInput, dueAt:number):void {
    if(input.metadata.personal_unclassified || input.metadata.task_context || input.message.system_notice?.kind==='task_graph' || input.metadata.context_only)return;
    // Admission can finish out of arrival order (particularly after a review retry).
    this.db.prepare(`INSERT OR IGNORE INTO inbox_schedule(ord,seq,agent_id,due_at)
      SELECT max(seq,coalesce((SELECT max(ord) FROM inbox_schedule),0)+1,coalesce((SELECT max(watermark) FROM wakes),0)+1),seq,agent_id,?
      FROM inbox WHERE agent_id=? AND message_id=? AND consumed=0 AND review_state='admitted'`)
      .run(dueAt,input.agent_id,input.message.id);
  }
  /** Persist authenticated PA facts on a pending input while preserving any non-observation relay envelope. */
  stagePersonal(input: RelayInput, attention: boolean, dueAt: number | null): RelayInput {
    delete input.metadata.personal_unclassified;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const existingRow = this.db.prepare('SELECT payload FROM inbox WHERE agent_id=? AND message_id=?').get(input.agent_id, input.message.id) as {payload:string}|undefined;
      let merged = input;
      if (existingRow) {
        const existing = JSON.parse(existingRow.payload) as RelayInput;
        if (!existing.metadata.pa_observation && input.metadata.pa_observation === true) {
          merged = { ...existing, metadata: { ...existing.metadata, ...input.metadata } };
          delete merged.metadata.pa_observation;
          delete merged.metadata.personal_unclassified;
        }
      } else {
        this.db.prepare(`INSERT INTO inbox(seq,agent_id,target,message_id,payload,attention) VALUES((SELECT max(
          coalesce((SELECT max(seq) FROM inbox),0),coalesce((SELECT max(watermark) FROM wakes),0),
          coalesce((SELECT max(ord) FROM inbox_schedule),0),coalesce((SELECT max(watermark) FROM inbox_batch),0),
          coalesce((SELECT CAST(value AS INTEGER) FROM metadata WHERE key='inbox_sequence'),0))+1),?,?,?,?,?)`)
          .run(input.agent_id, inputTarget(input), input.message.id, JSON.stringify(input), Number(attention));
        this.reviews.initialize({ ...input, metadata: { ...input.metadata, personal_unclassified: true } });
      }
      this.db.prepare('UPDATE inbox SET target=?,payload=?,attention=?,review_due_at=coalesce(review_due_at,?) WHERE agent_id=? AND message_id=?')
        .run(inputTarget(merged), JSON.stringify(merged), Number(attention), dueAt, merged.agent_id, merged.message.id);
      this.db.exec('COMMIT');
      return merged;
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Save authoritative PA provenance and arm its deadline after the review admits the input. */
  classify(input: RelayInput, attention: boolean, high=attention, dueAt?: number | null): void {
    delete input.metadata.personal_unclassified;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const existingRow = this.db.prepare('SELECT payload FROM inbox WHERE agent_id=? AND message_id=?').get(input.agent_id, input.message.id) as {payload:string}|undefined;
      let merged = input;
      if (existingRow) {
        const existing = JSON.parse(existingRow.payload) as RelayInput;
        if (!existing.metadata.pa_observation && input.metadata.pa_observation === true) {
          merged = { ...existing, metadata: { ...existing.metadata, ...input.metadata } };
          delete merged.metadata.pa_observation;
          delete merged.metadata.personal_unclassified;
        }
      }
      this.db.prepare('UPDATE inbox SET target=?,payload=?,attention=? WHERE agent_id=? AND message_id=?').run(inputTarget(merged),JSON.stringify(merged),Number(attention),merged.agent_id,merged.message.id);
      this.scheduleAt(merged, high ? 0 : (dueAt ?? Date.now() + CHAT_BACKGROUND_DELAY_MS));
      this.db.exec('COMMIT');
    } catch(error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Find the oldest fixed deadline and the current batch boundary for this Agent. */
  background(agent:string):{dueAt:number;watermark:number;pending:boolean;unread:boolean}|undefined {
    const pending=this.db.prepare('SELECT watermark FROM inbox_batch WHERE agent_id=?').get(agent) as {watermark:number}|undefined;
    const row=this.db.prepare(`SELECT min(s.due_at) dueAt,max(s.ord) watermark FROM inbox_schedule s
      JOIN inbox i ON s.seq=i.seq WHERE s.agent_id=? AND s.notified=0 AND i.consumed=0`).get(agent) as {dueAt:number|null;watermark:number};
    if(pending)return {dueAt:0,watermark:pending.watermark,pending:true,unread:row.dueAt!==null};
    if(row.dueAt!==null)return {dueAt:row.dueAt,watermark:row.watermark,pending:false,unread:true};
  }
  /** Reconcile every unread source, including messages still pending or failed in review. */
  revokeUnavailableSources(agent: string, allowed: ReadonlySet<string>): void {
    const targets = this.db.prepare('SELECT DISTINCT target FROM inbox WHERE agent_id=? AND consumed=0').all(agent);
    const revoked = new Set<string>();
    for (const {target} of targets) {
      const base = splitThreadTarget(String(target)).base;
      if (!allowed.has(base) && !revoked.has(base)) { revoked.add(base); this.revokeSource(agent, base); }
    }
  }
  /** Remove a revoked source (main timeline and all its threads) from future reads and frozen page caches. */
  revokeSource(agent: string, target: string): void {
    const base = splitThreadTarget(target).base;
    const prefix = `${base}:%`;
    // Saved model projections changed shape; fragment ownership is stable across versions.
    this.db.prepare(`DELETE FROM reads WHERE EXISTS (
      SELECT 1 FROM json_each(reads.fragments) part JOIN inbox i ON i.seq=json_extract(part.value,'$.seq')
      WHERE i.agent_id=? AND (i.target=? OR i.target LIKE ?))`).run(agent,base,prefix);
    this.db.prepare(`DELETE FROM query_reads WHERE EXISTS (
      SELECT 1 FROM json_each(query_reads.fragments) part JOIN inbox i ON i.seq=json_extract(part.value,'$.seq')
      WHERE i.agent_id=? AND (i.target=? OR i.target LIKE ?))`).run(agent,base,prefix);
    const rows = this.db.prepare('SELECT seq FROM inbox WHERE agent_id=? AND (target=? OR target LIKE ?)').all(agent,base,prefix) as {seq:number}[];
    for(const {seq} of rows) {
      this.db.prepare('DELETE FROM imported_parts WHERE seq=?').run(seq);
      this.db.prepare('DELETE FROM fragments WHERE seq=?').run(seq);
    }
    this.db.prepare(`INSERT INTO metadata(key,value) SELECT 'inbox_sequence',max(seq) FROM inbox WHERE agent_id=? AND (target=? OR target LIKE ?) HAVING count(*)>0
      ON CONFLICT(key) DO UPDATE SET value=max(CAST(metadata.value AS INTEGER),CAST(excluded.value AS INTEGER))`).run(agent,base,prefix);
    this.db.prepare('DELETE FROM inbox_schedule WHERE seq IN (SELECT seq FROM inbox WHERE agent_id=? AND (target=? OR target LIKE ?))').run(agent,base,prefix);
    this.db.prepare('DELETE FROM inbox WHERE agent_id=? AND (target=? OR target LIKE ?)').run(agent,base,prefix);
    this.db.prepare("DELETE FROM snapshots WHERE json_extract(data,'$.agent')=? AND (json_extract(data,'$.target')=? OR json_extract(data,'$.target') LIKE ?)").run(agent,base,prefix);
    this.db.prepare('DELETE FROM targets WHERE agent_id=? AND (target=? OR target LIKE ?)').run(agent,base,prefix);
  }
  /** Reset per-session thread context memory (e.g., after compaction) so the next read re-attaches thread_context. */
  clearSeenThreads(sessionId: string): void {
    this.db.prepare('DELETE FROM inbox_seen_threads WHERE session_id=?').run(sessionId);
  }
  private entries(agent: string, target?: string): Entry[] {
    return this.db.prepare("SELECT * FROM inbox WHERE agent_id=? AND consumed=0 AND review_state='admitted' AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0 AND (? IS NULL OR target=?) ORDER BY seq").all(agent, target ?? null, target ?? null) as unknown as Entry[];
  }
  /** Count unread admitted conversational Inbox entries (excluding passive task_graph system notices) for sync deltas. */
  unreadEntryCount(agent: string): number {
    return Number((this.db.prepare("SELECT count(*) AS n FROM inbox WHERE agent_id=? AND consumed=0 AND review_state='admitted' AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0 AND coalesce(json_extract(payload,'$.message.system_notice.kind'),'')!='task_graph'").get(agent) as { n: number } | undefined)?.n ?? 0);
  }
  /** Select full original Task notices for direct native context, not a duplicate private snapshot. */
  prepareSystemContext(agentId:string,sessionId:string):{inputId:string;conversationId:string;humanControl?:Record<string,unknown>;content:{type:'text';text:string}[]}[] {
    return this.entries(agentId).flatMap(row=>this.systemContextEntry(agentId,row));
  }
  private systemContextEntry(agentId:string,row:Entry) {
      const input=JSON.parse(row.payload) as RelayInput;
      const notice=input.message.system_notice as {kind?:string;attention_actor_ids?:string[]}|undefined;
      if(notice?.kind!=='task_graph'||!input.metadata.task_context&&!notice.attention_actor_ids?.includes(agentId))return [];
      const attested=notice as typeof notice&{change_kinds?:string[];human_control?:unknown;actor?:unknown;task_refs?:unknown;event_time?:string};
      const {human_control,actor,...business}=attested;
      const revoked=attested.change_kinds?.includes('access_revoked');
      const event=revoked?{message_id:input.message.id,conversation_id:input.conversation_id,event_time:input.message.created_at}
        :{...business,message_id:input.message.id,conversation_id:input.conversation_id,event_time:input.message.created_at,
          actor:actor??input.message.sender,content:input.message.content};
      const text=(revoked?"Your access or handling eligibility for the identified conversation or Tasks was revoked at event_time. Stop actions that require missing eligibility, and do not read or disclose content you can no longer access. On a later independently authorized request, check current permissions through available tools and use their current verified access facts instead of treating this historical loss as permanent. Restored access alone does not resume paused Tasks or authorize previously denied actions. Continue unrelated authorized work. This notice grants no permission and does not erase already consumed history.":"Task update from its fixed conversation. Apply the stated business change before further action on the affected Task. If its requirements changed, read the latest Task details. This system message does not grant human permission or start todo/paused work.")+'\n'+JSON.stringify(event)
        +(!revoked&&attested.human_control?'\n'+"Application-attested human Task control follows. Apply it only to the identified Task or scope. Inputs queued before a stop cannot resume its paused Tasks. Only a later explicit human resume supersedes that pause; it grants no additional tool permission. Unrelated work may continue."+'\n'+JSON.stringify(attested.human_control):'');
      return [{inputId:input.message.id,conversationId:input.conversation_id,...(!revoked&&human_control&&typeof human_control==='object'?{humanControl:human_control as Record<string,unknown>}:{}),content:[{type:'text' as const,text}]}];
  }
  /** Look up an exact durable ingestion, which revocation alone cannot create. */
  systemContextIngested(agentId:string,sessionId:string,inputId:string,turn:number):boolean {
    return !!this.db.prepare(`SELECT 1 FROM inbox i JOIN ingestions d ON d.seq=i.seq
      WHERE i.agent_id=? AND i.message_id=? AND d.session_id=? AND d.turn=?`).get(agentId,inputId,sessionId,turn);
  }

  /** Mark direct reading only after matching native durable execution evidence. */
  commitSystemContext(agentId:string,sessionId:string,inputId:string,content:{type:string;text?:string}[],turn:number):boolean {
    const row=this.db.prepare("SELECT * FROM inbox WHERE agent_id=? AND message_id=? AND consumed=0 AND review_state='admitted' AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0").get(agentId,inputId) as unknown as Entry|undefined;
    const prepared=row&&this.systemContextEntry(agentId,row)[0];
    if(!row||!prepared||JSON.stringify(prepared.content)!==JSON.stringify(content)||!Number.isSafeInteger(turn))return false;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('UPDATE inbox SET consumed=1 WHERE seq=?').run(row.seq);
      this.db.prepare(`DELETE FROM reads WHERE EXISTS(SELECT 1 FROM json_each(reads.fragments) part WHERE json_extract(part.value,'$.seq')=?)`).run(row.seq);
      this.db.prepare(`DELETE FROM query_reads WHERE EXISTS(SELECT 1 FROM json_each(query_reads.fragments) part WHERE json_extract(part.value,'$.seq')=?)`).run(row.seq);
      this.db.prepare('INSERT OR IGNORE INTO ingestions VALUES(?,?,?)').run(row.seq,sessionId,turn);
      this.db.exec('COMMIT');
      return true;
    }catch(error){this.db.exec('ROLLBACK');throw error;}
  }
  /** Retire unread context while preserving its raw journal/history and consumed history. */
  revokeSystemContext(agentId:string,messageId:string):void {
    this.db.prepare(`DELETE FROM reads WHERE EXISTS(SELECT 1 FROM json_each(reads.fragments) part JOIN inbox i ON i.seq=json_extract(part.value,'$.seq') WHERE i.agent_id=? AND i.message_id=?)`).run(agentId,messageId);
    this.db.prepare(`DELETE FROM query_reads WHERE EXISTS(SELECT 1 FROM json_each(query_reads.fragments) part JOIN inbox i ON i.seq=json_extract(part.value,'$.seq') WHERE i.agent_id=? AND i.message_id=?)`).run(agentId,messageId);
    this.db.prepare('UPDATE inbox SET consumed=1 WHERE agent_id=? AND message_id=?').run(agentId,messageId);
  }
  /** List unread sources; personal projection omits host scheduling state. */
  check(agent: string, personal = false, timezone?:string, entries=this.entries(agent)) {
    const sources = new Map<string,Source>();
    const instants = new Map<string,number>();
    for (const row of entries) {
      const input = JSON.parse(row.payload) as RelayInput;
      if ((input.message.system_notice as { kind?: string } | undefined)?.kind === 'task_graph') continue;
      const meta=input.metadata;
      const { base, root } = splitThreadTarget(row.target);
      const source:Source = sources.get(row.target) ?? { target: row.target, ...(root ? { parent_target: base } : {}), name: this.targetName(agent,row.target,input), unread: 0, mentions: 0,
        latest_message_at:null, conversation_type:String(meta.conversation_type),
        ...(personal ? {delivery:String(meta.personal_delivery)} : {requires_attention:false}) };
      source.unread++;
      const mentions = meta.explicit_mentioned_agent_ids
        ?? (input.message.interaction_reply || input.message.sender_type === 'system' ? [] : meta.mentioned_agent_ids);
      if (Array.isArray(mentions) && mentions.includes(agent)) source.mentions++;
      const instant=sourceInstant(input);
      if(instant!==undefined && instant>(instants.get(row.target)??-Infinity)) {
        source.latest_message_at=formatLocalTime(instant,timezone);instants.set(row.target,instant);
      }
      if (personal) {
        const owner=meta.addressed_to_owner===true || source.addressed_to==='owner' || source.addressed_to==='both';
        const addressed=meta.addressed_to_agent===true || (meta.addressed_to_agent===undefined && !!row.attention) || source.addressed_to==='agent' || source.addressed_to==='both';
        if(owner||addressed)source.addressed_to=owner&&addressed?'both':owner?'owner':'agent';
        source.delivery=String(meta.personal_delivery);
      } else source.requires_attention ||= !!row.attention;
      sources.set(row.target, source);
    }
    const sorted=[...sources.values()].sort((a,b)=>(instants.get(b.target)??-Infinity)-(instants.get(a.target)??-Infinity) || (a.target<b.target?-1:a.target>b.target?1:0));
    return { sources: sorted, ...(personal?{review_failures:this.reviews.failures(agent).map(({event_id,event_delivered,...failure})=>failure)}:{}) };
  }
  private targetName(agent: string, target: string, input: RelayInput): string {
    const base = splitThreadTarget(target).base;
    return (this.db.prepare('SELECT name FROM targets WHERE agent_id=? AND target=?').get(agent,base) as {name:string}|undefined)?.name ?? String(input.metadata.conversation_title ?? base);
  }
  blocking(agent: string, target: string): boolean {
    return !!this.db.prepare(`SELECT 1 FROM inbox WHERE agent_id=? AND target=? AND consumed=0 AND attention=1
      AND review_state IN ('pending','reviewing','admitted') AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0 LIMIT 1`).get(agent, target);
  }
  watermark(agent:string):number {
    return Number(this.db.prepare('SELECT coalesce(max(ord),0) value FROM inbox_schedule WHERE agent_id=?').get(agent)!.value);
  }
  unreadAttention(agent:string):number|undefined {
    return this.db.prepare('SELECT max(ord) value FROM inbox_schedule s JOIN inbox i ON s.seq=i.seq WHERE s.agent_id=? AND i.consumed=0 AND (s.notified=1 OR s.due_at=0)').get(agent)!.value as number || undefined;
  }
  admittedWake(agent:string):number {return Number(this.db.prepare('SELECT watermark FROM wakes WHERE agent_id=?').get(agent)?.watermark??0);}
  wakePending(agent:string):number|undefined {
    const batch=this.background(agent);
    if(batch && batch.dueAt<=Date.now())return batch.watermark;
  }
  admitWake(agent:string,watermark:number,session?:string,inputId?:string):void {
    const notice=session && inputId ? this.db.prepare('SELECT seqs FROM inbox_notifications WHERE session_id=? AND input_id=?').get(session,inputId) : undefined;
    if(notice)this.db.prepare('UPDATE inbox_schedule SET notified=1 WHERE agent_id=? AND seq IN (SELECT value FROM json_each(?))').run(agent,notice.seqs);
    else this.db.prepare('UPDATE inbox_schedule SET notified=1 WHERE agent_id=? AND ord<=?').run(agent,watermark);
    this.db.prepare('INSERT INTO wakes VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET watermark=max(watermark,excluded.watermark)').run(agent,watermark);
    this.db.prepare('DELETE FROM inbox_batch WHERE agent_id=? AND watermark=?').run(agent,watermark);
  }

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
    if (prior) return JSON.parse(this.restrictedRead(session,call)??prior.body) as Record<string, unknown>;
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
    // Keep cursor offsets fixed, but revalidate eligibility at every unread page.
    // A saved cut is not permission to replay withdrawn or directly consumed content.
    const unread = (fragment: Snapshot['fragments'][number]) => !!this.db.prepare('SELECT 1 FROM inbox WHERE seq=? AND consumed=0 AND NOT EXISTS(SELECT 1 FROM fragments WHERE seq=? AND part=?)').get(fragment.seq,fragment.seq,fragment.part);
    const maxEntries = Math.min(MAX_INBOX_READ_ENTRIES, Math.max(1, args.limit ?? MAX_INBOX_READ_ENTRIES));
    const candidates = snapshot.fragments.slice(offset).filter(unread).slice(0, maxEntries);
    const inputCache = new Map<number, RelayInput>();
    const sourceInput = (seq: number) => {
      let cached = inputCache.get(seq);
      if (!cached) {
        cached = JSON.parse((this.db.prepare('SELECT payload FROM inbox WHERE seq=?').get(seq) as {payload:string}).payload) as RelayInput;
        inputCache.set(seq, cached);
      }
      return cached;
    };
    const first = candidates.length ? sourceInput(candidates[0]!.seq) : undefined;
    const personal = first?.metadata.personal_delivery !== undefined;
    const firstContext = personal ? JSON.stringify([first!.metadata.personal_delivery, first!.metadata.conversation_type, first!.metadata.channel]) : undefined;
    const selected: Fragment[] = [];
    let totalChars = 0;
    let totalImages = 0;
    for (const fragment of candidates) {
      const input = sourceInput(fragment.seq);
      if (personal && JSON.stringify([input.metadata.personal_delivery, input.metadata.conversation_type, input.metadata.channel]) !== firstContext) {
        // A page shares source context; stop at a historical relationship boundary.
        break;
      }
      const partBlocks = this.parts(input, fragment.seq)[fragment.part] ?? [];
      let chars = 0;
      let images = 0;
      for (const block of partBlocks) {
        if (typeof block.text === 'string') chars += block.text.length;
        if (typeof block.content_type === 'string' && isRasterImageMime(block.content_type)) images++;
      }
      if (selected.length > 0 && (totalChars + chars > MAX_INBOX_READ_CHARS || totalImages + images > MAX_INBOX_READ_IMAGES)) {
        break;
      }
      selected.push(fragment);
      totalChars += chars;
      totalImages += images;
    }
    const { base: baseTarget, root: threadRoot } = splitThreadTarget(args.target);
    const alreadySeen = threadRoot
      ? !!this.db.prepare('SELECT 1 FROM inbox_seen_threads WHERE session_id=? AND target=?').get(session, args.target)
      : false;
    const selectedInputs = selected.map(fragment => sourceInput(fragment.seq));
    const reactivatedInput = threadRoot ? selectedInputs.find(input => input.metadata.thread_follow_reactivated === true) : undefined;
    const reactivated = Boolean(reactivatedInput);
    const contextInput = reactivatedInput ?? first;
    const includeThreadContext = !!threadRoot && selected.length > 0 && ((!alreadySeen && !args.cursor) || reactivated)
      && typeof contextInput?.metadata.thread_root_excerpt === 'string';
    const truncated = contextInput?.metadata.thread_history_truncated === true;
    const threadContext = includeThreadContext ? {
      root_message_id: threadRoot,
      root_sender: contextInput!.metadata.thread_root_sender ?? '',
      root_excerpt: contextInput!.metadata.thread_root_excerpt,
      earlier_replies: Array.isArray(contextInput!.metadata.thread_earlier) ? contextInput!.metadata.thread_earlier : [],
      truncated,
      ...(truncated ? { hint: 'Call read_messages with this target for full thread history.' } : {}),
    } : undefined;
    const messages = selected.map(fragment => {
      const row = this.db.prepare('SELECT * FROM inbox WHERE seq=?').get(fragment.seq) as unknown as Entry;
      const input = JSON.parse(row.payload) as RelayInput;
      const parts = this.parts(input, row.seq);
      const instant = input.message.created_at ?? input.metadata.created_at ?? input.metadata.source_time
        ?? (input.metadata.source_timestamp ? Number(input.metadata.source_timestamp) : undefined);
      return { id: input.message.id, ...(input.message.pa_agent_id?{pa_agent_id:input.message.pa_agent_id}:{}), sender: { id: input.message.sender_user_id, type: input.message.sender_type,
        name: input.message.sender?.display_name ?? input.metadata.sender_display_name ?? input.metadata.sender_name ?? input.message.sender_user_id,
        ...(personal ? {is_owner:input.metadata.personal_is_owner === true} : {}) }, time: instant === undefined ? null : formatLocalTime(instant as string | number, input.message.timezone),
        ...(!personal && input.metadata.channel ? {channel:input.metadata.channel} : {}),
        ...(input.metadata.personal_actor_risk ? {actor_risk:personal ? this.actorRisk(input) : input.metadata.personal_actor_risk} : {}),
        ...(input.message.reply_to ? { reply_to: projectChatReplyContext(input.message.reply_to) } : {}),
        content: parts[fragment.part], ...(parts.length > 1 ? { partial: true, part: fragment.part + 1, parts: parts.length } : {}) };
    });
    const next = selected.length ? snapshot.fragments.indexOf(selected.at(-1)!)+1 : snapshot.fragments.length;
    const body = present({ target: args.target,
      ...(threadRoot ? { parent_target: baseTarget } : {}),
      ...(personal ? {name:this.targetName(agent,args.target,first!),conversation_type:first!.metadata.conversation_type,delivery:first!.metadata.personal_delivery,channel:first!.metadata.channel} : {}),
      ...(threadContext ? { thread_context: threadContext } : {}),
      ...(reactivated ? { follow_reactivated: true, follow_reactivated_notice: 'You had unfollowed this thread; a mention or quote reactivated your follow.' } : {}),
      messages, ...(snapshot.fragments.slice(next).some(unread) ? { next_cursor: Buffer.from(JSON.stringify({ id: snapshotId, offset: next })).toString('base64url') } : {}) });
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
    const text = withInteractionContext(input.message.content, input.message.interaction_reply, input.metadata.interaction_contexts, input.message.interactive);
    const result: Record<string, unknown>[][] = [];
    for (let start = 0; start < text.length || start === 0; start += 6000) result.push([{ type: 'text', text: text.slice(start, start + 6000) }]);
    for (const attachment of input.message.attachments) {
      const isTranscribedVoiceRaw = input.metadata.channel === 'wechat'
        && typeof attachment.file_name === 'string'
        && /^voice-raw\.(wav|mp3)$/i.test(attachment.file_name);
      result.push([{
        type: 'attachment',
        ...attachment,
        ...(isTranscribedVoiceRaw
          ? { note: 'Raw audio of the transcribed voice message above; call download_attachment only if raw audio file is needed' }
          : {}),
      }]);
    }
    return result;
  }
  updateTarget(agent: string, target: string, name: string): void { this.db.prepare('INSERT INTO targets VALUES(?,?,?) ON CONFLICT(agent_id,target) DO UPDATE SET name=excluded.name').run(agent, target, name); }
  /** Return whether the latest non-context human message across an external chat and its IM shadow originated from internal Web IM. */
  latestHumanTriggerIsInternalIm(agent: string, shadowId: string, externalId?: string): boolean {
    const targets = externalId && externalId !== shadowId ? [shadowId, externalId] : [shadowId];
    const row = this.db.prepare(
      `SELECT target, payload FROM inbox
       WHERE agent_id = ? AND target IN (SELECT value FROM json_each(?))
         AND json_extract(payload, '$.message.sender_type') = 'user'
         AND coalesce(json_extract(payload, '$.metadata.context_only'), 0) = 0
         AND coalesce(json_extract(payload, '$.metadata.scope_skipped'), 0) = 0
       ORDER BY seq DESC LIMIT 1`,
    ).get(agent, JSON.stringify(targets)) as { target: string; payload: string } | undefined;
    if (!row) return false;
    const input = JSON.parse(row.payload) as RelayInput;
    if (input.metadata.trigger_source === 'im') return true;
    if (input.metadata.channel === 'web') return true;
    if (!input.metadata.channel && row.target === shadowId && !shadowId.startsWith('external:')) return true;
    return false;
  }
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
    const body = JSON.parse(this.restrictedRead(session,call)??row.body) as { target: string; messages: { id: string; target?: string; content: { type: string; content_type?: string; url?: string }[] }[] };
    return body.messages.flatMap(message => message.content.filter(part => isRasterImageMime(part.content_type)).map(part => ({
      kind: 'chat' as const, conversationId: message.target ?? body.target, messageId: message.id, url: part.url!,
    })));
  }
  prepareRead(session: string, call: string, content: { type: string; text?: string }[]): void {
    const row = this.db.prepare('SELECT body FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { body: string } | undefined;
    if (!row || content[0]?.text !== row.body || content.filter(part => part.type === 'image').length !== this.imageReferences(session, call).length) throw new Error('Incomplete prepared inbox content');
    // A mixed page may retain only some of its images when the scope narrows.
    const digest=content.length>1?JSON.stringify(content.map(block=>hash(JSON.stringify(block)))):hash(JSON.stringify(content));
    this.db.prepare('INSERT INTO read_content VALUES(?,?,?) ON CONFLICT(session_id,call_id) DO UPDATE SET digest=excluded.digest').run(session,call,digest);
  }
  reviewTargets(session: string, turn: number): string[] {
    return (this.db.prepare('SELECT DISTINCT i.target FROM inbox i JOIN ingestions g ON g.seq=i.seq WHERE g.session_id=? AND g.turn=? AND i.consumed=1').all(session, turn) as { target: string }[]).map(row => row.target);
  }

  /** Record eligible plain-text unread inbox rows shown in a read_messages result for durable commit.
   *
   * Args:
   *   agent: Trusted product Agent identity.
   *   session: Execution session receiving the read_messages result.
   *   call: Durable tool call identity.
   *   rawResult: Unprojected query result containing canonical message_ids and completeness flags.
   *   projectedResult: Exact model-visible JSON object whose serialized text DSH commits.
   */
  recordQueryRead(agent: string, session: string, call: string, rawResult: unknown, projectedResult: unknown): void {
    if (!rawResult || typeof rawResult !== 'object' || Array.isArray(rawResult)) return;
    const rawMessages = (rawResult as { messages?: unknown }).messages;
    if (!Array.isArray(rawMessages) || !rawMessages.length) return;
    const seenSeq = new Set<number>();
    const selected: Fragment[] = [];
    for (const item of rawMessages) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
      const msg = item as { message_id?: unknown; complete_message?: unknown };
      if (typeof msg.message_id !== 'string' || !msg.message_id || msg.complete_message === false) continue;
      const row = this.db.prepare(`SELECT seq, target, payload FROM inbox
        WHERE agent_id=? AND message_id=? AND consumed=0 AND review_state='admitted'
          AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0`).get(agent, msg.message_id) as { seq: number; target: string; payload: string } | undefined;
      if (!row || seenSeq.has(row.seq)) continue;
      const input = JSON.parse(row.payload) as RelayInput;
      // High-risk, private-interaction, multi-part, or attachment/image items must still be read via inbox(read).
      if (input.metadata.personal_actor_risk) continue;
      if (Array.isArray(input.metadata.interaction_contexts) && input.metadata.interaction_contexts.length > 0) continue;
      const parts = this.parts(input, row.seq);
      if (parts.length !== 1) continue;
      if (parts[0]!.some(block => typeof block.content_type === 'string' && isRasterImageMime(block.content_type))) continue;
      if (this.db.prepare('SELECT 1 FROM fragments WHERE seq=? AND part=0').get(row.seq)) continue;
      seenSeq.add(row.seq);
      selected.push({ seq: row.seq, part: 0 });
    }
    if (!selected.length) return;
    const digest = hash(JSON.stringify(projectedResult));
    this.db.prepare('INSERT OR REPLACE INTO query_reads VALUES(?,?,?,?)').run(session, call, JSON.stringify(selected), digest);
  }

  /** Return canonical source refs committed by a read_messages call, if any. */
  committedQuerySources(session: string, call: string): { conversation_id: string; message_id: string; complete_message: boolean }[] | undefined {
    const row = this.db.prepare('SELECT fragments FROM query_reads WHERE session_id=? AND call_id=?').get(session, call) as { fragments: string } | undefined;
    if (!row) return undefined;
    const fragments = JSON.parse(row.fragments) as Fragment[];
    const refs: { conversation_id: string; message_id: string; complete_message: boolean }[] = [];
    for (const fragment of fragments) {
      const entry = this.db.prepare('SELECT target, message_id FROM inbox WHERE seq=?').get(fragment.seq) as { target: string; message_id: string } | undefined;
      if (!entry) continue;
      refs.push({ conversation_id: splitThreadTarget(entry.target).base, message_id: entry.message_id, complete_message: true });
    }
    return refs;
  }

  /** Find saved reads (inbox or read_messages) that could still consume an unread fragment in the destination. */
  pendingReadCalls(session: string, targets: string[]): string[] {
    return (this.db.prepare(`SELECT call_id FROM (
      SELECT session_id, call_id, fragments FROM reads
      UNION ALL
      SELECT session_id, call_id, fragments FROM query_reads
    ) r WHERE session_id=? AND EXISTS (
      SELECT 1 FROM json_each(r.fragments) fragment JOIN inbox i ON i.seq=json_extract(fragment.value,'$.seq')
      LEFT JOIN fragments f ON f.seq=i.seq AND f.part=json_extract(fragment.value,'$.part')
      WHERE i.attention=1 AND i.consumed=0 AND f.seq IS NULL AND i.target IN (SELECT value FROM json_each(?))
    )`).all(session, JSON.stringify(targets)) as {call_id: string}[]).map(row => row.call_id);
  }
  completedInputs(session: string, turn: number): { seq: number; input: RelayInput }[] {
    return (this.db.prepare('SELECT i.seq,i.payload FROM inbox i JOIN ingestions g ON g.seq=i.seq LEFT JOIN receipts r ON r.seq=i.seq WHERE g.session_id=? AND g.turn=? AND r.seq IS NULL').all(session, turn) as { seq: number; payload: string }[]).map(row => ({ seq: row.seq, input: JSON.parse(row.payload) as RelayInput }));
  }
  confirmReceipt(seq: number, status: string): void { this.db.prepare('INSERT OR REPLACE INTO receipts VALUES(?,?)').run(seq, status); }
  /** Match the exact committed tool body, never a summary, truncation, or failed call. */
  commitRead(session: string, call: string, content: { type: string; text?: string; contextItemId?: string }[], isError: boolean, turn?: number): boolean {
    if (isError) return false;
    const read = this.db.prepare('SELECT fragments,digest FROM reads WHERE session_id=? AND call_id=?').get(session, call) as { fragments: string; digest: string } | undefined;
    if (read) {
      const prepared = this.db.prepare('SELECT digest FROM read_content WHERE session_id=? AND call_id=?').get(session, call) as { digest: string } | undefined;
      if(prepared){
        const digest=prepared.digest.startsWith('[')?JSON.stringify(content.map(block=>hash(JSON.stringify(block)))):hash(JSON.stringify(content));
        if(prepared.digest!==digest)return false;
      } else if(this.imageReferences(session,call).length || read.digest!==hash(content.filter(block=>block.type==='text').map(block=>block.text??'').join('')))return false;
      return this.commitFragments(session, JSON.parse(read.fragments) as Fragment[], turn);
    }
    const queryRead = this.db.prepare('SELECT fragments,digest FROM query_reads WHERE session_id=? AND call_id=?').get(session, call) as { fragments: string; digest: string } | undefined;
    if (!queryRead) return false;
    const allText = content.filter(block => block.type === 'text').map(block => block.text ?? '').join('');
    const coreText = content.filter(block => block.type === 'text' && !block.contextItemId).map(block => block.text ?? '').join('');
    if (queryRead.digest !== hash(allText) && queryRead.digest !== hash(coreText)) return false;
    return this.commitFragments(session, JSON.parse(queryRead.fragments) as Fragment[], turn, true);
  }
  private commitFragments(session: string, fragments: Fragment[], turn?: number, requireAdmitted = false): boolean {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      let committedAny = false;
      for (const fragment of fragments) {
        const row = this.db.prepare('SELECT seq,target,payload,review_state,consumed FROM inbox WHERE seq=?').get(fragment.seq) as { seq: number; target: string; payload: string; review_state: string; consumed: number } | undefined;
        // Older revocations can leave saved reads behind; reject their entire consumption.
        if (!row) { this.db.exec('ROLLBACK'); return false; }
        if (requireAdmitted && row.review_state !== 'admitted') continue;
        this.db.prepare('INSERT OR IGNORE INTO fragments VALUES(?,?)').run(fragment.seq, fragment.part);
        if (splitThreadTarget(row.target).root) {
          this.db.prepare('INSERT OR IGNORE INTO inbox_seen_threads VALUES(?,?)').run(session, row.target);
        }
        const count = (this.db.prepare('SELECT count(*) AS n FROM fragments WHERE seq=?').get(fragment.seq) as { n: number }).n;
        if (count === this.parts(JSON.parse(row.payload) as RelayInput, row.seq).length) {
          if (row.consumed === 0) committedAny = true;
          this.db.prepare('UPDATE inbox SET consumed=1 WHERE seq=?').run(fragment.seq);
          if (turn !== undefined) this.db.prepare('INSERT OR IGNORE INTO ingestions VALUES(?,?,?)').run(fragment.seq, session, turn);
        }
      }
      this.db.exec('COMMIT');
      return requireAdmitted ? committedAny : true;
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Read durable product processing positions for one root and its children. */
  workCheckpoints(rootSessionId:string):Record<string,WorkCheckpoint> {
    return Object.fromEntries((this.db.prepare('SELECT session_id,checkpoint FROM work_checkpoints WHERE root_session_id=?').all(rootSessionId) as {session_id:string;checkpoint:string}[])
      .map(row=>[row.session_id,JSON.parse(row.checkpoint) as WorkCheckpoint]));
  }
  /** Look up one durable execution position without loading its siblings. */
  workCut(sessionId:string):WorkCheckpoint|undefined {
    const row=this.db.prepare('SELECT checkpoint FROM work_checkpoints WHERE session_id=?').get(sessionId) as {checkpoint:string}|undefined;
    return row ? JSON.parse(row.checkpoint) as WorkCheckpoint : undefined;
  }

  /** Read the child events still needed to pair its open logical turn. */
  workOpenEvents(sessionId: string): RuntimeEvent[] {
    return (this.db.prepare('SELECT event FROM work_open_events WHERE session_id=? ORDER BY seq').all(sessionId) as {event:string}[])
      .map(row=>JSON.parse(row.event) as RuntimeEvent);
  }

  /** Commit display facts and their processing cut in one local transaction.
   *
   * Args:
   *   sessionId: Execution whose own events were processed.
   *   checkpoint: Position covered by the supplied projection facts.
   *   events: Product facts carrying their stable source identities.
   *   native: Newly received child events, kept only while their logical turn is open.
   *   positioned: Root facts with their native position, for merging pending delivery facts.
   */
  commitWork(sessionId:string,checkpoint:WorkCheckpoint,events:WorkDraft[],native?: RuntimeEvent[],positioned: {seq: number; event: WorkDraft}[] = []):void {
    if (this.deletedSession(checkpoint.rootSessionId)) return;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      for(const event of events)this.append(event);
      const waiting = sessionId === checkpoint.rootSessionId ? this.db.prepare('SELECT seq,event FROM work_waiting_facts WHERE session_id=? AND seq<=? ORDER BY seq,rowid')
        .all(sessionId, checkpoint.throughSeq) as {seq: number; event: string}[] : [];
      let next = 0;
      for (const fact of positioned) {
        while (waiting[next] && waiting[next]!.seq < fact.seq) this.append(JSON.parse(waiting[next++]!.event) as WorkDraft);
        this.append(fact.event);
      }
      while (waiting[next]) this.append(JSON.parse(waiting[next++]!.event) as WorkDraft);
      if (waiting.length) this.db.prepare('DELETE FROM work_waiting_facts WHERE session_id=? AND seq<=?').run(sessionId, checkpoint.throughSeq);
      if (native) {
        this.db.prepare('DELETE FROM work_open_events WHERE session_id=? AND seq<?').run(sessionId,checkpoint.replayFrom);
        const put=this.db.prepare('INSERT OR REPLACE INTO work_open_events VALUES(?,?,?)');
        for (const event of native) if (event.seq>=checkpoint.replayFrom) put.run(sessionId,event.seq,JSON.stringify(event));
      }
      this.db.prepare('INSERT INTO work_checkpoints VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET root_session_id=excluded.root_session_id,checkpoint=excluded.checkpoint WHERE checkpoint!=excluded.checkpoint')
        .run(sessionId,checkpoint.rootSessionId,JSON.stringify(checkpoint));
      this.db.exec('COMMIT');
    }catch(error){this.db.exec('ROLLBACK');throw error;}
  }
  /** Keep incomplete reconciliation visible across a Node crash. */
  workPending(rootSessionId:string,pending:boolean,childrenOnly = false):void {
    if (this.deletedSession(rootSessionId)) return;
    if (pending && childrenOnly) this.childOnlyRecovery.add(rootSessionId);
    else this.childOnlyRecovery.delete(rootSessionId);
    this.db.prepare('INSERT INTO work_recovery VALUES(?,?) ON CONFLICT(root_session_id) DO UPDATE SET pending=excluded.pending WHERE pending!=excluded.pending').run(rootSessionId,Number(pending));
  }
  /** Report each settled Agent's last journal event while its peers catch up.
   *
   * Args:
   *   agents: Configured Work producers on this node.
   *   ownerOf: Resolve a durable recovery root to its Agent.
   * Returns:
   *   Agent IDs whose processing has settled and the ACK each one requires.
   */
  readyWorkAgents(agents: string[], ownerOf: (session: string) => string | undefined): Record<string, WorkReadyCut> {
    const pending = new Set<string>();
    const childOnly = new Set<string>();
    for (const {root_session_id} of this.db.prepare('SELECT root_session_id FROM work_recovery WHERE pending=1').all()) {
      const agent = ownerOf(String(root_session_id));
      if (!agent) return {};
      if (this.childOnlyRecovery.has(String(root_session_id))) childOnly.add(agent);
      else pending.add(agent);
    }
    for (const row of this.db.prepare("SELECT DISTINCT json_extract(event,'$.root_agent_id') AS agent FROM work_waiting_facts").all())
      pending.add(String(row.agent));
    const last = this.db.prepare("SELECT seq FROM journal WHERE json_extract(event,'$.root_agent_id')=? ORDER BY seq DESC LIMIT 1");
    return Object.fromEntries(agents.filter(agent => !pending.has(agent)).map(agent => {
      const through = Number(last.get(agent)?.seq ?? 0);
      return [agent, childOnly.has(agent) ? {main: through} : through];
    }));
  }
  get workProcessingPending():boolean {
    return !!this.db.prepare('SELECT 1 FROM work_recovery WHERE pending=1 UNION ALL SELECT 1 FROM work_waiting_facts LIMIT 1').get();
  }
  /** Keep delivery facts behind their native Work position so they cannot create a newer turn first. */
  appendAfterWork(event: WorkDraft, seq?: number): void {
    if (this.deletedAgent(event.root_agent_id)) return;
    if (seq === undefined || (this.workCut(event.session_id)?.throughSeq ?? -1) >= seq) this.append(event);
    else this.db.prepare('INSERT OR IGNORE INTO work_waiting_facts VALUES(?,?,?,?)').run(event.session_id, seq, event.event_id, JSON.stringify(event));
  }
  append(event: WorkDraft): void {
    if (this.deletedAgent(event.root_agent_id)) return;
    if (this.db.prepare('SELECT 1 FROM journal WHERE event_id=?').get(event.event_id)) return;
    const seq = (this.db.prepare('SELECT coalesce(max(seq),0)+1 AS seq FROM journal').get() as { seq: number }).seq;
    this.db.prepare('INSERT INTO journal VALUES(?,?,?)').run(seq, event.event_id, JSON.stringify({ ...event, seq }));
  }
  journal(after: number, limit = 100): WorkJournalEvent[] { return (this.db.prepare('SELECT event FROM journal WHERE seq>? ORDER BY seq LIMIT ?').all(after,limit) as { event: string }[]).map(row => decodeWorkEvent(JSON.parse(row.event)).event); }
  get journalSeq(): number {return Number((this.db.prepare('SELECT coalesce(max(seq),0) seq FROM journal').get() as {seq:number}).seq);}
  get throughSeq(): number { return Number((this.db.prepare('SELECT value FROM metadata WHERE key=?').get('through') as { value: string } | undefined)?.value ?? 0); }
  acknowledge(seq: number): void { this.db.prepare('INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run('through', String(seq)); }
  publication(id: string): { target: string; body: string; state: string; result: string | null; source: string | null } | undefined { return this.db.prepare('SELECT target,body,state,result,source FROM publications WHERE id=?').get(id) as { target: string; body: string; state: string; result: string | null; source: string | null } | undefined; }
  /** Read uncertain sends owned by this execution session without replaying them. */
  /** Find the current incident attempt, preserving uncertain delivery across wording changes. */
  incidentPublication(prefix: string): ({id:string} & NonNullable<ReturnType<InboxStore['publication']>>) | undefined {
    return this.db.prepare('SELECT id,target,body,state,result,source FROM publications WHERE id=? OR substr(id,1,?)=? ORDER BY rowid DESC LIMIT 1').get(prefix,prefix.length+1,prefix+':') as ReturnType<InboxStore['incidentPublication']>;
  }
  pendingPublications(session: string): {id:string;target:string;body:string;source:string|null}[] { return this.db.prepare("SELECT id,target,body,source FROM publications WHERE state IN ('sending','unknown') AND substr(id,1,?)=?").all(session.length+1,`${session}:`) as {id:string;target:string;body:string;source:string|null}[]; }
  preparePublication(id: string, target: string, body: string, agentId?: string, source?: {turn?: number; seq?: number; threadRoot?:string; text: string}): void {
    this.db.prepare(`INSERT INTO publications(id,target,body,state,result,agent_id,source) VALUES(?,?,?,'prepared',NULL,?,?)
      ON CONFLICT(id) DO UPDATE SET source=excluded.source WHERE publications.source IS NULL AND excluded.source IS NOT NULL`)
      .run(id, target, body, agentId ?? null, source ? JSON.stringify(source) : null);
  }
  settlePublication(id: string, state: string, result?: unknown): void { this.db.prepare('UPDATE publications SET state=?,result=? WHERE id=?').run(state, result === undefined ? null : JSON.stringify(result), id); }
  /** Persist the send outcome and its future Work fact together, even when Work is still behind. */
  settlePublicationWithWork(id: string, state: string, result: unknown, event: WorkDraft, seq?: number): void {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.settlePublication(id, state, result);
      this.appendAfterWork(event, seq);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  close(): void { this.db.close(); }
}
