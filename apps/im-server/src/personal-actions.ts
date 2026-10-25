import { mergeStatements } from '@openuidev/lang-core';
import { interactiveResponse } from '@nano/product-contracts';
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { all, one, now, fail, transaction, type Row } from './context.js';
import { agentAvailable } from './identity.js';
import { conversationAccess } from './conversation-access.js';
import type { PersonalAgents } from './personal-agent.js';

export const PEER_NOTICE='无法提供主人的私人信息。相关请求已记录，并已通知主人。';
const digest=(value:unknown)=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
/** Freeze proposals and enforce the independent host review at the actual IM write. */
export class PersonalActions {
  constructor(readonly pa:PersonalAgents) {}
  get db(){return this.pa.db;}
  audience(conversationId:string) {return all(this.db,'SELECT user_id FROM conversation_participants WHERE conversation_id=? ORDER BY user_id',conversationId).map(r=>r.user_id);}
  transport(b:Row,conversationId:string,input:Row) {
    const chat=one(this.db,'SELECT * FROM conversations WHERE id=?',conversationId);
    const channel=one(this.db,"SELECT * FROM agent_channels WHERE agent_id=? AND node_id=? AND owner_id=? AND provider=? AND enabled=1 AND json_extract(config_json,'$.app_id')=?",b.agent_id,b.node_id,b.owner_id,input.kind,input.destination?.app_id??'');
    if(chat?.type==='group')fail(409,'external_group_audience_unavailable');
    if(!chat||!channel||chat.config_agent_id!==b.agent_id||chat.external_source!==input.kind||chat.external_chat_id!==input.destination?.source_id||!String(input.destination?.source_id??'').startsWith(`${input.kind}:${input.destination?.app_id}:dm:`)||typeof input.destination?.chat_id!=='string'||!input.destination.chat_id)fail(403,'external_destination_not_verified');
    const actor=`external:${conversationId}:${chat.external_chat_id.slice(`${input.kind}:${input.destination.app_id}:dm:`.length)}`;
    if(one(this.db,'SELECT 1 FROM pa_contact_blocks WHERE binding_id=? AND actor_id=?',b.binding_id,actor))fail(403,'contact_blocked');
    return {kind:input.kind,destination:{app_id:JSON.parse(channel.config_json).app_id,chat_id:input.destination.chat_id,source_id:chat.external_chat_id},channel_id:channel.channel_id,channel_revision:channel.channel_revision,...(input.card?{card:input.card}:{})};
  }
  attachments(b:Row,conversationId:string,items:Row[],content:string) {
    if(!Array.isArray(items)||items.length>5)fail(422,'invalid_attachments');
    const urls=[...items.map(item=>item.url),...content.matchAll(/\/im\/v1\/conversations\/([^/\s]+)\/(images|attachments)\/([\w-]+)/g)].map(value=>typeof value==='string'?value:value[0]);
    const snapshots:Row[]=[];
    for(const url of [...new Set(urls)]) {
      const match=typeof url==='string'&&url.match(/^\/im\/v1\/conversations\/([^/]+)\/(images|attachments)\/([\w-]+)$/);
      if(!match||!this.pa.sourceAllowed(b,match[1]!))fail(403,'attachment_source_not_accessible');
      const resource=one(this.db,'SELECT * FROM message_images WHERE conversation_id=? AND image_id=?',match[1]!,match[3]!);
      if(!resource||!this.pa.ctx.dbPath)fail(409,'attachment_snapshot_unavailable');
      let bytes:Buffer;try{bytes=readFileSync(join(dirname(this.pa.ctx.dbPath),'message-images',resource.storage_name));}catch{fail(409,'attachment_snapshot_unavailable');}
      if(createHash('sha256').update(bytes!).digest('hex')!==resource.sha256)fail(409,'attachment_snapshot_changed');
      const textual=['text/plain','text/markdown','application/json'].includes(resource.content_type);
      if(conversationId!==b.conversation_id&&!textual)fail(409,'attachment_content_review_unavailable');
      snapshots.push({url,conversation_id:resource.conversation_id,resource_id:resource.image_id,sha256:resource.sha256,content_type:resource.content_type,file_name:resource.file_name,byte_size:bytes!.length,...(textual?{text:bytes!.toString('utf8')}:{})});
    }
    return {items:items.map(item=>{const snapshot=snapshots.find(s=>s.url===item.url)!;return {url:snapshot.url,content_type:snapshot.content_type,file_name:snapshot.file_name};}),snapshots};
  }
  recipients(conversationId:string,payload:Row) {return payload.transport?[payload.transport.destination.source_id]:this.audience(conversationId);}
  securityNotice(b:Row,id:string,conversationId:string,content:string) {
    const incident=one(this.db,"SELECT i.* FROM pa_incidents i JOIN messages m ON m.id=i.owner_notice_message_id WHERE i.id=? AND i.binding_id=? AND i.conversation_id=? AND i.status IN ('open','dismissed') AND m.conversation_id=? AND m.delivery_status='completed'",id,b.binding_id,conversationId,b.conversation_id);
    if(!incident||content!==PEER_NOTICE)fail(403,'invalid_security_notice');return incident;
  }
  operation(b:Row,id:string) {
    const op=one(this.db,'SELECT * FROM pa_operations WHERE operation_id=? AND binding_id=?',id,b.binding_id);
    if(!op)fail(404,'proposal_not_found');return op;
  }
  private destination(b:Row,cid:string,payload:Row):void {
    if(!this.pa.sourceAllowed(b,cid,'write'))fail(403,'destination_not_accessible');
    if(payload.representation==='owner') {
      const chat=one(this.db,'SELECT external_source FROM conversations WHERE id=?',cid);
      if(this.pa.ownerConversation(b,cid)||chat?.external_source||payload.transport||payload.task||payload.incident_ref)fail(422,'invalid_owner_representation');
      if(!conversationAccess(this.db,cid,b.owner_user_id)?.can_write)fail(403,'destination_not_accessible');
      if(payload.interactive) {
        const agent=one(this.db,'SELECT * FROM agent_profiles WHERE agent_id=?',b.agent_id);
        if(!agentAvailable(this.db,agent)||!conversationAccess(this.db,cid,this.pa.ctx.messaging.agentUser(b.agent_id).id)?.can_write)fail(403,'owner_interactive_requires_pa_participant');
      }
    } else if(!payload.task&&!payload.transport&&!conversationAccess(this.db,cid,this.pa.ctx.messaging.agentUser(b.agent_id).id)?.can_write)fail(403,'destination_not_accessible');
  }
  private lastOwnerMessage(b:Row,cid:string):string|null {
    return one(this.db,"SELECT m.id FROM messages m WHERE m.conversation_id=? AND m.sender_user_id=? AND NOT EXISTS(SELECT 1 FROM pa_delegated_messages d WHERE d.message_id=m.id AND d.representation_operation_id IS NOT NULL) ORDER BY m.rowid DESC LIMIT 1",cid,b.owner_user_id)?.id??null;
  }
  validate(b:Row,op:Row) {
    const frozen=JSON.parse(op.payload_json);
    this.destination(b,op.conversation_id,frozen);
    const profile=one(this.db,'SELECT profile_version FROM agent_profiles WHERE agent_id=?',b.agent_id);
    if(profile?.profile_version!==JSON.parse(op.evidence_json).agent_profile_version)fail(409,'capability_policy_changed');
    const checkedAttachments=this.attachments(b,op.conversation_id,frozen.attachments,frozen.content+(frozen.interactive?.source??''));
    if(JSON.stringify(checkedAttachments.snapshots)!==JSON.stringify(frozen.attachment_snapshots))fail(409,'attachment_snapshot_changed');
    if(frozen.task && frozen.task.action !== 'create') {
      const graph=one(this.db,'SELECT revision,conversation_id FROM task_graphs WHERE graph_id=?',frozen.task.arguments.graph_id);
      if(!graph||graph.revision!==JSON.parse(op.evidence_json).task_revision||graph.conversation_id!==op.conversation_id)fail(409,'task_revision_changed');
    }
    if(this.pa.authorizationGuard(b)!==JSON.parse(op.evidence_json).owner_guard)fail(409,'owner_authorization_changed');
    if(frozen.incident_ref)this.securityNotice(b,frozen.incident_ref,op.conversation_id,frozen.content);
    if(frozen.transport && JSON.stringify(this.transport(b,op.conversation_id,frozen.transport))!==JSON.stringify(frozen.transport))fail(409,'external_destination_changed');
    const policy=one(this.db,'SELECT * FROM pa_policies WHERE binding_id=?',b.binding_id)!;
    if(policy.revision!==op.policy_revision || policy.disclosure_revision!==op.disclosure_revision)fail(409,'proposal_requires_review');
    if(JSON.stringify(this.recipients(op.conversation_id,frozen))!==op.audience_json)fail(409,'audience_changed');
    if(one(this.db,'SELECT type FROM conversations WHERE id=?',op.conversation_id)?.type !== 'group' && this.audience(op.conversation_id).some(id=>this.pa.actorRisk(b,id)))fail(403,'contact_blocked');
    for(const source of JSON.parse(op.evidence_json).sources??[])if(this.pa.sourceAllowed(b,source.conversation_id)!==source.allowed)fail(409,'source_revoked');
    // An owner reply after preparation invalidates the decision to interject.
    const last=this.lastOwnerMessage(b,op.conversation_id);
    if(last!==JSON.parse(op.evidence_json).last_owner_message_id)fail(409,'owner_already_replied');
  }
  prepare(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args);
    if(args.reply_draft!==undefined)fail(422,'reply_draft is retired; use ComposeMessage');
    if(args.network) fail(422,'unsupported_disclosure_kind');
    if(args.representation!==undefined&&!['self','owner'].includes(args.representation))fail(422,'invalid_representation');
    if(args.representation==='owner'&&(args.task||args.transport||args.incident_ref))fail(422,'invalid_owner_representation');
    if(args.task) {
      const command=args.task;
      if(!['create','apply','delete'].includes(command.action)||!command.arguments||typeof command.arguments!=='object')fail(422,'invalid_task_proposal');
      const graph=command.action==='create'?undefined:one(this.db,'SELECT * FROM task_graphs WHERE graph_id=?',command.arguments.graph_id);
      const destination=command.action==='create'?command.arguments.conversation_id:graph?.conversation_id;
      if(!destination||!this.pa.sourceAllowed(b,destination,'write'))fail(403,'destination_not_accessible');
      if(command.arguments.conversation_id&&command.arguments.conversation_id!==destination)fail(422,'task_conversation_mismatch');
      if(destination===b.conversation_id)return {owner_private:true,conversation_id:destination};
      args={...args,conversation_id:destination,content:'Shared task change',task:{action:command.action,arguments:command.arguments,...(command.source_message_id?{source_message_id:command.source_message_id}:{})}};
    }
    if(typeof args.request_key!=='string'||!args.request_key||typeof args.content!=='string'||!args.content.trim())fail(422,'concrete_proposal_required');
    if(!this.pa.sourceAllowed(b,args.conversation_id,'write'))fail(403,'destination_not_accessible');
    if(args.transport&&args.attachments?.length)fail(409,'external_attachment_adapter_unavailable');
    let interactive;try{interactive=interactiveResponse(args.interactive);}catch(error){fail(422,(error as Error).message);}
    if(interactive?.source_mode==='patch') {
      const original=this.pa.ctx.messaging.interactions.source(interactive.supersedes_message_id!,args.conversation_id);
      if(original.executor_agent_id!==b.agent_id)fail(403,'interactive_source_not_accessible');
      const {source_mode,...publication}=interactive;
      interactive={...publication,source:mergeStatements(original.source,interactive.source)};
    }
    if(args.incident_ref&&(interactive||args.attachments?.length||args.task))fail(403,'invalid_security_notice');
    const attachments=this.attachments(b,args.conversation_id,args.attachments??[],args.content+(interactive?.source??''));
    const securityNotice=args.incident_ref?this.securityNotice(b,args.incident_ref,args.conversation_id,args.content):undefined;
    const payload={representation:args.representation??'self',content:args.content,attachments:attachments.items,attachment_snapshots:attachments.snapshots,...(args.task?{task:args.task}:{}),...(interactive?{interactive}:{}),...(securityNotice?{incident_ref:securityNotice.id}:{}),...(args.transport?{transport:this.transport(b,args.conversation_id,args.transport)}:{})}, hash=digest(payload);
    if(payload.transport && this.pa.ownerConversation(b,args.conversation_id))return {owner_private:true,conversation_id:args.conversation_id};
    this.destination(b,args.conversation_id,payload);
    const previous=one(this.db,'SELECT * FROM pa_operations WHERE binding_id=? AND request_key=?',b.binding_id,args.request_key);
    if(previous) {
      const oldPayload=JSON.parse(previous.payload_json);
      const samePayload=previous.payload_digest===hash || oldPayload.representation===undefined && digest({representation:'self',...oldPayload})===hash;
      if(!samePayload||previous.conversation_id!==args.conversation_id)fail(409,'operation_key_content_conflict');
      if(['confirmed','sending','unknown','deny','needs_owner'].includes(previous.state)) {
        if(['deny','needs_owner'].includes(previous.state))this.validate(b,previous);
        return {...this.project(previous),message_id:previous.message_id,result:previous.result_json?JSON.parse(previous.result_json):undefined,conversation_id:previous.conversation_id};
      }
    }
    const policy=one(this.db,'SELECT * FROM pa_policies WHERE binding_id=?',b.binding_id)!;
    // The runtime supplies actual read bodies. IM contributes only current access facts.
    const sources=all(this.db,'SELECT DISTINCT conversation_id FROM pa_source_reads WHERE binding_id=? ORDER BY conversation_id',b.binding_id)
      .map(source=>({...source,allowed:this.pa.sourceAllowed(b,source.conversation_id)}));
    const chat=one(this.db,'SELECT id,title,type,external_source FROM conversations WHERE id=?',args.conversation_id)!;
    const evidence={agent_profile_version:one(this.db,'SELECT profile_version FROM agent_profiles WHERE agent_id=?',b.agent_id)!.profile_version,
      owner_guard:this.pa.authorizationGuard(b),policy:this.pa.policy(b.binding_id),
      owner_user_id:b.owner_user_id,
      recipient:{conversation_id:chat.id,name:chat.title,conversation_type:chat.type,channel:chat.external_source??'web',members:this.pa.ctx.messaging.members(chat.id).map(member=>this.pa.ctx.messaging.actor(member))},
      ...(args.task&&args.task.action!=='create'?{task_revision:one(this.db,'SELECT revision FROM task_graphs WHERE graph_id=?',args.task.arguments.graph_id)?.revision}:{}),
      ...(securityNotice?{security_notice:{content:PEER_NOTICE,owner_notice_message_id:securityNotice.owner_notice_message_id}}:{}),
      recipient_risks:this.audience(args.conversation_id).flatMap(id=>{const risk=this.pa.actorRisk(b,id);return risk?[risk]:[];}),
      recipient_ids:this.recipients(args.conversation_id,payload),external_destination:payload.transport?.destination??null,payload,sources,
      last_owner_message_id:this.lastOwnerMessage(b,args.conversation_id)};
    // Unsent operations may refresh review evidence, but never reuse a prior permit.
    // Consumed or uncertain operations above keep their original delivery identity.
    if(previous) {
      const refreshed={...previous,policy_revision:policy.revision,disclosure_revision:policy.disclosure_revision,audience_json:JSON.stringify(evidence.recipient_ids),evidence_json:JSON.stringify(evidence)};
      this.validate(b,refreshed);
      this.db.prepare("UPDATE pa_operations SET policy_revision=?,disclosure_revision=?,audience_json=?,evidence_json=?,state='prepared',verdict_json=NULL,verdict_ref=NULL,expires_at=NULL WHERE operation_id=?").run(refreshed.policy_revision,refreshed.disclosure_revision,refreshed.audience_json,refreshed.evidence_json,previous.operation_id);
      return this.project(this.operation(b,previous.operation_id));
    }
    const id=randomUUID();
    this.db.prepare(`INSERT INTO pa_operations(operation_id,binding_id,request_key,policy_revision,disclosure_revision,conversation_id,audience_json,payload_json,payload_digest,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)`).run(id,b.binding_id,args.request_key,policy.revision,policy.disclosure_revision,args.conversation_id,JSON.stringify(evidence.recipient_ids),JSON.stringify(payload),hash,JSON.stringify(evidence),now());
    return this.project(this.operation(b,id));
  }
  project(op:Row){return {proposal_ref:op.operation_id,payload_digest:op.payload_digest,evidence_digest:digest({evidence:op.evidence_json,policy:op.policy_revision,disclosure:op.disclosure_revision}),evidence:JSON.parse(op.evidence_json),policy_revision:op.policy_revision,disclosure_revision:op.disclosure_revision,state:op.state};}
  review(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args),op=this.operation(b,args.proposal_ref);
    this.validate(b,op);
    if(op.state==='confirmed')return {state:op.state,verdict_ref:null};
    if(args.evidence_digest!==this.project(op).evidence_digest)fail(409,'review_evidence_changed');
    if(args.payload_digest!==op.payload_digest||!['allow','deny','needs_owner','unavailable'].includes(args.verdict?.decision))fail(422,'invalid_independent_verdict');
    const ref=args.verdict.decision==='allow'?randomUUID():null,state=args.verdict.decision==='allow'?'allowed':args.verdict.decision;
    this.db.prepare('UPDATE pa_operations SET verdict_json=?,verdict_ref=?,expires_at=?,state=? WHERE operation_id=?').run(JSON.stringify(args.verdict),ref,new Date(Date.now()+60000).toISOString(),state,op.operation_id);
    return {verdict_ref:ref,state};
  }
  /** Verify native schedule evidence before entering the reviewed write transaction. */
  async commitChecked(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args),initial=this.operation(b,args.proposal_ref);
    if(initial.state==='confirmed')return this.commit(principal,args);
    this.validate(b,initial);
    if(initial.state!=='allowed'||!initial.verdict_ref||initial.verdict_ref!==args.verdict_ref||initial.expires_at<now())fail(403,'independent_review_required');
    const original=JSON.parse(initial.payload_json).task;
    const waits=original?await this.pa.ctx.gateway.tasks.prepareWaits({kind:'agent',id:b.agent_id,node_id:b.node_id},original.action,original.arguments,{ownerUserId:b.owner_user_id,sourceAllowed:id=>this.pa.sourceAllowed(b,id)}):[];
    return this.commit(principal,args,waits);
  }
  commit(principal:Row,args:Row,waits:{node_id:string;wait:Row}[] = []) {
    const b=this.pa.authority(principal,args), initial=this.operation(b,args.proposal_ref);
    if(initial.state==='confirmed')return {state:'confirmed',message_id:initial.message_id,result:initial.result_json?JSON.parse(initial.result_json):undefined,conversation_id:initial.conversation_id};
    if(['sending','unknown'].includes(initial.state))return {state:'unknown',conversation_id:initial.conversation_id};
    const original=JSON.parse(initial.payload_json).task;
    const taskService=this.pa.ctx.gateway.tasks;
    const hint=original?taskService.changeHint(original.arguments.graph_id):undefined;
    const notices:Row[]=[];
    const result=transaction(this.db,()=>{
      const op=this.operation(b,args.proposal_ref);this.validate(b,op);
      if(op.state!=='allowed'||!op.verdict_ref||op.verdict_ref!==args.verdict_ref||op.expires_at<now())fail(403,'independent_review_required');
      const payload=JSON.parse(op.payload_json),s=this.pa.ctx.messaging;
      if(payload.task) {
        const task=payload.task;
        const result=this.pa.ctx.gateway.tasks.executeDelegated({kind:'agent',id:b.agent_id,node_id:b.node_id,source_message_id:task.source_message_id},b.owner_user_id,task.action,task.arguments,notices,waits);
        this.db.prepare("UPDATE pa_operations SET state='confirmed',result_json=?,verdict_ref=NULL WHERE operation_id=?").run(JSON.stringify(result),op.operation_id);
        this.db.prepare('UPDATE pa_policies SET disclosure_revision=disclosure_revision+1 WHERE binding_id=?').run(b.binding_id);
        return {state:'confirmed',conversation_id:op.conversation_id,result};
      }
      if(payload.transport) {
        this.db.prepare("UPDATE pa_operations SET state='sending',verdict_ref=NULL WHERE operation_id=?").run(op.operation_id);
        this.db.prepare('UPDATE pa_policies SET disclosure_revision=disclosure_revision+1 WHERE binding_id=?').run(b.binding_id);
        return {state:'sending',conversation_id:op.conversation_id,payload};
      }
      const rewrite=(value:string)=>value.replace(/\/im\/v1\/conversations\/([^/\s]+)\/(images|attachments)\/([\w-]+)/g,(url:string,source:string)=>s.copyReferences(source,op.conversation_id,url));
      const owner=payload.representation==='owner';
      const message=s.insertMessage(op.conversation_id,owner?b.owner_user_id:s.agentUser(b.agent_id).id,owner?'user':'agent',rewrite(payload.content),payload.attachments.map((a:Row)=>({...a,url:rewrite(a.url)})),`pa:${op.operation_id}`,'completed',{publish:false,interactive:payload.interactive,
        ...(op.conversation_id!==b.conversation_id?{personal_source:{...b,operation_id:owner?op.operation_id:null}}:{})});
      if(owner)s.queueRepresentedRelays(message,b.agent_id);
      else {s.queueDirectAgentRelays(message);this.pa.ctx.gateway.groupReply(message.id,{deferDelivery:true});}
      this.db.prepare("UPDATE pa_operations SET state='confirmed',message_id=?,verdict_ref=NULL WHERE operation_id=?").run(message.id,op.operation_id);
      if(payload.incident_ref)this.db.prepare('UPDATE pa_incidents SET peer_notice_message_id=? WHERE id=?').run(message.id,payload.incident_ref);
      this.db.prepare('UPDATE pa_policies SET disclosure_revision=disclosure_revision+1 WHERE binding_id=?').run(b.binding_id);
      return {state:'confirmed',message_id:message.id,conversation_id:op.conversation_id};
    });
    if(result.state==='sending')return result;
    if('result' in result){taskService.notifyChange(hint,result.result?.graph_id);this.pa.ctx.messaging.publishMessages(notices);return result;}
    const m=this.pa.ctx.messaging.message(result.message_id!);
    // Message, events and relays are durable; transport failure cannot revoke this receipt.
    // The existing delivery timer/reconnect path drains the queued Agent recipients.
    try {this.pa.ctx.messaging.publishMessages([m],{deferDelivery:true});} catch { /* Browser events replay on reconnect. */ }
    return result;
  }
  complete(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args),op=this.operation(b,args.proposal_ref);
    const payload=JSON.parse(op.payload_json);
    if(!payload.transport || !['sending','unknown','confirmed'].includes(op.state))fail(409,'external_send_not_started');
    if(op.state==='confirmed')return {state:'confirmed',provider_message_id:op.message_id};
    if(!['confirmed','unknown'].includes(args.state)||(args.state==='confirmed'&&!args.provider_message_id))fail(422,'provider_receipt_required');
    this.db.prepare('UPDATE pa_operations SET state=?,message_id=? WHERE operation_id=?').run(args.state,args.provider_message_id??null,op.operation_id);
    const incident=JSON.parse(op.payload_json).incident_ref;
    if(incident&&args.state==='confirmed')this.db.prepare('UPDATE pa_incidents SET peer_notice_message_id=? WHERE id=?').run(args.provider_message_id,incident);
    return {state:args.state,provider_message_id:args.provider_message_id??null};
  }
}
