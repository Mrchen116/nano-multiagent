import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import type { StreamProgress, FrozenBatch, CycleTarget } from './memory-sources.js';
import type { DocumentOperation, DocumentReceipt } from './memory-documents.js';

export interface DreamingOwner {
  protocol: 2;
  activationAt: number; streams: Record<string, StreamProgress>; seen: string[]; rotation: number;
  integrated: Record<string, string>;
  lastAttempt?: number; lastSuccessAutomatic?: number; retryAt?: number; failures: number;
}
export interface DreamingRun {
  id: string; agentId: string; rootSessionId: string; childSessionId?: string;
  identityRecorded?: boolean;
  stage: 'extract' | 'consolidate'; cycleId: string;
  mode: 'automatic' | 'manual'; state: 'prepared' | 'running' | 'applying' | 'completed' | 'partial' | 'failed' | 'cancelled';
  at: number; endedAt?: number; generation: number; directory: string; batch: FrozenBatch;
  target: CycleTarget; summaries: TaskSummary[]; inputHash?: string;
  importLegacy?: boolean; sourcesChecked?: boolean;
  planRetired?: boolean;
  plan?: Array<Omit<DocumentOperation, 'content'> & { afterHash: string }>; receipts: DocumentReceipt[]; summary?: string; error?: string;
}
export interface TaskSummary {
  agentId: string; sessionId: string; rootSessionId: string; baseline: number; through: number;
  sourceVersion: string; generation: number; path: string; hash: string; noSignal: boolean;
  extractionRunId: string; slug: string;
}
interface DreamingDomain extends DomainSpec { tables: { owners: DomainTableSpec<string, DreamingOwner>; runs: DomainTableSpec<string, DreamingRun>; summaries: DomainTableSpec<string, TaskSummary> } }
/** Only scheduling, provenance and operation metadata live here; Markdown remains authoritative. */
export const dreamingDomain: DreamingDomain = defineDomain({ name: 'nano_dreaming', version: 1, layout: 'per-record', tables: {
  owners: domainTable(z.custom<DreamingOwner>()), runs: domainTable(z.custom<DreamingRun>()), summaries: domainTable(z.custom<TaskSummary>()),
} });
