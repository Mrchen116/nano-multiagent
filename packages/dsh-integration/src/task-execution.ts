import {randomUUID} from 'node:crypto';
import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import type {ToolExecution} from '@deepseek-ai/dsh-tools';
import {freezeMessage,MessageId,type UserMessage} from '@deepseek-ai/dsh-llm';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';
import type {AgentConfiguration,SessionBinding} from './index.js';
import type {RpcPeer} from './rpc.js';

const channel=(m:UserMessage)=>m.source.kind==='nano-system'?m.source.channel:undefined;
const automatic=(m:UserMessage)=>channel(m)==='task-execution';
const change=(m:UserMessage)=>channel(m)==='task-change';
interface State {
  checking:boolean;requested:boolean;queued?:string;changeQueued?:string;serial:number;seenSerial:number;
  automaticTurn:boolean;interrupted?:'error'|'cancelled'|'source'|'flush';interruptedAt?:string;recoveringTurn?:number;
  blocked:boolean;shown?:TaskExecutionSnapshot;limited?:string;
  denied:Map<string,Map<string,string>>;deniedCalls:Set<string>;
}
const fingerprint=(snapshot:TaskExecutionSnapshot)=>JSON.stringify(snapshot);
type Task=TaskExecutionSnapshot['tasks'][number];
const taskId=(task:Task)=>`${task.graph_id}/${task.node_id}`;
const taskVersion=({revision,...task}:Task)=>JSON.stringify(task);
const responsibility=(snapshot:TaskExecutionSnapshot|undefined)=>JSON.stringify(snapshot?.tasks.map(taskVersion));
const actionKey=(exec:ToolExecution)=>JSON.stringify([exec.name,exec.arguments]);

/** Schedule native turns from current product responsibility, without another execution loop. */
export class TaskExecutionDriver {
  private readonly states=new Map<string,State>();
  constructor(private readonly ctx:Context,private readonly options:{peer:RpcPeer;bindings:Map<string,SessionBinding>;configuration:(agent:Agent)=>AgentConfiguration|undefined}) {
    ctx.on('agent/status',({agent,status})=>{
      if(status!=='idle')return;
      void this.poke(agent);
    });
    ctx.on('tools/result',(exec,result)=>{
      if(!exec.agent||!options.bindings.has(exec.agent.id))return;
      const state=this.state(exec.agent.id);
      const rejected=state.deniedCalls.delete(exec.callId);
      if(result.isError&&(rejected||result.error.info?.name==='NanoApprovalDenied'))this.denied(exec,state);
      else if(!result.isError)state.denied.delete(actionKey(exec));
    });
    ctx.on('approval/request',async(request,next)=>{
      const outcome=await next();
      if(options.bindings.has(request.agent.id)&&outcome!=='allowed-once'&&request.callId)this.state(request.agent.id).deniedCalls.add(request.callId);
      return outcome;
    });
    ctx.on('agent/error',({agent})=>{this.hold(this.state(agent.id),'error');});
    ctx.on('agent/turn-stopping',({agent,turn})=>{
      const state=this.state(agent.id);
      // A successful new input proves runtime recovery, never permission for a denied action.
      if(state.recoveringTurn===turn&&['error','flush'].includes(state.interrupted??''))state.interrupted=undefined;
      state.recoveringTurn=undefined;
    });
    ctx.on('agent/disposed',({agent})=>{this.states.delete(agent.id);});
    ctx.on('agent/pre-step',async({agent,messages,signal,step,turn},next)=>{
      if(!options.bindings.has(agent.id))return next();
      const state=this.state(agent.id),own=messages.filter(automatic),changes=messages.filter(change),ordinary=messages.filter(m=>!automatic(m)&&!change(m));
      if(ordinary.length){
        state.automaticTurn=false;
        if(state.interrupted==='error'||state.interrupted==='flush')state.recoveringTurn=turn;
      }
      if(own.length)state.queued=undefined;
      if(changes.length)state.changeQueued=undefined;
      const retain=()=>messages.splice(0,messages.length,...ordinary);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      if(!this.enabled(agent)){retain();return own.length&&!ordinary.length?{kind:'reject'}:next();}
      if(state.interrupted&&own.length&&!ordinary.length){retain();return {kind:'reject'};}
      const dirty=state.serial!==state.seenSerial;
      if(!own.length&&!changes.length&&!ordinary.length&&!dirty&&!state.automaticTurn)return next();
      const serial=state.serial,snapshot=await this.snapshot(agent);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      signal.throwIfAborted();
      state.seenSerial=serial;
      const previous=state.shown;
      const changed=!previous||fingerprint(previous)!==fingerprint(snapshot);
      if(snapshot.kind==='unavailable'){
        if(!state.interrupted)this.hold(state,'source');
        retain();state.automaticTurn=false;
        if(own.length&&!ordinary.length)return {kind:'reject'};
        if(previous?.tasks.length)messages.push(this.message(agent,this.delta(previous,snapshot),'task-change'));
        return next();
      }
      if(state.interrupted==='source')state.interrupted=undefined;
      this.refreshDenials(state,snapshot);
      state.shown=snapshot;retain();
      const resumes=snapshot.tasks.filter(task=>task.resume_request&&JSON.stringify(task.resume_request)!==JSON.stringify(previous?.tasks.find(old=>old.graph_id===task.graph_id&&old.node_id===task.node_id)?.resume_request));
      if(resumes.length)messages.push(this.message(agent,JSON.stringify(resumes.map(task=>({graph_id:task.graph_id,node_id:task.node_id,action:'resume',...task.resume_request}))), 'task-human-control'));
      if(!this.runnable(state,snapshot)) {
        if(own.length&&!ordinary.length){state.automaticTurn=false;return {kind:'reject'};}
        // A tool may have just completed or parked the last Task. Preserve the
        // next native step so its result can still produce a meaningful reply.
        state.automaticTurn=false;
        // A responsibility withdrawn during ordinary work must be visible at the
        // next step; rejecting the whole turn would also discard unrelated work.
        if(changed&&previous?.tasks.length)messages.push(this.message(agent,this.delta(previous,snapshot),'task-change',changes[0]?.id));
        if(!messages.length&&changes.length&&step===1)return {kind:'reject'};
        return next();
      }
      if(own.length) {
        messages.push(this.message(agent,this.prompt(agent,snapshot,state),'task-execution',own[0]!.id));
        state.automaticTurn=ordinary.length===0;
        if(snapshot.reason==='cron_disabled'&&!snapshot.tasks.some(t=>t.status==='doing'))state.limited=fingerprint(snapshot);
      } else if(changed) {
        messages.push(this.message(agent,previous?this.delta(previous,snapshot):this.prompt(agent,snapshot,state),'task-change',changes[0]?.id));
      }
      if(!messages.length&&changes.length&&step===1)return {kind:'reject'};
      return next();
    },{prepend:true});
  }
  private state(id:string):State {
    let state=this.states.get(id);
    if(!state){state={checking:false,requested:false,serial:1,seenSerial:0,automaticTurn:false,blocked:false,denied:new Map(),deniedCalls:new Set()};this.states.set(id,state);}return state;
  }
  private hold(state:State,reason:NonNullable<State['interrupted']>):void {
    state.interrupted=reason;state.interruptedAt=responsibility(state.shown);state.recoveringTurn=undefined;
  }
  private denied(exec:ToolExecution,state:State):void {
    const snapshot=state.shown;if(!snapshot)return;
    let tasks=snapshot.tasks.filter(task=>task.status==='doing'||snapshot.repair_task_ids.includes(taskId(task)));
    const args=exec.arguments as {action?:string;graph_id?:string;node_id?:string;operations?:{node_id?:string;container_id?:string;scope_id?:string;from?:string;to?:string}[]};
    if(exec.name==='task_graph'&&args.graph_id){
      const ids=[args.node_id,...(args.operations??[]).flatMap(op=>[op.node_id,op.container_id,op.scope_id,op.from,op.to])].filter(Boolean);
      // Deletion can cover descendants absent from the responsibility projection.
      // Hold that graph's batch rather than guessing subtree membership.
      tasks=tasks.filter(task=>task.graph_id===args.graph_id&&(args.action==='delete'||!ids.length||ids.includes(task.node_id)));
    }
    // Unattributed tools can affect the current batch; do not guess a task identity.
    if(tasks.length)state.denied.set(actionKey(exec),new Map(tasks.map(task=>[taskId(task),taskVersion(task)])));
  }
  private refreshDenials(state:State,snapshot:TaskExecutionSnapshot):void {
    const current=new Map(snapshot.tasks.map(task=>[taskId(task),taskVersion(task)]));
    for(const [action,tasks] of state.denied){
      for(const [id,version] of tasks)if(current.get(id)!==version)tasks.delete(id);
      if(!tasks.size)state.denied.delete(action);
    }
  }
  private heldTasks(state:State):Set<string> {return new Set([...state.denied.values()].flatMap(tasks=>[...tasks.keys()]));}
  private runnable(state:State,snapshot:TaskExecutionSnapshot):boolean {
    const held=this.heldTasks(state);
    return snapshot.kind==='continue'&&snapshot.tasks.some(task=>!held.has(taskId(task))&&(task.status==='doing'||snapshot.repair_task_ids.includes(taskId(task))));
  }
  private enabled(agent:Agent):boolean {
    const config=this.options.configuration(agent);
    return !!config&&config.features?.task_graph!==false&&(!config.toolAllowlist||config.toolAllowlist.includes('task_graph'));
  }
  private identity(agent:Agent){const binding=this.options.bindings.get(agent.id)!;return {sessionId:agent.id,agentId:binding.agentId,ownerId:binding.ownerId};}
  private async snapshot(agent:Agent):Promise<TaskExecutionSnapshot> {
    try{return await this.options.peer.request('product.task_execution.snapshot',this.identity(agent)) as TaskExecutionSnapshot;}
    catch{return {kind:'unavailable',tasks:[],repair_task_ids:[],reason:'task_source_unavailable'};}
  }
  private prompt(agent:Agent,snapshot:TaskExecutionSnapshot,state:State):string {
    const closing=this.options.configuration(agent)?.mode==='global'
      ? 'Use send_message to actually deliver meaningful results or a new blocker to the Task\'s fixed conversation. Finish with a brief non-empty private closing note about what was delivered or why no public update was needed.'
      : 'Deliver meaningful results or a new blocker to the Task conversation. Use NO_REPLY only when the existing SingleThread delivery rules call for silence.';
    return [
      'Continue working on your owned Tasks in this same session. The current workspace, tool results and durable Task state are authoritative: inspect them rather than relying only on earlier narration.',
      'Make concrete progress on executable work and verify the result. Read details or discussion only as needed. Ending a reply does not finish a Task; before marking completed, check the whole objective and record evidence.',
      'Before waiting, verify the blocker, reconsider whether it is necessary, and try authorized alternatives or independent parts. If another person or Agent is needed, confirm your request was actually delivered. Create a real future native Schedule, then record waiting with its reason and schedule_id; the next check must be within one hour. Choose the interval for the actual task, with no fixed default.',
      'At a scheduled recheck, read current Task and external facts again, including unannounced recovery. Even if the blocker is unchanged, reconsider other permitted ways forward. Resume executable work or renew a valid check within one hour. A relevant reply can resume earlier. Repair invalid waiting arrangements; continue other doing Tasks.',
      'Do not reopen paused, closed, done or in_review Tasks merely because a timer fired. This reminder grants no new human authority. Do not bypass a denied action. Unchanged automatic retries for held Task IDs are suspended; new evidence, permitted alternatives and independent work can still be handled.',
      closing+' Do not repeat an already confirmed delivery or publish unchanged routine progress.',
      JSON.stringify({...snapshot,automatic_retry_held_task_ids:[...this.heldTasks(state)]}),
    ].join('\n');
  }
  private delta(before:TaskExecutionSnapshot,after:TaskExecutionSnapshot):string {
    if(after.kind==='unavailable')return 'Current Task responsibility cannot be verified. Do not issue further Task-related actions based on the previous snapshot until a fresh read succeeds. This does not complete or pause any task; unrelated work may continue.';
    const ids=new Set(after.tasks.map(t=>`${t.graph_id}/${t.node_id}`));
    const removed=before.tasks.filter(t=>!ids.has(`${t.graph_id}/${t.node_id}`)).map(t=>`${t.graph_id}/${t.node_id}`);
    const changed=after.tasks.filter(t=>JSON.stringify(before.tasks.find(p=>p.graph_id===t.graph_id&&p.node_id===t.node_id))!==JSON.stringify(t));
    return 'Task responsibility changed. Stop further actions for removed/reassigned/paused/completed Tasks. Continue unrelated user work and remaining responsibilities. This is not human consent.\n'+JSON.stringify({removed,changed,doing:after.tasks.filter(t=>t.status==='doing').map(t=>`${t.graph_id}/${t.node_id}`),waiting:after.tasks.filter(t=>t.status==='waiting').map(t=>`${t.graph_id}/${t.node_id}`),repair_task_ids:after.repair_task_ids});
  }
  private message(agent:Agent,text:string,sourceChannel:'task-execution'|'task-change'|'task-human-control',id=MessageId(`${sourceChannel}:${randomUUID()}`)):UserMessage {
    return freezeMessage({id,role:'user',source:{kind:'nano-system',actorId:this.options.bindings.get(agent.id)!.agentId,channel:sourceChannel,messageId:id},content:[{type:'text',text}]});
  }
  private restore(agent:Agent,messages:UserMessage[]):void {
    for(const message of messages.toReversed())if(!agent.inbox.nextTurn.some(m=>m.id===message.id)&&!agent.inbox.nextStep.some(m=>m.id===message.id))agent.inbox.prepend('next-turn',message);
  }
  /** Reserve one continuation after persistence and a second native inbox check. */
  async poke(agent:Agent,reconsider=false):Promise<void> {
    if(!this.options.bindings.has(agent.id)||!this.enabled(agent))return;
    const state=this.state(agent.id);
    if(state.checking){state.requested=true;return;}
    if(state.queued||state.blocked||['error','cancelled'].includes(state.interrupted??'')&&!reconsider||agent.status!=='idle'||agent.inbox.nextTurn.length||agent.inbox.nextStep.length)return;
    state.checking=true;
    try {
      await this.ctx.sessions.flush(agent.session);
      const snapshot=await this.snapshot(agent);
      if(snapshot.kind==='unavailable'){if(!state.interrupted)this.hold(state,'source');return;}
      this.refreshDenials(state,snapshot);
      if(!this.runnable(state,snapshot)||state.limited===fingerprint(snapshot)||state.blocked||agent.status!=='idle'||agent.inbox.nextTurn.length||agent.inbox.nextStep.length)return;
      if(state.interrupted){
        if(['error','cancelled'].includes(state.interrupted)&&(!reconsider||responsibility(snapshot)===state.interruptedAt))return;
        state.interrupted=undefined;
      }
      const message=this.message(agent,this.prompt(agent,snapshot,state),'task-execution');state.queued=message.id;
      agent.followup(message);
    } catch {this.hold(state,'flush');}
    finally {state.checking=false;if(state.requested){state.requested=false;void this.poke(agent);}}
  }
  /** Observe bound native sessions without loading or waking them. */
  observe(agentId:string):{state:'running'|'idle'} {
    for(const [id,binding] of this.options.bindings)if(binding.agentId===agentId&&this.ctx.agents.get(id as Agent['id'])?.status==='running')return {state:'running'};
    return {state:'idle'};
  }
  /** Retry runtime failures after an effective execution configuration change. */
  configured(agentId:string):void {
    for(const [id,binding] of this.options.bindings)if(binding.agentId===agentId) {
      const state=this.state(id);
      if(state.interrupted&&state.interrupted!=='cancelled') {
        state.interrupted=undefined;
        const agent=this.ctx.agents.get(id as Agent['id']);
        // A failed native turn can leave ordinary input queued. Wake that input
        // after repair; poke intentionally yields when the inbox is nonempty.
        if(agent?.status==='idle'&&!state.blocked&&this.enabled(agent)&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))
          agent.followup(this.message(agent,'Recheck current Task responsibility after execution configuration was repaired.','task-change'));
      }
    }
    this.changed(agentId);
  }
  /** Merge change hints and refresh at the nearest native model boundary. */
  changed(agentId:string,reset=true):void {
    for(const [id,binding] of this.options.bindings)if(binding.agentId===agentId) {
      const state=this.state(id);state.serial++;if(reset)state.limited=undefined;
      const agent=this.ctx.agents.get(id as Agent['id']);if(!agent||state.blocked||!this.enabled(agent))continue;
      if(agent.status==='running'&&!state.interrupted&&!state.changeQueued) {
        const message=this.message(agent,'Recheck current Task responsibility before the next action.','task-change');state.changeQueued=message.id;agent.steer(message);
      } else void this.poke(agent,reset);
    }
  }
  /** Fence all native admission while a durable stop is unresolved, retaining queued input. */
  block(sessionId:string,blocked:boolean):void {
    const state=this.state(sessionId);state.blocked=blocked;
    const agent=this.ctx.agents.get(sessionId as Agent['id']);
    if(!blocked&&agent?.status==='idle'&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))agent.followup(this.message(agent,'Recheck current Task state after human stop.','task-change'));
  }
  interrupt(sessionId:string):void {this.hold(this.state(sessionId),'cancelled');}
}
