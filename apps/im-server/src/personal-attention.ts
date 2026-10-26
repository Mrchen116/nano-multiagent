import { createHash, randomUUID } from 'node:crypto';
import { canonicalJson } from '@nano/product-contracts';
import { all, fail, now, one, transaction, type Row } from './context.js';
import type { PersonalAgents } from './personal-agent.js';
import { TaskGraphService } from './task-graphs.js';

const digest=(value:unknown)=>createHash('sha256').update(canonicalJson(value)).digest('hex');
const list=(value:unknown,name:string,max=50):string[]=>{
 if(!Array.isArray(value)||value.length>max||value.some(id=>typeof id!=='string'||!id))fail(422,`invalid_${name}`);
 return [...new Set(value)].sort();
};
const required=(value:unknown,name:string,max=4000):string=>{
 if(typeof value!=='string'||!value.trim()||value.length>max)fail(422,`invalid_${name}`);
 return value;
};

/** Persist private discovery and source receipts beside the existing personal binding. */
export class PersonalAttention {
 constructor(private readonly pa:PersonalAgents) {}
 private get db(){return this.pa.db;}
 private feature(b:Row){return JSON.parse(one(this.db,'SELECT features_json FROM agent_profiles WHERE agent_id=?',b.agent_id)!.features_json).personal_proactivity===true;}
 private settings(b:Row):Row {
  const row=one(this.db,'SELECT * FROM pa_attention_settings WHERE binding_id=?',b.binding_id);
  return row?{...JSON.parse(row.settings_json),revision:row.revision}:{revision:1,mode:this.feature(b)?'prepare':'response_only',quiet_hours:null,suppressed_topics:[],daily_budget:20,batch_budget:5};
 }
 private sources(b:Row,ids:string[]):Row[] {
  return ids.map(id=>{const m=one(this.db,'SELECT * FROM messages WHERE id=?',id);
   if(!m||!this.pa.messageAllowed(b,m))fail(403,'attention_source_not_accessible');return m;
  });
 }
 private watermark(cid:string):string {
  // Conversation events include Task changes and completed message edits, so a
  // new source state invalidates a previous read even when message count is stable.
  const event=one(this.db,'SELECT MAX(event_id) id FROM conversation_events WHERE conversation_id=?',cid)?.id??0;
  const message=one(this.db,'SELECT MAX(rowid) id FROM messages WHERE conversation_id=?',cid)?.id??0;
  return `${event}:${message}`;
 }
 private task(b:Row,ref:Row):Row {
  if(!ref||typeof ref.graph_id!=='string'||typeof ref.node_id!=='string')fail(422,'invalid_task_ref');
  const graph=new TaskGraphService(this.db,this.pa.ctx.messaging).readPersonal({kind:'agent',id:b.agent_id,node_id:b.node_id},b.owner_user_id,'get',{graph_id:ref.graph_id,view:'all'},id=>this.pa.sourceAllowed(b,id));
  const document=graph.document??graph;
  const node=document.nodes?.find((n:Row)=>n.id===ref.node_id);
  if(!node)fail(404,'attention_task_not_found');
  return {graph_id:ref.graph_id,node_id:ref.node_id,revision:graph.revision??document.revision,title:node.title,status:node.status,assignee:node.assignee,result:node.result};
 }
 private item(b:Row,id:string):Row {
  const row=one(this.db,'SELECT * FROM pa_attention_items WHERE id=? AND binding_id=?',id,b.binding_id);
  if(!row)fail(404,'attention_not_found');
  const item={...JSON.parse(row.data_json),id:row.id,revision:row.revision,created_at:row.created_at,updated_at:row.updated_at};
  this.sources(b,item.source_refs);
  if(item.canonical_task_ref)this.task(b,item.canonical_task_ref);
  const delivery=one(this.db,'SELECT operation_id,message_id,item_revision FROM pa_attention_deliveries WHERE item_id=? AND message_id IS NOT NULL ORDER BY item_revision DESC LIMIT 1',id);
  return {...item,...(delivery?{last_delivery_receipt:delivery}:{})};
 }
 private visible(b:Row):Row[] {
  return all(this.db,'SELECT id FROM pa_attention_items WHERE binding_id=? ORDER BY updated_at DESC,id',b.binding_id).flatMap(row=>{
   try{return [this.item(b,row.id)];}catch(error){if([403,404].includes((error as Row).statusCode)||(error as Row).code==='not_found_or_forbidden')return [];throw error;}
  });
 }
 /** Read a bounded source page without acknowledging or mutating the main Inbox.
  * Args:
  *   b: Trusted current binding.
  *   args: Optional scope, query, page size and opaque query cursor.
  * Returns:
  *   References, current canonical Tasks, and explicit complete/partial coverage.
  */
 query(b:Row,args:Row):Row {
  const policy=this.pa.policy(b.binding_id).revision,limit=Math.max(1,Math.min(100,Number(args.limit)||30));
  let request:Row,offset=0,seen:string[]=[],coverage:Row;
  if(args.cursor){
   const previous=one(this.db,'SELECT * FROM pa_context_receipts WHERE id=? AND binding_id=?',args.cursor,b.binding_id);
   if(!previous||previous.policy_revision!==policy)fail(409,'context_cursor_invalidated');
   request=JSON.parse(previous.request_json);coverage=JSON.parse(previous.coverage_json);offset=previous.cursor_row;seen=JSON.parse(previous.message_ids_json);
   if(Object.keys(coverage.watermarks).some((id:string)=>!this.pa.sourceAllowed(b,id)||coverage.watermarks[id]!==this.watermark(id)))fail(409,'context_cursor_invalidated');
  }else{
   const conversations=args.conversation_ids===undefined?this.pa.sourceConversations(b).filter(c=>!c.excluded).sort((a,c)=>String(c.last_message_at??'').localeCompare(String(a.last_message_at??''))).slice(0,5).map(c=>c.id):list(args.conversation_ids,'conversation_ids',10);
   if(args.task_refs!==undefined&&(!Array.isArray(args.task_refs)||args.task_refs.length>20))fail(422,'invalid_task_refs');
   request={conversation_ids:conversations,task_refs:args.task_refs??[],query:typeof args.query==='string'?args.query.slice(0,500):'',upper:Number(one(this.db,'SELECT MAX(rowid) id FROM messages')?.id??0),explicit_scope:args.conversation_ids!==undefined};
   coverage={status:'partial',scope:request.explicit_scope?'specified_conversations':'bounded_recent_conversations',watermarks:{},sources:[]};
   for(const id of conversations){const readable=this.pa.sourceAllowed(b,id);coverage.sources.push({conversation_id:id,status:readable?'pending':'unavailable'});if(readable)coverage.watermarks[id]=this.watermark(id);}
  }
  const allowed=request.conversation_ids.filter((id:string)=>this.pa.sourceAllowed(b,id));
  let rows:Row[]=[];
  if(allowed.length) rows=all(this.db,`SELECT rowid query_row,* FROM messages WHERE rowid>? AND rowid<=? AND conversation_id IN (${allowed.map(()=>'?').join(',')}) ORDER BY rowid LIMIT ?`,offset,request.upper,...allowed,limit+1);
  const more=rows.length>limit;rows=rows.slice(0,limit);offset=rows.at(-1)?.query_row??offset;
  const readable=rows.filter(m=>this.pa.messageAllowed(b,m));coverage.omitted_messages=!!coverage.omitted_messages||readable.length!==rows.length;seen=[...new Set([...seen,...readable.map(m=>m.id)])];
  const complete=!more&&!coverage.omitted_messages&&coverage.sources.every((s:Row)=>s.status!=='unavailable');
  coverage={...coverage,status:complete?'complete':'partial',sources:coverage.sources.map((s:Row)=>({...s,status:s.status==='unavailable'?'unavailable':more?'partial':'complete'})),checked_at:now()};
  const tasks=request.task_refs.map((ref:Row)=>this.task(b,ref));
  const id=randomUUID();
  this.db.prepare('INSERT INTO pa_context_receipts VALUES(?,?,?,?,?,?,?,?)').run(id,b.binding_id,policy,canonicalJson(request),canonicalJson(coverage),canonicalJson(seen),offset,now());
  const query=request.query.toLowerCase();
  return {receipt_id:id,messages:readable.filter(m=>!query||m.content.toLowerCase().includes(query)).map(m=>({...this.pa.messageEvidence(b,m),content:m.content.slice(0,2000),truncated:m.content.length>2000})),tasks,
   attention:this.visible(b).filter(item=>!query||canonicalJson(item).toLowerCase().includes(query)).slice(0,limit),source_coverage:coverage,checked_watermarks:coverage.watermarks,next_cursor:more?id:null,
   external_connections:{status:'unknown'}};
 }
 private receipt(b:Row,id:string|undefined,sources:Row[]):Row|null {
  if(!id)return null;
  const row=one(this.db,'SELECT * FROM pa_context_receipts WHERE id=? AND binding_id=?',id,b.binding_id);
  if(!row||row.policy_revision!==this.pa.policy(b.binding_id).revision)fail(409,'context_receipt_invalidated');
  const coverage=JSON.parse(row.coverage_json),seen=JSON.parse(row.message_ids_json);
  if(coverage.status!=='complete'||sources.some(m=>!seen.includes(m.id)||coverage.watermarks[m.conversation_id]!==this.watermark(m.conversation_id)))fail(409,'context_receipt_incomplete');
  return {receipt_id:id,policy_revision:row.policy_revision,watermarks:coverage.watermarks};
 }
 private persist(b:Row,item:Row,dedup:string,receiptId?:string,batchId?:string):Row {
  const stamp=now();
  const {last_delivery_receipt:_receipt,...data}=item;
  this.db.prepare('INSERT INTO pa_attention_items(id,binding_id,dedup_key,revision,data_json,query_receipt_id,exploration_batch_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data_json=excluded.data_json,query_receipt_id=COALESCE(excluded.query_receipt_id,pa_attention_items.query_receipt_id),updated_at=excluded.updated_at')
   .run(item.id,b.binding_id,dedup,item.revision,canonicalJson(data),receiptId??null,batchId??'',item.created_at??stamp,stamp);
  return this.item(b,item.id);
 }
 private feedback(b:Row,args:Row,item:Row):void {
  if(!args.owner_instruction_id)return;
  const original=this.pa.ownerMessage(b,args.owner_instruction_id);
  const source=original.interaction_reply?.source_message_id;
  if(!source)return;
  const publication=one(this.db,'SELECT * FROM pa_attention_publications WHERE message_id=? AND binding_id=?',source,b.binding_id);
  if(!publication||publication.item_id!==item.id)fail(409,'attention_feedback_target_mismatch');
  if(publication.item_revision!==item.revision||args.expected_revision!==publication.item_revision)fail(409,'attention_revision_conflict');
 }
 /** Apply versioned discovery changes without creating or mutating a canonical Task.
  * Args:
  *   b: Trusted binding.
  *   args: Discriminated command and optional authentic owner feedback reference.
  * Returns:
  *   Current item or settings; snooze remains pending until its native receipt arrives.
  */
 command(b:Row,args:Row):Row {
  if(args.action==='list')return {items:this.visible(b).filter(item=>!args.status||item.status===args.status).slice(0,Math.max(1,Math.min(100,Number(args.limit)||30)))};
  if(args.action==='get')return this.item(b,args.id);
  if(args.action==='settings')return this.changeSettings(b,args);
  if(!['upsert','snooze','dismiss','resolve','link'].includes(args.action))fail(422,'invalid_attention_action');
  required(args.idempotency_key,'idempotency_key',200);
  if(args.action==='upsert')required(args.exploration_batch_id,'exploration_batch_id',300);
  const {request_id:_requestId,exploration_batch_id:_explorationBatchId,...operation}=args;
  const payload=canonicalJson(operation);
  return transaction(this.db,()=>{
   const prior=one(this.db,'SELECT * FROM pa_attention_mutations WHERE binding_id=? AND request_key=?',b.binding_id,args.idempotency_key);
   if(prior){if(prior.payload_json!==payload)fail(409,'attention_idempotency_conflict');const result=JSON.parse(prior.result_json);this.item(b,result.id);return result;}
   let item:Row|undefined=args.id?this.item(b,args.id):undefined;
   const sourceIds=args.source_refs===undefined?item?.source_refs:list(args.source_refs,'source_refs');
   if(!sourceIds?.length)fail(422,'attention_sources_required');
   const sources=this.sources(b,sourceIds);
   const kind=args.kind??item?.kind,topic=args.topic??item?.topic;
   required(kind,'kind',100);required(topic,'topic',200);
   const dedup=digest({source_refs:sourceIds,kind,topic});
   if(!item&&args.action==='upsert'){
    const existing=one(this.db,'SELECT id FROM pa_attention_items WHERE binding_id=? AND dedup_key=?',b.binding_id,dedup);
    if(existing){const result=this.item(b,existing.id);this.db.prepare('INSERT INTO pa_attention_mutations VALUES(?,?,?,?)').run(b.binding_id,args.idempotency_key,payload,canonicalJson(result));return result;}
   }
   const before=item?canonicalJson({kind:item.kind,topic:item.topic,why_now:item.why_now,next_step:item.next_step,prepared_result_refs:item.prepared_result_refs,canonical_task_ref:item.canonical_task_ref??null,status:item.status}):null;
   if(item&&args.expected_revision!==item.revision)fail(409,'attention_revision_conflict');
   if(item&&dedup!==one(this.db,'SELECT dedup_key FROM pa_attention_items WHERE id=?',item.id)!.dedup_key)fail(422,'attention_identity_immutable');
   if(!item&&args.action!=='upsert')fail(404,'attention_not_found');
   if(item)this.feedback(b,args,item);
   const checked=args.query_receipt_id?this.receipt(b,args.query_receipt_id,sources):item?.checked_watermarks??null;
   if(!item){
    const settings=this.settings(b);
    if(!this.feature(b)||settings.mode==='response_only')fail(409,'personal_proactivity_disabled');
    const count=Number(one(this.db,'SELECT COUNT(*) n FROM pa_attention_items WHERE binding_id=? AND created_at>=?',b.binding_id,`${now().slice(0,10)}T00:00:00.000Z`)!.n);
    const batch=Number(one(this.db,'SELECT COUNT(*) n FROM pa_attention_items WHERE binding_id=? AND exploration_batch_id=?',b.binding_id,args.exploration_batch_id)!.n);
    if(count>=settings.daily_budget||batch>=settings.batch_budget)fail(409,'attention_budget_exhausted');
    item={id:randomUUID(),revision:0,kind,topic,source_refs:sourceIds,status:'active',prepared_result_refs:[],checked_watermarks:checked};
   }
   if(args.action==='upsert'){
    item={...item,why_now:required(args.why_now??item.why_now,'why_now'),next_step:required(args.next_step??item.next_step,'next_step'),checked_watermarks:checked,
     ...(args.prepared_result_refs!==undefined?{prepared_result_refs:list(args.prepared_result_refs,'prepared_result_refs')}:{}),...(args.canonical_task_ref!==undefined?{canonical_task_ref:args.canonical_task_ref}:{})};
   }else if(args.action==='link')item.canonical_task_ref=args.canonical_task_ref;
   else if(args.action==='resolve'){
    if(!args.owner_instruction_id&&!args.query_receipt_id)fail(422,'attention_resolution_evidence_required');
    if(args.owner_instruction_id)this.pa.ownerMessage(b,args.owner_instruction_id);
    item.status='resolved';item.checked_watermarks=checked;
   }else{
    this.pa.ownerMessage(b,args.owner_instruction_id);
    item.status=args.action==='dismiss'?'dismissed':'snoozed';
    if(args.action==='snooze'){
     if(typeof args.snoozed_until!=='string'||!Number.isFinite(Date.parse(args.snoozed_until))||Date.parse(args.snoozed_until)<=Date.now())fail(422,'future_snooze_time_required');
     item.snoozed_until=new Date(args.snoozed_until).toISOString();item.schedule_status='pending';delete item.schedule_id;
    }
   }
   if(item.canonical_task_ref)this.task(b,item.canonical_task_ref);
   const after=canonicalJson({kind:item.kind,topic:item.topic,why_now:item.why_now,next_step:item.next_step,prepared_result_refs:item.prepared_result_refs,canonical_task_ref:item.canonical_task_ref??null,status:item.status});
   const unchanged=args.action==='upsert'&&before===after;
   const result=this.persist(b,{...item,revision:item.revision+(unchanged?0:1)},dedup,args.query_receipt_id,args.exploration_batch_id);
   this.db.prepare('INSERT INTO pa_attention_mutations VALUES(?,?,?,?)').run(b.binding_id,args.idempotency_key,payload,canonicalJson(result));
   return result;
  });
 }
 private changeSettings(b:Row,args:Row):Row {
  const current=this.settings(b);if(args.settings===undefined)return current;
  this.pa.ownerMessage(b,args.owner_instruction_id);
  if(args.expected_revision!==current.revision)fail(409,'attention_settings_revision_conflict');
  if(!args.settings||typeof args.settings!=='object'||Array.isArray(args.settings)||Object.keys(args.settings).some(key=>!['mode','quiet_hours','suppressed_topics','daily_budget','batch_budget'].includes(key)))fail(422,'invalid_attention_settings');
  const next={...current,...args.settings,revision:current.revision+1};
  if(!['response_only','prepare','authorized_action'].includes(next.mode))fail(422,'invalid_attention_mode');
  next.suppressed_topics=list(next.suppressed_topics,'suppressed_topics',100);
  for(const name of ['daily_budget','batch_budget'])if(!Number.isSafeInteger(next[name])||next[name]<0||next[name]>1000)fail(422,'invalid_attention_budget');
  if(next.quiet_hours){
   const q=next.quiet_hours;required(q.timezone,'quiet_timezone',100);
   if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(q.start)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(q.end))fail(422,'invalid_quiet_hours');
   try{new Intl.DateTimeFormat('en',{timeZone:q.timezone}).format();}catch{fail(422,'invalid_quiet_timezone');}
  }
  this.db.prepare('INSERT INTO pa_attention_settings VALUES(?,?,?) ON CONFLICT(binding_id) DO UPDATE SET revision=excluded.revision,settings_json=excluded.settings_json').run(b.binding_id,next.revision,canonicalJson(next));
  return next;
 }
 private quiet(settings:Row):boolean {
  if(!settings.quiet_hours)return false;
  const {start,end,timezone}=settings.quiet_hours;
  const time=new Intl.DateTimeFormat('en-GB',{timeZone:timezone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date());
  return start===end||start<end?start===end||time>=start&&time<end:time>=start||time<end;
 }
 private deliveryCheck(b:Row,args:Row):Row {
  const evidence=args.evidence;
  if(evidence?.kind==='direct_request'){
   const message=one(this.db,'SELECT * FROM messages WHERE id=?',evidence.source_message_id);
   if(this.pa.ownerConversation(b,args.conversation_id))this.pa.ownerMessage(b,evidence.source_message_id);
   else if(!message||message.sender_type!=='user'||message.conversation_id!==args.conversation_id||!this.pa.messageAllowed(b,message)||this.pa.sourceFacts(b,message).delivery!=='participant')fail(403,'direct_request_evidence_required');
   return {status:'allowed',classification:'direct_request'};
  }
  if(evidence?.kind==='schedule'){
   if(evidence.owner_ui!==true)this.pa.ownerMessage(b,evidence.source_message_id);required(evidence.schedule_id,'schedule_id',200);
   return {status:'allowed',classification:'schedule'};
  }
  if(evidence?.kind==='task'){
   const task=this.task(b,evidence);
   if(task.assignee?.type!=='agent'||task.assignee?.id!==b.agent_id||['paused','closed'].includes(task.status))fail(403,'task_delivery_evidence_required');
   return {status:'allowed',classification:'task'};
  }
  if(!args.attention_id)return {status:'requires_attention'};
  if(!this.pa.ownerConversation(b,args.conversation_id))fail(403,'attention_private_destination_required');
  const item=this.item(b,args.attention_id);
  if(item.revision!==args.attention_revision)fail(409,'attention_revision_conflict');
  const sent=one(this.db,'SELECT message_id FROM pa_attention_deliveries WHERE item_id=? AND item_revision=? AND message_id IS NOT NULL',item.id,item.revision);
  if(sent)return {status:'already_sent',message_id:sent.message_id};
  const settings=this.settings(b);
  if(!args.feature_enabled||!this.feature(b)||settings.mode==='response_only')return {status:'held',reason:'personal_proactivity_disabled'};
  if(settings.suppressed_topics.includes(item.topic))return {status:'held',reason:'suppressed_topic'};
  if(['dismissed','resolved'].includes(item.status))return {status:'held',reason:item.status};
  if(item.status==='snoozed'&&(item.schedule_status!=='scheduled'||Date.parse(item.snoozed_until)>Date.now()))return {status:'held',reason:'snoozed'};
  if(this.quiet(settings))return {status:'held',reason:'quiet_hours'};
  const checked=item.checked_watermarks;
  const sources=this.sources(b,item.source_refs);
  if(!checked||checked.policy_revision!==this.pa.policy(b.binding_id).revision||sources.some(m=>checked.watermarks[m.conversation_id]!==this.watermark(m.conversation_id)))return {status:'held_for_revalidation'};
  if(item.canonical_task_ref&&['done','closed'].includes(this.task(b,item.canonical_task_ref).status))return {status:'held',reason:'task_completed'};
  return {status:'allowed',classification:'attention',item_id:item.id,item_revision:item.revision};
 }
 /** Classify a host-confirmed live reply or reserve a checked private notification.
  * Args:
  *   b: Trusted binding.
  *   args: Host evidence, target and optional attention revision; evidence is not a model argument.
  * Returns:
  *   A durable reservation or an explicit reason to withhold delivery.
  */
 prepare(b:Row,args:Row):Row {
  required(args.operation_id,'operation_id',200);required(args.conversation_id,'conversation_id',200);
  if(!this.pa.sourceAllowed(b,args.conversation_id,'write'))fail(403,'attention_destination_not_accessible');
  const {request_id:_requestId,...operation}=args;
  const request=canonicalJson(operation),existing=one(this.db,'SELECT * FROM pa_attention_deliveries WHERE operation_id=?',args.operation_id);
  if(existing){
   if(existing.binding_id!==b.binding_id||existing.request_json!==request)fail(409,'attention_delivery_conflict');
   if(existing.message_id)return {status:'already_sent',message_id:existing.message_id,operation_id:args.operation_id};
  }
  const check=this.deliveryCheck(b,args);
  if(check.status!=='allowed')return check;
  const reserved=check.item_id?one(this.db,'SELECT * FROM pa_attention_deliveries WHERE item_id=? AND item_revision=?',check.item_id,check.item_revision):undefined;
  if(reserved&&reserved.operation_id!==args.operation_id)return {status:'pending',operation_id:reserved.operation_id};
  this.db.prepare('INSERT OR IGNORE INTO pa_attention_deliveries VALUES(?,?,?,?,?,?,?,?,?)').run(args.operation_id,b.binding_id,args.conversation_id,check.item_id??null,check.item_revision??null,check.classification,request,null,now());
  return {...check,operation_id:args.operation_id};
 }
 /** Bind publication inside Messaging's insert transaction before any broadcast.
  * Args:
  *   operationId: Host reservation, never an arbitrary model exemption.
  *   messageId: Actual just-inserted message.
  * Returns:
  *   Nothing; invalid or stale reservations abort the message transaction.
  */
 recordPublication(operationId:string,messageId:string):void {
  const delivery=one(this.db,'SELECT * FROM pa_attention_deliveries WHERE operation_id=?',operationId);
  const message=one(this.db,'SELECT * FROM messages WHERE id=?',messageId);
  if(!delivery||!message)fail(409,'attention_delivery_not_committed');
  const b=one(this.db,'SELECT * FROM personal_agent_bindings WHERE binding_id=?',delivery.binding_id)!;
  if(delivery.message_id&&delivery.message_id!==messageId)fail(409,'attention_already_delivered');
  if(message.conversation_id!==delivery.conversation_id||message.sender_user_id!==this.pa.ctx.messaging.agentUser(b.agent_id).id)fail(403,'attention_delivery_message_mismatch');
  this.db.prepare('UPDATE pa_attention_deliveries SET message_id=? WHERE operation_id=?').run(messageId,operationId);
  if(delivery.item_id){
   const interactive=one(this.db,'SELECT registry_json,source FROM message_interactive WHERE message_id=?',messageId);
   this.db.prepare('INSERT OR IGNORE INTO pa_attention_publications VALUES(?,?,?,?,?)').run(messageId,b.binding_id,delivery.item_id,delivery.item_revision,canonicalJson(interactive?{...JSON.parse(interactive.registry_json),source:interactive.source}:{}));
  }
 }
 /** Recheck immediately before insert while the source watermark still excludes our message. */
 beforePublication(operationId:string):void {
  const delivery=one(this.db,'SELECT * FROM pa_attention_deliveries WHERE operation_id=?',operationId);
  if(!delivery)fail(409,'attention_delivery_not_prepared');
  const b=one(this.db,'SELECT * FROM personal_agent_bindings WHERE binding_id=?',delivery.binding_id)!;
  if(delivery.message_id)fail(409,'attention_already_delivered');
  const check=this.deliveryCheck(b,JSON.parse(delivery.request_json));
  if(check.status!=='allowed')fail(409,check.status);
 }
 /** Confirm only the receipt already committed atomically by Messaging. */
 complete(b:Row,args:Row):Row {
  const delivery=one(this.db,'SELECT * FROM pa_attention_deliveries WHERE operation_id=? AND binding_id=?',args.operation_id,b.binding_id);
  if(!delivery?.message_id||delivery.message_id!==args.message_id)fail(409,'attention_delivery_not_committed');
  return {status:'sent',operation_id:delivery.operation_id,message_id:delivery.message_id};
 }
 /** Record the authenticated channel adapter's actual provider receipt after dispatch. */
 completeExternal(b:Row,args:Row):Row {
  const delivery=one(this.db,'SELECT * FROM pa_attention_deliveries WHERE operation_id=? AND binding_id=?',args.operation_id,b.binding_id);
  const chat=delivery&&one(this.db,'SELECT external_source FROM conversations WHERE id=?',delivery.conversation_id);
  if(!delivery||!chat?.external_source||!this.pa.ownerConversation(b,delivery.conversation_id))fail(409,'external_attention_delivery_not_prepared');
  required(args.provider_message_id,'provider_message_id',200);
  const receipt=`external:${args.provider_message_id}`;
  if(delivery.message_id&&delivery.message_id!==receipt)fail(409,'attention_already_delivered');
  this.db.prepare('UPDATE pa_attention_deliveries SET message_id=? WHERE operation_id=?').run(receipt,args.operation_id);
  return {status:'sent',operation_id:args.operation_id,provider_message_id:args.provider_message_id};
 }
 /** Attach a real native schedule receipt; this storage never runs a scheduler. */
 snoozeComplete(b:Row,args:Row):Row {
  const item=this.item(b,args.id);
  if(item.revision!==args.expected_revision||item.status!=='snoozed')fail(409,'attention_revision_conflict');
  if(args.scheduled_at!==item.snoozed_until)fail(409,'attention_schedule_time_mismatch');
  required(args.schedule_id,'schedule_id',200);
  const row=one(this.db,'SELECT dedup_key FROM pa_attention_items WHERE id=?',item.id)!;
  return this.persist(b,{...item,schedule_status:'scheduled',schedule_id:args.schedule_id},row.dedup_key);
 }
}
