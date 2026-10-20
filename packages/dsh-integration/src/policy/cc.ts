import { Service, type Context } from '@deepseek-ai/cordis';
import { classify } from './classifier.js';
import { workspaceFileAllowed } from './cc-workspace.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import type { AgentConfiguration } from '../index.js';

declare module '@deepseek-ai/cordis' { interface Context { ccApproval: CcApproval } }
/** CC's workspace exemption and pinned two-stage classifier. */
export class CcApproval extends Service {
  static inject = ['llm'];
  constructor(ctx: Context) { super(ctx, 'ccApproval'); }
  /** Resolve the existing exemption before the facade allocates model recovery. */
  exempt(exec: ToolExecution, config: AgentConfiguration): Promise<boolean> {
    return workspaceFileAllowed(exec.agent!.session.header.cwd!, exec.name, exec.arguments, config.approval!);
  }
  async review(request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
    return classify(this.ctx, request);
  }
}
