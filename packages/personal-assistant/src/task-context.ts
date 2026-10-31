import {createHash,randomUUID} from 'node:crypto';
import type {AgentConfiguration,RelayInput,RuntimePort,SessionBinding} from '@nano/product-contracts';
import type {ProtocolFrame} from '@nano/channels';
import type {NodeStore} from './store.js';
import type {InboxStore} from './inbox.js';
const digest=(content:unknown)=>createHash('sha256').update(JSON.stringify(content)).digest('hex');
interface Identity {agentId:string;sessionId:string;ownerId:string}
interface Evidence {inputId:string;content:{type:string;text?:string}[];turn:number;consumedSeq:number}
interface Options {nodeId:string;ownerId:string;agents:AgentConfiguration[];store:NodeStore;inbox:InboxStore;runtime:RuntimePort;
  relay:{request(type:string,payload:Record<string,unknown>):Promise<ProtocolFrame>};refreshSources(agentId:string):Promise<void>}
/** Product owner of original Task-message catch-up and native consumption receipts. */
export class TaskContext {
  private readonly syncing=new Map<string,Promise<void>>();
  constructor(private readonly options:Options){}
  private binding(identity:Identity):SessionBinding {
    const binding=this.options.store.bindings().find(item=>item.sessionId===identity.sessionId);
    if(!binding||binding.agentId!==identity.agentId||binding.ownerId!==identity.ownerId||binding.ownerId!==this.options.ownerId)throw new Error('Task context identity mismatch');
    this.options.store.lifecycle.assert(identity.agentId);return binding;
  }
  private async sync(agentId:string):Promise<void> {
    const previous=this.syncing.get(agentId)??Promise.resolve();
    const next=previous.catch(()=>{}).then(async()=>{
      await this.options.refreshSources(agentId);
      let after=this.options.store.taskContextCursor(agentId),through:number|undefined;
      do {
        const pending:string[]=[];
        const frame=await this.options.relay.request('task.context.sync',{node_id:this.options.nodeId,agent_id:agentId,request_id:randomUUID(),after,through,limit:32,pending});
        this.options.store.lifecycle.assert(agentId);
        if(!frame.payload.ok)throw new Error('Task context authority unavailable');
        const page=frame.payload.result as {through:number;next:number;items:{message_id:string;conversation_id:string;allowed:boolean;input?:RelayInput}[];revoked_message_ids:string[]};
        if(!Number.isSafeInteger(page.through)||!Number.isSafeInteger(page.next)||page.next<after||page.next>page.through||through!==undefined&&through!==page.through||page.next===after&&page.next!==page.through)throw new Error('Invalid Task context fixed range');
        through=page.through;
        const revoke=(id:string,cid:string)=>{this.options.store.revokeSystemContext(agentId,id,cid);this.options.inbox.revokeSystemContext(agentId,id);};
        for(const item of page.items) {
          if(item.allowed&&item.input)this.options.inbox.receive(item.input,false);
          else revoke(item.message_id,item.conversation_id);
        }
        for(const id of page.revoked_message_ids??[]){const row=this.options.store.systemContextInputs(agentId).find(row=>row.message_id===id);if(row)revoke(id,row.conversation_id);}
        // Inbox writes precede this cursor. A crash retries immutable IDs, never skips originals.
        this.options.store.advanceTaskContext(agentId,page.next);after=page.next;
      }while(after<through);
      // Revalidate every pending original after the fixed cut, not just the first
      // page. A membership change may occur while a large catch-up is paging.
      const ids=[...new Set([
        ...this.options.store.systemContextInputs(agentId).filter(row=>row.state==='prepared').map(row=>row.message_id),
        ...this.options.inbox.prepareSystemContext(agentId,'').map(message=>message.inputId)
      ])];
      for(let i=0;i<ids.length;i+=32) {
        const frame=await this.options.relay.request('task.context.sync',{node_id:this.options.nodeId,agent_id:agentId,request_id:randomUUID(),after,through,limit:32,pending:ids.slice(i,i+32)});
        this.options.store.lifecycle.assert(agentId);
        if(!frame.payload.ok)throw new Error('Task context revalidation unavailable');
        const page=frame.payload.result as {through:number;next:number;revoked_message_ids:string[]};
        if(page.through!==through||page.next!==after)throw new Error('Invalid Task context revalidation cut');
        for(const id of page.revoked_message_ids??[]) {
          const message=this.options.inbox.prepareSystemContext(agentId,'').find(message=>message.inputId===id);
          const row=this.options.store.systemContextInputs(agentId).find(row=>row.message_id===id);
          this.options.store.revokeSystemContext(agentId,id,row?.conversation_id??message?.conversationId??'');
          this.options.inbox.revokeSystemContext(agentId,id);
        }
      }
    });
    this.syncing.set(agentId,next);
    try{await next;}finally{if(this.syncing.get(agentId)===next)this.syncing.delete(agentId);}
  }
  /** Complete current authority synchronization before any original message is admitted. */
  async prepare(identity:Identity&{evidence?:Evidence[]}):Promise<{messages:ReturnType<InboxStore['prepareSystemContext']>;revoked:string[];unavailable?:boolean;unavailableInputs?:{inputId:string;conversationId:string}[]}> {
    const binding=this.binding(identity);
    const config=this.options.agents.find(item=>item.agentId===identity.agentId)!;
    const scope=config.mode==='global'?undefined:this.options.store.imConversation(identity.agentId,binding.conversationId);
    const inScope=(message:{conversationId:string})=>config.mode==='global'||message.conversationId===scope;
    try {await this.sync(identity.agentId);}
    catch {
      // Source uncertainty blocks originals, not independent already-authorized input.
      // Keep unread/prepared rows pending for the next successful catch-up.
      this.binding(identity);
      const revoked=this.options.store.systemContextInputs(identity.agentId).filter(row=>row.state==='revoked').map(row=>row.input_id);
      const unavailableInputs=this.options.inbox.prepareSystemContext(identity.agentId,identity.sessionId)
        .filter(message=>inScope(message)&&!revoked.includes(message.inputId)).map(({inputId,conversationId})=>({inputId,conversationId}));
      return {messages:[],revoked,unavailable:true,unavailableInputs};
    }
    await this.commit({...identity,evidence:identity.evidence??[]});
    const messages=this.options.inbox.prepareSystemContext(identity.agentId,identity.sessionId).filter(inScope);
    for(const message of messages)this.options.store.prepareSystemContext(identity.agentId,message.inputId,message.conversationId,identity.sessionId,digest(message.content));
    const rows=this.options.store.systemContextInputs(identity.agentId);
    return {messages:messages.filter(message=>rows.find(row=>row.message_id===message.inputId)?.state==='prepared'&&rows.find(row=>row.message_id===message.inputId)?.session_id===identity.sessionId),revoked:rows.filter(row=>row.state==='revoked').map(row=>row.input_id)};
  }
  /** Reconcile only flushed native user/message evidence, never queue/ACK/summary evidence. */
  async commit(identity:Identity&{evidence:Evidence[]}):Promise<void> {
    this.binding(identity);
    for(const evidence of identity.evidence) {
      if(!Number.isSafeInteger(evidence.turn)||!Number.isSafeInteger(evidence.consumedSeq))continue;
      const row=this.options.store.systemContextInputs(identity.agentId).find(row=>row.session_id===identity.sessionId&&row.input_id===evidence.inputId);
      if(!row||row.state==='revoked'||row.digest!==digest(evidence.content))continue;
      // Recover the product side even when the process died after the native flush.
      const unread=this.options.inbox.prepareSystemContext(identity.agentId,identity.sessionId).some(item=>item.inputId===evidence.inputId);
      if(unread)this.options.inbox.commitSystemContext(identity.agentId,identity.sessionId,evidence.inputId,evidence.content,evidence.turn);
      this.options.store.commitSystemContext(identity.sessionId,evidence.inputId,digest(evidence.content),evidence.turn);
    }
  }
}
