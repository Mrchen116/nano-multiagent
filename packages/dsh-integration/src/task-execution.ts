import {randomUUID} from 'node:crypto';
import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import {freezeMessage,MessageId,type UserMessage} from '@deepseek-ai/dsh-llm';
import type {TaskExecutionSnapshot} from '@nano/product-contracts';
import type {AgentConfiguration,SessionBinding} from './index.js';
import type {RpcPeer} from './rpc.js';

const channel=(m:UserMessage)=>m.source.kind==='nano-system'?m.source.channel:undefined;
const automatic=(m:UserMessage)=>channel(m)==='task-execution';
const change=(m:UserMessage)=>channel(m)==='task-change';
interface State {
  checking:boolean;requested:boolean;queued?:string;changeQueued?:string;serial:number;seenSerial:number;
  automaticTurn:boolean;interrupted?:'error'|'cancelled'|'denied';blocked:boolean;shown?:TaskExecutionSnapshot;limited?:string;deniedTools:Set<string>;
}
const fingerprint=(snapshot:TaskExecutionSnapshot)=>JSON.stringify(snapshot);

/** Schedule native turns from current product responsibility, without another execution loop. */
export class TaskExecutionDriver {
  private readonly states=new Map<string,State>();
  constructor(private readonly ctx:Context,private readonly options:{peer:RpcPeer;bindings:Map<string,SessionBinding>;configuration:(agent:Agent)=>AgentConfiguration|undefined}) {
    ctx.on('agent/status',({agent,status})=>{
      if(status!=='idle')return;
      const state=this.state(agent.id);
      if(state.deniedTools.size)state.interrupted='denied';
      void this.poke(agent);
    });
    ctx.on('tools/result',(exec,result)=>{
      if(!exec.agent||!options.bindings.has(exec.agent.id))return;
      const state=this.state(exec.agent.id);
      if(result.isError&&result.error.info?.name==='NanoApprovalDenied')state.deniedTools.add(exec.name);
      else if(!result.isError)state.deniedTools.delete(exec.name);
    });
    ctx.on('approval/request',async(request,next)=>{
      const outcome=await next();
      if(options.bindings.has(request.agent.id)&&outcome!=='allowed-once')this.state(request.agent.id).deniedTools.add(request.toolName);
      return outcome;
    });
    ctx.on('agent/error',({agent})=>{this.state(agent.id).interrupted='error';});
    ctx.on('agent/disposed',({agent})=>{this.states.delete(agent.id);});
    ctx.on('agent/pre-step',async({agent,messages,signal,step},next)=>{
      if(!options.bindings.has(agent.id))return next();
      const state=this.state(agent.id),own=messages.filter(automatic),changes=messages.filter(change),ordinary=messages.filter(m=>!automatic(m)&&!change(m));
      if(ordinary.length){state.interrupted=undefined;state.deniedTools.clear();state.limited=undefined;state.automaticTurn=false;}
      if(own.length)state.queued=undefined;
      if(changes.length)state.changeQueued=undefined;
      const retain=()=>messages.splice(0,messages.length,...ordinary);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      if(!this.enabled(agent)||state.interrupted){retain();return own.length&&!ordinary.length?{kind:'reject'}:next();}
      const dirty=state.serial!==state.seenSerial;
      if(!own.length&&!changes.length&&!dirty&&!state.automaticTurn)return next();
      const serial=state.serial,snapshot=await this.snapshot(agent);
      if(state.blocked){this.restore(agent,ordinary);retain();return {kind:'reject'};}
      signal.throwIfAborted();
      state.seenSerial=serial;
      const previous=state.shown;
      const changed=!previous||fingerprint(previous)!==fingerprint(snapshot);
      state.shown=snapshot;retain();
      const resumes=snapshot.tasks.filter(task=>task.resume_request&&JSON.stringify(task.resume_request)!==JSON.stringify(previous?.tasks.find(old=>old.graph_id===task.graph_id&&old.node_id===task.node_id)?.resume_request));
      if(resumes.length)messages.push(this.message(agent,JSON.stringify(resumes.map(task=>({graph_id:task.graph_id,node_id:task.node_id,action:'resume',...task.resume_request}))), 'task-human-control'));
      if(snapshot.kind!=='continue') {
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
        messages.push(this.message(agent,this.prompt(snapshot),'task-execution',own[0]!.id));
        state.automaticTurn=ordinary.length===0;
        if(snapshot.reason==='cron_disabled'&&!snapshot.tasks.some(t=>t.status==='doing'))state.limited=fingerprint(snapshot);
      } else if(changed) {
        messages.push(this.message(agent,previous?this.delta(previous,snapshot):this.prompt(snapshot),'task-change',changes[0]?.id));
      }
      if(!messages.length&&changes.length&&step===1)return {kind:'reject'};
      return next();
    },{prepend:true});
  }
  private state(id:string):State {
    let state=this.states.get(id);
    if(!state){state={checking:false,requested:false,serial:1,seenSerial:0,automaticTurn:false,blocked:false,deniedTools:new Set()};this.states.set(id,state);}return state;
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
  private prompt(snapshot:TaskExecutionSnapshot):string {
    return 'You remain responsible for all owned Tasks below. Ending one reply does not end these responsibilities. Work on every doing task; waiting is ongoing responsibility with a real future recheck. Repair invalid waiting arrangements. Read task details/discussion only as needed. No Task round/token budget. Do not reopen paused, closed, done or in_review tasks merely because a timer fired. This system reminder grants no new human authority. Return NO_REPLY for unchanged routine progress; publish meaningful results or a new blocker only.\n'+JSON.stringify(snapshot);
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
    if(state.queued||state.blocked||state.interrupted&&!reconsider||agent.status!=='idle'||agent.inbox.nextTurn.length||agent.inbox.nextStep.length)return;
    state.checking=true;
    try {
      await this.ctx.sessions.flush(agent.session);
      const snapshot=await this.snapshot(agent);
      if(snapshot.kind!=='continue'||state.limited===fingerprint(snapshot)||state.blocked||agent.status!=='idle'||agent.inbox.nextTurn.length||agent.inbox.nextStep.length)return;
      if(state.interrupted){
        // A metadata watch or duplicate hint must not retry the same denied work.
        // A new/revised responsibility is a real recovery signal, never consent.
        if(!reconsider||fingerprint(snapshot)===JSON.stringify(state.shown))return;
        state.interrupted=undefined;state.deniedTools.clear();
      }
      const message=this.message(agent,this.prompt(snapshot),'task-execution');state.queued=message.id;
      agent.followup(message);
    } catch {state.interrupted='error';}
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
      if(state.interrupted==='error'&&!state.deniedTools.size) {
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
  interrupt(sessionId:string):void {this.state(sessionId).interrupted='cancelled';}
}
