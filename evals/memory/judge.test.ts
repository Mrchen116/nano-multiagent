import { createServer } from 'node:http';
import { expect, it } from 'vitest';
import { createJudge, judgePrompt } from './judge.js';
import { QUESTION_TYPES } from './dataset.js';

it('selects the frozen official rules while preserving question, gold and raw answer', () => {
  for (const type of QUESTION_TYPES) {
    const prompt = judgePrompt({ questionId: 'a', type, question: 'Q{}', answer: 'G{}', abstention: false }, 'A{}');
    expect(prompt).toContain('Q{}'); expect(prompt).toContain('G{}'); expect(prompt).toContain('A{}');
    if (type === 'temporal-reasoning') expect(prompt).toContain('off-by-one');
    if (type === 'knowledge-update') expect(prompt).toContain('updated answer');
    if (type === 'single-session-preference') expect(prompt).toContain('Rubric:');
  }
  expect(judgePrompt({ questionId: 'a_abs', type: 'multi-session', question: 'Q', answer: 'G', abstention: true }, 'A')).toContain('unanswerable question');
});

it('requires opt-in and records judge failures, raw decisions and available usage without automatic retries', async () => {
  let count = 0;
  const bodies: unknown[] = [];
  const server = createServer(async (request, response) => {
    let body = ''; for await (const chunk of request) body += chunk; bodies.push(JSON.parse(body));
    if (++count === 1) { response.writeHead(503); response.end(); return; }
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({ choices: [{ message: { content: 'Yes' } }], usage: { prompt_tokens: 42, completion_tokens: 1 } }));
  });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const route = { baseURL: `http://127.0.0.1:${(server.address() as { port: number }).port}/v1`, apiKeyEnv: 'MEMORY_JUDGE_TEST', model: 'fixture' };
  process.env.MEMORY_JUDGE_TEST = 'fixture';
  try {
    expect(() => createJudge(route)).toThrow(/allow-model-calls/);
    const judge = createJudge(route, true);
    const gold = { questionId: 'a', type: 'multi-session', question: 'Q', answer: 'G', abstention: false };
    const limits = { timeoutMs: 1000, maxModelCalls: 1, maxOutputTokens: 30 };
    expect(await judge(gold, 'A', limits)).toMatchObject({ status: 'failed', usage: { modelCalls: 1, costUsd: null } });
    expect(count).toBe(1);
    expect(await judge(gold, 'A', limits)).toMatchObject({ status: 'completed', correct: true, raw: 'Yes', usage: { inputTokens: 42, outputTokens: 1 } });
    expect(bodies[1]).toMatchObject({ temperature: 0, max_tokens: 10, model: 'fixture', n: 1 });
  } finally { delete process.env.MEMORY_JUDGE_TEST; server.closeAllConnections(); await new Promise<void>(done => server.close(() => done())); }
});
