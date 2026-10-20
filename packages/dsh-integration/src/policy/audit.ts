import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

const recovery = z.object({
  reviewId: z.string(), callId: z.string(), rules: z.string(), reviewer: z.object({ provider: z.string(), model: z.string() }),
  startedAt: z.number(), endedAt: z.number().optional(), elapsedMs: z.number().optional(), terminalReason: z.string().optional(),
  finalRoute: z.string().optional(), fallbackOutcome: z.string().optional(), retriesUsed: z.number(), formatRetriesUsed: z.number(),
  contextRebuilds: z.number(), complete: z.boolean(), requestsTruncated: z.boolean(), knownUsage: z.array(z.unknown()), overflowKnownUsage: z.record(z.string(), z.number()).optional(), usageComplete: z.boolean(),
  attempts: z.array(z.object({
    scope: z.string(), attemptOrdinal: z.number(), retryOrdinal: z.number(), generation: z.number(), budgetMs: z.number(),
    startedAt: z.number(), endedAt: z.number().optional(), outcome: z.string().optional(), category: z.string().optional(),
    code: z.string().optional(), status: z.number().optional(), delayMs: z.number().optional(), retryAfterKnown: z.boolean().optional(),
    sessionId: z.string().optional(), contextMode: z.string().optional(), requestCount: z.number(),
    requests: z.array(z.object({ requestOrdinal: z.number(), provider: z.string(), model: z.string(), startedAt: z.number(),
      endedAt: z.number().optional(), code: z.string().optional(), status: z.number().optional(), requestId: z.string().optional(),
      usage: z.unknown().optional(), usageComplete: z.boolean(), retryAfterKnown: z.boolean().optional(), outcome: z.string().optional() })),
  })),
});
const review = z.object({
  time: z.number(), callId: z.string(), tool: z.string(), source: z.string(), decision: z.string(), reason: z.string(),
  consecutive: z.number(), total: z.number(), reviewer: z.object({ provider: z.string(), model: z.string() }).optional(),
  rules: z.enum(['nano', 'codex', 'dsh']).optional(), elapsedMs: z.number().optional(), usage: z.unknown().optional(),
  recovery: recovery.optional(), reviewId: z.string().optional(),
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
