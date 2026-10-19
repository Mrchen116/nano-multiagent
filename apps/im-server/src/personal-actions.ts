import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { all, one, now, fail, transaction, type Row } from './context.js';
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
  recipients(conversationId:string,payload:Row) {return payload.network?[`network:${new URL(payload.network.url).origin}`]:payload.transport?[payload.transport.destination.source_id]:this.audience(conversationId);}
  securityNotice(b:Row,id:string,conversationId:string,content:string) {
    const incident=one(this.db,"SELECT i.* FROM pa_incidents i JOIN messages m ON m.id=i.owner_notice_message_id WHERE i.id=? AND i.binding_id=? AND i.conversation_id=? AND i.status='open' AND m.conversation_id=? AND m.delivery_status='completed'",id,b.binding_id,conversationId,b.conversation_id);
    if(!incident||content!==PEER_NOTICE)fail(403,'invalid_security_notice');return incident;
  }
  operation(b:Row,id:string) {
    const op=one(this.db,'SELECT * FROM pa_operations WHERE operation_id=? AND binding_id=?',id,b.binding_id);
    if(!op)fail(404,'proposal_not_found');return op;
  }
  validate(b:Row,op:Row) {
    if(!this.pa.sourceAllowed(b,op.conversation_id,'write'))fail(403,'destination_not_accessible');
    const frozen=JSON.parse(op.payload_json);
    const profile=one(this.db,'SELECT profile_version FROM agent_profiles WHERE agent_id=?',b.agent_id);
    if(profile?.profile_version!==JSON.parse(op.evidence_json).agent_profile_version)fail(409,'capability_policy_changed');
    const checkedAttachments=this.attachments(b,op.conversation_id,frozen.attachments,frozen.content);
    if(JSON.stringify(checkedAttachments.snapshots)!==JSON.stringify(frozen.attachment_snapshots))fail(409,'attachment_snapshot_changed');
    if(frozen.task) {
      const graph=one(this.db,'SELECT revision,conversation_id FROM task_graphs WHERE graph_id=?',frozen.task.graph_id);
      if(!graph||graph.revision!==frozen.task.base_revision||graph.conversation_id!==op.conversation_id)fail(409,'task_revision_changed');
    }
    if(frozen.incident_ref)this.securityNotice(b,frozen.incident_ref,op.conversation_id,frozen.content);
    if(frozen.transport && JSON.stringify(this.transport(b,op.conversation_id,frozen.transport))!==JSON.stringify(frozen.transport))fail(409,'external_destination_changed');
    const policy=one(this.db,'SELECT * FROM pa_policies WHERE binding_id=?',b.binding_id)!;
    if(policy.revision!==op.policy_revision || policy.disclosure_revision!==op.disclosure_revision)fail(409,'proposal_requires_review');
    if(JSON.stringify(this.recipients(op.conversation_id,frozen))!==op.audience_json)fail(409,'audience_changed');
    if(this.audience(op.conversation_id).some(id=>one(this.db,'SELECT 1 FROM pa_contact_blocks WHERE binding_id=? AND actor_id=?',b.binding_id,id)))fail(403,'contact_blocked');
    if(op.scope_id) {
      const scope=one(this.db,'SELECT * FROM pa_goal_scopes WHERE scope_id=? AND binding_id=?',op.scope_id,b.binding_id);
      if(!scope||scope.revoked||scope.revision!==op.scope_revision)fail(409,'scope_changed');
      const expires=JSON.parse(scope.scope_json).expires_at;if(expires && (!Number.isFinite(Date.parse(expires))||Date.parse(expires)<=Date.now()))fail(409,'scope_expired');
      const assistance=one(this.db,'SELECT * FROM pa_assistance WHERE binding_id=? AND task_ref=?',b.binding_id,op.task_ref);
      if(assistance?.paused)fail(409,'goal_paused');
      const graph=one(this.db,'SELECT document_json FROM task_graphs WHERE graph_id=?',op.task_ref);
      if(graph){const d=JSON.parse(graph.document_json);if(['done','closed'].includes(d.nodes.find((n:Row)=>n.id===d.root_node_id)?.status))fail(409,'goal_ended');}
    }
    for(const source of JSON.parse(op.evidence_json).sources??[])if(!this.pa.sourceAllowed(b,source.conversation_id))fail(409,'source_revoked');
    // An owner reply after preparation invalidates the decision to interject.
    const last=one(this.db,"SELECT id FROM messages WHERE conversation_id=? AND sender_user_id=? ORDER BY rowid DESC LIMIT 1",op.conversation_id,b.owner_user_id)?.id??null;
    if(last!==JSON.parse(op.evidence_json).last_owner_message_id)fail(409,'owner_already_replied');
  }
  prepare(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args);
    if(args.task) {
      const graph=one(this.db,'SELECT * FROM task_graphs WHERE graph_id=?',args.task.graph_id);
      if(!graph||!args.task.patch||Object.keys(args.task.patch).some(k=>!['status','result'].includes(k))||!Object.keys(args.task.patch).length||!Number.isInteger(args.task.base_revision))fail(422,'invalid_task_proposal');
      args={...args,task_ref:args.task_ref??graph.graph_id,conversation_id:graph.conversation_id,content:'Task result update',task:{graph_id:graph.graph_id,node_id:args.task.node_id,base_revision:args.task.base_revision,patch:args.task.patch}};
    }
    if(args.network) {
      let url:URL;try{url=new URL(args.network.url);}catch{fail(422,'invalid_network_proposal');}
      if(!['http:','https:'].includes(url!.protocol)||url!.username||url!.password||typeof args.network.method!=='string')fail(422,'invalid_network_proposal');
      args={...args,conversation_id:b.conversation_id,content:'Network request',network:{url:url!.href,method:args.network.method.toUpperCase(),requestDigest:args.network.requestDigest,headerNames:args.network.headerNames,...(args.network.query!==undefined?{query:args.network.query}:{}),...(args.network.body!==undefined?{body:args.network.body}:{}),...(args.network.headers!==undefined?{headers:args.network.headers}:{})}};
    }
    if(typeof args.request_key!=='string'||!args.request_key||typeof args.content!=='string'||!args.content.trim())fail(422,'concrete_proposal_required');
    if(!this.pa.sourceAllowed(b,args.conversation_id,'write'))fail(403,'destination_not_accessible');
    if(args.transport&&args.attachments?.length)fail(409,'external_attachment_adapter_unavailable');
    const attachments=this.attachments(b,args.conversation_id,args.attachments??[],args.content);
    const securityNotice=args.incident_ref?this.securityNotice(b,args.incident_ref,args.conversation_id,args.content):undefined;
    const payload={content:args.content,attachments:attachments.items,attachment_snapshots:attachments.snapshots,...(args.task?{task:args.task}:{}),...(args.network?{network:args.network}:{}),...(securityNotice?{incident_ref:securityNotice.id}:{}),...(args.transport?{transport:this.transport(b,args.conversation_id,args.transport)}:{})}, hash=digest(payload);
    const previous=one(this.db,'SELECT * FROM pa_operations WHERE binding_id=? AND request_key=?',b.binding_id,args.request_key);
    if(previous) {
      if(previous.payload_digest!==hash||previous.conversation_id!==args.conversation_id)fail(409,'operation_key_content_conflict');
      if(['confirmed','sending','unknown','deny','needs_owner'].includes(previous.state)) {
        if(['deny','needs_owner'].includes(previous.state))this.validate(b,previous);
        return {...this.project(previous),message_id:previous.message_id,result:previous.result_json?JSON.parse(previous.result_json):undefined,conversation_id:previous.conversation_id};
      }
    }
    const ownerOnly=args.conversation_id===b.conversation_id;
    const scope=args.task_ref?one(this.db,'SELECT * FROM pa_goal_scopes WHERE binding_id=? AND task_ref=? AND revoked=0',b.binding_id,args.task_ref):undefined;
    if(scope && one(this.db,'SELECT paused FROM pa_assistance WHERE binding_id=? AND task_ref=?',b.binding_id,args.task_ref)?.paused) fail(409,'goal_paused');
    if(!ownerOnly&&!securityNotice) {
      if(!scope)fail(403,'goal_scope_required');
      const allowed=JSON.parse(scope.scope_json);
      if(!allowed.allowed_conversation_ids.includes(args.conversation_id)||!allowed.allowed_action_kinds.includes(args.task?'task_update':'message'))fail(403,'scope_does_not_allow_message');
    }
    const policy=one(this.db,'SELECT * FROM pa_policies WHERE binding_id=?',b.binding_id)!;
    const sources=all(this.db,`SELECT m.id message_id,m.conversation_id,m.sender_user_id author_id,m.content,m.created_at FROM pa_source_reads r JOIN messages m ON m.id=r.message_id WHERE r.binding_id=?`,b.binding_id)
      .filter(s=>this.pa.sourceAllowed(b,s.conversation_id));
    // History is evidence, never a replacement for the originating owner request.
    const prior=all(this.db,"SELECT payload_json,conversation_id,audience_json,state FROM pa_operations WHERE binding_id=? AND state IN ('confirmed','sending','unknown')",b.binding_id)
      .filter(op=>args.network ? (JSON.parse(op.payload_json).network || JSON.parse(op.payload_json).transport || op.conversation_id!==b.conversation_id) : JSON.parse(op.audience_json).some((id:string)=>this.recipients(args.conversation_id,payload).includes(id)&&id!==b.owner_user_id));
    const evidence={agent_profile_version:one(this.db,'SELECT profile_version FROM agent_profiles WHERE agent_id=?',b.agent_id)!.profile_version,active_scopes:args.network?this.pa.scopes(principal,{...args,task_ref:undefined}).scopes:undefined,owner_text:scope?.owner_text??null,owner_decisions:this.pa.ownerDecisions(b.binding_id,args.task_ref),scope:scope?JSON.parse(scope.scope_json):securityNotice?{kind:'system_security_notice',content:PEER_NOTICE,conversation_id:args.conversation_id,owner_notice_message_id:securityNotice.owner_notice_message_id}:null,recipient_ids:this.recipients(args.conversation_id,payload),external_destination:payload.transport?.destination??null,payload,sources,previous_disclosures:prior.map(op=>({...op,payload:JSON.parse(op.payload_json)})),last_owner_message_id:one(this.db,'SELECT id FROM messages WHERE conversation_id=? AND sender_user_id=? ORDER BY rowid DESC LIMIT 1',args.conversation_id,b.owner_user_id)?.id??null};
    const denials=all(this.db,"SELECT evidence_json FROM pa_operations WHERE binding_id=? AND conversation_id=? AND scope_id IS ? AND scope_revision IS ? AND state='deny'",b.binding_id,args.conversation_id,scope?.scope_id??null,scope?.revision??null)
      .filter(op=>{const e=JSON.parse(op.evidence_json);return JSON.stringify(e.owner_decisions)===JSON.stringify(evidence.owner_decisions)&&JSON.stringify(e.recipient_ids)===JSON.stringify(evidence.recipient_ids)&&e.last_owner_message_id===evidence.last_owner_message_id;});
    if(denials.length>=3)fail(409,'disclosure_rewrite_budget_exhausted');
    // Unsent operations may refresh review evidence, but never reuse a prior permit.
    // Consumed or uncertain operations above keep their original delivery identity.
    if(previous) {
      const refreshed={...previous,task_ref:args.task_ref??null,scope_id:scope?.scope_id??null,scope_revision:scope?.revision??null,policy_revision:policy.revision,disclosure_revision:policy.disclosure_revision,audience_json:JSON.stringify(evidence.recipient_ids),evidence_json:JSON.stringify(evidence)};
      this.validate(b,refreshed);
      this.db.prepare("UPDATE pa_operations SET task_ref=?,scope_id=?,scope_revision=?,policy_revision=?,disclosure_revision=?,audience_json=?,evidence_json=?,state='prepared',verdict_json=NULL,verdict_ref=NULL,expires_at=NULL WHERE operation_id=?").run(refreshed.task_ref,refreshed.scope_id,refreshed.scope_revision,refreshed.policy_revision,refreshed.disclosure_revision,refreshed.audience_json,refreshed.evidence_json,previous.operation_id);
      return this.project(this.operation(b,previous.operation_id));
    }
    const id=randomUUID();
    this.db.prepare(`INSERT INTO pa_operations(operation_id,binding_id,request_key,task_ref,scope_id,scope_revision,policy_revision,disclosure_revision,conversation_id,audience_json,payload_json,payload_digest,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(id,b.binding_id,args.request_key,args.task_ref??null,scope?.scope_id??null,scope?.revision??null,policy.revision,policy.disclosure_revision,args.conversation_id,JSON.stringify(evidence.recipient_ids),JSON.stringify(payload),hash,JSON.stringify(evidence),now());
    return this.project(this.operation(b,id));
  }
  project(op:Row){return {proposal_ref:op.operation_id,payload_digest:op.payload_digest,evidence:JSON.parse(op.evidence_json),scope_revision:op.scope_revision,policy_revision:op.policy_revision,disclosure_revision:op.disclosure_revision,state:op.state};}
  review(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args),op=this.operation(b,args.proposal_ref);
    this.validate(b,op);
    if(op.state==='confirmed')return {state:op.state,verdict_ref:null};
    if(args.payload_digest!==op.payload_digest||!['allow','deny','needs_owner','unavailable'].includes(args.verdict?.decision))fail(422,'invalid_independent_verdict');
    const ref=args.verdict.decision==='allow'?randomUUID():null,state=args.verdict.decision==='allow'?'allowed':args.verdict.decision;
    this.db.prepare('UPDATE pa_operations SET verdict_json=?,verdict_ref=?,expires_at=?,state=? WHERE operation_id=?').run(JSON.stringify(args.verdict),ref,new Date(Date.now()+60000).toISOString(),state,op.operation_id);
    return {verdict_ref:ref,state};
  }
  commit(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args), initial=this.operation(b,args.proposal_ref);
    if(initial.state==='confirmed')return {state:'confirmed',message_id:initial.message_id,result:initial.result_json?JSON.parse(initial.result_json):undefined,conversation_id:initial.conversation_id};
    if(['sending','unknown'].includes(initial.state))return {state:'unknown',conversation_id:initial.conversation_id};
    const notices:Row[]=[];
    const result=transaction(this.db,()=>{
      const op=this.operation(b,args.proposal_ref);this.validate(b,op);
      if(op.state!=='allowed'||!op.verdict_ref||op.verdict_ref!==args.verdict_ref||op.expires_at<now())fail(403,'independent_review_required');
      const payload=JSON.parse(op.payload_json),s=this.pa.ctx.messaging;
      if(payload.task) {
        const task=payload.task;
        const result=this.pa.ctx.gateway.tasks.executeDelegated({kind:'agent',id:b.agent_id,node_id:b.node_id},b.owner_user_id,{graph_id:task.graph_id,conversation_id:op.conversation_id,base_revision:task.base_revision,request_key:`pa:${op.operation_id}`,change_note:'',operations:[{op:'update_task',node_id:task.node_id,patch:task.patch}]},notices);
        this.db.prepare("UPDATE pa_operations SET state='confirmed',result_json=?,verdict_ref=NULL WHERE operation_id=?").run(JSON.stringify(result),op.operation_id);
        this.db.prepare('UPDATE pa_policies SET disclosure_revision=disclosure_revision+1 WHERE binding_id=?').run(b.binding_id);
        return {state:'confirmed',conversation_id:op.conversation_id,result};
      }
      if(payload.transport||payload.network) {
        this.db.prepare("UPDATE pa_operations SET state='sending',verdict_ref=NULL WHERE operation_id=?").run(op.operation_id);
        this.db.prepare('UPDATE pa_policies SET disclosure_revision=disclosure_revision+1 WHERE binding_id=?').run(b.binding_id);
        return {state:'sending',conversation_id:op.conversation_id,payload};
      }
      const rewrite=(value:string)=>value.replace(/\/im\/v1\/conversations\/([^/\s]+)\/(images|attachments)\/([\w-]+)/g,(url:string,source:string)=>s.copyReferences(source,op.conversation_id,url));
      const message=s.insertMessage(op.conversation_id,s.agentUser(b.agent_id).id,'agent',rewrite(payload.content),payload.attachments.map((a:Row)=>({...a,url:rewrite(a.url)})),`pa:${op.operation_id}`,'completed',{publish:false});
      if(op.conversation_id!==b.conversation_id)this.db.prepare('INSERT INTO pa_delegated_messages VALUES(?,?,?,?,?)').run(message.id,b.binding_id,b.agent_id,b.owner_user_id,b.display_name);
      this.db.prepare("UPDATE pa_operations SET state='confirmed',message_id=?,verdict_ref=NULL WHERE operation_id=?").run(message.id,op.operation_id);
      if(payload.incident_ref)this.db.prepare('UPDATE pa_incidents SET peer_notice_message_id=? WHERE id=?').run(message.id,payload.incident_ref);
      this.db.prepare('UPDATE pa_policies SET disclosure_revision=disclosure_revision+1 WHERE binding_id=?').run(b.binding_id);
      return {state:'confirmed',message_id:message.id,conversation_id:op.conversation_id};
    });
    if(result.state==='sending')return result;
    if('result' in result){this.pa.ctx.messaging.publishMessages(notices);return result;}
    const m=this.pa.ctx.messaging.message(result.message_id!);
    this.pa.ctx.messaging.publishMessages([m]);
    this.pa.ctx.gateway.groupReply(m.id);
    return result;
  }
  complete(principal:Row,args:Row) {
    const b=this.pa.authority(principal,args),op=this.operation(b,args.proposal_ref);
    const payload=JSON.parse(op.payload_json);
    if((!payload.transport&&!payload.network) || !['sending','unknown','confirmed'].includes(op.state))fail(409,'external_send_not_started');
    if(op.state==='confirmed')return {state:'confirmed',provider_message_id:op.message_id};
    if(!['confirmed','unknown'].includes(args.state)||(args.state==='confirmed'&&!args.provider_message_id&&!payload.network))fail(422,'provider_receipt_required');
    this.db.prepare('UPDATE pa_operations SET state=?,message_id=? WHERE operation_id=?').run(args.state,args.provider_message_id??null,op.operation_id);
    const incident=JSON.parse(op.payload_json).incident_ref;
    if(incident&&args.state==='confirmed')this.db.prepare('UPDATE pa_incidents SET peer_notice_message_id=? WHERE id=?').run(args.provider_message_id,incident);
    return {state:args.state,provider_message_id:args.provider_message_id??null};
  }
}
