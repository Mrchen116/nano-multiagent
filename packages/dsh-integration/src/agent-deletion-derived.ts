import { rm } from 'node:fs/promises';
import { join } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Domain, DomainSpec, KvTable } from '@deepseek-ai/dsh-storage-domain';
import { descendantDomain } from './descendants.js';
import { subagentRecoveryDomain } from './subagent-recovery.js';
import { historyDomain } from './history.js';
import { dreamingDomain } from './knowledge/dreaming-state.js';
import { knowledgeDomain } from './knowledge/state.js';
import { modelRunsDomain } from './model-fallback.js';
import { modelDomain } from './model-policy.js';
import { approvalDomain } from './policy/audit.js';
import { trajectorySourcesDomain } from './trajectory-attachments.js';
import { trajectoryRunsDomain } from './trajectory-runs.js';
import { workflowDomain } from './workflow/state.js';

const encode = (id: string) => Buffer.from(id).toString('base64url');
const decode = (key: string) => Buffer.from(key, 'base64url').toString();
export const tupleOwner = (key: string): string | undefined => {
  const tuple: unknown = JSON.parse(decode(key));
  return Array.isArray(tuple) && typeof tuple[0] === 'string' ? tuple[0] : undefined;
};

function mounted<S extends DomainSpec>(ctx: Context, spec: S): Domain<S> {
  const domain = ctx.storageDomain.get(spec.name) as Domain<S> | undefined;
  if (!domain) throw new Error(`Agent deletion needs the mounted ${spec.name} domain`);
  return domain;
}

/** Collect supplemental identities from their owning domains, with edges to a known root. */
export function ownedLinks(ctx: Context, agentId: string) {
  const links = new Map<string, Set<string>>();
  const known: string[] = [];
  const link = (parent: string, child?: string) => {
    if (!child) return;
    const ids = links.get(parent) ?? new Set<string>();
    ids.add(child);
    links.set(parent, ids);
  };
  for (const [key, catalog] of mounted(ctx, descendantDomain).table('sessions').entries()) {
    link(catalog.rootId, decode(key));
    for (const child of catalog.children) if (child.mode !== 'unknown') link(catalog.rootId, child.id);
  }
  for (const [, fork] of mounted(ctx, historyDomain).table('forks').entries()) link(fork.source, fork.sessionId);
  for (const [, run] of mounted(ctx, trajectoryRunsDomain).table('runs').entries()) link(run.parentSessionId, run.sessionId);
  for (const [, run] of mounted(ctx, workflowDomain).table('runs').entries())
    for (const call of run.calls) for (const attempt of call.attempts) link(run.parentSessionId, attempt.id);
  for (const [parent, audits] of mounted(ctx, approvalDomain).table('sessions').entries())
    for (const audit of audits) if (audit.rules === 'codex') link(parent, audit.metadata?.sessionId);
  for (const [, review] of mounted(ctx, knowledgeDomain).table('reviews').entries())
    if (review.agentId === agentId && review.childSessionId) known.push(review.childSessionId);
  for (const [, run] of mounted(ctx, dreamingDomain).table('runs').entries())
    if (run.agentId === agentId && run.childSessionId) known.push(run.childSessionId);
  return { known, links };
}

async function remove<V>(table: KvTable<string, V>, select: (key: string, value: V) => boolean) {
  for (const [key, value] of table.entries()) if (select(key, value)) {
    await table.delete(key);
    if (table.get(key) !== undefined) throw new Error('Agent record remained after deletion');
  }
}

/** Delete records and exports in Nano-owned domains after their target writers settle. */
export async function purgeDerived(ctx: Context, home: string, agentId: string, sessionIds: string[]): Promise<void> {
  const ids = new Set(sessionIds);
  const owned = (id?: string) => id !== undefined && ids.has(id);
  const history = mounted(ctx, historyDomain), models = mounted(ctx, modelDomain), approval = mounted(ctx, approvalDomain);
  const workflow = mounted(ctx, workflowDomain), knowledge = mounted(ctx, knowledgeDomain), dreaming = mounted(ctx, dreamingDomain);
  await Promise.all([
    remove(history.table('snapshots'), (_, row) => owned(row.sessionId)),
    remove(history.table('overrides'), key => owned(decode(key))),
    remove(history.table('forks'), (_, row) => row.sessionId ? owned(row.sessionId) : owned(row.source)),
    remove(mounted(ctx, descendantDomain).table('sessions'), key => owned(decode(key))),
    remove(mounted(ctx, subagentRecoveryDomain).table('sessions'), key => owned(key)),
    remove(models.table('sessions'), key => owned(decode(key))),
    remove(models.table('commands'), (_, row) => owned(row.sessionId)),
    remove(mounted(ctx, modelRunsDomain).table('runs'), (_, row) => owned(row.sessionId)),
    remove(mounted(ctx, trajectorySourcesDomain).table('sources'), key => owned(tupleOwner(key))),
    remove(mounted(ctx, trajectoryRunsDomain).table('runs'), (_, row) => owned(row.sessionId)),
    remove(approval.table('sessions'), key => owned(key)),
    remove(approval.table('delegated'), key => owned(key)),
    remove(workflow.table('runs'), (_, row) => owned(row.parentSessionId)),
    remove(workflow.table('budgets'), (_, row) => owned(row.parentSessionId)),
    remove(workflow.table('commands'), (_, row) => owned(row.sessionId)),
    remove(knowledge.table('facts'), (_, row) => row.agentId === agentId),
    remove(knowledge.table('reviews'), (_, row) => row.agentId === agentId),
    remove(knowledge.table('counters'), key => owned(decode(key).replace(/:(memory|skills):iterations$/, ''))),
    remove(dreaming.table('owners'), key => key === encode(agentId)),
    remove(dreaming.table('runs'), (_, row) => row.agentId === agentId),
    remove(dreaming.table('summaries'), (_, row) => row.agentId === agentId),
    ...sessionIds.flatMap(id => ['', '.tmp'].map(suffix => rm(join(home, 'exports', `${encode(id)}.jsonl${suffix}`), { force: true }))),
  ]);
}
