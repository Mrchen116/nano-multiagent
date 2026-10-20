import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import { createUserMessage, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { SessionId, SessionLogOffset, type SessionEvent } from '@deepseek-ai/dsh-session';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-compaction';
import { deriveTurnTokenUsage } from '@deepseek-ai/dsh-token-meter/client';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { codexPolicy, parseCodexDecision, reviewInput, tokenCost } from './codex-context.js';
import { inspectionTools } from './codex-inspection.js';
import { codexEntries } from './sources.js';

declare module '@deepseek-ai/cordis' { interface Context { codexApproval: CodexApproval } }
interface Checkpoint { rows: string[]; events: SessionEvent[]; sessionId: string }
interface Reviewer { handle: AgentHandle; signal: AbortSignal; failure?: Error; start: number; input: string; first: boolean; limit: number; overhead: number }
interface Trunk { fingerprint: string; busy: boolean; reviewer?: Reviewer; checkpoint?: Checkpoint }
class ReviewBudgetError extends Error {}
const outputReserve=2048;
const prefix=(before:string[],after:string[])=>before.length<=after.length&&before.every((value,i)=>value===after[i]);
const recoverable=(error:unknown)=>error instanceof ReviewBudgetError || /context.{0,20}(window|overflow|exceed)|compaction|CONTEXT_WINDOW_EXCEEDED/i.test(String(error));

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
  async release(sessionId:string):Promise<void>{
    const trunk=this.trunks.get(sessionId);this.trunks.delete(sessionId);
    if(trunk&&!trunk.busy&&trunk.reviewer)await this.discard(trunk.reviewer);
  }

  /** Review one action, sharing a single deadline across preparation, tools and retry. */
  async review(request:ApprovalReviewRequest):Promise<ApprovalReviewResult>{
    const parent=request.exec.agent!;
    const deadline=AbortSignal.timeout(90_000);
    const signal=AbortSignal.any([request.exec.signal,deadline]);signal.throwIfAborted();
    const cwd=parent.session.header.cwd!;
    const fingerprint=JSON.stringify([request.config,request.reviewer,cwd]);
    let trunk=this.trunks.get(parent.id);
    if(!trunk||trunk.fingerprint!==fingerprint){
      const old=trunk;
      trunk={fingerprint,busy:false};this.trunks.set(parent.id,trunk);
      if(old&&!old.busy&&old.reviewer){await this.discard(old.reviewer);old.reviewer=undefined;}
    }
    // Claim before any asynchronous preparation. Busy callers fork the last committed checkpoint.
    const fork=trunk.busy;
    if(!fork)trunk.busy=true;
    let checkpoint=trunk.checkpoint;
    let reviewer=fork?undefined:trunk.reviewer;
    let committed=false;
    try{
      const [system,rows,model]=await Promise.all([
        codexPolicy(request.config.approval!),
        request.sources.history(parent,request.exec.callId,request.config.mode !== 'global',{toolResults:true,fullAssistant:true}),
        this.ctx.llm.resolveModelInfo(request.reviewer.provider,request.reviewer.model,signal),
      ]);
      signal.throwIfAborted();
      const evidence=[...codexEntries(request.sources.restoreEntries(request.inherited,false)),...rows];
      const serialized=evidence.map(row=>JSON.stringify(row));
      if(checkpoint&&!prefix(checkpoint.rows,serialized)){checkpoint=undefined;if(reviewer){await this.discard(reviewer);reviewer=undefined;}}
      const schemas=inspectionTools(cwd,()=>signal).map(({name,description,parameters})=>({name,description,parameters}));
      const overhead=tokenCost(system)+tokenCost(JSON.stringify(schemas))+outputReserve+512;
      const limit=model.context?.contextWindow;
      if(!limit)throw new Error('Guardian reviewer model has no declared context window');
      const action={name:request.exec.name,arguments:request.exec.arguments,id:request.exec.callId,schema:this.ctx.tools.schemas(parent).find(tool=>tool.name===request.exec.name),cwd,rules:request.config.approval,recipient:request.messageContext};
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
            try { input=reviewInput(delta,action,remaining,false); } catch(error) { throw new ReviewBudgetError(String(error)); }
            if(input.includes('reason="evidence_budget"'))throw new ReviewBudgetError('Guardian delta requires budget rebuild');
          }else input=reviewInput(evidence,action,limit-overhead);
          if(!reviewer)reviewer=await this.create(request,system,signal,checkpoint,limit,overhead);
          reviewer.signal=signal;reviewer.failure=undefined;reviewer.input=input;reviewer.first=true;
          reviewer.start=reviewer.handle.agent.session.snapshotEvents().length;
          const agent=reviewer.handle.agent;
          const cancel=()=>agent.cancel({kind:'parent'});
          signal.addEventListener('abort',cancel,{once:true});
          try{
            signal.throwIfAborted();
            agent.followup(createUserMessage({content:[{type:'text',text:input}],source:{kind:'user'}}));
            await agent.whenIdle();
            signal.throwIfAborted();
          }finally{signal.removeEventListener('abort',cancel);}
          const events=agent.session.snapshotEvents();const added=events.slice(reviewer.start);
          if(added.some(event=>event.type==='compaction/start'))throw new ReviewBudgetError('Guardian compaction invalidated pending evidence');
          if(reviewer.failure)throw reviewer.failure;
          const end=added.findLast(event=>event.type==='turn/end');
          if(end?.type==='turn/end'&&end.data.reason.kind!=='completed')throw new Error(JSON.stringify(end.data.reason));
          const last=added.findLast(event=>event.type==='assistant/message');
          const text=last?.type==='assistant/message'?last.data.message.content.filter(block=>block.type==='text').map(block=>block.text).join(''):'';
          const decision=parseCodexDecision(text);
          if(!decision)throw new Error('Invalid Guardian verdict');
          signal.throwIfAborted();
          if(!fork&&this.trunks.get(parent.id)===trunk){trunk.checkpoint={rows:serialized,events:[...events],sessionId:agent.id};trunk.reviewer=reviewer;committed=true;}
          return{decision,usage:deriveTurnTokenUsage(added.slice(added.findIndex(event=>event.type==='turn/start'),added.findLastIndex(event=>event.type==='turn/end')+1)),metadata:{sessionId:agent.id,contextMode:mode,risk:decision.risk,authorization:decision.authorization}};
        }catch(error){
          if(reviewer){await this.discard(reviewer);reviewer=undefined;}
          signal.throwIfAborted();
          if(attempt||!recoverable(error))throw error;
          checkpoint=undefined;mode=fork?'fork-rebuild':'rebuild';
        }
      }
      throw new Error('Guardian review unavailable');
    }finally{
      if(!committed&&reviewer)await this.discard(reviewer);
      if(!fork){trunk.reviewer=committed?reviewer:undefined;trunk.busy=false;}
    }
  }

  private async discard(reviewer:Reviewer){await reviewer.handle.dispose();this.active.delete(reviewer);}
  private async create(request:ApprovalReviewRequest,system:string,signal:AbortSignal,checkpoint:Checkpoint|undefined,limit:number,overhead:number):Promise<Reviewer>{
    const effort = ReasoningEffortId('low');
    const reviewer={} as Reviewer;
    reviewer.signal=signal;reviewer.limit=limit;reviewer.overhead=overhead;reviewer.start=checkpoint?.events.length??0;
    const handle=await this.ctx.agents.create({sessionId:SessionId(`nano-codex-${randomUUID()}`),signal,
      meta:{cwd:request.exec.agent!.session.header.cwd,agentPreset:'nano-codex-reviewer',...(checkpoint?{parentSession:SessionId(checkpoint.sessionId),isSeeded:true}:{})},
      ...(checkpoint?{seed:checkpoint.events,inheritedEventCount:SessionLogOffset(checkpoint.events.length)}:{}),
      agentOptions:{...request.reviewer,reasoningEffort:effort,maxTokens:outputReserve},
      setup:(scope,agent)=>{
        setApprovalPolicy(agent.session,'never');
        scope.tools.presentAs('native');scope.tools.restrict({allow:[]});
        const tools=inspectionTools(request.exec.agent!.session.header.cwd!,()=>reviewer.signal);
        for(const tool of tools)scope.tools.register(tool);
        const names=new Set(tools.map(tool=>tool.name));
        scope.tools.guard(exec=>names.has(exec.name)?undefined:'Guardian permits only host-owned read-only inspection');
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
        scope.on('agent/request-error',async({failure})=>{reviewer.failure=new Error(JSON.stringify(failure));return undefined;},{prepend:true});
      },
    });
    reviewer.handle=handle;this.active.add(reviewer);
    if(signal.aborted){await this.discard(reviewer);signal.throwIfAborted();}
    return reviewer;
  }
}
