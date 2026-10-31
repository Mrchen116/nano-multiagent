import {randomUUID} from 'node:crypto';
import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import type {ToolExecution} from '@deepseek-ai/dsh-tools';
import {freezeMessage,MessageId,type UserMessage} from '@deepseek-ai/dsh-llm';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';
import type {AgentConfiguration,SessionBinding} from './index.js';
import type {RpcPeer} from './rpc.js';
import {inputEvidence} from './input-evidence.js';
import {scheduleEvidence} from './schedule-evidence.js';

const channel=(m:UserMessage)=>m.source.kind==='nano-system'?m.source.channel:undefined;
const automatic=(m:UserMessage)=>channel(m)==='task-execution'||channel(m)==='task-wait-repair';
const change=(m:UserMessage)=>channel(m)==='task-change';
const externalWake=(m:UserMessage)=>m.source.kind==='user'||m.source.kind==='schedule'||
  m.source.kind==='nano-system'&&!['task-execution','task-change','task-human-control','task-context','task-reminder','task-context-limitation','schedule-change','task-wait-repair','revalidation','personal-state'].includes(m.source.channel);
const freshWake=(message:UserMessage,stoppedAt:number|undefined)=>{const admittedAt=(message.source as {admittedAt?:number}).admittedAt;return externalWake(message)&&typeof admittedAt==='number'&&admittedAt>(stoppedAt??Infinity);};
const SHORT_RUN_LIMIT=256;
const SUSTAINED_STEPS=3;
interface State {
  checking:boolean;requested:boolean;queued?:string;serial:number;seenSerial:number;
  automaticTurn:boolean;stoppedAt?:number;interrupted?:'error'|'cancelled'|'source'|'flush';interruptedAt?:string;recoveringTurn?:number;
  blocked:boolean;contextUnavailable?:boolean;shown?:TaskExecutionSnapshot;limited?:string;
  denied:Map<string,Map<string,string>>;deniedCalls:Set<string>;
  run?:{steps:number;automatic:boolean;external:boolean};
}
const fingerprint=(snapshot:TaskExecutionSnapshot)=>JSON.stringify(snapshot);
type Task=TaskExecutionSnapshot['tasks'][number];
const taskId=(task:{graph_id:string;node_id:string})=>`${task.graph_id}/${task.node_id}`;
const taskVersion=({revision,...task}:Task)=>JSON.stringify(task);
const responsibility=(snapshot:TaskExecutionSnapshot|undefined)=>JSON.stringify(snapshot?.tasks.map(taskVersion));
const actionKey=(exec:ToolExecution)=>JSON.stringify([exec.name,exec.arguments]);

/** Schedule native turns from current product responsibility, without another execution loop. */
export class TaskExecutionDriver {
  private stopped = false;
  /** Prevent any late idle/change callback from producing new work. */
  stop(): void { this.stopped = true; }
  /** Record the current step's source authority without reviving uncertain automatic work.
   *
   * Args:
   *   agent: Bound native execution.
   *   available: Whether complete original/source reconciliation succeeded.
   */
  contextAvailability(agent:Agent,available:boolean):void {
    const state=this.state(agent.id);state.contextUnavailable=!available;
    if(!available){
      if(state.queued)agent.inbox.remove(MessageId(state.queued));
      state.queued=undefined;state.automaticTurn=false;
      if(!state.interrupted)this.hold(state,'source');
    }
  }
  private readonly states=new Map<string,State>();
  private readonly shortRuns=new Map<string,number>();
  constructor(private readonly ctx:Context,private readonly options:{peer:RpcPeer;bindings:Map<string,SessionBinding>;configuration:(agent:Agent)=>AgentConfiguration|undefined;lifecycleRevision?:(agentId:string)=>number;allowed?:(agentId:string)=>boolean}) {
    ctx.on('session/event',(session,event)=>{
      const binding=options.bindings.get(session.id);if(!binding)return;
      const state=this.state(session.id),agentId=binding.agentId;
      if(event.type==='turn/start')state.run={steps:0,automatic:false,external:false};
      const run=state.run;if(!run)return;
      if(event.type==='step/start') {
        // pre-step is only a proposal; rejected steps and provider retries are not work rounds.
        if(++run.steps>=SUSTAINED_STEPS&&!this.exhausted(agentId))this.shortRuns.set(agentId,0);
      } else if(event.type==='user/message') {
        if(automatic(event.data))run.automatic=true;
        if(externalWake(event.data)) {
          run.external=true;
          // Admission of an independent input reopens a stopped Agent, but does
          // not replenish a still-active short-run streak.
          if(this.exhausted(agentId))this.shortRuns.set(agentId,0);
        }
      } else if(event.type==='turn/end') {
        if(run.automatic&&!run.external&&run.steps>0&&run.steps<SUSTAINED_STEPS) {
          const count=Math.min(SHORT_RUN_LIMIT,(this.shortRuns.get(agentId)??0)+1);
          if(count===SHORT_RUN_LIMIT&&!this.exhausted(agentId))ctx.logger('nano-task-execution').warn(`Agent ${agentId}: automatic Task continuation stopped after ${SHORT_RUN_LIMIT} consecutive short runs; waiting for an independent wake.`);
          this.shortRuns.set(agentId,count);
        }
        state.run=undefined;
      }
    });
    ctx.on('agent/status',({agent,status})=>{
      if(status!=='idle')return;
      void this.poke(agent);
    });
    // D9 is explanatory, not authority: prevent even a model-forced Task tool call.
    ctx.on('tools/pre-execute',async(exec,next)=>{
      if(exec.name==='task_graph'&&exec.agent&&options.bindings.has(exec.agent.id)){
        const state=this.state(exec.agent.id);
        if(state.contextUnavailable||(await this.snapshot(exec.agent)).kind==='unavailable')return {kind:'deny',reason:'Current Task facts or source permissions are unavailable; revalidate before using Task tools.'};
      }
      return next();
    },{prepend:true});
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
      const state=this.state(agent.id);
      const own=messages.filter(automatic),changes=messages.filter(change),ordinary=messages.filter(m=>!automatic(m)&&!change(m));
      if(ordinary.length){
        if(state.interrupted==='cancelled'&&ordinary.some(message=>freshWake(message,state.stoppedAt)))state.interrupted=undefined;
        state.automaticTurn=false;
        if(state.interrupted==='error'||state.interrupted==='flush')state.recoveringTurn=turn;
      }
      if(own.length)state.queued=undefined;
      const retain=()=>messages.splice(0,messages.length,...ordinary);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      if(own.length&&this.exhausted(options.bindings.get(agent.id)!.agentId)&&!ordinary.some(externalWake)){retain();return {kind:'reject'};}
      if(!this.enabled(agent)&&!state.contextUnavailable){retain();return own.length&&!ordinary.length?{kind:'reject'}:next();}
      if(state.interrupted&&own.length&&!ordinary.length){retain();return {kind:'reject'};}
      const dirty=state.serial!==state.seenSerial;
      if(!own.length&&!changes.length&&!ordinary.length&&!dirty&&!state.automaticTurn&&!state.contextUnavailable)return next();
      const serial=state.serial,snapshot=await this.snapshot(agent);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      if(own.length&&this.exhausted(options.bindings.get(agent.id)!.agentId)&&!ordinary.some(externalWake)){retain();return {kind:'reject'};}
      signal.throwIfAborted();
      state.seenSerial=serial;
      if(snapshot.kind==='unavailable'){
        if(!state.interrupted)this.hold(state,'source');
        retain();state.automaticTurn=false;
        if(own.length&&!ordinary.length)return {kind:'reject'};
        messages.push(this.message(agent,"Current Task facts or the identified source permissions cannot be verified. Do not continue affected Task actions from an older snapshot or use content whose access has not been verified. This does not complete or pause any Task. Independently authorized work outside the affected scope may continue. Recheck through the available tools when the limitation is resolved; do not invent a missing Schedule or a completed synchronization."+'\n'+JSON.stringify({reason_code:snapshot.reason??'task_source_unavailable',checked_at:new Date().toISOString()}),'task-context-limitation'));
        return next();
      }
      if(state.interrupted==='source')state.interrupted=undefined;
      this.refreshDenials(state,snapshot);
      state.shown=snapshot;retain();
      const ids=new Set<string>(ordinary.filter(message=>message.source.kind==='schedule').map(message=>message.id));
      const checks=scheduleEvidence(agent.session.snapshotEvents()).filter(item=>ids.has(item.messageId)).flatMap(item=>snapshot.tasks
        .filter(task=>task.status==='waiting'&&task.wait?.schedule_id===item.scheduleId&&task.wait.session_id===agent.id)
        .map(task=>({graph_id:task.graph_id,node_id:task.node_id,schedule_id:item.scheduleId,occurrence_id:item.messageId,planned_check_at:item.scheduledAt??task.wait!.next_check_at,checked_at:new Date().toISOString()})));
      if(!this.runnable(state,snapshot)) {
        state.automaticTurn=false;
        if(own.length&&!ordinary.length)return {kind:'reject'};
        if(checks.length)messages.push(this.message(agent,this.prompt(agent,snapshot,state,false,checks),'task-reminder'));
        return next();
      }
      if(own.length||checks.length||snapshot.repair_task_ids.length) {
        const repairOnly=own.length>0&&own.every(message=>channel(message)==='task-wait-repair');
        messages.push(this.message(agent,this.prompt(agent,snapshot,state,own.length>0&&!repairOnly,checks),repairOnly?'task-wait-repair':own.length?'task-execution':'task-reminder',own[0]?.id));
        // Each stable receipt remains consumable; only the first carries this
        // step's single combined Task package rather than duplicating it.
        if(repairOnly)messages.push(...own.slice(1));
        state.automaticTurn=own.length>0&&ordinary.length===0;
        if(own.length&&snapshot.reason==='cron_disabled'&&!snapshot.tasks.some(t=>t.status==='doing'))state.limited=fingerprint(snapshot);
      }
      return next();
    },{prepend:true});
  }
  private state(id:string):State {
    let state=this.states.get(id);
    if(!state){state={checking:false,requested:false,serial:1,seenSerial:0,automaticTurn:false,blocked:false,denied:new Map(),deniedCalls:new Set()};this.states.set(id,state);}return state;
  }
  private exhausted(agentId:string):boolean {return (this.shortRuns.get(agentId)??0)>=SHORT_RUN_LIMIT;}
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
    return !this.stopped&&!!config&&this.options.allowed?.(config.agentId)!==false&&config.features?.task_graph!==false&&(!config.toolAllowlist||config.toolAllowlist.includes('task_graph'));
  }
  private identity(agent:Agent){const binding=this.options.bindings.get(agent.id)!;return {sessionId:agent.id,agentId:binding.agentId,ownerId:binding.ownerId};}
  private async snapshot(agent:Agent):Promise<TaskExecutionSnapshot> {
    if(agent.status==='running'&&this.state(agent.id).contextUnavailable)return {kind:'unavailable',tasks:[],repair_task_ids:[],reason:'task_context_sync_unavailable'};
    try{return await this.options.peer.request('product.task_execution.snapshot',this.identity(agent)) as TaskExecutionSnapshot;}
    catch{return {kind:'unavailable',tasks:[],repair_task_ids:[],reason:'task_source_unavailable'};}
  }
  private prompt(agent:Agent,snapshot:TaskExecutionSnapshot,state:State,automatic=true,checks:{graph_id:string;node_id:string;schedule_id:string;occurrence_id:string;planned_check_at:string;checked_at:string}[]=[]):string {
    const closing=this.options.configuration(agent)?.mode==='global'
      ? "Deliver meaningful results or a new blocker with send_message to the Task's fixed conversation. Skip confirmed feedback and unchanged routine progress. End with a brief non-empty private closing note."
      : "Deliver meaningful results or a new blocker to the Task's fixed conversation. Skip confirmed feedback and unchanged routine progress. Use NO_REPLY only when the SingleThread delivery protocol requires silence.";
    const tasks=snapshot.tasks.map(task=>({graph_id:task.graph_id,node_id:task.node_id,title:task.title,status:task.status,conversation_id:task.conversation.id,relative_url:task.relative_url,
      ...(task.wait?{wait:{reason:task.wait.reason,schedule_id:task.wait.schedule_id,next_check_at:task.wait.next_check_at}}:{})}));
    const refs=new Set(tasks.map(taskId)),checked=new Set(checks.map(taskId));
    const repairs=(snapshot.repairs??[]).filter(repair=>refs.has(taskId(repair))&&!checked.has(taskId(repair)));
    const limits=snapshot.reason==='cron_disabled'?[{reason_code:'cron_disabled',reason:'Cron scheduling is disabled for this Agent.',blocked_actions:['schedule_create','schedule_update'],
      task_refs:tasks.filter(task=>snapshot.repair_task_ids.includes(taskId(task))&&!checked.has(taskId(task))).map(({graph_id,node_id})=>({graph_id,node_id})),checked_at:new Date().toISOString()}].filter(limit=>limit.task_refs.length):[];
    const held_actions=[...state.denied].map(([action,held])=>({task_refs:tasks.filter(task=>held.has(taskId(task))).map(({graph_id,node_id})=>({graph_id,node_id})),action:JSON.parse(action)})).filter(held=>held.task_refs.length);
    const context={tasks,...(checks.length?{checks}:{}),...(repairs.length?{repairs}:{}),...(limits.length?{limits}:{}),...(held_actions.length?{held_actions}:{})};
    return [limits.length?"Cron scheduling is disabled for this Agent. The affected Tasks and unavailable actions are listed in limits. Their Task state and Schedule problem have been verified; the limitation is not an unknown lookup result.\n\nDo not try to create or renew Schedules while this capability is disabled, and do not bypass the configuration or claim that a future check is arranged. Reassess whether the affected work can proceed without waiting. If it cannot, communicate the concrete limitation when useful and retain the actual Task state; do not claim completion or silently change it to paused. Enabling a capability requires the existing configuration and authorization process. Continue independent executable work. Resume Schedule repair only when current capability facts permit it; do not repeat unchanged automatic attempts or public notices.":undefined,automatic?"Continue your owned Tasks in this same session. Inspect the current workspace, tool results and durable Task state instead of relying only on earlier narration. Read Task details and discussion as needed.\n\nMake concrete progress on executable work and verify it. Ending a reply does not finish a Task; before completion, check the whole objective and record evidence.\n\nBefore waiting, verify the blocker, reconsider whether it is necessary and try authorized alternatives or independent work. Confirm any needed request was delivered. When scheduling is available, create a real future native Schedule, then record waiting with its reason and schedule_id. Choose the interval for the actual Task, without a fixed default, and check again within one hour. Follow any verified runtime limitation below instead of attempting its unavailable actions. Continue other doing Tasks.\n\nDo not reopen paused, closed, done or in_review Tasks because of this reminder. It grants no new human authority. Do not bypass a denied action. For listed held actions, unchanged automatic retries remain suspended; new evidence, permitted alternatives and independent work may still be handled.":undefined,
      checks.length?"This scheduled check concerns the Tasks listed in checks. Read their current state and external facts; recovery may have occurred without a message. Reconsider whether each blocker is still necessary and whether authorized alternatives or independent parts can progress.\n\nIf work is executable, continue it. If waiting is still necessary and scheduling is available, establish a valid next check within one hour using an interval appropriate to the Task. Otherwise follow the verified runtime limitation rather than attempting unavailable actions. Continue other doing Tasks. This timer is not consent and cannot reopen paused, closed, done or in_review Tasks.":undefined,repairs.length?"The Tasks listed in repairs are still waiting, but their linked Schedules are not valid for the planned wake. The verified reason for each Task is included. Check whether the Task is already finished. Continue executable work, or establish a new valid check within one hour if waiting is still necessary and scheduling is available. Follow any verified runtime limitation instead of attempting unavailable actions. Reconsider the blocker and authorized alternatives; continue other doing Tasks.\n\nThis reminder does not change Task state, reopen paused/closed/done/in_review work or grant authority. A Schedule deletion receipt does not replace handling these Tasks.":undefined,
      'Current Task context:',JSON.stringify(context),closing].filter(part=>part!==undefined).join('\n\n');
  }
  private message(agent:Agent,text:string,sourceChannel:'task-execution'|'task-reminder'|'task-context-limitation'|'task-human-control'|'task-wait-repair',id=MessageId(`${sourceChannel}:${randomUUID()}`)):UserMessage {
    return freezeMessage({id,role:'user',source:{kind:'nano-system',lifecycle_revision:this.options.lifecycleRevision?.(this.options.bindings.get(agent.id)!.agentId)??1,actorId:this.options.bindings.get(agent.id)!.agentId,channel:sourceChannel,messageId:id},content:[{type:'text',text}]});
  }
  private restore(agent:Agent,messages:UserMessage[]):void {
    for(const message of messages.toReversed())if(!agent.inbox.nextTurn.some(m=>m.id===message.id)&&!agent.inbox.nextStep.some(m=>m.id===message.id))agent.inbox.prepend(channel(message)==='task-human-control'?'next-step':'next-turn',message);
  }
  /** Notifications do not override the stop fence or an explicit cancellation. */
  passive(sessionId:string):boolean {const state=this.state(sessionId);return state.blocked||state.interrupted==='cancelled';}
  /** Admit a stable repair candidate; native pre-step re-reads facts before projection. */
  async repair(agent:Agent,inputId:string):Promise<void>{
    if(inputEvidence(agent.session.snapshotEvents(),inputId).accepted)return;
    const message=this.message(agent,'Recheck the current waiting Tasks and their linked Schedules.','task-wait-repair',MessageId(inputId));
    if(this.passive(agent.id))agent.inject(message);else agent.followup(message);
    await this.ctx.sessions.flush(agent.session);
  }
  /** Reserve one continuation after persistence and a second native inbox check. */
  async poke(agent:Agent,reconsider=false):Promise<void> {
    if(!this.options.bindings.has(agent.id)||!this.enabled(agent))return;
    const agentId=this.options.bindings.get(agent.id)!.agentId;
    if(this.exhausted(agentId))return;
    const state=this.state(agent.id);
    if(state.checking){state.requested=true;return;}
    if(state.contextUnavailable&&!reconsider)return;
    if(state.queued||state.blocked||['error','cancelled'].includes(state.interrupted??'')&&!reconsider||agent.status!=='idle'||!reconsider&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))return;
    state.checking=true;
    try {
      await this.ctx.sessions.flush(agent.session);
      const snapshot=await this.snapshot(agent);
      if(!this.enabled(agent)||this.exhausted(agentId))return;
      if(snapshot.kind==='unavailable'){if(!state.interrupted)this.hold(state,'source');return;}
      this.refreshDenials(state,snapshot);
      if(!this.runnable(state,snapshot)||state.limited===fingerprint(snapshot)||state.blocked||agent.status!=='idle'||!reconsider&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))return;
      if(state.interrupted){
        if(state.interrupted==='cancelled') {
          const freshInput=agent.session.snapshotEvents().some(event=>event.type==='user/message'&&freshWake(event.data,state.stoppedAt));
          const resumed=snapshot.tasks.some(task=>task.status==='doing'&&task.resume_request&&task.resume_request.revision<=task.revision&&Date.parse(task.resume_request.at)>(state.stoppedAt??Infinity));
          if(!freshInput&&!resumed)return;
        } else if(state.interrupted==='error'&&(!reconsider||responsibility(snapshot)===state.interruptedAt))return;
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
          agent.followup(this.message(agent,'Continue current Task work.','task-execution'));
      }
    }
    this.changed(agentId);
  }
  /** Merge change hints and refresh at the nearest native model boundary. */
  changed(agentId:string,reset=true):void {
    for(const [id,binding] of this.options.bindings)if(binding.agentId===agentId) {
      const state=this.state(id);state.serial++;if(reset)state.limited=undefined;
      const agent=this.ctx.agents.get(id as Agent['id']);if(!agent||state.blocked||!this.enabled(agent))continue;
      // Running agents revalidate on every native pre-step. The authority index
      // carries the original change; a second private steer would duplicate it.
      if(agent.status!=='running')void this.poke(agent,reset);
    }
  }
  /** Fence all native admission while a durable stop is unresolved, retaining queued input. */
  block(sessionId:string,blocked:boolean):void {
    const state=this.state(sessionId);state.blocked=blocked;
    // Releasing a stop fence permits a future wake; queued context is not a wake request.
  }
  interrupt(sessionId:string,stoppedAt?:string):void {const state=this.state(sessionId);this.hold(state,'cancelled');const at=stoppedAt?Date.parse(stoppedAt):NaN;state.stoppedAt=Math.max(state.stoppedAt??-Infinity,Number.isFinite(at)?at:Date.now());}
}
