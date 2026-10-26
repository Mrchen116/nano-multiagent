import { expect, it } from 'vitest';
import { personalFixture } from './personal-fixture.js';

function setup() {
 const f=personalFixture();
 f.db.prepare("UPDATE agent_profiles SET features_json=json_set(features_json,'$.personal_proactivity',json('true'))").run();
 const call=(type:string,extra:Record<string,unknown>={})=>f.service.handle(f.principal,type,{...f.args,...extra});
 const command=(extra:Record<string,unknown>)=>call('pa.attention',{exploration_batch_id:'host-session:turn-1',...extra});
 const source=f.ctx.messaging.insertMessage('peer','u1','user','I will send the proposal tomorrow');
 const owner=f.ctx.messaging.insertMessage('chat','u1','user','Prepare privately and remind me about this');
 const query=()=>call('pa.context.query',{conversation_ids:['peer']});
 const candidate=async()=>command({action:'upsert',kind:'commitment',topic:'proposal',why_now:'due tomorrow',next_step:'prepare outline',source_refs:[source.id],query_receipt_id:(await query()).receipt_id,idempotency_key:'candidate'});
 return {...f,call,command,source,owner,query,candidate};
}

it('keeps context pagination separate from Inbox and never turns partial or revoked reads into complete coverage',async()=>{
 const f=setup();
 f.ctx.messaging.insertMessage('peer','u2','user','Already sent, thank you');
 const before=f.service.observations(f.principal,f.args).items;
 const first=await f.call('pa.context.query',{conversation_ids:['peer'],limit:1});
 expect(first.source_coverage.status).toBe('partial');expect(first.next_cursor).toBeTruthy();
 const second=await f.call('pa.context.query',{cursor:first.next_cursor,limit:1});
 expect(second.source_coverage.status).toBe('complete');
 expect(second.messages[0].content).toContain('Already sent');
 expect(f.service.observations(f.principal,f.args).items).toEqual(before);
 f.service.updatePolicy('o1',{expected_revision:1,excluded_conversation_ids:['peer']});
 await expect(f.call('pa.context.query',{cursor:first.next_cursor})).rejects.toThrow('context_cursor_invalidated');
 const revoked=await f.call('pa.context.query',{conversation_ids:['peer']});
 expect(revoked.messages).toEqual([]);expect(revoked.source_coverage.status).toBe('partial');
});

it('deduplicates candidates independently of caller keys and enforces latest sources and revisions',async()=>{
 const f=setup(),item=await f.candidate();
 const duplicate=await f.command({action:'upsert',kind:'commitment',topic:'proposal',why_now:'due tomorrow',next_step:'prepare outline',source_refs:[f.source.id],idempotency_key:'different'});
 expect(duplicate.id).toBe(item.id);expect(duplicate.revision).toBe(item.revision);
 await expect(f.command({action:'upsert',id:item.id,expected_revision:0,why_now:'changed',idempotency_key:'stale'})).rejects.toThrow('attention_revision_conflict');
 f.ctx.messaging.insertMessage('peer','u2','user','Resolved this already');
 expect(await f.call('pa.attention.delivery.prepare',{operation_id:'send',conversation_id:'chat',attention_id:item.id,attention_revision:item.revision,feature_enabled:true})).toMatchObject({status:'held_for_revalidation'});
 f.service.updatePolicy('o1',{expected_revision:1,excluded_conversation_ids:['peer']});
 await expect(f.command({action:'get',id:item.id})).rejects.toThrow('attention_source_not_accessible');
});

it('requires attention without current host evidence and applies quiet/feature policy only to exploration',async()=>{
 const f=setup();
 expect(await f.call('pa.attention.delivery.prepare',{operation_id:'none',conversation_id:'chat',feature_enabled:true})).toMatchObject({status:'requires_attention'});
 const settings=await f.command({action:'settings'});
 await f.command({action:'settings',expected_revision:settings.revision,owner_instruction_id:f.owner.id,settings:{quiet_hours:{start:'00:00',end:'00:00',timezone:'UTC'}}});
 const item=await f.candidate();
 expect(await f.call('pa.attention.delivery.prepare',{operation_id:'quiet',conversation_id:'chat',attention_id:item.id,attention_revision:item.revision,feature_enabled:true})).toMatchObject({status:'held',reason:'quiet_hours'});
 expect(await f.call('pa.attention.delivery.prepare',{operation_id:'direct',conversation_id:'chat',evidence:{kind:'direct_request',source_message_id:f.owner.id}})).toMatchObject({status:'allowed',classification:'direct_request'});
 expect(await f.call('pa.attention.delivery.prepare',{operation_id:'schedule',conversation_id:'chat',evidence:{kind:'schedule',source_message_id:f.owner.id,schedule_id:'actual-host-schedule'}})).toMatchObject({status:'allowed',classification:'schedule'});
 await expect(f.call('pa.attention.delivery.prepare',{operation_id:'fake',conversation_id:'chat',evidence:{kind:'direct_request',source_message_id:f.source.id}})).rejects.toThrow('direct_owner_evidence_required');
});

it('ties sent receipts to real owner messages and refuses duplicate delivery after completion',async()=>{
 const f=setup(),item=await f.candidate();
 const args={operation_id:'send',conversation_id:'chat',attention_id:item.id,attention_revision:item.revision,feature_enabled:true};
 expect(await f.call('pa.attention.delivery.prepare',args)).toMatchObject({status:'allowed'});
 await expect(f.call('pa.attention.delivery.complete',{operation_id:'send',message_id:'invented'})).rejects.toThrow('attention_delivery_not_committed');
 const message=f.ctx.messaging.insertMessage('chat','a1','agent','Prepared outline',[],'send','completed',{personal_delivery_operation_id:'send'});
 expect(await f.call('pa.attention.delivery.complete',{operation_id:'send',message_id:message.id})).toMatchObject({status:'sent',message_id:message.id});
 expect(await f.call('pa.attention.delivery.prepare',args)).toMatchObject({status:'already_sent',message_id:message.id});
 expect(await f.call('pa.attention.delivery.prepare',{...args,operation_id:'duplicate'})).toMatchObject({status:'already_sent',message_id:message.id});
});

it('snoozes with an explicit pending schedule receipt, and single dismissal does not suppress its topic',async()=>{
 const f=setup(),item=await f.candidate(),until=new Date(Date.now()+3600000).toISOString();
 const snoozed=await f.command({action:'snooze',id:item.id,expected_revision:1,idempotency_key:'later',owner_instruction_id:f.owner.id,snoozed_until:until});
 expect(snoozed).toMatchObject({status:'snoozed',schedule_status:'pending'});
 expect(await f.call('pa.attention.snooze.complete',{id:item.id,expected_revision:snoozed.revision,schedule_id:'native-1',scheduled_at:until})).toMatchObject({schedule_status:'scheduled'});
 const dismissed=await f.command({action:'dismiss',id:item.id,expected_revision:snoozed.revision,idempotency_key:'dismiss',owner_instruction_id:f.owner.id});
 expect(dismissed.status).toBe('dismissed');expect((await f.command({action:'settings'})).suppressed_topics).toEqual([]);
});

it('preserves notification revision on revalidation with no business change and applies exploration budgets',async()=>{
 const f=setup(),item=await f.candidate();
 const revalidated=await f.command({action:'upsert',id:item.id,expected_revision:item.revision,idempotency_key:'read-again',query_receipt_id:(await f.query()).receipt_id});
 expect(revalidated.revision).toBe(item.revision);
 const settings=await f.command({action:'settings'});
 await f.command({action:'settings',expected_revision:settings.revision,owner_instruction_id:f.owner.id,settings:{daily_budget:1}});
 await expect(f.command({action:'upsert',source_refs:[f.source.id],kind:'opportunity',topic:'other',why_now:'another opportunity',next_step:'research',idempotency_key:'over-budget'})).rejects.toThrow('attention_budget_exhausted');
 await expect(f.command({action:'settings',expected_revision:2,owner_instruction_id:f.source.id,settings:{suppressed_topics:['proposal']}})).rejects.toThrow('direct_owner_evidence_required');
});

it('binds original card revisions and deduplicates a logical click across caller keys',async()=>{
 const f=setup(),item=await f.candidate();
 await f.call('pa.attention.delivery.prepare',{operation_id:'card',conversation_id:'chat',attention_id:item.id,attention_revision:item.revision,feature_enabled:true});
 const card=f.ctx.messaging.insertMessage('chat','a1','agent','Outline ready',[],'card','completed',{personal_delivery_operation_id:'card',interactive:{format:'openui',catalog_version:'nano-1',source:'root = Stack([ContinueButton("dismiss", "Ignore this"), ContinueButton("later", "Later")])'}});
 const submit=(key:string,action='dismiss')=>f.ctx.messaging.sendMessage({headers:{'x-user':'u1','idempotency-key':key},params:{conversation_id:'chat'},query:{},body:{sender_user_id:'u1',interaction_reply:{source_message_id:card.id,action_id:action,state:{}}}} as any);
 const first=await submit('device-one'),duplicate=await submit('device-two');
 expect(duplicate.id).toBe(first.id);
 const changed=await f.command({action:'dismiss',id:item.id,expected_revision:1,idempotency_key:'dismiss-business',owner_instruction_id:first.id});
 expect(changed.revision).toBe(2);
 expect((await submit('device-three')).id).toBe(first.id);
 await expect(submit('new-action','later')).rejects.toThrow('attention_revision_conflict');
 await expect(f.command({action:'snooze',id:item.id,expected_revision:2,idempotency_key:'pretend-current',owner_instruction_id:first.id,snoozed_until:new Date(Date.now()+3600000).toISOString()})).rejects.toThrow('attention_revision_conflict');
});

it('validates canonical Task links and checks latest Task completion before delivery',async()=>{
 const f=setup();
 const {TaskGraphService}=await import('../src/task-graphs.js');
 const tasks=new TaskGraphService(f.db,f.ctx.messaging);
 const graph=tasks.execute({kind:'user',id:'u1'},'create',{conversation_id:'peer',title:'Proposal',mode:'dag',request_key:'create-proposal'});
 const item=await f.candidate();
 const linked=await f.command({action:'link',id:item.id,expected_revision:item.revision,idempotency_key:'link',canonical_task_ref:{graph_id:graph.graph_id,node_id:graph.root_node_id}});
 expect(linked.canonical_task_ref.graph_id).toBe(graph.graph_id);
 expect(await f.call('pa.context.query',{conversation_ids:['peer'],task_refs:[linked.canonical_task_ref]})).toMatchObject({tasks:[{status:'todo'}]});
 tasks.execute({kind:'user',id:'u1'},'apply',{graph_id:graph.graph_id,base_revision:graph.revision,request_key:'complete',change_note:'Actually sent',operations:[{op:'update_task',node_id:graph.root_node_id,patch:{status:'done'}}]});
 const updated=await f.command({action:'upsert',id:item.id,expected_revision:linked.revision,idempotency_key:'refresh',query_receipt_id:(await f.query()).receipt_id});
 expect(await f.call('pa.attention.delivery.prepare',{operation_id:'completed-task',conversation_id:'chat',attention_id:item.id,attention_revision:updated.revision,feature_enabled:true})).toMatchObject({status:'held',reason:'task_completed'});
 await expect(f.command({action:'link',id:item.id,expected_revision:updated.revision,idempotency_key:'bad-link',canonical_task_ref:{graph_id:'missing',node_id:'n1'}})).rejects.toThrow('not accessible');
 expect((await f.command({action:'get',id:item.id})).canonical_task_ref).toEqual(linked.canonical_task_ref);
});
