import { decodeChatStream, type ChatEvent, type ChatStreamFact, type ChatStreamReceipt } from '@nano/product-contracts';
import type { DatabaseSync } from 'node:sqlite';
import { MessageRecords, withHumanApproval } from './message-records.js';
import { lifecycle, requireLifecycle } from './agent-lifecycle.js';
import { fail } from './context.js';

export interface ChatConnection {node_id:string; owner_id:string; node_epoch:number}
interface Ports<C extends ChatConnection> {
  requireAgent(connection:C,id:string):{agent_id:string;work_mode?:string};
  requirePersonalConversation(agentId:string,conversationId:string):void;
  agentUserId(agentId:string):string;
  resolveTarget(agentId:string,target:string):string;
  access(connection:C,conversationId:string,agentId:string):void;
  groupReply(messageId:string):void;
}
/** Apply authenticated stream facts without owning transport or the application container. */
export class ChatStreaming<C extends ChatConnection> {
  constructor(private readonly db:DatabaseSync,private readonly records:MessageRecords,private readonly ports:Ports<C>) {}
  /** Reject malformed stable fields before consuming a retry key or writing any projection. */
  receive(connection:C,value:unknown):ChatStreamReceipt {
    let fact:ChatStreamFact;
    try {fact=decodeChatStream(value);}catch(error){fail(400,(error as Error).message);}
    return this.apply(connection,fact);
  }
  private apply(c:C,p:ChatStreamFact):ChatStreamReceipt {
    const records=this.records,ports=this.ports;
    if(p.kind==='turn_start') {
      const agent=ports.requireAgent(c,p.agent_id);
      requireLifecycle(this.db,agent.agent_id,p.lifecycle_revision);
      if(p.agent_user_id&&p.agent_user_id!==ports.agentUserId(agent.agent_id))fail(403,'agent_user_id does not match source Agent');
      const cid=p.conversation_id??ports.resolveTarget(agent.agent_id,p.to_user_id!);
      ports.requirePersonalConversation(agent.agent_id,cid);ports.access(c,cid,agent.agent_id);
      const transition=p.reply_process_transition;
      if(transition?.predecessor_message_id) {
        const previous=records.message(transition.predecessor_message_id);
        if(previous.conversation_id!==cid||previous.sender.id!==agent.agent_id)fail(403,'reply process predecessor must belong to source Agent');
      }
      const message=records.insert(cid,ports.agentUserId(agent.agent_id),'agent','',[],p.shadow_message_id??p.idempotency_key??null,'running');
      if(p.background_returns)records.background(message.id,p.background_returns);
      if(transition) {
        if(transition.predecessor_message_id&&transition.include_handoff)this.apply(c,{kind:'reply_process',lifecycle_revision:p.lifecycle_revision,message_id:transition.predecessor_message_id,item:{item_id:`handoff:${transition.run_id}:${message.id}`,kind:'segment_handoff',run_id:transition.run_id,successor_message_id:message.id}});
        this.apply(c,{kind:'reply_process',lifecycle_revision:p.lifecycle_revision,message_id:message.id,item:{item_id:`revalidation:${transition.run_id}:${message.id}`,kind:'revalidation',run_id:transition.run_id,source_messages:transition.source_messages??[],predecessor_message_id:transition.predecessor_message_id??null,status:'running'}});
      }
      return {kind:p.kind,run_id:p.run_id,message_id:message.id,conversation_id:cid};
    }
    if(p.kind==='run_terminal_reconcile')return {kind:p.kind,run_id:p.run_id};
    // Deltas never load tool/permission/history JSON. Other facts reuse their one public projection.
    const view=p.kind==='message_delta'?undefined:records.message(p.message_id);
    const identity=view??records.streamIdentity(p.message_id);
    if(identity.sender_type!=='agent')fail(403,'streaming message must belong to an Agent');
    ports.requireAgent(c,identity.sender.id);
    requireLifecycle(this.db,identity.sender.id,p.lifecycle_revision);requireLifecycle(this.db,identity.sender.id,identity.lifecycle_revision);
    ports.requirePersonalConversation(identity.sender.id,identity.conversation_id);ports.access(c,identity.conversation_id,identity.sender.id);
    if(p.kind==='message_delta') {
      if(!records.appendDelta(identity,p.delta_text??'',p.idempotency_key))return {message_id:identity.id};
      records.chatEvent(identity.conversation_id,identity.id,{type:'message.delta',data:{delta:p.delta_text??'',delta_text:p.delta_text??'',idempotency_key:p.idempotency_key}},p.delivery_status??identity.delivery_status);
      return {kind:p.kind,run_id:p.run_id,message_id:identity.id};
    }
    const m=view!;
    let event:ChatEvent;
    switch(p.kind) {
      case 'message_completed':
        records.complete(m,p);event={type:'message.completed',data:{...records.message(m.id),content:p.final_content??m.content}};break;
      case 'message_discarded':
        records.discard(m.id);records.chatEvent(m.conversation_id,null,{type:'message.discarded',data:{message_id:m.id,reason:p.reason}});return {message_id:m.id};
      case 'thinking_segment': {
        const items=m.thinking,item={seq:p.process_seq??items.length,text:p.text??''};
        if(!items.some(existing=>existing.seq===item.seq))items.push(item);
        records.thinking(m.id,items);event={type:'thinking.segment',data:{segment:item,...item}};break;
      }
      case 'tool_call_upserted':case 'tool_call_completed': {
        const items=m.tool_calls,item=withHumanApproval({...p.tool_call,...(p.process_seq!==undefined?{seq:p.process_seq}:{})},m.permission_requests);
        const index=items.findIndex(existing=>existing.id===item.id);
        if(index<0)items.push(item);else {item.seq=items[index].seq??item.seq;items[index]={...items[index],...item};}
        records.tools(m.id,items);event={type:p.kind==='tool_call_completed'?'tool_call.completed':'tool_call.upserted',data:{tool_call:item}};break;
      }
      case 'permission_request':case 'permission_resolved': {
        const items=m.permission_requests,item=p.permission_request??p,id=item.request_id??p.request_id;
        let entry=items.find(existing=>existing.request_id===id);
        if(!entry){entry={...item,request_id:id};items.push(entry);}
        if(p.kind==='permission_request') {
          if(['submitted','resolved'].includes(entry.status??''))return {message_id:m.id};
          const agent=ports.requireAgent(c,m.sender.id);
          if(agent.work_mode!=='single_thread')fail(400,'global Agent does not expose chat permission cards');
          Object.assign(entry,{status:'pending',conversation_id:m.conversation_id,message_id:m.id,agent_id:agent.agent_id,node_id:c.node_id,node_epoch:c.node_epoch,lifecycle_revision:lifecycle(this.db,agent.agent_id).revision,run_id:p.run_id});
        }else Object.assign(entry,{status:'resolved',decision:p.decision});
        records.permissions(m.id,items,p.kind==='permission_request');event={type:p.kind==='permission_request'?'permission.request':'permission.resolved',data:{...entry,permission_request:entry}};break;
      }
      case 'reply_process': {
        const items=m.reply_process,index=items.findIndex(existing=>existing.item_id===p.item.item_id);
        if(index<0)items.push(p.item);else items[index]=p.item;
        records.process(m.id,items);event={type:'reply_process.upserted',data:{item:p.item}};break;
      }
      case 'run_heartbeat':
        if(m.awaiting_permission_at)records.heartbeat(m.id);
        event={type:'run.heartbeat',data:{source:p.source}};break;
    }
    records.chatEvent(m.conversation_id,m.id,event,p.delivery_status??(p.kind==='message_completed'?'completed':m.delivery_status));
    if(p.kind==='message_completed')ports.groupReply(m.id);
    return {kind:p.kind,run_id:p.run_id,message_id:m.id};
  }
}
