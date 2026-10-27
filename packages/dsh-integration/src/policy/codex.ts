import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { BlockAssembler, createUserMessage, expandAssistantStream, LlmError, type ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { ReviewFailure, reviewFailure } from './retry.js';
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
  parent: Agent;
  signal?: AbortSignal;
  config: AgentConfiguration;
  reviewer: {provider:string;model:string};
  system: () => string | Promise<string>;
  evidence: () => Promise<Record<string, unknown>[]>;
  action: unknown;
  parse: (text:string) => T | undefined;
  snapshot?: ApprovalReviewRequest['snapshot'];
  children?: ApprovalReviewRequest['children'];
}
interface Checkpoint { rows: string[]; events: SessionEvent[]; sessionId: string }
interface Reviewer { handle: AgentHandle; signal: AbortSignal; failure?: Error; start: number; input: string; inputId?: string; first: boolean; limit: number; overhead: number }
interface Trunk { fingerprint: string; busy: boolean; reviewer?: Reviewer; checkpoint?: Checkpoint }
class ReviewBudgetError extends Error {}
const outputReserve=2048;
const prefix=(before:string[],after:string[])=>before.length<=after.length&&before.every((value,i)=>value===after[i]);
const recoverable=(error:unknown)=>error instanceof ReviewBudgetError || reviewFailure(error).category === 'context';

/** Synchronous Guardian hosted by DSH; each parent owns one reusable idle reviewer. */
export class CodexApproval extends Service {
  static inject=['agents','tools','systemPrompt','llm','approval'];
  private readonly trunks=new Map<string,Trunk>();
  private readonly active=new Set<Reviewer>();
  constructor(ctx:Context){
    super(ctx,'codexApproval');
    ctx.on('agent/disposed',({agent})=>this.release(agent.id));
    ctx.effect(()=>async()=>{await Promise.all([...this.active].map(reviewer=>reviewer.handle.dispose()));this.active.clear();this.trunks.clear();});
  }

  /** Drop a parent cache at a configuration boundary; in-flight work cannot republish it. */
  async release(sessionId:string, purpose?: 'tool' | 'disclosure'):Promise<void>{
    for(const kind of purpose ? [purpose] : ['tool','disclosure']) {
      const key=`${kind}:${sessionId}`,trunk=this.trunks.get(key);this.trunks.delete(key);
      if(trunk&&!trunk.busy&&trunk.reviewer)await this.discard(trunk.reviewer);
    }
  }

  /** Review one action under a full-attempt deadline, with at most one evidence rebuild.
   * Args:
   *   request: Frozen authorization/action and this attempt's cancellation signal.
   * Returns:
   *   Final Guardian verdict and available accounting; failures never publish a checkpoint.
   */
  async review(request:ApprovalReviewRequest):Promise<ApprovalReviewResult>{
    const parent=request.exec.agent!;
    const result=await this.run({purpose:'tool',parent,signal:request.attemptSignal ?? request.exec.signal,config:request.config,reviewer:request.reviewer,
      snapshot:request.snapshot,children:request.children,
      system:()=>codexPolicy(request.config.approval!),
      evidence:async()=>[...codexEntries(request.sources.restoreEntries(request.inherited,false)),...await request.sources.history(parent,request.exec.callId,request.config.mode !== 'global',{toolResults:true,fullAssistant:true})],
      action:{name:request.exec.name,arguments:request.exec.arguments,id:request.exec.callId,schema:this.ctx.tools.schemas(parent).find(tool=>tool.name===request.exec.name),cwd:parent.session.header.cwd,rules:request.config.approval,recipient:request.messageContext},
      parse:parseCodexDecision});
    return {...result,metadata:{...result.metadata,risk:result.decision.risk,authorization:result.decision.authorization}};
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
    const deadline=new AbortController();
    const timer=request.purpose==='tool'?setTimeout(()=>deadline.abort(new ReviewFailure('timeout')),90_000):undefined;
    const budget=request.purpose==='tool'?deadline.signal:AbortSignal.timeout(90_000);
    const signal=request.signal?AbortSignal.any([request.signal,budget]):budget;
    if(signal.aborted){clearTimeout(timer);signal.throwIfAborted();}
    const cwd=parent.session.header.cwd!;
    const fingerprint=JSON.stringify([request.config,request.reviewer,cwd]);
    let trunk=this.trunks.get(key);
    if(!trunk||trunk.fingerprint!==fingerprint){
      const old=trunk;
      trunk={fingerprint,busy:false};this.trunks.set(key,trunk);
      if(old&&!old.busy&&old.reviewer){await this.discard(old.reviewer);old.reviewer=undefined;}
    }
    // Claim before any asynchronous preparation. Busy callers fork the last committed checkpoint.
    const fork=trunk.busy;
    if(!fork)trunk.busy=true;
    let checkpoint=trunk.checkpoint;
    let reviewer=fork?undefined:trunk.reviewer;
    let committed=false;
    try{
      const snapshot=request.snapshot ?? {};
      snapshot.codex ??= (async()=>{
        const [system,evidence]=await Promise.all([request.system(),request.evidence()]);
        return {system,evidence:structuredClone(evidence),action:structuredClone(request.action)};
      })();
      const [{system,evidence,action},model]=await Promise.all([snapshot.codex,this.ctx.llm.resolveModelInfo(request.reviewer.provider,request.reviewer.model,signal)]);
      signal.throwIfAborted();
      const effort=model.reasoning?.efforts.find(value=>value.id==='low')?.id??model.reasoning?.defaultEffort??model.reasoning?.efforts[0]?.id;
      const serialized=evidence.map(row=>JSON.stringify(row));
      if(checkpoint&&!prefix(checkpoint.rows,serialized)){checkpoint=undefined;if(reviewer){await this.discard(reviewer);reviewer=undefined;}}
      const schemas=inspectionTools(cwd,()=>signal).map(({name,description,parameters})=>({name,description,parameters}));
      const overhead=tokenCost(system)+tokenCost(JSON.stringify(schemas))+outputReserve+512;
      const limit=model.context?.contextWindow;
      if(!limit)throw new Error('Guardian reviewer model has no declared context window');
      let mode=fork?'fork':checkpoint?'delta':'full';
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
          reviewer.signal=signal;reviewer.failure=undefined;reviewer.input=input;reviewer.first=true;
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
          }finally{
            signal.removeEventListener('abort',cancel);
            for(const event of request.children ? agent.session.snapshotEvents().slice(reviewer.start) : []){
              if(event.type!=='assistant/message'&&event.type!=='assistant/attempt')continue;
              const assembly=new BlockAssembler();
              for(const {chunk} of expandAssistantStream(event.data.stream))assembly.push(chunk);
              const usage=assembly.usage;
              request.children?.push({request:event.data.step,sessionId:agent.id,contextMode:mode,...(usage!==undefined?{usage}:{})});
            }
          }
          const events=agent.session.snapshotEvents();const added=events.slice(reviewer.start);
          if(added.some(event=>event.type==='compaction/start'))throw new ReviewBudgetError('Guardian compaction invalidated pending evidence');
          if(reviewer.failure)throw reviewer.failure;
          const end=added.findLast(event=>event.type==='turn/end');
          if(end?.type==='turn/end'&&end.data.reason.kind!=='completed'){
            if(end.data.reason.kind==='error'){
              const failure=end.data.reason.error;
              throw new LlmError(failure.message ?? 'Guardian request failed',failure.code,failure);
            }
            throw new ReviewFailure('unknown');
          }
          const last=added.findLast(event=>event.type==='assistant/message');
          const text=last?.type==='assistant/message'?last.data.message.content.filter(block=>block.type==='text').map(block=>block.text).join(''):'';
          const decision=request.parse(text);
          if(!decision)throw new ReviewFailure('invalid');
          signal.throwIfAborted();
          if(!fork&&this.trunks.get(key)===trunk){trunk.checkpoint={rows:serialized,events:[...events],sessionId:agent.id};trunk.reviewer=reviewer;committed=true;}
          const hasUsage=added.some(event=>event.type==='assistant/message'&&event.data.usage!==undefined);
          return{decision,...(hasUsage?{usage:deriveTurnTokenUsage(added.slice(added.findIndex(event=>event.type==='turn/start'),added.findLastIndex(event=>event.type==='turn/end')+1))}:{}),metadata:{sessionId:agent.id,contextMode:mode}};
        }catch(error){
          if(reviewer){await this.discard(reviewer);reviewer=undefined;}
          signal.throwIfAborted();
          if(attempt||!recoverable(error))throw error;
          checkpoint=undefined;mode=fork?'fork-rebuild':'rebuild';
        }
      }
      throw new Error('Guardian review unavailable');
    }finally{
      clearTimeout(timer);
      if(!committed&&reviewer)await this.discard(reviewer);
      if(!fork){trunk.reviewer=committed?reviewer:undefined;trunk.busy=false;}
    }
  }

  private async discard(reviewer:Reviewer){await reviewer.handle.dispose();this.active.delete(reviewer);}
  private async create(request:Pick<ReviewRun<unknown>,'parent'|'reviewer'>,system:string,signal:AbortSignal,checkpoint:Checkpoint|undefined,limit:number,overhead:number,effort:ReasoningEffortId|undefined):Promise<Reviewer>{
    const reviewer={} as Reviewer;
    reviewer.signal=signal;reviewer.limit=limit;reviewer.overhead=overhead;reviewer.start=checkpoint?.events.length??0;
    const handle=await this.ctx.agents.create({sessionId:SessionId(`nano-codex-${randomUUID()}`),signal,
      meta:{cwd:request.parent.session.header.cwd,agentPreset:'nano-codex-reviewer',...(checkpoint?{parentSession:SessionId(checkpoint.sessionId),isSeeded:true}:{})},
      ...(checkpoint?{seed:checkpoint.events,inheritedEventCount:SessionLogOffset(checkpoint.events.length)}:{}),
      agentOptions:{...request.reviewer,reasoningEffort:effort,maxTokens:outputReserve},
      setup:(scope,agent)=>{
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
        // Do not delegate: provider `always` must never multiply whole-review attempts.
        scope.on('agent/request-error',async({failure})=>{reviewer.failure=new LlmError(failure.message,failure.code,failure);return undefined;},{prepend:true});
        // Preparation and thrown stream failures bypass request-error in the public loop.
        scope.on('agent/error',({error})=>{reviewer.failure ??= error instanceof Error?error:new ReviewFailure('unknown');});
      },
    });
    reviewer.handle=handle;this.active.add(reviewer);
    if(signal.aborted){await this.discard(reviewer);signal.throwIfAborted();}
    return reviewer;
  }
}
