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
  personalAuthorization?: unknown;
  reviewer: { provider: string; model: string };
  attemptSignal?: AbortSignal;
  children?: ReviewChild[];
  snapshot?: { classifier?: Promise<{ system: string; transcript: string }>; codex?: Promise<{ system: string; evidence: Record<string, unknown>[]; action: unknown }> };
}

/** Available facts for one stage or native model request, never synthetic zero usage. */
export interface ReviewChild {
  stage?: number;
  request?: number;
  sessionId?: string;
  contextMode?: string;
  usage?: unknown;
}
/** One executed full strategy attempt, distinct from stages and tool calls. */
export interface ReviewAttempt {
  ordinal: number; start: number; end: number; elapsedMs: number;
  outcome: string; category: string; reviewer: { provider: string; model: string };
  failure?: import('@deepseek-ai/dsh-llm').LlmFailure;
  delayAfterMs?: number; cleanupConfirmed?: boolean; usage?: unknown;
  metadata?: ApprovalReviewResult['metadata']; children: ReviewChild[];
}
/** Persisted aggregate for one original tool call and automatic review. */
export interface ReviewRetry {
  reviewId: string; attempts: ReviewAttempt[]; extraUsed: number; invalidRecoveryUsed: number; finalCategory: string; totalElapsedMs: number;
}
export interface ApprovalReviewResult {
  decision: ReviewDecision;
  usage?: unknown;
  source?: string;
  metadata?: { sessionId?: string; contextMode?: string; risk?: string; authorization?: string };
}
