import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import type { StreamProgress, FrozenBatch } from './memory-sources.js';
import type { DocumentOperation, DocumentReceipt } from './memory-documents.js';

export interface DreamingOwner {
  activationAt: number; streams: Record<string, StreamProgress>; seen: string[]; rotation: number;
  lastAttempt?: number; lastSuccessAutomatic?: number; retryAt?: number; failures: number;
}
export interface DreamingRun {
  id: string; agentId: string; rootSessionId: string; childSessionId?: string;
  identityRecorded?: boolean;
  mode: 'automatic' | 'manual'; state: 'prepared' | 'running' | 'applying' | 'completed' | 'partial' | 'failed' | 'cancelled';
  at: number; endedAt?: number; generation: number; directory: string; batch: FrozenBatch;
  plan?: Array<Omit<DocumentOperation, 'content'> & { afterHash: string }>; receipts: DocumentReceipt[]; reviewed: string[]; summary?: string; error?: string;
}
interface DreamingDomain extends DomainSpec { tables: { owners: DomainTableSpec<string, DreamingOwner>; runs: DomainTableSpec<string, DreamingRun> } }
/** Only scheduling, provenance and operation metadata live here; Markdown remains authoritative. */
export const dreamingDomain: DreamingDomain = defineDomain({ name: 'nano_dreaming', version: 1, layout: 'per-record', tables: {
  owners: domainTable(z.custom<DreamingOwner>()), runs: domainTable(z.custom<DreamingRun>()),
} });
