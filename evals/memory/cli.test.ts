import { createServer } from 'node:http';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { expect, it } from 'vitest';

it('defaults to a verifiable plan with zero model requests and gates execution before credential use', async () => {
  const root = await mkdtemp(join(tmpdir(), 'memory-cli-'));
  let requests = 0;
  const server = createServer((_request, response) => { requests++; response.end('{}'); });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address() as { port: number };
  const data = JSON.stringify([{ question_id: 'synthetic', question_type: 'single-session-user', question: 'Future question',
    question_date: '2024/02/01', answer: 'Gold only', haystack_dates: ['2024/01/01'], haystack_session_ids: ['s'],
    haystack_sessions: [[{ role: 'user', content: 'Original history' }]], answer_session_ids: ['s'] }]);
  const limits = { timeoutMs: 1000, maxModelCalls: 5, maxOutputTokens: 100 };
  const route = { baseURL: `http://127.0.0.1:${address.port}/v1`, apiKeyEnv: 'EVAL_TEST_UNSET_KEY', model: 'fixture-model' };
  const config = { dataset: { path: 'dataset.json', revision: 'synthetic-v1', sha256: createHash('sha256').update(data).digest('hex') },
    candidate: { ...route, dreaming: { maxInputTokens: 2000 } }, judge: route,
    limits: { prepare: limits, answer: limits, score: limits } };
  await writeFile(join(root, 'dataset.json'), data); await writeFile(join(root, 'ids.json'), '["synthetic"]');
  await writeFile(join(root, 'config.json'), JSON.stringify(config));
  const invoke = (...args: string[]) => promisify(execFile)(process.execPath, ['--import', 'tsx', resolve('evals/memory/cli.ts'), ...args], { cwd: process.cwd() });
  try {
    const { stdout } = await invoke('--config', join(root, 'config.json'), '--ids', join(root, 'ids.json'), '--output', join(root, 'plan'));
    const plan = JSON.parse(stdout);
    expect(plan.counts).toEqual({ questions: 1, sessions: 1, messages: 1 });
    expect(plan.modelCallsStarted).toBe(0); expect(requests).toBe(0);
    expect(await readFile(join(root, 'plan/plan.json'), 'utf8')).not.toContain('Gold only');
    expect(stdout).not.toContain('Original history');
    for (const command of ['run', 'score']) await expect(invoke(command)).rejects.toThrow(/allow-model-calls/);
    await writeFile(join(root, 'retired-config.json'), JSON.stringify({ ...config,
      candidate: { ...config.candidate, dreaming: { ...config.candidate.dreaming, maxSteps: 10, maxRunMs: 1000 } } }));
    await expect(invoke('--config', join(root, 'retired-config.json'), '--ids', join(root, 'ids.json'))).rejects.toThrow(/maxSteps.*maxRunMs/);
    await writeFile(join(root, 'ids.json'), '[]');
    await expect(invoke('run', '--allow-model-calls', '--config', join(root, 'config.json'), '--ids', join(root, 'ids.json'))).rejects.toThrow(/nonempty/);
    expect(requests).toBe(0);
  } finally { server.closeAllConnections(); await new Promise<void>(done => server.close(() => done())); await rm(root, { recursive: true, force: true }); }
}, 15000);
