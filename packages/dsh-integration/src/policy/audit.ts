import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

const metadata = z.object({ sessionId: z.string().optional(), contextMode: z.string().optional(), risk: z.string().optional(), authorization: z.string().optional() });
const retry = z.object({
  reviewId: z.string(), extraUsed: z.number(), invalidRecoveryUsed: z.number(), finalCategory: z.string(), totalElapsedMs: z.number(),
  attempts: z.array(z.object({
    ordinal: z.number(), start: z.number(), end: z.number(), elapsedMs: z.number(), outcome: z.string(), category: z.string(),
    reviewer: z.object({ provider: z.string(), model: z.string() }),
    failure: z.object({ code: z.string(), message: z.string(), status: z.number().optional(), requestId: z.string().optional(), providerRetryAfterMs: z.number().optional() }).optional(),
    delayAfterMs: z.number().optional(), cleanupConfirmed: z.boolean().optional(), usage: z.unknown().optional(), metadata: metadata.optional(),
    children: z.array(z.object({ stage: z.number().optional(), request: z.number().optional(), sessionId: z.string().optional(), contextMode: z.string().optional(), usage: z.unknown().optional() })),
  })),
});
const review = z.object({
  time: z.number(), callId: z.string(), tool: z.string(), source: z.string(), decision: z.string(), reason: z.string(),
  consecutive: z.number(), total: z.number(), reviewer: z.object({ provider: z.string(), model: z.string() }).optional(),
  rules: z.enum(['nano', 'codex', 'dsh']).optional(), elapsedMs: z.number().optional(), usage: z.unknown().optional(),
  metadata: metadata.optional(), retry: retry.optional(),
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
