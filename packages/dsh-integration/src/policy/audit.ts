import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

const review = z.object({
  time: z.number(), callId: z.string(), tool: z.string(), source: z.string(), decision: z.string(), reason: z.string(),
  consecutive: z.number(), total: z.number(), reviewer: z.object({ provider: z.string(), model: z.string() }).optional(),
  rules: z.enum(['nano', 'codex', 'dsh']).optional(), elapsedMs: z.number().optional(), usage: z.unknown().optional(),
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
