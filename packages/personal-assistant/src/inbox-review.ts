import type { DatabaseSync } from 'node:sqlite';
import type { RelayInput } from '@nano/product-contracts';

export type InputReviewState = 'pending' | 'reviewing' | 'admitted' | 'rejected' | 'failed';
export interface InputReview {
  message_id: string; state: InputReviewState; generation: number; reason?: string; error_code?: string;
  incident_id?: string; event_id?: string; event_delivered: boolean;
}
interface Row {message_id:string;review_state:InputReviewState;review_generation:number;review_reason:string|null;review_error_code:string|null;review_incident_id:string|null;review_event_id:string|null;review_event_delivered:number}
const project=(r:Row):InputReview=>({message_id:r.message_id,state:r.review_state,generation:r.review_generation,
 ...(r.review_reason?{reason:r.review_reason}:{}),...(r.review_error_code?{error_code:r.review_error_code}:{}),
 ...(r.review_incident_id?{incident_id:r.review_incident_id}:{}),...(r.review_event_id?{event_id:r.review_event_id}:{}),event_delivered:!!r.review_event_delivered});

/** Message admission state shares the Inbox transaction and never consumes another message. */
export class InboxReviews {
 constructor(private readonly db:DatabaseSync) {
  const columns=new Set(db.prepare('PRAGMA table_info(inbox)').all().map(row=>row.name));
  for(const [name,type] of Object.entries({review_state:'TEXT',review_generation:'INTEGER NOT NULL DEFAULT 0',review_reason:'TEXT',review_error_code:'TEXT',review_incident_id:'TEXT',review_event_id:'TEXT',review_event_delivered:'INTEGER NOT NULL DEFAULT 0'}))
   if(!columns.has(name))db.exec(`ALTER TABLE inbox ADD COLUMN ${name} ${type}`);
  // This store is opened once per Node process. An interrupted request has no verdict to replay.
  db.prepare(`UPDATE inbox SET review_state='failed',review_error_code='interrupted',review_reason='Input review was interrupted before a verdict',
    review_event_id='input-review:'||agent_id||':'||message_id||':'||review_generation,review_event_delivered=0 WHERE review_state='reviewing'`).run();
 }
 /** Establish the state only on first receipt; a duplicate cannot reset a terminal result. */
 initialize(input:RelayInput):void {
  this.db.prepare('UPDATE inbox SET review_state=? WHERE agent_id=? AND message_id=? AND review_state IS NULL')
   .run(input.metadata.personal_unclassified===true?'pending':'admitted',input.agent_id,input.message.id);
 }
 get(agent:string,message:string):InputReview|undefined {
  const row=this.db.prepare('SELECT * FROM inbox WHERE agent_id=? AND message_id=?').get(agent,message) as unknown as Row|undefined;
  return row?.review_state?project(row):undefined;
 }
 /** Claim one generation; only an explicit review operation may retry a failed input. */
 begin(agent:string,message:string,explicit=false):number|undefined {
  const row=this.db.prepare(`UPDATE inbox SET review_state='reviewing',review_generation=review_generation+1,review_reason=NULL,review_error_code=NULL,review_event_id=NULL,review_event_delivered=0
    WHERE agent_id=? AND message_id=? AND (review_state='pending' OR (? AND review_state='failed' AND coalesce(review_error_code,'')!='legacy_settled')) RETURNING review_generation`).get(agent,message,Number(explicit)) as {review_generation:number}|undefined;
  return row?.review_generation;
 }
 settle(agent:string,message:string,generation:number,result:{state:'admitted'|'rejected'|'failed';reason?:string;error_code?:string;incident_id?:string}):boolean {
  return Number(this.db.prepare(`UPDATE inbox SET review_state=?,review_reason=?,review_error_code=?,review_incident_id=?,review_event_id=?,review_event_delivered=0
    WHERE agent_id=? AND message_id=? AND review_state='reviewing' AND review_generation=?`)
   .run(result.state,result.reason??null,result.error_code??null,result.incident_id??null,result.state==='failed'?`input-review:${agent}:${message}:${generation}`:null,agent,message,generation).changes)>0;
 }
 pending(agent:string):RelayInput[] {
  return (this.db.prepare("SELECT payload FROM inbox WHERE agent_id=? AND consumed=0 AND review_state='pending' ORDER BY seq").all(agent) as {payload:string}[]).map(row=>JSON.parse(row.payload));
 }
 failures(agent:string,undelivered=false):InputReview[] {
  return (this.db.prepare("SELECT * FROM inbox WHERE agent_id=? AND review_state='failed' AND NOT (consumed=1 AND coalesce(review_error_code,'')='legacy_settled') AND (?=0 OR review_event_delivered=0) ORDER BY seq").all(agent,Number(undelivered)) as unknown as Row[]).map(project);
 }
 delivered(agent:string,message:string,generation:number):void {
  this.db.prepare("UPDATE inbox SET review_event_delivered=1 WHERE agent_id=? AND message_id=? AND review_generation=? AND review_state='failed'").run(agent,message,generation);
 }
 securityPending(agent:string):RelayInput[] {
  return (this.db.prepare("SELECT payload FROM inbox WHERE agent_id=? AND review_state='rejected' AND review_error_code IS NULL AND review_incident_id IS NULL ORDER BY seq").all(agent) as {payload:string}[]).map(row=>JSON.parse(row.payload));
 }
 incident(agent:string,message:string,id:string):void {this.db.prepare("UPDATE inbox SET review_incident_id=? WHERE agent_id=? AND message_id=? AND review_state='rejected'").run(id,agent,message);}
 /** One-time historical classification; no legacy unknown input is admitted by absence of evidence. */
 migrate(personalAgents:string[]):void {
  this.db.exec('BEGIN IMMEDIATE');
  try {
   if(this.db.prepare("SELECT 1 FROM metadata WHERE key='input-review-v1'").get()){this.db.exec('COMMIT');return;}
   for(const agent of personalAgents)this.db.prepare(`UPDATE inbox SET review_state=CASE
     WHEN consumed=1 THEN 'failed'
     WHEN json_extract(payload,'$.metadata.personal_delivery') IN ('participant','observer') AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0 THEN 'admitted'
     ELSE 'failed' END,review_error_code=CASE WHEN consumed=1 THEN 'legacy_settled' WHEN json_extract(payload,'$.metadata.personal_delivery') IN ('participant','observer') AND coalesce(json_extract(payload,'$.metadata.personal_unclassified'),0)=0 THEN NULL ELSE 'legacy_unreviewed' END,
     review_event_delivered=CASE WHEN consumed=1 THEN 1 ELSE 0 END,review_reason='Historical input retained without replay',review_event_id='input-review:'||agent_id||':'||message_id||':0'
     WHERE agent_id=? AND review_state IS NULL`).run(agent);
   this.db.prepare("UPDATE inbox SET review_state='admitted' WHERE review_state IS NULL").run();
   this.db.prepare("INSERT INTO metadata(key,value) VALUES('input-review-v1','1')").run();this.db.exec('COMMIT');
  }catch(error){this.db.exec('ROLLBACK');throw error;}
 }
}
