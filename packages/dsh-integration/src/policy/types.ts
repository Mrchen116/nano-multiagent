import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import type { MessageApprovalContext } from '@nano/product-contracts';
import type { AgentConfiguration } from '../index.js';
import type { ApprovalSources } from './sources.js';
import type { ReviewDecision } from './rules.js';

/** Frozen inputs shared by the independently installed approval strategies. */
export interface ApprovalReviewRequest {
  exec: ToolExecution;
  config: AgentConfiguration;
  sources: ApprovalSources;
  inherited: unknown[];
  messageContext?: MessageApprovalContext;
  reviewer: { provider: string; model: string };
}
export interface ApprovalReviewResult {
  decision: ReviewDecision;
  usage?: unknown;
  source?: string;
  metadata?: { sessionId?: string; contextMode?: string; risk?: string; authorization?: string };
}
