import { Service, type Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-working-directory';
import { classify } from './classifier.js';
import { workspaceFileAllowed } from './file-approval.js';
import type { ApprovalReviewRequest, ApprovalReviewResult } from './types.js';

declare module '@deepseek-ai/cordis' { interface Context { ccApproval: CcApproval } }
/** CC's workspace exemption and pinned two-stage classifier. */
export class CcApproval extends Service {
  static inject = ['llm', 'workingDirectory'];
  constructor(ctx: Context) { super(ctx, 'ccApproval'); }
  async review(request: ApprovalReviewRequest): Promise<ApprovalReviewResult> {
    const { exec, config } = request;
    const workspaceRoot = exec.agent!.session.header.cwd!;
    const effectiveCwd = this.ctx.get('workingDirectory')?.get(exec.agent!.session) || workspaceRoot;
    if (await workspaceFileAllowed({ workspaceRoot, effectiveCwd }, exec.name, exec.arguments, config.approval!)) {
      return { decision: { behavior: 'allow', reason: 'Ordinary workspace file operation' }, source: 'workspace_file' };
    }
    return classify(this.ctx, request);
  }
}
