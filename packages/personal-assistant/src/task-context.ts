import {createHash,randomUUID} from 'node:crypto';
import type {AgentConfiguration,RelayInput,RuntimePort,SessionBinding} from '@nano/product-contracts';
import type {ProtocolFrame} from '@nano/channels';
import type {NodeStore} from './store.js';
import type {InboxStore} from './inbox.js';
const digest=(content:unknown)=>createHash('sha256').update(JSON.stringify(content)).digest('hex');
interface Identity {agentId:string;sessionId:string;ownerId:string}
interface Evidence {inputId:string;content:{type:string;text?:string}[];turn:number;consumedSeq:number}
export interface PendingTaskContextItem {messageId:string;conversationId:string;conversationRef?:string;timeMs:number;text:string}
interface Options {nodeId:string;ownerId:string;agents:AgentConfiguration[];store:NodeStore;inbox:InboxStore;runtime:RuntimePort;
  relay:{request(type:string,payload:Record<string,unknown>):Promise<ProtocolFrame>};refreshSources(agentId:string):Promise<void>;
  settlePersonalInputs?:(agentId:string,sessionId:string)=>Promise<void>}
/** Product owner of original Task-message catch-up and native consumption receipts. */
export class TaskContext {
  private readonly syncing=new Map<string,{started:boolean;done:Promise<void>}>();
  constructor(private readonly options:Options){
    options.inbox.attachToolReferences(options.store.toolReferences);
  }
  private binding(identity:Identity):SessionBinding {
    const binding=this.options.store.bindingForSession(identity.sessionId);
    if(!binding||binding.agentId!==identity.agentId||binding.ownerId!==identity.ownerId||binding.ownerId!==this.options.ownerId)throw new Error('Task context identity mismatch');
    this.options.store.lifecycle.assert(identity.agentId);return binding;
  }
  private async sync(agentId:string):Promise<void> {
    const previous=this.syncing.get(agentId);
    if(previous && !previous.started)return previous.done;
    const cut={started:false,done:Promise.resolve()};
    cut.done=(previous?.done??Promise.resolve()).catch(()=>{}).then(async()=>{
      cut.started=true;
      const config=this.options.agents.find(item=>item.agentId===agentId);
      await this.options.refreshSources(agentId);
      let after=this.options.store.taskContextCursor(agentId),through:number|undefined;
      do {
        const pending:string[]=[];
        const frame=await this.options.relay.request('task.context.sync',{node_id:this.options.nodeId,agent_id:agentId,request_id:randomUUID(),after,through,limit:32,pending});
        this.options.store.lifecycle.assert(agentId);
        if(!frame.payload.ok)throw new Error('Task context authority unavailable');
        const page=frame.payload.result as {through:number;next:number;items:{message_id:string;conversation_id:string;projection_kind?:string;allowed:boolean;input?:RelayInput}[];revoked_message_ids:string[]};
        if(!Number.isSafeInteger(page.through)||!Number.isSafeInteger(page.next)||page.next<after||page.next>page.through||through!==undefined&&through!==page.through||page.next===after&&page.next!==page.through)throw new Error('Invalid Task context fixed range');
        through=page.through;
        const revoke=(id:string,cid:string)=>{this.options.store.revokeSystemContext(agentId,id,cid);this.options.inbox.revokeSystemContext(agentId,id);};
        for(const item of page.items) {
          if(item.allowed&&item.input) {
            if(config?.personal&&item.projection_kind!=='revoked'&&!this.options.inbox.input(agentId,item.input.message.id)) {
              const staged=structuredClone(item.input);
              staged.metadata={...staged.metadata,personal_unclassified:true};
              this.options.inbox.receive(staged,false);
            } else {
              this.options.inbox.receive(item.input,false);
            }
          } else revoke(item.message_id,item.conversation_id);
        }
        for(const id of page.revoked_message_ids??[]){const row=this.options.store.systemContextInput(agentId,id);if(row)revoke(id,row.conversation_id);}
        // Inbox writes precede this cursor. A crash retries immutable IDs, never skips originals.
        this.options.store.advanceTaskContext(agentId,page.next);after=page.next;
      }while(after<through);
      // Revalidate every pending original after the fixed cut, not just the first
      // page. A membership change may occur while a large catch-up is paging.
      const ids=[...new Set([
        ...this.options.store.systemContextInputs(agentId,'prepared').map(row=>row.message_id),
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
          const row=this.options.store.systemContextInput(agentId,id);
          this.options.store.revokeSystemContext(agentId,id,row?.conversation_id??message?.conversationId??'');
          this.options.inbox.revokeSystemContext(agentId,id);
        }
      }
    });
    this.syncing.set(agentId,cut);
    try{await cut.done;}finally{if(this.syncing.get(agentId)===cut)this.syncing.delete(agentId);}
  }
  /** Complete current authority synchronization before any original message is admitted. */
  async prepare(identity:Identity&{evidenceReady?:boolean}):Promise<{messages:ReturnType<InboxStore['prepareSystemContext']>;revoked:string[];unavailable?:boolean;unavailableInputs?:{inputId:string;conversationId:string}[]}> {
    const {agentId,sessionId}=identity;
    const {agents,store,inbox}=this.options;
    const binding=this.binding(identity);
    if(store.taskContextRetired(sessionId))return {messages:[],revoked:[]};
    const config=agents.find(item=>item.agentId===agentId)!;
    const scope=config.mode==='global'?undefined:store.imConversation(agentId,binding.conversationId);
    let authority=true;
    try {
      await this.sync(agentId);
      if(config.personal)await this.options.settlePersonalInputs?.(agentId,sessionId);
    } catch {authority=false;}
    this.binding(identity);
    if(store.taskContextRetired(sessionId))return {messages:[],revoked:[]};
    const revoked=store.systemContextInputs(agentId,'revoked').map(row=>row.input_id);
    const messages=inbox.prepareSystemContext(agentId,sessionId).filter(message=>config.mode==='global'||message.conversationId===scope);
    if(!authority||identity.evidenceReady===false) {
      return {messages:[],revoked,unavailable:true,unavailableInputs:messages.map(({inputId,conversationId})=>({inputId,conversationId}))};
    }
    return {revoked,messages:messages.filter(message=>{
      store.prepareSystemContext(agentId,message.inputId,message.conversationId,sessionId,digest(message.content));
      const row=store.systemContextInput(agentId,message.inputId);
      return row?.state==='prepared'&&row.session_id===sessionId;
    })};
  }

  /** Synchronize Task notices and inspect unconsumed admitted items for Dreaming without mutating consumption state. */
  async peekPendingForDreaming(identity:Identity):Promise<PendingTaskContextItem[]> {
    const {agentId,sessionId}=identity;
    const {agents,store,inbox}=this.options;
    const binding=this.binding(identity);
    if(store.taskContextRetired(sessionId))return [];
    const config=agents.find(item=>item.agentId===agentId);
    if(!config)return [];
    const scope=config.mode==='global'?undefined:store.imConversation(agentId,binding.conversationId);
    await this.sync(agentId);
    if(config.personal)await this.options.settlePersonalInputs?.(agentId,sessionId);
    this.binding(identity);
    if(store.taskContextRetired(sessionId))return [];
    const revoked=new Set(store.systemContextInputs(agentId,'revoked').map(row=>row.input_id));
    return inbox.prepareSystemContext(agentId,sessionId)
      .filter(message=>(config.mode==='global'||message.conversationId===scope)&&!revoked.has(message.inputId))
      .filter(message=>{
        const state=store.systemContextInput(agentId,message.inputId)?.state;
        return state!=='consumed'&&state!=='revoked';
      })
      .map(message=>{
        const original=inbox.input(agentId,message.inputId);
        const noticeTime=(original?.message.system_notice as {event_time?:string}|undefined)?.event_time;
        const parsed=Date.parse(String(original?.message.created_at??noticeTime??''));
        return {
          messageId:message.inputId,
          conversationId:message.conversationId,
          conversationRef:message.conversationRef ?? store.toolReferences.conversationRef(agentId,message.conversationId),
          timeMs:Number.isFinite(parsed)?parsed:0,
          text:message.content.map(part=>part.text??'').join('\n'),
        };
      });
  }

  /** Acknowledge only a matching durable ingestion or a terminally discarded claim. */
  async commit(identity:Identity&{evidence:Evidence[]}) {
    this.binding(identity);
    const {agentId,sessionId}=identity;
    const {store,inbox}=this.options;
    const retired=store.taskContextRetired(sessionId);
    const confirmed:{inputId:string;consumedSeq:number;status:'consumed'|'discarded'}[]=[];
    for(const {inputId,content,turn,consumedSeq} of identity.evidence) {
      if(!Number.isSafeInteger(turn)||!Number.isSafeInteger(consumedSeq)||consumedSeq<0)continue;
      const row=store.systemContextInput(agentId,inputId);
      if(!row||row.digest!==digest(content)||row.state==='consumed'&&row.turn!==turn)continue;
      if(row.session_id!==sessionId&&!retired)continue;
      const ingested=inbox.systemContextIngested(agentId,sessionId,inputId,turn);
      if(ingested || (row.session_id===sessionId && row.state!=='revoked' && !retired &&
        inbox.commitSystemContext(agentId,sessionId,inputId,content,turn))) {
        if(row.state==='prepared')store.commitSystemContext(sessionId,inputId,row.digest,turn);
        confirmed.push({inputId,consumedSeq,status:'consumed'});
      } else if(retired || row.state==='revoked') {
        confirmed.push({inputId,consumedSeq,status:'discarded'});
      }
    }
    return {confirmed};
  }
}
