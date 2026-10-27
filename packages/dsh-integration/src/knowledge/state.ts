import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
export type KnowledgeKind = 'memory' | 'skills';
export interface KnowledgeFact {
  id: string; agentId: string; rootSessionId: string; sessionId: string; kind: KnowledgeKind; turn: number; action: string; path: string;
  cancelledByDisable?: boolean;
  name?: string; scope?: string; skill_root?: string; source?: string; reviewId?: string;
}
export interface KnowledgeReview { id: string; agentId: string; rootSessionId: string; kind: KnowledgeKind | 'combined'; source?: 'F3' | 'F4'; target?: {root:string;name:string}; evidenceSessionIds?: string[]; skipReason?: string; turn: number; status: string; diagnostic?: string; childSessionId?: string; at: number }
export interface KnowledgeDomain extends DomainSpec {
  tables: { counters: DomainTableSpec<string, { memory: number; skills: number }>; reviews: DomainTableSpec<string, KnowledgeReview>; facts: DomainTableSpec<string, KnowledgeFact> };
}
export const knowledgeDomain: KnowledgeDomain = defineDomain({ name: 'nano_knowledge', version: 1, layout: 'per-record', tables: {
  counters: domainTable(z.object({ memory: z.number(), skills: z.number() })),
  reviews: domainTable(z.object({ id: z.string(), agentId: z.string(), rootSessionId: z.string(), kind: z.enum(['memory', 'skills', 'combined']), source: z.enum(['F3','F4']).optional(), target: z.object({root:z.string(),name:z.string()}).optional(), evidenceSessionIds:z.array(z.string()).optional(), skipReason:z.string().optional(), turn: z.number(), status: z.string(), diagnostic: z.string().optional(), childSessionId: z.string().optional(), at: z.number() })),
  facts: domainTable(z.object({ cancelledByDisable: z.boolean().optional(), id: z.string(), agentId: z.string(), rootSessionId: z.string(), sessionId: z.string(), kind: z.enum(['memory', 'skills']), turn: z.number(), action: z.string(), path: z.string(), name: z.string().optional(), scope: z.string().optional(), skill_root: z.string().optional(), source: z.string().optional(), reviewId: z.string().optional() })),
} });
