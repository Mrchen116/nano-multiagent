import { randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { createUserMessage, type ImageBlock, type ReasoningEffortId, type ResolvedRetryPolicy } from '@deepseek-ai/dsh-llm';
import { SessionId, SessionLogOffset, type SessionEvent } from '@deepseek-ai/dsh-session';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-compaction';
import type {} from '@deepseek-ai/dsh-llm-retry';
import { deriveTurnTokenUsage } from '@deepseek-ai/dsh-token-meter/client';
import type { AgentConfiguration } from '../index.js';
import { inputEvidence } from '../input-evidence.js';
import { inspectionTools } from './codex-inspection.js';
import { reviewEnvelope, tokenCost } from './codex-context.js';
import { retainedEnvelope, type RetainedInstructions } from './retained-instructions.js';

export interface ReviewPlan<T> {
  purpose: 'tool' | 'disclosure'; parent: Agent; signal?: AbortSignal;
  config: AgentConfiguration; reviewer: {provider:string;model:string};
  system: () => string | Promise<string>; evidence: () => Promise<Record<string, unknown>[]>;
  retained: () => RetainedInstructions; action: unknown; images?: readonly ImageBlock[];
  parse: (text:string) => T | undefined;
}
type Metadata = {sessionId:string;contextMode:string};
export class ReviewFailure extends Error {
  constructor(readonly kind:'runtime'|'timeout'|'invalid_verdict'|'evidence_unavailable', message:string) { super(message); }
}
export type ReviewExecution<T> =
  | {kind:'decision';value:T;usage:unknown;metadata:Metadata}
  | {kind:'cancelled'}
  | {kind:'unavailable';cause:ReviewFailure;metadata?:Metadata};
class ContextRebuild extends Error {}
interface Checkpoint { rows:string[]; events:SessionEvent[]; sessionId:string }
interface Reviewer { handle:AgentHandle; run?:Run; start:number; input:string; inputId?:string; images?:readonly ImageBlock[]; first:boolean }
interface Trunk { fingerprint:string; busy:boolean; reviewer?:Reviewer; checkpoint?:Checkpoint }
interface Run {
  signal:AbortSignal; retries:number; formats:number; rebuilds:number;
  controller:AbortController; cause?:'attempt_timeout'|'context_rebuild'|'total_timeout';
  pause:()=>void; restart:()=>void; clear:()=>void;
}
const outputReserve=2048, activityMs=90_000;
const permanentFailures=new Set(['AUTH','INVALID_REQUEST','INVALID_CREDENTIAL','MISSING_CREDENTIAL','NO_ADAPTER','UNKNOWN_MODEL','UNSUPPORTED_CONTENT','UNSUPPORTED_REASONING_EFFORT','UNSUPPORTED_OPTION']);
const prefix=(before:string[],after:string[])=>before.length<=after.length&&before.every((value,i)=>value===after[i]);
const imagesIn=(messages:readonly {content:readonly unknown[]}[])=>messages.flatMap(message=>message.content.filter((block):block is ImageBlock=>!!block&&typeof block==='object'&&'type' in block&&block.type==='image'));

/** Own reviewer sessions and checkpoints; native DSH remains the request-retry owner. */
export class ReviewSession {
  private readonly trunks=new Map<string,Trunk>();
  private readonly active=new Set<Reviewer>();
  constructor(private readonly ctx:Context) {}

  /** Discard reusable sessions; busy callers cannot publish into a removed trunk. */
  async release(sessionId:string):Promise<void>{
    for(const purpose of ['tool','disclosure']) {
      const key=`${purpose}:${sessionId}`,trunk=this.trunks.get(key);this.trunks.delete(key);
      if(trunk&&!trunk.busy&&trunk.reviewer)await this.discard(trunk.reviewer);
    }
  }
  /** Drain runtime resources when the owning service is disposed. */
  async dispose():Promise<void>{await Promise.all([...this.active].map(reviewer=>this.discard(reviewer)));this.trunks.clear();}

  /** Execute one frozen review through a terminal decision, cancellation or unavailable result. */
  async run<T>(plan:ReviewPlan<T>,parentSignal?:AbortSignal):Promise<ReviewExecution<T>> {
    if(parentSignal?.aborted)return{kind:'cancelled'};
    let policy:ResolvedRetryPolicy;
    try { policy=this.ctx.llm.providerRetryPolicy(plan.reviewer.provider); }
    catch(error){return{kind:'unavailable',cause:new ReviewFailure('runtime',String(error))};}
    const key=`${plan.purpose}:${plan.parent.id}`;
    const fingerprint=JSON.stringify([plan.config,plan.reviewer,plan.parent.session.header.cwd]);
    let trunk=this.trunks.get(key);
    const old=trunk;
    if(!trunk||trunk.fingerprint!==fingerprint){trunk={fingerprint,busy:false};this.trunks.set(key,trunk);}
    const fork=trunk.busy; if(!fork)trunk.busy=true;
    let checkpoint=trunk.checkpoint,reviewer=fork?undefined:trunk.reviewer,committed=false;
    const total=new AbortController();
    const totalTimer=setTimeout(()=>total.abort(new ReviewFailure('timeout','Review total recovery deadline exceeded')),3*activityMs+2*policy.maxDelayMs);
    const lifetime=parentSignal?AbortSignal.any([parentSignal,total.signal]):total.signal;
    const run=this.createRun(lifetime);
    let mode=fork?'fork':checkpoint?'delta':'full';
    let metadata:Metadata|undefined;
    try {
      lifetime.throwIfAborted();
      if(old&&old!==trunk&&!old.busy&&old.reviewer)await this.discard(old.reviewer);
      const [system,evidence,model]=await Promise.all([plan.system(),plan.evidence(),this.ctx.llm.resolveModelInfo(plan.reviewer.provider,plan.reviewer.model,run.signal)]);
      run.signal.throwIfAborted();
      const retained=plan.retained();
      const limit=model.context?.contextWindow;
      if(!limit)throw new ReviewFailure('evidence_unavailable','Reviewer model has no declared context window');
      const effort=model.reasoning?.efforts.find(value=>value.id==='low')?.id??model.reasoning?.defaultEffort??model.reasoning?.efforts[0]?.id;
      const tools=inspectionTools(this.ctx);
      const overhead=tokenCost(system)+tokenCost(JSON.stringify(tools.map(({name,description,parameters})=>({name,description,parameters}))))+outputReserve+512;
      if(plan.images?.length&&!model.inputModalities?.includes('image'))throw new ReviewFailure('evidence_unavailable','Reviewer model does not support images');
      const pricing=this.ctx.llm.imageRequestPricing(plan.reviewer.provider,plan.reviewer.model);
      if(plan.images?.length&&!pricing)throw new ReviewFailure('evidence_unavailable','Reviewer image token pricing unavailable');
      const imageCost=(images:readonly ImageBlock[])=>{
        if(!images.length)return 0;
        const prices=pricing?.priceImages(images);
        if(!prices||prices.length!==images.length||prices.some(price=>!Number.isFinite(price.visualTokens)||price.visualTokens<=0))throw new ReviewFailure('evidence_unavailable','Complete reviewer image projection unavailable');
        return prices.reduce((sum,price)=>sum+price.visualTokens+tokenCost(price.text),0);
      };
      const serialized=evidence.map(row=>JSON.stringify(row));
      if(checkpoint&&!prefix(checkpoint.rows,serialized)){checkpoint=undefined;if(reviewer){await this.discard(reviewer);reviewer=undefined;}mode=fork?'fork-rebuild':'rebuild';}
      while(true) {
        try {
          run.signal.throwIfAborted();
          const history=reviewer?.handle.agent.session.deriveMessages()??[];
          // A fork is rehydrated before budgeting, so visibility uses its actual surface too.
          if(!reviewer&&checkpoint){reviewer=await this.create(plan,system,checkpoint,limit,overhead,effort,imageCost);continue;}
          const original=retainedEnvelope(retained,history,Math.min(8192,Math.max(0,(limit-overhead)/4)));
          const allImages=[...imagesIn(history),...(plan.images??[])];
          const available=limit-overhead-tokenCost(JSON.stringify(history))-imageCost(allImages)-tokenCost(original);
          const envelope=reviewEnvelope(checkpoint?evidence.slice(checkpoint.rows.length):evidence,plan.action,available,!!checkpoint,plan.purpose==='disclosure');
          if(envelope.kind==='needs_rebuild')throw new ContextRebuild(envelope.reason);
          if(envelope.kind==='evidence_unavailable')throw new ReviewFailure('evidence_unavailable',envelope.reason);
          const input=original+envelope.input;
          if(!reviewer)reviewer=await this.create(plan,system,undefined,limit,overhead,effort,imageCost);
          reviewer.run=run;reviewer.input=input;reviewer.images=plan.images;reviewer.first=true;
          const agent=reviewer.handle.agent;
          metadata={sessionId:agent.id,contextMode:mode};
          reviewer.start=agent.session.snapshotEvents().length;
          const cancel=()=>agent.cancel({kind:'parent'});
          run.signal.addEventListener('abort',cancel,{once:true});
          try {
            run.signal.throwIfAborted();
            const message=createUserMessage({content:[{type:'text',text:input},...(plan.images??[])],source:{kind:'user'}});
            reviewer.inputId=message.id;
            agent.followup(message);await agent.whenIdle();
            run.signal.throwIfAborted();
          } finally {run.signal.removeEventListener('abort',cancel);reviewer.run=undefined;}
          const events=agent.session.snapshotEvents(),added=events.slice(reviewer.start);
          if(added.some(event=>event.type==='compaction/start'))throw new ContextRebuild('Reviewer compaction requires full evidence rebuild');
          const turn=inputEvidence(added,reviewer.inputId!).turn;
          const end=added.findLast(event=>event.type==='turn/end'&&event.data.turn===turn);
          if(end?.type!=='turn/end')throw new ReviewFailure('runtime','Reviewer did not produce a terminal turn');
          if(end.data.reason.kind==='error') {
            if(end.data.reason.error.code==='CONTEXT_WINDOW_EXCEEDED')throw new ContextRebuild('Reviewer context overflow');
            throw new ReviewFailure('runtime',`${end.data.reason.error.code}: ${end.data.reason.error.message}`);
          }
          if(end.data.reason.kind!=='completed')throw new ReviewFailure('runtime',`Reviewer turn ended: ${end.data.reason.kind}`);
          const last=added.findLast(event=>event.type==='assistant/message'&&event.data.turn===turn);
          const text=last?.type==='assistant/message'?last.data.message.content.filter(block=>block.type==='text').map(block=>block.text).join(''):'';
          const decision=plan.parse(text);
          if(!decision)throw new ReviewFailure('invalid_verdict','Invalid reviewer verdict');
          lifetime.throwIfAborted();
          if(!fork&&this.trunks.get(key)===trunk){trunk.checkpoint={rows:serialized,events:[...events],sessionId:agent.id};trunk.reviewer=reviewer;committed=true;}
          return{kind:'decision',value:decision,usage:deriveTurnTokenUsage(added.slice(added.findIndex(event=>event.type==='turn/start'),added.findLastIndex(event=>event.type==='turn/end')+1)),metadata:{sessionId:agent.id,contextMode:mode}};
        } catch(error) {
          if(reviewer){await this.discard(reviewer);reviewer=undefined;}
          lifetime.throwIfAborted();
          const context=error instanceof ContextRebuild||run.cause==='context_rebuild';
          const format=error instanceof ReviewFailure&&error.kind==='invalid_verdict';
          const timeout=run.cause==='attempt_timeout';
          if(run.retries>=2||context&&run.rebuilds>=1||format&&run.formats>=1||timeout&&policy.mode==='normal'&&run.retries>=policy.maxRetries||!context&&!format&&!timeout)throw error;
          run.retries++;if(context)run.rebuilds++;if(format)run.formats++;
          checkpoint=undefined;mode=fork?'fork-rebuild':'rebuild';run.restart();
        }
      }
    } catch(error) {
      if(parentSignal?.aborted)return{kind:'cancelled'};
      const cause=total.signal.aborted?total.signal.reason:run.cause==='attempt_timeout'?new ReviewFailure('timeout','Reviewer activity deadline exceeded'):error instanceof ReviewFailure?error:new ReviewFailure(error instanceof ContextRebuild?'evidence_unavailable':'runtime',String(error));
      return{kind:'unavailable',cause,metadata};
    } finally {
      clearTimeout(totalTimer);run.clear();
      if(!committed&&reviewer)await this.discard(reviewer);
      if(!fork){trunk.reviewer=committed?reviewer:undefined;trunk.busy=false;}
    }
  }

  private createRun(lifetime:AbortSignal):Run {
    let timer:ReturnType<typeof setTimeout>|undefined;
    const run={} as Run;
    run.retries=0;run.formats=0;run.rebuilds=0;
    run.pause=()=>{clearTimeout(timer);timer=undefined;};
    run.restart=()=>{
      run.pause();run.cause=undefined;
      if(!run.controller||run.controller.signal.aborted){run.controller=new AbortController();run.signal=AbortSignal.any([lifetime,run.controller.signal]);}
      timer=setTimeout(()=>{run.cause='attempt_timeout';run.controller.abort(new ReviewFailure('timeout','Reviewer activity deadline exceeded'));},activityMs);
    };
    run.clear=run.pause;run.restart();return run;
  }
  private async discard(reviewer:Reviewer){await reviewer.handle.dispose();this.active.delete(reviewer);}
  private async create(plan:ReviewPlan<unknown>,system:string,checkpoint:Checkpoint|undefined,limit:number,overhead:number,effort:ReasoningEffortId|undefined,imageCost:(images:readonly ImageBlock[])=>number):Promise<Reviewer>{
    const reviewer={start:checkpoint?.events.length??0,input:'',first:true} as Reviewer;
    const handle=await this.ctx.agents.create({sessionId:SessionId(`nano-codex-${randomUUID()}`),
      meta:{cwd:plan.parent.session.header.cwd,agentPreset:'nano-codex-reviewer',...(checkpoint?{parentSession:SessionId(checkpoint.sessionId),isSeeded:true}:{})},
      ...(checkpoint?{seed:checkpoint.events,inheritedEventCount:SessionLogOffset(checkpoint.events.length)}:{}),
      agentOptions:{...plan.reviewer,...(effort?{reasoningEffort:effort}:{}),maxTokens:outputReserve},
      setup:(scope,agent)=>{
        setApprovalPolicy(agent.session,'never');
        scope.tools.presentAs('native');scope.tools.restrict({allow:[]});
        const tools=inspectionTools(this.ctx);
        for(const tool of tools)scope.tools.register(tool);
        const names=new Set(tools.map(tool=>tool.name));
        scope.tools.guard(exec=>names.has(exec.name)?undefined:'Reviewer permits only native read-only inspection');
        scope.on('agent/pre-step',async(_payload,next)=>{
          const decision=await next();
          return decision.kind==='reject'?decision:{...decision,messages:decision.messages.filter(message=>message.id===reviewer.inputId)};
        },{prepend:true});
        scope.systemPrompt.section({name:'nano-guardian',order:0,text:system,complete:true,interpolate:false});
        scope.on('system-prompt/assemble',async(_assembly,_context,next)=>({...await next(),contexts:[],tools:scope.tools.schemas(agent)}),{prepend:true});
        scope.on('agent/request',async(_payload,next)=>{
          const run=reviewer.run!;run.signal.throwIfAborted();
          const history=agent.session.deriveMessages();
          const cost=tokenCost(JSON.stringify(history))+(reviewer.first&&!history.some(message=>message.id===reviewer.inputId)?tokenCost(reviewer.input):0)+overhead+imageCost(imagesIn(history));
          if(agent.session.snapshotEvents().slice(reviewer.start).some(event=>event.type==='compaction/start')||cost>limit){run.cause='context_rebuild';throw new ContextRebuild('Reviewer request requires evidence rebuild');}
          reviewer.first=false;
          const {reasoningEffort:_previous,...call}=await next();
          return{...call,...plan.reviewer,...(effort?{reasoningEffort:effort}:{}),maxTokens:outputReserve};
        },{prepend:true});
        // This hook only constrains this logical review. DSH owns backoff and request attempts.
        scope.on('agent/request-error',async({failure},next)=>{
          const run=reviewer.run!;
          if(failure.code==='CONTEXT_WINDOW_EXCEEDED'){run.cause='context_rebuild';return;}
          if(failure.code==='IMAGE_OFFLOAD_REQUIRED'){
            if(imagesIn(agent.session.deriveMessages()).length>(reviewer.images?.length??0))run.cause='context_rebuild';
            return;
          }
          if(permanentFailures.has(failure.code)||run.retries>=2)return;
          run.signal.throwIfAborted();run.pause();
          const cursor=agent.session.snapshotEvents().length;
          {
            const result=await next();
            run.retries+=agent.session.snapshotEvents().slice(cursor).filter(event=>event.type==='llm/retry').length;
            run.signal.throwIfAborted();
            if(result?.kind==='retry')run.restart();
            return result;
          }
        },{prepend:true});
        scope.on('llm/stream',async function*(options,next){
          if(options.sessionId===agent.id&&reviewer.images?.length){
            const pending=options.messages.find(message=>message.id===reviewer.inputId);
            const images=pending?imagesIn([pending]):[];
            if(tokenCost(JSON.stringify(options.messages))+tokenCost(JSON.stringify(options.tools??[]))+outputReserve+512+imageCost(imagesIn(options.messages))>limit)throw new ReviewFailure('evidence_unavailable','Frozen images exceed actual request budget');
            if(images.length!==reviewer.images.length||images.some((image,index)=>image.offloaded||JSON.stringify(image.attachment)!==JSON.stringify(reviewer.images![index]!.attachment)))throw new ReviewFailure('evidence_unavailable','Frozen review images missing from actual model request');
          }
          yield* next();
        },{prepend:true});
      },
    });
    reviewer.handle=handle;this.active.add(reviewer);return reviewer;
  }
}
