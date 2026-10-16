import { Service, type Context } from '@deepseek-ai/cordis';
import { classify } from './classifier.js';
import { workspaceFileAllowed } from './cc-workspace.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';

declare module '@deepseek-ai/cordis' { interface Context { ccApproval: CcApproval } }
/** CC's workspace exemption and pinned two-stage classifier. */
export class CcApproval extends Service {
  static inject = ['llm'];
  constructor(ctx: Context) { super(ctx, 'ccApproval'); }
  async review(request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
    const { exec, config } = request;
    if (await workspaceFileAllowed(exec.agent!.session.header.cwd!, exec.name, exec.arguments, config.approval!)) {
      return { decision: { behavior: 'allow', reason: 'Ordinary workspace file operation' }, source: 'workspace_file' };
    }
    return classify(this.ctx, request);
  }
}
