import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { createUserMessage, ReasoningEffortId, isAgentLoopRequest } from '@deepseek-ai/dsh-llm';
import { ReviewRecovery, ReviewAttempt, ReviewFailure, invalidVerdict, publicFailure } from './recovery.js';
import { SessionId, SessionLogOffset, type SessionEvent } from '@deepseek-ai/dsh-session';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-compaction';
import { deriveTurnTokenUsage } from '@deepseek-ai/dsh-token-meter/client';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { codexPolicy, parseCodexDecision, reviewInput, tokenCost } from './codex-context.js';
import { inspectionTools } from './codex-inspection.js';
import { codexEntries } from './sources.js';
import type { AgentConfiguration } from '../index.js';
import { personalReviewPolicy, parsePersonalDecision, type PersonalReview } from '../personal-security.js';

declare module '@deepseek-ai/cordis' { interface Context { codexApproval: CodexApproval } }
interface ReviewRun<T> {
  purpose: 'tool' | 'disclosure';
  recovery?: ReviewRecovery;
  parent: Agent;
  signal?: AbortSignal;
  config: AgentConfiguration;
  reviewer: {provider:string;model:string};
  system: () => string | Promise<string>;
  evidence: () => Promise<Record<string, unknown>[]>;
  action: unknown;
  parse: (text:string) => T | undefined;
}
interface Checkpoint { rows: string[]; events: SessionEvent[]; sessionId: string }
interface Reviewer { handle: AgentHandle; signal: AbortSignal; failure?: Error; start: number; input: string; inputId?: string; first: boolean; limit: number; overhead: number;
  currentAttempt?: ReviewAttempt; retired?: boolean; cleanupFailed?: boolean; dispose?: Promise<void>; route: { provider: string; model: string; reasoningEffort?: ReasoningEffortId };
}
interface Trunk { fingerprint: string; busy: boolean; reviewer?: Reviewer; checkpoint?: Checkpoint }
class ReviewBudgetError extends ReviewFailure { constructor(message: string) { super('context', message); } }
const outputReserve=2048;
const prefix=(before:string[],after:string[])=>before.length<=after.length&&before.every((value,i)=>value===after[i]);
const recoverable=(error:unknown)=>error instanceof ReviewFailure && (error.category==='context' || error.failure?.code==='CONTEXT_WINDOW_EXCEEDED');

/** Synchronous Guardian hosted by DSH; each parent owns one reusable idle reviewer. */
export class CodexApproval extends Service {
  static inject=['agents','tools','systemPrompt','llm','approval'];
  private readonly trunks=new Map<string,Trunk>();
  private readonly active=new Set<Reviewer>();
  private readonly streamOwners=new Map<string,Reviewer>();
  private readonly quarantine=new Map<string,Promise<unknown>>();
  constructor(ctx:Context){
    super(ctx,'codexApproval');
    ctx.on('agent/disposed',({agent})=>this.release(agent.id));
    ctx.effect(()=>async()=>{await Promise.all([...this.active].map(reviewer=>this.discard(reviewer)));await Promise.allSettled(this.quarantine.values());this.active.clear();this.trunks.clear();});
    const owners=this.streamOwners;
    ctx.on('llm/stream',async function*(options,next){
      // llm events have a global runtime carrier: identity must precede any owner access.
      if(!isAgentLoopRequest(options)||!options.sessionId||options.purpose){yield*next();return;}
      const owner=owners.get(String(options.sessionId));
      if(!owner){yield*next();return;}
      const attempt=owner.currentAttempt;
      if(!attempt||owner.retired)throw new ReviewFailure('cancelled','Guardian reviewer has no active action');
      attempt.assertActive();
      if(options.provider!==owner.route.provider||options.model!==owner.route.model||options.reasoningEffort!==owner.route.reasoningEffort)throw new ReviewFailure('permanent','Guardian model route changed during review');
      yield*attempt.stream(owner.route,next);
    },{prepend:true});
  }

  /** Drop a parent cache at a configuration boundary; in-flight work cannot republish it. */
  async release(sessionId:string):Promise<void>{
    for(const purpose of ['tool','disclosure']) {
      const key=`${purpose}:${sessionId}`,trunk=this.trunks.get(key);this.trunks.delete(key);
      if(trunk&&!trunk.busy&&trunk.reviewer)await this.discard(trunk.reviewer);
    }
  }

  /** Review one action, sharing a single deadline across preparation, tools and retry. */
  async review(request:ApprovalReviewRequest):Promise<ApprovalReviewResult>{
    const parent=request.exec.agent!;
    const recovery=request.recovery??new ReviewRecovery(request.exec.signal,request.exec.callId);
    try{
    const result=await this.run({purpose:'tool',recovery,parent,signal:request.exec.signal,config:request.config,reviewer:request.reviewer,
      system:()=>codexPolicy(request.config.approval!),
      evidence:async()=>[...codexEntries(request.sources.restoreEntries(request.inherited,false)),...await request.sources.history(parent,request.exec.callId,request.config.mode !== 'global',{toolResults:true,fullAssistant:true})],
      action:{name:request.exec.name,arguments:request.exec.arguments,id:request.exec.callId,schema:this.ctx.tools.schemas(parent).find(tool=>tool.name===request.exec.name),cwd:parent.session.header.cwd,rules:request.config.approval,recipient:request.messageContext},
      parse:parseCodexDecision});
    return {...result,metadata:{...result.metadata,risk:result.decision.risk,authorization:result.decision.authorization}};
    }finally{if(!request.recovery)recovery.finish('service_result','internal');}
  }

  /** Review a host-frozen PA disclosure with its own policy and cache namespace.
   *
   * Args:
   *   request: Verified PA scope, current evidence supplier and exact pending action.
   * Returns:
   *   A strict PA verdict plus the shared reviewer's usage and session metadata.
   */
  async reviewDisclosure(request:{agent:Agent;config:AgentConfiguration;action:unknown;evidence:()=>Promise<Record<string,unknown>[]>;signal?:AbortSignal}):Promise<PersonalReview & {usage?:unknown;metadata?:ApprovalReviewResult['metadata']}> {
    const header=request.agent.session.requestHeader();
    const reviewer=request.config.approval?.reviewer??{provider:header?.config.provider??request.config.provider,model:header?.config.model??request.config.model};
    const result=await this.run({purpose:'disclosure',parent:request.agent,signal:request.signal,config:request.config,reviewer,
      system:()=>personalReviewPolicy('action'),evidence:request.evidence,action:request.action,parse:parsePersonalDecision});
    return {...result.decision,usage:result.usage,metadata:result.metadata};
  }

  private async run<T>(request:ReviewRun<T>) {
    const parent=request.parent,key=`${request.purpose}:${parent.id}`;
    const recovery=request.recovery;
    if(this.quarantine.has(key))throw new ReviewFailure('cleanup_unavailable','Previous Guardian resource is quarantined');
    const deadline=recovery?.signal??AbortSignal.timeout(90_000);
    let signal=request.signal?AbortSignal.any([request.signal,deadline]):deadline;signal.throwIfAborted();
    const cwd=parent.session.header.cwd!;
    const fingerprint=JSON.stringify([request.config,request.reviewer,cwd]);
    let trunk=this.trunks.get(key);
    if(!trunk||trunk.fingerprint!==fingerprint){
      const old=trunk;
      trunk={fingerprint,busy:false};this.trunks.set(key,trunk);
      if(old&&!old.busy&&old.reviewer){await this.discard(old.reviewer,recovery,key);old.reviewer=undefined;}
    }
    // Claim before any asynchronous preparation. Busy callers fork the last committed checkpoint.
    const fork=trunk.busy;
    if(!fork)trunk.busy=true;
    let checkpoint=trunk.checkpoint;
    let reviewer=fork?undefined:trunk.reviewer;
    let committed=false;
    try{
      const prepare=(prepareSignal:AbortSignal)=>Promise.all([
        request.system(),request.evidence(),
        this.ctx.llm.resolveModelInfo(request.reviewer.provider,request.reviewer.model,prepareSignal),
      ]);
      const [system,rawEvidence,model]=await (recovery?recovery.prepare(prepare):prepare(signal));
      const evidence=structuredClone(rawEvidence);
      signal.throwIfAborted();
      const effort=model.reasoning?.efforts.find(value=>value.id==='low')?.id??model.reasoning?.defaultEffort??model.reasoning?.efforts[0]?.id;
      const serialized=evidence.map(row=>JSON.stringify(row));
      if(checkpoint&&!prefix(checkpoint.rows,serialized)){checkpoint=undefined;if(reviewer){await this.discard(reviewer,recovery,key);reviewer=undefined;}}
      const schemas=inspectionTools(cwd,()=>signal).map(({name,description,parameters})=>({name,description,parameters}));
      const overhead=tokenCost(system)+tokenCost(JSON.stringify(schemas))+outputReserve+512;
      const limit=model.context?.contextWindow;
      if(!limit)throw new Error('Guardian reviewer model has no declared context window');
      const action=request.action;
      let mode=fork?'fork':checkpoint?'delta':'full';
      let normalAttempts=0;
      const judge=async(currentAttempt?:ReviewAttempt)=>{
      if(currentAttempt)signal=currentAttempt.signal;
      if(normalAttempts++){checkpoint=undefined;reviewer=undefined;mode='full-retry';}
      for(let attempt=0;attempt<2;attempt++){
        signal.throwIfAborted();
        try{
          const history=reviewer?reviewer.handle.agent.session.deriveMessages():undefined;
          const seeded=history?tokenCost(JSON.stringify(history)):checkpoint?tokenCost(JSON.stringify(checkpoint.events)):0;
          const remaining=limit-overhead-seeded;
          let input:string;
          if(checkpoint){
            // A delta cannot silently drop new evidence. Rebuild from the current parent when tight.
            const delta=evidence.slice(checkpoint.rows.length);
            try { input=reviewInput(delta,action,remaining,false,request.purpose==='disclosure'); } catch(error) { throw new ReviewBudgetError(String(error)); }
            if(input.includes('reason="evidence_budget"'))throw new ReviewBudgetError('Guardian delta requires budget rebuild');
          }else input=reviewInput(evidence,action,limit-overhead,true,request.purpose==='disclosure');
          if(!reviewer)reviewer=await this.create(request,system,signal,checkpoint,limit,overhead,effort);
          reviewer.signal=signal;reviewer.currentAttempt=currentAttempt;reviewer.failure=undefined;reviewer.input=input;reviewer.first=true;
          if(currentAttempt){currentAttempt.assertActive();currentAttempt.trace.sessionId=reviewer.handle.agent.id;currentAttempt.trace.contextMode=mode;}
          reviewer.start=reviewer.handle.agent.session.snapshotEvents().length;
          const agent=reviewer.handle.agent;
          const cancel=()=>agent.cancel({kind:'parent'});
          signal.addEventListener('abort',cancel,{once:true});
          try{
            signal.throwIfAborted();
            const message=createUserMessage({content:[{type:'text',text:input}],source:{kind:'user'}});
            reviewer.inputId=message.id;
            agent.followup(message);
            await agent.whenIdle();
            signal.throwIfAborted();
          }finally{signal.removeEventListener('abort',cancel);}
          const events=agent.session.snapshotEvents();const added=events.slice(reviewer.start);
          if(added.some(event=>event.type==='compaction/start'))throw new ReviewBudgetError('Guardian compaction invalidated pending evidence');
          if(reviewer.failure)throw reviewer.failure;
          const end=added.findLast(event=>event.type==='turn/end');
          if(end?.type==='turn/end'&&end.data.reason.kind!=='completed'){
            if(end.data.reason.kind==='error'&&end.data.reason.error.code==='CONTEXT_WINDOW_EXCEEDED')throw new ReviewBudgetError('Guardian native context window exceeded');
            throw new Error(`Guardian turn ended: ${end.data.reason.kind}`);
          }
          const last=added.findLast(event=>event.type==='assistant/message');
          const text=last?.type==='assistant/message'?last.data.message.content.filter(block=>block.type==='text').map(block=>block.text).join(''):'';
          const decision=request.parse(text);
          if(!decision)throw invalidVerdict(text.trim()?'malformed':'empty_text');
          signal.throwIfAborted();currentAttempt?.assertActive();
          if(!fork&&this.trunks.get(key)===trunk){trunk.checkpoint={rows:serialized,events:[...events],sessionId:agent.id};trunk.reviewer=reviewer;committed=true;}
          return{decision,usage:deriveTurnTokenUsage(added.slice(added.findIndex(event=>event.type==='turn/start'),added.findLastIndex(event=>event.type==='turn/end')+1)),metadata:{sessionId:agent.id,contextMode:mode}};
        }catch(error){
          if(reviewer){await this.discard(reviewer,recovery,key);reviewer=undefined;}
          signal.throwIfAborted();
          if(attempt||!recoverable(error)||recovery&&!recovery.takeContextRebuild())throw error;
          checkpoint=undefined;mode=fork?'fork-rebuild':'rebuild';
        }
      }
      throw new Error('Guardian review unavailable');
      };
      if(!recovery)return await judge();
      let pending:Promise<Awaited<ReturnType<typeof judge>>>|undefined;
      try{return await recovery.run('guardian',90_000,attempt=>{pending=judge(attempt);return pending;});}
      catch(error){
        if(error instanceof ReviewFailure&&error.category==='cleanup_unavailable'&&pending)this.trackQuarantine(key,pending);
        throw error;
      }
    }finally{
      if(reviewer)reviewer.currentAttempt=undefined;
      if(!committed&&reviewer)await this.discard(reviewer,recovery,key);
      if(!fork){trunk.reviewer=committed?reviewer:undefined;trunk.busy=false;}
    }
  }

  private trackQuarantine(key:string,pending:Promise<unknown>):void{
    const previous=this.quarantine.get(key);
    const tracked=Promise.all([...(previous?[previous]:[]),pending]);
    this.quarantine.set(key,tracked);
    void tracked.then(()=>{if(this.quarantine.get(key)===tracked)this.quarantine.delete(key);},()=>{/* Failed disposal keeps this parent quarantined until service teardown. */});
  }
  private async discard(reviewer:Reviewer,recovery?:ReviewRecovery,key?:string){
    reviewer.retired=true;reviewer.currentAttempt=undefined;
    reviewer.dispose??=Promise.resolve().then(()=>{reviewer.handle.agent.cancel({kind:'parent'});return reviewer.handle.dispose();}).then(()=>{
      this.active.delete(reviewer);
      const id=reviewer.handle.agent.id;if(this.streamOwners.get(id)===reviewer)this.streamOwners.delete(id);
    });
    if(!recovery)return reviewer.dispose;
    if(reviewer.cleanupFailed)throw new ReviewFailure('cleanup_unavailable','Guardian resource remains quarantined');
    try{await recovery.cleanup(reviewer.dispose);}catch(error){reviewer.cleanupFailed=true;if(key)this.trackQuarantine(key,reviewer.dispose);throw error;}
  }
  private async create(request:Pick<ReviewRun<unknown>,'parent'|'reviewer'|'recovery'>,system:string,signal:AbortSignal,checkpoint:Checkpoint|undefined,limit:number,overhead:number,effort:ReasoningEffortId|undefined):Promise<Reviewer>{
    const reviewer={} as Reviewer;
    reviewer.route={...request.reviewer,reasoningEffort:effort};
    reviewer.signal=signal;reviewer.limit=limit;reviewer.overhead=overhead;reviewer.start=checkpoint?.events.length??0;
    const sessionId=SessionId(`nano-codex-${randomUUID()}`);
    const handle=await this.ctx.agents.create({sessionId,signal,
      meta:{cwd:request.parent.session.header.cwd,agentPreset:'nano-codex-reviewer',...(checkpoint?{parentSession:SessionId(checkpoint.sessionId),isSeeded:true}:{})},
      ...(checkpoint?{seed:checkpoint.events,inheritedEventCount:SessionLogOffset(checkpoint.events.length)}:{}),
      agentOptions:{...request.reviewer,reasoningEffort:effort,maxTokens:outputReserve},
      setup:(scope,agent)=>{
        if(request.recovery){
          if(signal.aborted)signal.throwIfAborted();
          this.streamOwners.set(agent.id,reviewer);

        }
        setApprovalPolicy(agent.session,'never');
        scope.tools.presentAs('native');scope.tools.restrict({allow:[]});
        const tools=inspectionTools(request.parent.session.header.cwd!,()=>reviewer.signal);
        for(const tool of tools)scope.tools.register(tool);
        const names=new Set(tools.map(tool=>tool.name));
        scope.tools.guard(exec=>names.has(exec.name)?undefined:'Guardian permits only host-owned read-only inspection');
        // Native workspace guidance enters through pre-step messages as well as system contexts.
        // Parent instructions are already evidence in input; only host review inputs may direct this Agent.
        scope.on('agent/pre-step',async(_payload,next)=>{
          const decision=await next();
          return decision.kind==='reject'?decision:{...decision,messages:decision.messages.filter(message=>message.id===reviewer.inputId)};
        },{prepend:true});
        scope.systemPrompt.section({name:'nano-guardian',order:0,text:system,complete:true,interpolate:false});
        scope.on('system-prompt/assemble',async(_assembly,_context,next)=>({...await next(),contexts:[],tools:scope.tools.schemas(agent)}),{prepend:true});
        scope.on('agent/request',async(_payload,next)=>{
          reviewer.signal.throwIfAborted();
          if(agent.session.snapshotEvents().slice(reviewer.start).some(event=>event.type==='compaction/start')){reviewer.failure=new ReviewBudgetError('Guardian compaction requires rebuild');throw reviewer.failure;}
          const cost=tokenCost(JSON.stringify(agent.session.deriveMessages()))+(reviewer.first?tokenCost(reviewer.input):0)+overhead;
          if(cost>limit){reviewer.failure=new ReviewBudgetError('Guardian request exceeds context budget');throw reviewer.failure;}
          reviewer.first=false;
          return{...await next(),...request.reviewer,reasoningEffort:effort,maxTokens:outputReserve};
        },{prepend:true});
        scope.on('agent/request-error',async({failure})=>{reviewer.failure=publicFailure(failure);return undefined;},{prepend:true});
      },
    }).catch(error=>{if(this.streamOwners.get(sessionId)===reviewer)this.streamOwners.delete(sessionId);throw error;});
    reviewer.handle=handle;this.active.add(reviewer);
    if(signal.aborted){await this.discard(reviewer);signal.throwIfAborted();}
    return reviewer;
  }
}
