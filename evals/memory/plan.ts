import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';
import { DEFAULT_DREAMING_SCHEDULE } from '@nano/product-contracts';
import { digest, loadCases } from './dataset.js';
import { judgeIdentity } from './judge.js';
import type { EvaluationPlan } from './runner.js';

const limits = z.object({ timeoutMs: z.number().int().positive(), maxModelCalls: z.number().int().positive(), maxOutputTokens: z.number().int().positive() }).strict();
const connection = z.object({ baseURL: z.url(), apiKeyEnv: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/), model: z.string().min(1) }).strict();
export const configurationSchema = z.object({
  dataset: z.object({ path: z.string().min(1), revision: z.string().min(1), sha256: z.string().regex(/^[a-f0-9]{64}$/) }).strict(),
  candidate: connection.extend({ reasoningEffort: z.string().optional(),
    dreaming: z.object({ maxInputTokens: z.number().int().positive(),
      intervalMs: z.number().int().positive().default(DEFAULT_DREAMING_SCHEDULE.intervalMs),
      quietMs: z.number().int().nonnegative().default(DEFAULT_DREAMING_SCHEDULE.quietMs),
    }).strict(),
  }).strict(),
  judge: connection,
  limits: z.object({ prepare: limits, answer: limits, score: limits }).strict(),
}).strict();
export type EvaluationConfiguration = z.infer<typeof configurationSchema>;
const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const sha256 = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');

/** Read and validate an explicit evaluation configuration without probing any model. */
export async function readConfiguration(path: string): Promise<EvaluationConfiguration> {
  const config = configurationSchema.parse(JSON.parse(await readFile(path, 'utf8')));
  config.dataset.path = resolve(dirname(path), config.dataset.path);
  for (const route of [config.candidate, config.judge]) {
    const url = new URL(route.baseURL);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Model baseURL must be HTTP(S) without credentials, query or fragment');
  }
  return config;
}

async function treeHash(path: string): Promise<string | null> {
  const rows: Array<[string, string]> = [];
  const walk = async (directory: string, prefix: string) => {
    for (const item of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      const name = prefix + item.name;
      if (item.isDirectory()) await walk(join(directory, item.name), name + '/');
      else if (item.isFile()) rows.push([name, sha256(await readFile(join(directory, item.name)))]);
    }
  };
  try { await walk(path, ''); } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null; throw error; }
  return digest(rows);
}

/** Freeze the protocol and candidate identities using exact inputs and installed build bytes. */
export async function makePlan(config: EvaluationConfiguration, idsFile: string) {
  const selected = JSON.parse(await readFile(idsFile, 'utf8')) as unknown;
  if (!Array.isArray(selected) || !selected.length || selected.some(id => typeof id !== 'string')) throw new Error('IDs file must contain a nonempty JSON string array');
  const data = await readFile(config.dataset.path);
  const datasetHash = sha256(data);
  if (datasetHash !== config.dataset.sha256) throw new Error('Dataset SHA-256 mismatch');
  const cases = loadCases(JSON.parse(data.toString('utf8')), selected);
  const exec = promisify(execFile);
  const [{ stdout: head }, { stdout: status }, lockHash, runtimeHash, guidanceHash] = await Promise.all([
    exec('git', ['rev-parse', 'HEAD'], { cwd: repository }), exec('git', ['status', '--porcelain'], { cwd: repository }),
    readFile(join(repository, 'pnpm-lock.yaml')).then(sha256), treeHash(join(repository, 'packages/dsh-integration/lib')), treeHash(join(repository, 'packages/personal-assistant/assets/skills/nano-memory')),
  ]);
  const protocol = { version: 2, datasetHash, datasetRevision: config.dataset.revision, selectedIds: selected,
    history: 'all user/assistant turns; stable session date order; unzoned dates interpreted as UTC',
    preparation: { ingestion: 'chronological-session-ingestion', arrival: 'atomic sessions; stable order at equal timestamps; arrivals before same-time maintenance',
      clock: 'first through last history timestamp; logical time pauses during maintenance; real-time execution budgets',
      freeze: 'wait for admitted work only; do not force a future cycle; retain untriggered backlog in evidence' },
    context: 'cold; candidate-persisted memory only; no original active history or external retrieval',
    judge: { ...judgeIdentity, configuration: config.judge, temperature: 0, maxTokens: Math.min(10, config.limits.score.maxOutputTokens) },
    scoreLimits: config.limits.score, retries: 'no automatic retries; explicit judge-only retry uses frozen answers',
  };
  const candidate = { adapter: 'nano-document-memory-v3', sourceCommit: head.trim(), dirty: status.trim().length > 0,
    runtimeHash, guidanceHash, lockHash, configuration: config.candidate, prepareLimits: config.limits.prepare, answerLimits: config.limits.answer };
  const plan: EvaluationPlan = { protocolId: digest(protocol), candidateId: digest(candidate), datasetHash, selectedIds: selected,
    protocol, candidate, judge: config.judge, scoreLimits: config.limits.score,
    counts: { questions: cases.length, sessions: cases.reduce((sum, item) => sum + item.history.sessions.length, 0),
      messages: cases.reduce((sum, item) => sum + item.history.sessions.reduce((count, session) => count + session.turns.length, 0), 0) },
    modelCallsStarted: 0,
  };
  return { plan, cases };
}
