import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ImageBlock } from '@deepseek-ai/dsh-llm';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import { codexPolicy, parseCodexDecision } from './codex-context.js';
import { codexEntries } from './sources.js';
import { retainInstructions } from './retained-instructions.js';
import { ReviewSession, ReviewFailure, type ReviewPlan } from './review-session.js';
import type { AgentConfiguration } from '../index.js';
import { personalReviewPolicy, parsePersonalDecision, type PersonalReview } from '../personal-security.js';

declare module '@deepseek-ai/cordis' { interface Context { codexApproval: CodexApproval } }

/** Map action-specific rules and evidence onto the isolated reviewer lifecycle. */
export class CodexApproval extends Service {
  static inject=['agents','tools','systemPrompt','llm','approval'];
  private readonly sessions: ReviewSession;
  constructor(ctx:Context) {
    super(ctx,'codexApproval');
    this.sessions=new ReviewSession(ctx);
    ctx.on('agent/disposed',({agent})=>this.release(agent.id));
    ctx.effect(()=>()=>this.sessions.dispose());
  }

  /** Release both purposes at a parent configuration or disposal boundary. */
  async release(sessionId:string):Promise<void>{ await this.sessions.release(sessionId); }

  /** Review the frozen action with purpose-specific policy and original human evidence. */
  async review(request:ApprovalReviewRequest):Promise<ApprovalReviewResult>{
    const parent=request.exec.agent!;
    const result=await this.execute({purpose:'tool',parent,signal:request.exec.signal,config:request.config,reviewer:request.reviewer,
      system:()=>codexPolicy(request.config.approval!),
      evidence:async()=>[...codexEntries(request.sources.restoreEntries(request.inherited,false)),...await request.sources.history(parent,request.exec.callId,request.config.mode !== 'global',{toolResults:true,fullAssistant:true})],
      action:{name:request.exec.name,arguments:request.exec.arguments,id:request.exec.callId,schema:this.ctx.tools.schemas(parent).find(tool=>tool.name===request.exec.name),cwd:parent.session.header.cwd,rules:request.config.approval,recipient:request.messageContext},
      retained:()=>retainInstructions(parent,request.sources.restoreEntries(request.inherited,false),request.config.personal?.ownerId),parse:parseCodexDecision});
    return {...result,metadata:{...result.metadata,risk:result.decision.risk,authorization:result.decision.authorization}};
  }

  /** Review a host-frozen PA disclosure with its own policy and cache namespace.
   *
   * Args:
   *   request: Verified PA scope, current evidence supplier and exact pending action.
   * Returns:
   *   A strict PA verdict plus the shared reviewer's usage and session metadata.
   */
  async reviewDisclosure(request:{agent:Agent;config:AgentConfiguration;action:unknown;evidence:()=>Promise<Record<string,unknown>[]>;signal?:AbortSignal;images?:readonly ImageBlock[]}):Promise<PersonalReview & {usage?:unknown;metadata?:ApprovalReviewResult['metadata']}> {
    const header=request.agent.session.requestHeader();
    const reviewer=request.config.approval?.reviewer??{provider:header?.config.provider??request.config.provider,model:header?.config.model??request.config.model};
    const result=await this.execute({purpose:'disclosure',parent:request.agent,signal:request.signal,config:request.config,reviewer,
      system:()=>personalReviewPolicy('action'),evidence:request.evidence,action:request.action,images:request.images,retained:()=>retainInstructions(request.agent,[],request.config.personal?.ownerId),parse:text=>{const decision=parsePersonalDecision(text);if(decision?.decision==='unavailable')throw new ReviewFailure('evidence_unavailable',decision.reason);return decision;}});
    return {...result.decision,usage:result.usage,metadata:result.metadata};
  }


  private async execute<T>(plan:ReviewPlan<T>) {
    const result=await this.sessions.run(plan,plan.signal);
    if(result.kind==='decision')return{decision:result.value,usage:result.usage,metadata:result.metadata};
    if(result.kind==='cancelled')throw plan.signal?.reason??new Error('Review cancelled');
    throw result.cause;
  }
}
