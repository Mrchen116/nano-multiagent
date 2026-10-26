import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

const httpFacts = z.object({ status: z.number().optional(), requestId: z.string().optional(), retryAfterMs: z.number().optional(), receivedAt: z.number().optional() });
const failureFacts = z.object({ code: z.string(), status: z.number().optional(), providerRetryAfterMs: z.number().optional() });
const requestTrace = z.object({
  requestOrdinal: z.number(), provider: z.string(), model: z.string(), resolvedEffort: z.string().optional(),
  startedAt: z.number(), endedAt: z.number().optional(), requestId: z.string().optional(), usage: z.unknown().optional(),
  outcome: z.string().optional(), http: httpFacts.optional(), failure: failureFacts.optional(),
});
export const recoveryTrace = z.object({
  reviewId: z.string(), callId: z.string(), startedAt: z.number(), endedAt: z.number().optional(), elapsedMs: z.number().optional(),
  terminalReason: z.string().optional(), finalRoute: z.string().optional(), fallbackOutcome: z.string().optional(), complete: z.boolean(),
  retriesUsed: z.number(), formatRetriesUsed: z.number(), contextRebuilds: z.number(), requestsTruncated: z.boolean(),
  knownUsage: z.record(z.string(), z.number()).optional(), usageComplete: z.boolean(),
  attempts: z.array(z.object({
    scope: z.string(), attemptOrdinal: z.number(), retryOrdinal: z.number(), generation: z.number(), budgetMs: z.number(),
    startedAt: z.number(), endedAt: z.number().optional(), outcome: z.string().optional(), category: z.string().optional(),
    code: z.string().optional(), status: z.number().optional(), delayMs: z.number().optional(), retryAfterKnown: z.boolean().optional(),
    sessionId: z.string().optional(), contextMode: z.string().optional(), requestCount: z.number(), requests: z.array(requestTrace),
  })),
});
const review = z.object({
  time: z.number(), callId: z.string(), tool: z.string(), source: z.string(), decision: z.string(), reason: z.string(),
  consecutive: z.number(), total: z.number(), reviewer: z.object({ provider: z.string(), model: z.string() }).optional(),
  rules: z.enum(['nano', 'codex', 'dsh']).optional(), elapsedMs: z.number().optional(), usage: z.unknown().optional(),
  recovery: recoveryTrace.optional(), reviewId: z.string().optional(),
  metadata: z.object({ sessionId: z.string().optional(), contextMode: z.string().optional(), risk: z.string().optional(), authorization: z.string().optional() }).optional(),
});
export type ApprovalAudit = z.infer<typeof review>;

// External Session events cannot be marked ignorable by the pinned public writer.
// Keep Nano-owned review facts in the public durable domain; native approval events stay native.
export interface ApprovalDomainSpec extends DomainSpec {
  tables: { sessions: DomainTableSpec<string, ApprovalAudit[]>; delegated: DomainTableSpec<string, { epoch: string; entries: unknown[]; codexEntries?: unknown[] }> };
}
export const approvalDomain: ApprovalDomainSpec = defineDomain({
  name: 'nano_approval', version: 1, layout: 'per-record',
  tables: { sessions: domainTable(z.array(review)), delegated: domainTable(z.object({ epoch: z.string(), entries: z.array(z.unknown()), codexEntries: z.array(z.unknown()).optional() })) },
});
