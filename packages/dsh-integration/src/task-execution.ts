import {randomUUID} from 'node:crypto';
import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import {freezeMessage,MessageId,type UserMessage} from '@deepseek-ai/dsh-llm';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';
import type {AgentConfiguration,SessionBinding} from './index.js';
import type {RpcPeer} from './rpc.js';
import {scheduleEvidence} from './schedule-evidence.js';
import {subagentRecoveryChannel} from './subagent-recovery.js';

const channel=(m:UserMessage)=>m.source.kind==='nano-system'?m.source.channel:undefined;
const automatic=(m:UserMessage)=>channel(m)==='task-execution';
const change=(m:UserMessage)=>channel(m)==='task-change';
const externalWake=(m:UserMessage)=>m.source.kind==='user'||m.source.kind==='schedule'||
  m.source.kind==='nano-system'&&!['task-execution','task-change','task-human-control','task-context','task-reminder','task-context-limitation','schedule-change','revalidation','personal-state',subagentRecoveryChannel].includes(m.source.channel);
const freshWake=(message:UserMessage,stoppedAt:number|undefined)=>{const admittedAt=(message.source as {admittedAt?:number}).admittedAt;return externalWake(message)&&typeof admittedAt==='number'&&admittedAt>(stoppedAt??Infinity);};

interface State {
  checking:boolean;requested:boolean;queued?:string;serial:number;seenSerial:number;
  automaticTurn:boolean;stoppedAt?:number;interrupted?:'error'|'cancelled'|'source'|'flush';interruptedAt?:string;recoveringTurn?:number;
  blocked:boolean;contextUnavailable?:boolean;shown?:TaskExecutionSnapshot;
  unavailableInputs?:{inputId:string;conversationId:string}[];
  ackedInMemory:Map<string,number>;
  pendingTurnRevisions:Map<string,number>;
}
type Task=TaskExecutionSnapshot['tasks'][number];
const taskId=(task:{graph_id:string;node_id:string})=>`${task.graph_id}/${task.node_id}`;
const taskVersion=({revision,...task}:Task)=>JSON.stringify(task);
const responsibility=(snapshot:TaskExecutionSnapshot|undefined)=>JSON.stringify(snapshot?.tasks.map(taskVersion));

/** Schedule single-shot edge-triggered doing wakes and scheduled waiting checks without idle polling loops. */
export class TaskExecutionDriver {
  private stopped = false;
  /** Prevent any late idle/change callback from producing new work. */
  stop(): void { this.stopped = true; }
  /** Record the current step's source authority without reviving uncertain automatic work. */
  contextAvailability(agent:Agent,available:boolean,inputs:{inputId:string;conversationId:string}[]=[]):void {
    const state=this.state(agent.id);state.contextUnavailable=!available;state.unavailableInputs=inputs;
    if(!available){
      if(state.queued)agent.inbox.remove(MessageId(state.queued));
      state.queued=undefined;state.automaticTurn=false;
      if(!state.interrupted)this.hold(state,'source');
    }
  }
  private readonly states=new Map<string,State>();
  constructor(private readonly ctx:Context,private readonly options:{peer:RpcPeer;bindings:Map<string,SessionBinding>;configuration:(agent:Agent)=>AgentConfiguration|undefined;lifecycleRevision?:(agentId:string)=>number;allowed?:(agentId:string)=>boolean;clockNow?:()=>number}) {
    ctx.on('session/event',(session,event)=>{
      const binding=options.bindings.get(session.id);if(!binding)return;
      const state=this.state(session.id);
      if(event.type==='turn/start') {
        state.pendingTurnRevisions.clear();
      } else if(event.type==='turn/end') {
        if(event.data.reason.kind==='completed'&&state.pendingTurnRevisions.size>0) {
          const items:{graph_id:string;node_id:string;revision:number}[]=[];
          for(const [key,revision] of state.pendingTurnRevisions) {
            state.ackedInMemory.set(key,Math.max(state.ackedInMemory.get(key)??0,revision));
            const sep=key.indexOf('/');
            items.push({graph_id:key.slice(0,sep),node_id:key.slice(sep+1),revision});
          }
          state.pendingTurnRevisions.clear();
          void options.peer.request('product.task_execution.ack',{sessionId:session.id,agentId:binding.agentId,ownerId:binding.ownerId,items}).catch(()=>{});
        } else {
          state.pendingTurnRevisions.clear();
        }
      }
    });
    ctx.on('agent/status',({agent,status})=>{
      if(status!=='idle')return;
      void this.poke(agent);
    });
    ctx.on('tools/pre-execute',async(exec,next)=>{
      if(exec.name==='task_graph'&&exec.agent&&options.bindings.has(exec.agent.id)){
        const state=this.state(exec.agent.id);
        if(state.contextUnavailable||(await this.snapshot(exec.agent)).kind==='unavailable')return {kind:'deny',reason:'Current Task facts or source permissions are unavailable; revalidate before using Task tools.'};
      }
      return next();
    },{prepend:true});
    ctx.on('agent/error',({agent})=>{this.hold(this.state(agent.id),'error');});
    ctx.on('agent/turn-stopping',({agent,turn})=>{
      const state=this.state(agent.id);
      if(state.recoveringTurn===turn&&['error','flush'].includes(state.interrupted??''))state.interrupted=undefined;
      state.recoveringTurn=undefined;
    });
    ctx.on('agent/disposed',({agent})=>{this.states.delete(agent.id);});
    ctx.on('agent/pre-step',async({agent,messages,signal,turn},next)=>{
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
      if(!this.enabled(agent)&&!state.contextUnavailable){retain();return own.length&&!ordinary.length?{kind:'reject'}:next();}
      if(state.interrupted&&own.length&&!ordinary.length){retain();return {kind:'reject'};}
      const dirty=state.serial!==state.seenSerial;
      if(!own.length&&!changes.length&&!ordinary.length&&!dirty&&!state.automaticTurn&&!state.contextUnavailable)return next();
      const serial=state.serial,snapshot=await this.snapshot(agent);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      signal.throwIfAborted();
      state.seenSerial=serial;
      if(snapshot.kind==='unavailable'){
        if(!state.interrupted)this.hold(state,'source');
        retain();state.automaticTurn=false;
        if(own.length&&!ordinary.length)return {kind:'reject'};
        const limitation=this.limitation(agent,state,snapshot);
        if(limitation)messages.push(this.message(agent,limitation,'task-context-limitation'));
        return next();
      }
      if(state.interrupted==='source')state.interrupted=undefined;
      state.shown=snapshot;retain();
      const nowIso=new Date(this.options.clockNow?.()??Date.now()).toISOString();
      const ids=new Set<string>(ordinary.filter(message=>message.source.kind==='schedule').map(message=>message.id));
      const checks=ids.size?scheduleEvidence(agent.session.snapshotEvents()).filter(item=>ids.has(item.messageId)).flatMap(item=>snapshot.tasks
        .filter(task=>task.status==='waiting'&&task.wait?.schedule_id&&task.wait.schedule_id===item.scheduleId&&task.wait.session_id===agent.id)
        .map(task=>({graph_id:task.graph_id,node_id:task.node_id,schedule_id:item.scheduleId,occurrence_id:item.messageId,planned_check_at:item.scheduledAt??task.wait!.next_check_at,checked_at:nowIso}))):[];
      const unwoken=this.unwokenTasks(state,snapshot);
      if(!unwoken.length) {
        state.automaticTurn=false;
        if(own.length&&!ordinary.length)return {kind:'reject'};
        if(checks.length)messages.push(this.message(agent,this.prompt(agent,snapshot,false,checks),'task-reminder'));
        return next();
      }
      for(const task of unwoken) {
        if(task.doing_wake?.revision)state.pendingTurnRevisions.set(taskId(task),task.doing_wake.revision);
      }
      messages.push(this.message(agent,this.prompt(agent,snapshot,true,checks),own.length?'task-execution':'task-reminder',own[0]?.id));
      state.automaticTurn=own.length>0&&ordinary.length===0;
      return next();
    },{prepend:true});
  }
  private state(id:string):State {
    let state=this.states.get(id);
    if(!state){state={checking:false,requested:false,serial:1,seenSerial:0,automaticTurn:false,blocked:false,ackedInMemory:new Map(),pendingTurnRevisions:new Map()};this.states.set(id,state);}return state;
  }
  private hold(state:State,reason:NonNullable<State['interrupted']>):void {
    state.interrupted=reason;state.interruptedAt=responsibility(state.shown);state.recoveringTurn=undefined;
  }
  private unwokenTasks(state:State,snapshot:TaskExecutionSnapshot):Task[] {
    if(snapshot.kind!=='continue')return [];
    return snapshot.tasks.filter(task=>{
      if(task.status!=='doing'||!task.unwoken_doing||!task.doing_wake?.revision)return false;
      const seen=Math.max(state.ackedInMemory.get(taskId(task))??0,state.pendingTurnRevisions.get(taskId(task))??0);
      return task.doing_wake.revision>seen;
    });
  }
  private enabled(agent:Agent):boolean {
    const config=this.options.configuration(agent);
    return !this.stopped&&!!config&&this.options.allowed?.(config.agentId)!==false&&config.features?.task_graph!==false&&(!config.toolAllowlist||config.toolAllowlist.includes('task_graph'));
  }
  private identity(agent:Agent){const binding=this.options.bindings.get(agent.id)!;return {sessionId:agent.id,agentId:binding.agentId,ownerId:binding.ownerId};}
  private async snapshot(agent:Agent):Promise<TaskExecutionSnapshot> {
    if(agent.status==='running'&&this.state(agent.id).contextUnavailable)return {kind:'unavailable',tasks:[],reason:'task_context_sync_unavailable'};
    try{return await this.options.peer.request('product.task_execution.snapshot',this.identity(agent)) as TaskExecutionSnapshot;}
    catch{return {kind:'unavailable',tasks:[],reason:'task_source_unavailable'};}
  }
  /** Explain only known affected work; native visible evidence owns repetition. */
  private limitation(agent:Agent,state:State,snapshot:TaskExecutionSnapshot):string|undefined {
    const tasks=snapshot.tasks.length?snapshot.tasks:state.shown?.tasks??[];
    const task_refs=tasks.filter(task=>task.status==='doing'||task.status==='waiting').map(({graph_id,node_id})=>({graph_id,node_id})).sort((a,b)=>taskId(a).localeCompare(taskId(b)));
    const input_refs=(state.unavailableInputs??[]).map(({inputId,conversationId})=>({input_id:inputId,conversation_id:conversationId})).sort((a,b)=>a.input_id.localeCompare(b.input_id));
    if(!task_refs.length&&!input_refs.length)return;
    const text='Verification is unavailable for the Task references or queued Task inputs listed below. Recheck their current facts and access before acting on them; queued input content has not been delivered. This does not complete or pause a Task. Independently authorized work can continue.\n'
      +JSON.stringify({reason_code:snapshot.reason??'task_source_unavailable',task_refs,input_refs});
    const events=agent.session.snapshotEvents(),visible=new Set(agent.session.surface.nodes);
    const calls=new Map(events.filter(event=>event.type==='tool/call').map(event=>[event.data.callId,event.data.name]));
    for(const event of events.toReversed()){
      if(!visible.has(event.seq))continue;
      if(event.type==='tool/result'&&!event.data.message.isError&&calls.get(event.data.message.toolCallId)==='task_graph')break;
      if(event.type!=='user/message'||event.data.source.kind!=='nano-system')continue;
      if(['task-context','task-execution','task-reminder'].includes(event.data.source.channel))break;
      if(event.data.source.channel==='task-context-limitation')return event.data.content.some(block=>block.type==='text'&&block.text===text)?undefined:text;
    }
    return text;
  }
  private prompt(agent:Agent,snapshot:TaskExecutionSnapshot,automatic=true,checks:{graph_id:string;node_id:string;schedule_id:string;occurrence_id:string;planned_check_at?:string|null;checked_at:string}[]=[]):string {
    const closing=this.options.configuration(agent)?.mode==='global'
      ? "Deliver meaningful results or a new blocker with send_message to the Task's fixed conversation. Skip confirmed feedback and unchanged routine progress. End with a brief non-empty private closing note."
      : "Deliver meaningful results or a new blocker to the Task's fixed conversation. Skip confirmed feedback and unchanged routine progress. Use NO_REPLY only when the SingleThread delivery protocol requires silence.";
    const tasks=snapshot.tasks.map(task=>({
      graph_id:task.graph_id,node_id:task.node_id,title:task.title,status:task.status,
      ...(task.root_node_id?{root_node_id:task.root_node_id}:{}),
      ...(task.root_title?{root_title:task.root_title}:{}),
      ...(task.root_goal_summary?{root_goal_summary:task.root_goal_summary}:{}),
      ...(task.parent_path?.length?{parent_path:task.parent_path}:{}),
      conversation_id:task.conversation.id,relative_url:task.relative_url,
      ...(task.wait?{wait:{reason:task.wait.reason,...(task.wait.schedule_id?{schedule_id:task.wait.schedule_id,next_check_at:task.wait.next_check_at}:{}),...(task.wait.question?{question:task.wait.question}:{}),...(task.wait.asked_user_id?{asked_user_id:task.wait.asked_user_id}:{})}}:{}),
    }));
    const context={tasks,...(checks.length?{checks}:{})};
    return [
      automatic?"A Task newly entered doing or was assigned/resumed for you in this session. Anchor your work to each Task's root North Star goal (root_title and root_goal_summary) and inspect current workspace, tool results and durable Task details before acting.\n\nMake concrete, verified progress on executable work. When a Task must wait on a future date/time or cross-day milestone, create a native Schedule (up to 180 days out) and record status=waiting with wait={reason, schedule_id}. When waiting on a human reply or external event with no fixed check time, deliver a clear question/update first and record status=waiting with wait={reason, question, asked_user_id} without a schedule_id. Do not reopen paused, backlog, closed, done or in_review Tasks because of this wake; it grants no new human authority.":undefined,
      checks.length?"This scheduled check concerns the Tasks listed in checks. Read current Task state, Inbox, and external facts first—completion or changes may already have happened. Keep each Task's root North Star goal in view. Continue executable work, update or close Tasks that are already resolved without sending redundant nudges, or establish an appropriate next Schedule if timed waiting is still needed. This timer grants no new human consent and cannot reopen paused, backlog, closed, done or in_review Tasks.":undefined,
      'Current Task context:',JSON.stringify(context),closing,
    ].filter(part=>part!==undefined).join('\n\n');
  }
  private message(agent:Agent,text:string,sourceChannel:'task-execution'|'task-reminder'|'task-context-limitation'|'task-human-control',id=MessageId(`${sourceChannel}:${randomUUID()}`)):UserMessage {
    return freezeMessage({id,role:'user',source:{kind:'nano-system',lifecycle_revision:this.options.lifecycleRevision?.(this.options.bindings.get(agent.id)!.agentId)??1,actorId:this.options.bindings.get(agent.id)!.agentId,channel:sourceChannel,messageId:id},content:[{type:'text',text}]});
  }
  private restore(agent:Agent,messages:UserMessage[]):void {
    for(const message of messages.toReversed())if(!agent.inbox.nextTurn.some(m=>m.id===message.id)&&!agent.inbox.nextStep.some(m=>m.id===message.id))agent.inbox.prepend(channel(message)==='task-human-control'?'next-step':'next-turn',message);
  }
  /** Notifications do not override the stop fence or an explicit cancellation. */
  passive(sessionId:string):boolean {const state=this.state(sessionId);return state.blocked||state.interrupted==='cancelled';}
  /** Enqueue at most one wake per unconsumed doing_wake transition. */
  async poke(agent:Agent,reconsider=false):Promise<void> {
    if(!this.options.bindings.has(agent.id)||!this.enabled(agent))return;
    const state=this.state(agent.id);
    if(state.checking){state.requested=true;return;}
    if(state.contextUnavailable&&!reconsider)return;
    if(state.queued||state.blocked||['error','cancelled'].includes(state.interrupted??'')&&!reconsider||agent.status!=='idle'||!reconsider&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))return;
    state.checking=true;
    try {
      await this.ctx.sessions.flush(agent.session);
      const snapshot=await this.snapshot(agent);
      if(!this.enabled(agent))return;
      if(snapshot.kind==='unavailable'){if(!state.interrupted)this.hold(state,'source');return;}
      const unwoken=this.unwokenTasks(state,snapshot);
      if(!unwoken.length||state.blocked||agent.status!=='idle'||!reconsider&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))return;
      if(state.interrupted){
        if(state.interrupted==='cancelled') {
          const freshInput=agent.session.snapshotEvents().some(event=>event.type==='user/message'&&freshWake(event.data,state.stoppedAt));
          const resumed=unwoken.some(task=>task.resume_request&&task.resume_request.revision<=task.revision&&Date.parse(task.resume_request.at)>(state.stoppedAt??Infinity));
          if(!freshInput&&!resumed)return;
        } else if(state.interrupted==='error'&&(!reconsider||responsibility(snapshot)===state.interruptedAt))return;
        state.interrupted=undefined;
      }
      const message=this.message(agent,this.prompt(agent,snapshot),'task-execution');state.queued=message.id;
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
        if(agent?.status==='idle'&&!state.blocked&&this.enabled(agent)&&(agent.inbox.nextTurn.length||agent.inbox.nextStep.length))
          agent.followup(this.message(agent,'Continue current Task work.','task-execution'));
      }
    }
    this.changed(agentId);
  }
  /** Merge change hints and refresh at the nearest native model boundary. */
  changed(agentId:string,reset=true):void {
    for(const [id,binding] of this.options.bindings)if(binding.agentId===agentId) {
      const state=this.state(id);state.serial++;
      const agent=this.ctx.agents.get(id as Agent['id']);if(!agent||state.blocked||!this.enabled(agent))continue;
      if(agent.status!=='running')void this.poke(agent,reset);
    }
  }
  /** Fence all native admission while a durable stop is unresolved, retaining queued input. */
  block(sessionId:string,blocked:boolean):void {
    const state=this.state(sessionId);state.blocked=blocked;
  }
  interrupt(sessionId:string,stoppedAt?:string):void {const state=this.state(sessionId);this.hold(state,'cancelled');const at=stoppedAt?Date.parse(stoppedAt):NaN;state.stoppedAt=Math.max(state.stoppedAt??-Infinity,Number.isFinite(at)?at:Date.now());}
}
