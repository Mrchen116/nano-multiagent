import type { ControlIntent } from './session-controls.js';
import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimePort, SessionBinding, TaskExecutionSnapshot, TaskResponsibility, TaskWaitInspection } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { NodeStore } from './store.js';

interface Options {
  nodeId:string;ownerId:string;agents:AgentConfiguration[];store:NodeStore;runtime:RuntimePort;
  relay:{request(type:string,payload:Record<string,unknown>):Promise<ProtocolFrame>};
  drain(sessionId:string):Promise<void>;
  context(binding:SessionBinding):Promise<{messages:{inputId:string;conversationId:string;content:{type:'text';text:string}[]}[];revoked:string[];unavailable?:boolean}>;
}
/** Resolve product scope and edge-triggered doing watermarks without scheduling a polling loop. */
export class TaskExecution {
  private readonly waitingAgents=new Set<string>();
  constructor(private readonly options:Options) {
    const runtime=options.runtime,relay=options.relay;
    this.options={...options,runtime:{onNotification:runtime.onNotification.bind(runtime),request:(method,params)=>runtime.request(method,options.store.executionPayload(params))},
      relay:{request:(type,payload)=>relay.request(type,options.store.executionPayload(payload))}};
  }
  private binding(identity:{sessionId:string;agentId:string;ownerId:string}):SessionBinding {
    const binding=this.options.store.bindingForSession(identity.sessionId);
    if(!binding||binding.agentId!==identity.agentId||binding.ownerId!==identity.ownerId||binding.ownerId!==this.options.ownerId)throw new Error('Task execution identity mismatch');
    return binding;
  }
  private scope(binding:SessionBinding):string|undefined {
    return this.options.agents.find(a=>a.agentId===binding.agentId)?.mode==='global'?undefined:this.options.store.imConversation(binding.agentId,binding.conversationId);
  }
  /** Read current full responsibility and compute unconsumed doing_wake transitions. */
  async snapshot(identity:{sessionId:string;agentId:string;ownerId:string}):Promise<TaskExecutionSnapshot> {
    if(!this.options.store.lifecycle.allowed(identity.agentId))return {kind:'quiescent',tasks:[],reason:'agent_disabled'};
    return this.options.store.lifecycle.run(identity.agentId,undefined,()=>this.snapshotAdmitted(identity));
  }
  private async snapshotAdmitted(identity:{sessionId:string;agentId:string;ownerId:string}):Promise<TaskExecutionSnapshot> {
    const binding=this.binding(identity),config=this.options.agents.find(a=>a.agentId===binding.agentId)!;
    const empty={tasks:[] as TaskResponsibility[]};
    if(!this.options.store.lifecycle.allowed(binding.agentId))return {kind:'quiescent',...empty,reason:'agent_disabled'};
    if(this.options.store.bindingFor(binding.agentId,binding.conversationId)?.sessionId!==binding.sessionId)return {kind:'quiescent',...empty,reason:'session_superseded'};
    if(config.features?.task_graph===false||config.toolAllowlist&&!config.toolAllowlist.includes('task_graph'))return {kind:'quiescent',...empty};
    if(this.options.store.controls().some(i=>i.action==='task-stop'&&i.binding.sessionId===binding.sessionId&&!i.text))return {kind:'unavailable',...empty,reason:'stop_pending'};
    const conversation=this.scope(binding);
    if(config.mode==='single_thread'&&!conversation)return {kind:'quiescent',...empty};
    try {
      const frame=await this.options.relay.request('task.execution.snapshot',{node_id:this.options.nodeId,agent_id:binding.agentId,conversation_id:conversation,request_id:randomUUID()});
      this.options.store.lifecycle.assert(binding.agentId);
      if(!frame.payload.ok)throw new Error('Task source unavailable');
      const items=(frame.payload.result as {items:TaskResponsibility[]}).items;
      const tasks:TaskResponsibility[]=items.map(item=>{
        let unwoken_doing=false;
        if(item.status==='doing'&&item.doing_wake?.assignee_id===binding.agentId){
          if(item.doing_wake.actor.type==='agent'&&item.doing_wake.actor.id===binding.agentId){
            this.options.store.advanceDoingWatermark(binding.agentId,item.graph_id,item.node_id,item.doing_wake.revision);
          }else{
            unwoken_doing=item.doing_wake.revision>this.options.store.doingWatermark(binding.agentId,item.graph_id,item.node_id);
          }
        }
        return {
          graph_id:item.graph_id,node_id:item.node_id,title:item.title,status:item.status,
          revision:item.revision,updated_at:item.updated_at,conversation:{id:item.conversation.id},
          relative_url:item.relative_url,
          ...(item.root_node_id?{root_node_id:item.root_node_id}:{}),
          ...(item.root_title?{root_title:item.root_title}:{}),
          ...(item.root_goal_summary!==undefined?{root_goal_summary:item.root_goal_summary}:{}),
          ...(item.parent_path?{parent_path:item.parent_path}:{}),
          ...(item.doing_wake!==undefined?{doing_wake:item.doing_wake}:{}),
          ...(unwoken_doing?{unwoken_doing:true}:{}),
          ...(item.wait?{wait:item.wait}:{}),
          ...(item.resume_request?{resume_request:item.resume_request}:{}),
        };
      });
      if(tasks.some(t=>t.status==='waiting'&&t.wait?.schedule_id))this.waitingAgents.add(binding.agentId);else this.waitingAgents.delete(binding.agentId);
      return {kind:tasks.some(t=>t.unwoken_doing)?'continue':'quiescent',tasks};
    } catch {return {kind:'unavailable',...empty,reason:'task_source_unavailable'};}
  }
  /** Persist consumed doing_wake watermarks after the runtime completes the corresponding wake turn. */
  ackDoing(input:{sessionId:string;agentId:string;ownerId:string;items:{graph_id:string;node_id:string;revision:number}[]}):{ok:true} {
    const binding=this.binding(input);
    for(const item of input.items)this.options.store.advanceDoingWatermark(binding.agentId,item.graph_id,item.node_id,item.revision);
    return {ok:true};
  }
  /** Resolve a Schedule only within the assignee's current product session scope. */
  async inspect(input:{agent_id:string;conversation_id:string;schedule_id:string}):Promise<TaskWaitInspection> {
    this.options.store.lifecycle.assert(input.agent_id);
    const config=this.options.agents.find(a=>a.agentId===input.agent_id);
    if(!config)throw new Error('Unknown task owner');
    const binding=this.options.store.bindingFor(config.agentId,config.mode==='global'?`global:${config.agentId}`:input.conversation_id);
    if(!binding || (config.mode!=='global' && this.options.store.imConversation(binding.agentId,binding.conversationId)!==input.conversation_id))return {valid:false,checked_at:new Date().toISOString(),reason_code:'owner_or_session_mismatch'};
    return await this.options.runtime.request('schedule.wait.inspect',{agentId:config.agentId,sessionId:binding.sessionId,scheduleId:input.schedule_id});
  }
  /** Fence, drain, and atomically pause the host-attested human stop scope. */
  async stop(binding:SessionBinding,input:RelayInput):Promise<{wasRunning:boolean;paused:number}> {
    input=this.options.store.admitInput(input);
    return this.options.store.lifecycle.run(binding.agentId,input.lifecycle_revision,()=>this.stopAdmitted(binding,input));
  }
  private async stopAdmitted(binding:SessionBinding,input:RelayInput):Promise<{wasRunning:boolean;paused:number}> {
    const config=this.options.agents.find(a=>a.agentId===binding.agentId);
    const taskGraphDisabled=config?.features?.task_graph===false||!!(config?.toolAllowlist&&!config.toolAllowlist.includes('task_graph'));
    const id=`task-stop:${binding.agentId}:${input.message.id}`;
    const intent:ControlIntent=this.options.store.control(id)??{id,binding,input,action:'task-stop',argument:''};
    intent.stoppedAt??=new Date().toISOString();
    this.options.store.saveControl(intent);
    if(intent.text)return JSON.parse(intent.text);
    await this.options.runtime.request('task.execution.block',{sessionId:binding.sessionId,blocked:true});
    await this.options.runtime.request('session.ensure',(({conversationId,...value})=>value)(binding));
    const cancelled=await this.options.runtime.request('session.cancel',{sessionId:binding.sessionId,stoppedAt:intent.stoppedAt});
    await this.options.drain(binding.sessionId);
    if(taskGraphDisabled) {
      const result={...cancelled,paused:0};
      intent.text=JSON.stringify(result);intent.delivered=true;this.options.store.saveControl(intent);
      await this.options.runtime.request('task.execution.block',{sessionId:binding.sessionId,blocked:false});
      return result;
    }
    const frame=await this.options.relay.request('task.execution.pause',{node_id:this.options.nodeId,agent_id:binding.agentId,conversation_id:this.scope(binding),request_id:randomUUID(),request_key:id,control_message_id:input.message.id});
    if(!frame.payload.ok)throw new Error('Stop is pending until Task state can be confirmed');
    const pauseResult=frame.payload.result as {paused:number;offline_unmirrored?:boolean};
    const result={...cancelled,paused:Number(pauseResult.paused)};
    if(!pauseResult.offline_unmirrored) {
      // The authority transaction created the real Task originals. Admit those same
      // IDs passively; a parallel private summary would split their consumption.
      const prepared=await this.options.context(binding);
      if(prepared.unavailable)throw new Error('Task context synchronization unavailable');
      await this.options.runtime.request('task.context.passive',{sessionId:binding.sessionId,agentId:binding.agentId,...prepared});
    }
    intent.text=JSON.stringify(result);intent.delivered=true;this.options.store.saveControl(intent);
    await this.options.runtime.request('task.execution.block',{sessionId:binding.sessionId,blocked:false});
    return result;
  }
  /** Restore pending stop fences before any runtime session is recovered. */
  async recoverStops(agentIds?:string[]):Promise<void> {
    const intents=agentIds ? agentIds.flatMap(id=>this.options.store.pendingControls(id)) : this.options.store.pendingControls();
    for(const intent of intents)
      if(this.options.store.lifecycle.allowed(intent.binding.agentId,intent.input.lifecycle_revision??1)&&intent.action==='task-stop'&&!intent.text)
        await this.stop(intent.binding,intent.input);
  }
  /** Restore responsibility even when a UI action preceded the first chat input. */
  async recover(agentIds:string[]):Promise<void> {
    for(const agentId of agentIds) {
      if(!this.options.store.lifecycle.allowed(agentId))continue;
      await this.options.store.lifecycle.run(agentId,undefined,async()=>{
      const config=this.options.agents.find(a=>a.agentId===agentId)!;
      if(config.features?.task_graph===false||config.toolAllowlist&&!config.toolAllowlist.includes('task_graph'))return;
      const frame=await this.options.relay.request('task.execution.scopes',{node_id:this.options.nodeId,agent_id:agentId,request_id:randomUUID()});
      if(!frame.payload.ok)return;
      const scopes=(frame.payload.result as {conversation_ids:string[]}).conversation_ids;
      for(const conversationId of config.mode==='global'?(scopes.length?[`global:${agentId}`]:[]):scopes) {
        const binding=this.options.store.bindingFor(agentId,conversationId)??this.options.store.bind({agentId,conversationId,sessionId:randomUUID(),ownerId:this.options.ownerId,cwd:config.workspace,revision:config.revision});
        await this.options.runtime.request('session.ensure',(({conversationId,...value})=>value)(binding));
      }
      await this.changed(agentId);
      });
    }
  }
  async changed(agentId:string,reset=true):Promise<void> {if(!this.options.store.lifecycle.allowed(agentId))return;await this.options.store.lifecycle.run(agentId,undefined,()=>this.options.runtime.request('task.execution.changed',{agentId,reset}));}
  async watch():Promise<void> {await Promise.allSettled([...this.waitingAgents].map(id=>this.changed(id,false)));}
}
