import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { Session } from '@deepseek-ai/dsh-session';
import { createHistoryView } from 'dsh-agent-context';
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

it('imports dialogue segments as restorable windows of one persistent Global session', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-eval-windows-'));
  const candidate = new NanoMemoryCandidate(await fixtureOptions(root));
  const recent = { ...history, sessions: history.sessions.map((session, index) => ({ ...session,
    timestamp: history.sessions[0]!.timestamp + index * 60000 })) };
  try {
    const result = await candidate.prepare(recent, limits);
    expect(result.status, JSON.stringify(result)).toBe('ready');
    if (result.status !== 'ready') throw new Error(JSON.stringify(result));
    expect(result.receipt.usage.modelCalls).toBe(0);
    const map = JSON.parse(await readFile(result.receipt.evidenceRef.replace('receipt.json', 'source-map.json'), 'utf8'));
    expect(new Set(map.map((row: {rootSessionId:string}) => row.rootSessionId)).size).toBe(1);
    expect(new Set(map.map((row: {windowId:string}) => row.windowId)).size).toBe(4);
    const saved = JSON.parse(await readFile(join(root, 'imported-root.json'), 'utf8'));
    const session = Session.create(saved.header.id, saved.events, saved.header);
    const active = JSON.stringify(session.surface.nodes.map(seq => saved.events[seq]));
    expect(active).toContain('UNTRIGGERED_SAME_TIME');
    expect(active).not.toContain('LONG_MESSAGE_END');
    expect(active).not.toContain('I moved to Paris.');
    const view = createHistoryView(saved.header.id, saved.events);
    expect(view.listWindows().items).toHaveLength(4);
    const original = view.search({ query: 'LONG_MESSAGE_END', max_chars_per_item: 4000 }).items;
    expect(original).toHaveLength(1);
    expect(original[0]?.window_id).toBe(map[0].windowId);
    const complete = view.read(original[0]!.window_id, original[0]!.item_id, 0, 20000);
    const recovered = JSON.parse(complete.content.split('\n')[0]!);
    expect(recovered.messages.map((message: {content:Array<{text:string}>}) => message.content[0]!.text).join('')).toBe(history.sessions[0]!.turns[0]!.content);
    const calls = saved.events.filter((event: {type:string}) => event.type === 'tool/call');
    expect(new Set(calls.map((event: {data:{callId:string}}) => event.data.callId)).size).toBe(6);
    const { identity } = JSON.parse(await readFile(result.preparedRef, 'utf8'));
    expect(saved.header.id).toBe(identity.rootSessionId);
    expect(new Set(calls.map((event: {data:{arguments:string}}) => JSON.parse(event.data.arguments).target))).toEqual(new Set([identity.conversationId]));
    const firstRead = saved.events.find((event: {type:string}) => event.type === 'tool/result');
    expect(JSON.parse(firstRead.data.message.content[0].text)).toMatchObject({ conversation_type: 'direct', delivery: 'participant', channel: 'web',
      messages: [expect.objectContaining({ sender: { id: identity.ownerId, type: 'user', name: 'Owner', is_owner: true } }), expect.anything()] });
    for (const row of map) {
      const source = recent.sessions.find(session => session.id === row.session)!;
      expect(saved.events.slice(row.firstSeq, row.lastSeq + 1).every((event: {time:number}) => event.time === source.timestamp)).toBe(true);
    }
  } finally { await candidate.close(); await rm(root, { recursive: true, force: true }); }
}, 60000);

it('replays only arrived history and freezes naturally formed memory for isolated answers', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-eval-'));
  const options = await fixtureOptions(root);
  const candidate = new NanoMemoryCandidate(options);
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
    expect(requests).not.toContain('I moved to Rome. UNTRIGGERED_LAST_UPDATE');
    expect(requests).not.toContain('UNTRIGGERED_SAME_TIME');
    expect(prepareRequests.every(request => request.logicalTime < history.sessions[2]!.timestamp)).toBe(true);
    const timeline = (await readFile(audit.requests.replace('requests.jsonl', 'timeline.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(timeline.filter(event => event.event === 'session_imported').map(event => event.sessionId)).toEqual(history.sessions.map(session => session.id));
    expect(timeline.at(-1)).toMatchObject({ event: 'frozen', importedSessions: 4, logicalTime: history.sessions[3]!.timestamp, backlog: { state: 'pending' } });
    // Recovery and source reads must work inside the candidate, not just appear in its tool list.
    for (const callId of ['fixture-0', 'fixture-5', 'fixture-6', 'fixture-11', 'fixture-12']) {
      expect(prepareRequests.some(request => request.messages.some((message: { role: string; toolCallId?: string; isError?: boolean }) =>
        message.role === 'tool' && message.toolCallId === callId && !message.isError))).toBe(true);
    }
    const chatResults = early.flatMap(request => request.messages).filter(message => message.role === 'tool' && message.toolCallId === 'fixture-11');
    expect(chatResults.some(message => JSON.parse(message.content[0].text).messages.some((item: {content:Array<{text:string}>}) => item.content[0]?.text.includes('LONG_MESSAGE_END')))).toBe(true);
    const futureResults = prepareRequests.flatMap(request => request.messages).filter(message => message.role === 'tool' && message.toolCallId === 'fixture-12');
    expect(futureResults.every(message => JSON.parse(message.content[0].text).messages.length === 0)).toBe(true);
    const listed = (rows: typeof prepareRequests) => rows.flatMap(request => request.messages)
      .filter(message => message.role === 'tool' && message.toolCallId === 'fixture-0')
      .map(message => JSON.parse(message.content[0].text));
    expect(listed(early).every(result => result.items.length === 1)).toBe(true);
    const later = prepareRequests.filter(request => request.importedSessions === 2);
    expect(listed(later).some(result => result.items.length === 2)).toBe(true);
    const oldReads = later.flatMap(request => request.messages)
      .filter(message => message.role === 'tool' && message.toolCallId === 'fixture-2' && !message.isError);
    expect(oldReads.some(message => message.content[0].text.includes('LONG_MESSAGE_END'))).toBe(true);
    for (const request of prepareRequests) {
      const plain = request.messages.flatMap((message: {content:Array<{type:string;text?:string}>}) => message.content)
        .filter((block: {type:string}) => block.type === 'text').map((block: {text:string}) => block.text).join('\n');
      const directory = JSON.parse(plain.match(/Source directory \(data\): (\[[^\n]*\])/)![1]!);
      expect(directory).toHaveLength(1);
      expect(directory[0].baseline).toBe(-1);
    }
    expect(requests).toContain('EVALUATION_RECOVERY');
    expect(requests).toContain('I moved to Paris.');
    const answerRequests = (await readFile(answerAudit.requests, 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const { identity } = JSON.parse(await readFile(prepared.preparedRef, 'utf8'));
    expect(answerRequests.every(request => request.sessionId === identity.rootSessionId)).toBe(true);
    const wake = answerRequests[0].messages.find((message: {source?:{channel?:string}}) => message.source?.channel === 'inbox');
    expect(wake.source).toMatchObject({ kind: 'nano-system', actorId: identity.agentId, channel: 'inbox' });
    expect(wake.content[0].text).toContain('New messages are waiting in your Inbox.');
    expect(wake.content[0].text).not.toContain(question.text);
    expect(JSON.stringify(answerRequests[0])).not.toContain('UNRELATED_HISTORY_ONLY');
    expect(JSON.stringify(answerRequests[0])).not.toContain('source_eligibility_pending');
    expect(JSON.stringify(answerRequests[0])).toContain('Current city: Paris');
    expect(JSON.stringify(answerRequests)).toContain('LONG_MESSAGE_END');
    expect(JSON.stringify(answerRequests)).not.toContain('EVALUATION_RECOVERY');
    expect(JSON.stringify(answerRequests)).toContain('2024/06/01');
    expect(JSON.stringify(answerRequests)).toContain('You live in Paris');
    const results = answerRequests.flatMap(request => request.messages).filter(message => message.role === 'tool');
    const result = (call: number) => results.find(message => message.toolCallId === `fixture-${call}`);
    expect(JSON.parse(result(0).content[0].text)).toMatchObject({ sources: [{ target: identity.conversationId, unread: 1, conversation_type: 'direct', delivery: 'participant' }] });
    expect(JSON.parse(result(1).content[0].text)).toMatchObject({ target: identity.conversationId, conversation_type: 'direct', delivery: 'participant', channel: 'web',
      messages: [{ sender: { id: identity.ownerId, is_owner: true }, time: question.date, content: [{ text: question.text }] }] });
    for (const call of [5, 6, 7, 9, 10, 11, 12, 13, 14]) expect(result(call), `tool result ${call}`).toMatchObject({ isError: false });
    expect(JSON.parse(result(10).content[0].text).items).toEqual([expect.objectContaining({ window_id: `${identity.rootSessionId}:initial` })]);
    expect(result(9).content[0].text).toContain('ANSWER_RECOVERY');
    expect(result(5).content[0].text).toContain('nano-memory');
    expect(JSON.parse(result(11).content[0].text).items).toEqual([]);
    expect(JSON.parse(result(12).content[0].text)).toEqual({ sources: [] });
    const stored = JSON.parse(result(13).content[0].text).messages;
    expect(stored.some((message: { content:Array<{text:string}> }) => message.content[0]?.text.includes('UNTRIGGERED_LAST_UPDATE'))).toBe(true);
    const mapping = JSON.parse(await readFile(audit.requests.replace('requests.jsonl', 'source-map.json'), 'utf8'));
    const original = stored.find((message: {message_id:string}) => message.message_id === mapping[0].messageId);
    expect(original).toMatchObject({ sender: { id: identity.ownerId, is_owner: true }, source_time: '2024-01-01T00:00:00+00:00',
      content: [{ text: history.sessions[0]!.turns[0]!.content }] });
    expect(JSON.parse(result(14).content[0].text)).toMatchObject({ status: 'sent', target: identity.conversationId });
    expect(JSON.stringify(answerRequests)).not.toContain('evaluation-answer-');
    expect(JSON.stringify(answerRequests)).not.toContain('evaluation-question');
    options.environment!.EVALUATION_DELEGATE_ROOT = identity.rootSessionId;
    const second = await candidate.answer(prepared.preparedRef, question, limits);
    expect(second.status, JSON.stringify(second)).toBe('completed');
    if (second.status !== 'completed') throw new Error(JSON.stringify(second));
    expect(second.evidenceRef).not.toBe(first.evidenceRef);
    expect(second.text).toBe('You live in Paris.');
    const delegatedAudit = JSON.parse(await readFile(second.evidenceRef, 'utf8'));
    const delegatedRequests = (await readFile(delegatedAudit.requests, 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(delegatedRequests.some(request => request.sessionId !== identity.rootSessionId)).toBe(true);
    expect(delegatedRequests.some(request => request.sessionId === identity.rootSessionId && JSON.stringify(request.messages).includes('DELEGATED_RESULT: You live in Paris.'))).toBe(true);
    expect(second.usage.modelCalls).toBe(delegatedRequests.length);
  } catch (error) {
    const dirs = (await readdir(root)).filter(name => name.startsWith('prepare-') || name.startsWith('answer-'));
    const logs = await Promise.all(dirs.map(async name => { try { return await readFile(join(root, name, 'runtime.log'), 'utf8'); } catch { return ''; } }));
    throw new Error((error instanceof Error ? error.stack : String(error)) + '\n' + logs.join('\n'));
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


it('isolates parallel case runtimes and keeps a sealed chat reusable after another case is cancelled', async () => {
  const roots = await Promise.all(['a', 'b'].map(label => mkdtemp(join(tmpdir(), `nano-eval-parallel-${label}-`))));
  const options = await Promise.all(roots.map(fixtureOptions));
  for (const option of options) option.environment!.EVALUATION_CHAT_ONLY = '1';
  const candidates = options.map(option => new NanoMemoryCandidate(option));
  try {
    const prepared = await Promise.all(candidates.map((candidate, index) => candidate.prepare({ caseKey: `case-${index}`, sessions: [{
      id: 'shared-dataset-id', date: '2024/01/01', timestamp: Date.UTC(2024, 0, 1), turns: [
        { role: 'user', content: `CASE_MARKER: owner ${index}` }, { role: 'assistant', content: `CASE_MARKER: reply ${index}` },
      ],
    }] }, limits)));
    for (const result of prepared) expect(result.status, JSON.stringify(result)).toBe('ready');
    const refs = prepared.map(result => { if (result.status !== 'ready') throw new Error(JSON.stringify(result)); return result.preparedRef; });
    const identities = await Promise.all(refs.map(async ref => JSON.parse(await readFile(ref, 'utf8')).identity));
    expect(identities[0].conversationId).not.toBe(identities[1].conversationId);
    options[1]!.environment!.EVALUATION_HANG = '1';
    const question = { id: 'question', text: 'Find the stored facts.', date: '2024/06/01' };
    const answeringA = candidates[0]!.answer(refs[0]!, question, limits);
    const answeringB = candidates[1]!.answer(refs[1]!, question, limits);
    await expect.poll(async () => {
      const dir = (await readdir(roots[1]!)).find(name => name.startsWith('answer-'));
      try { return JSON.parse(await readFile(join(roots[1]!, dir!, 'usage.json'), 'utf8')).usage.modelCalls; } catch { return 0; }
    }, { timeout: 10000 }).toBe(1);
    await candidates[1]!.close();
    const [answerA, interrupted] = await Promise.all([answeringA, answeringB]);
    expect(answerA).toMatchObject({ status: 'completed', text: 'CASE_MARKER: reply 0\nCASE_MARKER: owner 0' });
    expect(interrupted.status).toBe('failed');
    delete options[1]!.environment!.EVALUATION_HANG;
    const answerB = await candidates[1]!.answer(refs[1]!, question, limits);
    expect(answerB).toMatchObject({ status: 'completed', text: 'CASE_MARKER: reply 1\nCASE_MARKER: owner 1' });
    for (const root of roots) for (const name of (await readdir(root)).filter(name => name.startsWith('prepare-') || name.startsWith('answer-'))) {
      const audit = JSON.parse(await readFile(join(root, name, 'usage.json'), 'utf8'));
      expect(() => process.kill(audit.processId, 0)).toThrow();
    }
  } finally { await Promise.all(candidates.map(candidate => candidate.close())); await Promise.all(roots.map(root => rm(root, { recursive: true, force: true }))); }
}, 60000);
