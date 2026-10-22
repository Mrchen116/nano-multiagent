import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimePort, SessionBinding, TaskExecutionSnapshot, TaskResponsibility, TaskWaitInspection } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { NodeStore } from './store.js';

interface Options {
  nodeId:string;ownerId:string;agents:AgentConfiguration[];store:NodeStore;runtime:RuntimePort;
  relay:{request(type:string,payload:Record<string,unknown>):Promise<ProtocolFrame>};
  drain(sessionId:string):Promise<void>;
}
/** Resolve product scope and native waiting evidence without scheduling model execution. */
export class TaskExecution {
  private readonly waitingAgents=new Set<string>();
  constructor(private readonly options:Options) {}
  private binding(identity:{sessionId:string;agentId:string;ownerId:string}):SessionBinding {
    const binding=this.options.store.bindings().find(b=>b.sessionId===identity.sessionId);
    if(!binding||binding.agentId!==identity.agentId||binding.ownerId!==identity.ownerId||binding.ownerId!==this.options.ownerId)throw new Error('Task execution identity mismatch');
    return binding;
  }
  private scope(binding:SessionBinding):string|undefined {
    return this.options.agents.find(a=>a.agentId===binding.agentId)?.mode==='global'?undefined:this.options.store.imConversation(binding.agentId,binding.conversationId);
  }
  /** Read current full responsibility; missing runtime evidence is never valid waiting. */
  async snapshot(identity:{sessionId:string;agentId:string;ownerId:string}):Promise<TaskExecutionSnapshot> {
    const binding=this.binding(identity),config=this.options.agents.find(a=>a.agentId===binding.agentId)!;
    const empty={tasks:[],repair_task_ids:[]};
    if(this.options.store.bindingFor(binding.agentId,binding.conversationId)?.sessionId!==binding.sessionId)return {kind:'quiescent',...empty,reason:'session_superseded'};
    if(config.features?.task_graph===false||config.toolAllowlist&&!config.toolAllowlist.includes('task_graph'))return {kind:'quiescent',...empty};
    if(this.options.store.controls().some(i=>i.action==='task-stop'&&i.binding.sessionId===binding.sessionId&&!i.text))return {kind:'unavailable',...empty,reason:'stop_pending'};
    const conversation=this.scope(binding);
    if(config.mode==='single_thread'&&!conversation)return {kind:'quiescent',...empty};
    try {
      const frame=await this.options.relay.request('task.execution.snapshot',{node_id:this.options.nodeId,agent_id:binding.agentId,conversation_id:conversation,request_id:randomUUID()});
      if(!frame.payload.ok)throw new Error('Task source unavailable');
      const items=(frame.payload.result as {items:TaskResponsibility[]}).items;
      const tasks=items.map(({graph_id,node_id,title,status,revision,conversation,relative_url,wait,resume_request})=>({graph_id,node_id,title,status,revision,conversation:{id:conversation.id},relative_url,wait,resume_request}));
      if(tasks.some(t=>t.status==='waiting'))this.waitingAgents.add(binding.agentId);else this.waitingAgents.delete(binding.agentId);
      const repair:string[]=[];let unavailable=false;
      for(const task of tasks)if(task.status==='waiting') {
        try {
          const proof=await this.inspect({agent_id:binding.agentId,conversation_id:task.conversation.id,schedule_id:task.wait?.schedule_id??''});
          if(!proof.valid||proof.session_id!==task.wait?.session_id||proof.owner_agent_id!==task.wait?.owner_agent_id)repair.push(`${task.graph_id}/${task.node_id}`);
        } catch {unavailable=true;}
      }
      return {kind:tasks.some(t=>t.status==='doing')||repair.length?'continue':unavailable?'unavailable':'quiescent',tasks,repair_task_ids:repair,...(repair.length&&config.features?.cron_scheduling!==true?{reason:'cron_disabled'}:{})};
    } catch {return {kind:'unavailable',...empty,reason:'task_source_unavailable'};}
  }
  /** Resolve a Schedule only within the assignee's current product session scope. */
  async inspect(input:{agent_id:string;conversation_id:string;schedule_id:string}):Promise<TaskWaitInspection> {
    const config=this.options.agents.find(a=>a.agentId===input.agent_id);
    if(!config)throw new Error('Unknown task owner');
    const bindings=this.options.store.bindings().filter(b=>b.agentId===config.agentId&&this.options.store.bindingFor(b.agentId,b.conversationId)?.sessionId===b.sessionId);
    const binding=config.mode==='global'?bindings.find(b=>b.conversationId===`global:${config.agentId}`):bindings.find(b=>this.options.store.imConversation(b.agentId,b.conversationId)===input.conversation_id);
    if(!binding)return {valid:false,checked_at:new Date().toISOString(),reason_code:'session_unbound'};
    return await this.options.runtime.request('schedule.wait.inspect',{agentId:config.agentId,sessionId:binding.sessionId,scheduleId:input.schedule_id}) as TaskWaitInspection;
  }
  /** Fence, drain, and atomically pause the host-attested human stop scope. */
  async stop(binding:SessionBinding,input:RelayInput):Promise<{wasRunning:boolean;paused:number}> {
    const id=`task-stop:${binding.agentId}:${input.message.id}`;
    const intent=this.options.store.control(id)??{id,binding,input,action:'task-stop',argument:''};
    this.options.store.saveControl(intent);
    if(intent.text)return JSON.parse(intent.text);
    await this.options.runtime.request('task.execution.block',{sessionId:binding.sessionId,blocked:true});
    await this.options.runtime.request('session.ensure',(({conversationId,...value})=>value)(binding));
    const cancelled=await this.options.runtime.request('session.cancel',{sessionId:binding.sessionId}) as {wasRunning:boolean};
    await this.options.drain(binding.sessionId);
    const frame=await this.options.relay.request('task.execution.pause',{node_id:this.options.nodeId,agent_id:binding.agentId,conversation_id:this.scope(binding),request_id:randomUUID(),request_key:id});
    if(!frame.payload.ok)throw new Error('Stop is pending until Task state can be confirmed');
    const result={...cancelled,paused:Number((frame.payload.result as {paused:number}).paused)};
    intent.text=JSON.stringify(result);intent.delivered=true;this.options.store.saveControl(intent);
    await this.options.runtime.request('task.execution.block',{sessionId:binding.sessionId,blocked:false});
    return result;
  }
  /** Restore pending stop fences before any runtime session is recovered. */
  async recoverStops(agentIds?:string[]):Promise<void> {
    for(const intent of this.options.store.controls())if(intent.action==='task-stop'&&!intent.text&&(!agentIds||agentIds.includes(intent.binding.agentId)))await this.stop(intent.binding,intent.input);
  }
  /** Restore responsibility even when a UI action preceded the first chat input. */
  async recover(agentIds:string[]):Promise<void> {
    for(const agentId of agentIds) {
      const config=this.options.agents.find(a=>a.agentId===agentId)!;
      if(config.features?.task_graph===false||config.toolAllowlist&&!config.toolAllowlist.includes('task_graph'))continue;
      const frame=await this.options.relay.request('task.execution.scopes',{node_id:this.options.nodeId,agent_id:agentId,request_id:randomUUID()});
      if(!frame.payload.ok)continue;
      const scopes=(frame.payload.result as {conversation_ids:string[]}).conversation_ids;
      for(const conversationId of config.mode==='global'?(scopes.length?[`global:${agentId}`]:[]):scopes) {
        const binding=this.options.store.bindingFor(agentId,conversationId)??this.options.store.bind({agentId,conversationId,sessionId:randomUUID(),ownerId:this.options.ownerId,cwd:config.workspace,revision:config.revision});
        await this.options.runtime.request('session.ensure',(({conversationId,...value})=>value)(binding));
      }
      await this.changed(agentId);
    }
  }
  async changed(agentId:string,reset=true):Promise<void> {await this.options.runtime.request('task.execution.changed',{agentId,reset});}
  async watch():Promise<void> {await Promise.allSettled([...this.waitingAgents].map(id=>this.changed(id,false)));}
}
