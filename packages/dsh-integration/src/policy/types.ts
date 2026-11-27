import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import type { MessageApprovalContext } from '@nano/product-contracts';
import type { AgentConfiguration } from '../index.js';
import type { ApprovalSources } from './sources.js';
import type { ReviewDecision } from './rules.js';

export type ReviewAction = Pick<ToolExecution, 'agent' | 'callId' | 'arguments' | 'name' | 'signal'>;

/** Frozen inputs shared by the independently installed approval strategies. */
export interface ApprovalReviewRequest {
  exec: ReviewAction;
  worker?: boolean;
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
  /** Reject a verdict that became stale while awaiting host publication. */
  assertCurrent?: () => void;
}
