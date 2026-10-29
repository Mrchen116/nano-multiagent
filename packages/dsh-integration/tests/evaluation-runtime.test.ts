import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { NanoMemoryCandidate } from '../lib/evaluation.js';
import { fixtureOptions, history, limits } from './fixtures/evaluation.js';

it('freezes initial memory without forcing maintenance when no automatic cycle has arrived', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-eval-not-due-'));
  const candidate = new NanoMemoryCandidate(await fixtureOptions(root));
  const recent = { ...history, sessions: [{ ...history.sessions[0]!, turns: [{ role: 'user' as const, content: 'I live in Berlin.' }] }] };
  try {
    const result = await candidate.prepare(recent, limits);
    expect(result.status, JSON.stringify(result)).toBe('ready');
    if (result.status !== 'ready') throw new Error(JSON.stringify(result));
    expect(result.receipt.usage.modelCalls).toBe(0);
    const audit = JSON.parse(await readFile(result.receipt.evidenceRef, 'utf8'));
    expect(audit.result.details).toMatchObject({ active: false, backlog: { state: 'pending' } });
    const prepared = JSON.parse(await readFile(result.preparedRef, 'utf8'));
    expect(await readFile(join(prepared.workspace, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toContain('No topics saved yet');
  } finally { await candidate.close(); await rm(root, { recursive: true, force: true }); }
}, 60000);

it('replays only arrived history and freezes naturally formed memory for isolated answers', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-eval-'));
  const candidate = new NanoMemoryCandidate(await fixtureOptions(root));
  try {
    const prepared = await candidate.prepare(history, limits);
    expect(prepared.status, JSON.stringify(prepared)).toBe('ready');
    if (prepared.status !== 'ready') throw new Error(JSON.stringify(prepared));
    const audit = JSON.parse(await readFile(prepared.receipt.evidenceRef, 'utf8'));
    expect(audit.importedMessages).toBe(6);
    expect(audit.result.details).toMatchObject({ active: false, backlog: { state: 'pending' } });
    const question = { id: 'query', text: 'FUTURE_QUESTION: where do I live?', date: '2024/06/01' };
    const first = await candidate.answer(prepared.preparedRef, question, limits);
    expect(first.status, JSON.stringify(first)).toBe('completed');
    if (first.status !== 'completed') throw new Error(JSON.stringify(first));
    expect(first.text).toBe('You live in Paris.');
    const answerAudit = JSON.parse(await readFile(first.evidenceRef, 'utf8'));
    expect(answerAudit.deniedTools).toBeGreaterThan(0);
    const requests = await readFile(audit.requests, 'utf8');
    expect(requests).toContain('LONG_MESSAGE_END');
    expect(requests).toContain('2024/01/01');
    expect(requests).not.toContain('FUTURE_QUESTION');
    const prepareRequests = requests.trim().split('\n').map(line => JSON.parse(line));
    const early = prepareRequests.filter(request => request.importedSessions === 1);
    expect(early.length).toBeGreaterThan(0);
    expect(JSON.stringify(early)).toContain('I live in Berlin.');
    expect(JSON.stringify(early)).not.toContain('I moved to Paris.');
    expect(prepareRequests.some(request => request.importedSessions === 2 && JSON.stringify(request).includes('I moved to Paris.'))).toBe(true);
    expect(requests).not.toContain('UNTRIGGERED_LAST_UPDATE');
    expect(requests).not.toContain('UNTRIGGERED_SAME_TIME');
    expect(prepareRequests.every(request => request.logicalTime < history.sessions[2]!.timestamp)).toBe(true);
    const timeline = (await readFile(audit.requests.replace('requests.jsonl', 'timeline.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(timeline.filter(event => event.event === 'session_imported').map(event => event.sessionId)).toEqual(history.sessions.map(session => session.id));
    expect(timeline.at(-1)).toMatchObject({ event: 'frozen', importedSessions: 4, logicalTime: history.sessions[3]!.timestamp, backlog: { state: 'pending' } });
    // Recovery and source reads must work inside the candidate, not just appear in its tool list.
    for (const callId of ['fixture-0', 'fixture-4', 'fixture-5']) {
      expect(prepareRequests.some(request => request.messages.some((message: { role: string; toolCallId?: string; isError?: boolean }) =>
        message.role === 'tool' && message.toolCallId === callId && !message.isError))).toBe(true);
    }
    const futureReads = prepareRequests.flatMap(request => request.messages).filter(message => message.role === 'tool' && message.toolCallId === 'fixture-1');
    expect(futureReads.length).toBeGreaterThan(0);
    for (const message of futureReads) expect(JSON.parse(message.content[0].text)).toMatchObject({ items: [], allowed_range: { through: -1 } });
    expect(requests).toContain('EVALUATION_RECOVERY');
    expect(requests).toContain('I moved to Paris.');
    const answerRequests = (await readFile(answerAudit.requests, 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(JSON.stringify(answerRequests[0])).not.toContain('UNRELATED_HISTORY_ONLY');
    expect(JSON.stringify(answerRequests)).not.toContain('LONG_MESSAGE_END');
    expect(JSON.stringify(answerRequests)).not.toContain('EVALUATION_RECOVERY');
    expect(JSON.stringify(answerRequests)).toContain('2024/06/01');
    expect(JSON.stringify(answerRequests)).toContain('You live in Paris');
    const second = await candidate.answer(prepared.preparedRef, question, limits);
    expect(second.status).toBe('completed');
    if (second.status === 'completed') expect(second.evidenceRef).not.toBe(first.evidenceRef);
  } catch (error) {
    const dirs = (await readdir(root)).filter(name => name.startsWith('prepare-') || name.startsWith('answer-'));
    const logs = await Promise.all(dirs.map(async name => { try { return await readFile(join(root, name, 'runtime.log'), 'utf8'); } catch { return ''; } }));
    throw new Error(String(error) + '\n' + logs.join('\n'));
  } finally { await candidate.close(); await rm(root, { recursive: true, force: true }); }
}, 60000);

it('returns incomplete at a model-call limit and closes the runtime before accepting another case', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-eval-budget-'));
  const candidate = new NanoMemoryCandidate(await fixtureOptions(root));
  try {
    const result = await candidate.prepare(history, { ...limits, maxModelCalls: 1 });
    expect(result).toMatchObject({ status: 'incomplete', reason: 'Evaluation model-call budget exhausted', receipt: { usage: { modelCalls: 1 } } });
    if (result.status !== 'ready') expect(result.receipt).toMatchObject({ importedSessions: 1, importedMessages: 2 });
    await candidate.close();
    const retry = await candidate.prepare(history, limits);
    expect(retry.status, JSON.stringify(retry)).toBe('ready');
  } finally { await candidate.close(); await rm(root, { recursive: true, force: true }); }
}, 60000);

it('terminates a stalled provider at the preparation deadline and retains its usage evidence', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-eval-timeout-'));
  const options = await fixtureOptions(root);
  const candidate = new NanoMemoryCandidate({ ...options, environment: { ...options.environment, EVALUATION_HANG: '1' } });
  try {
    const result = await candidate.prepare(history, { ...limits, timeoutMs: 5000 });
    expect(result.status, JSON.stringify(result)).toBe('incomplete');
    if (result.status === 'ready' || !result.receipt) throw new Error('Missing interrupted preparation evidence');
    expect(result.receipt.usage.modelCalls).toBe(1);
    const audit = JSON.parse(await readFile(result.receipt.evidenceRef, 'utf8'));
    expect(() => process.kill(audit.processId, 0)).toThrow();
  } finally { await candidate.close(); await rm(root, { recursive: true, force: true }); }
}, 15000);
