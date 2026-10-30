import { randomUUID } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { EvaluationChat } from '../src/evaluation.js';

it('preserves imported dialogue and timestamps through product queries and independent snapshots', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-im-evaluation-'));
  const identity = () => ({ agentId: randomUUID(), ownerId: randomUUID(), nodeId: randomUUID(), bindingId: randomUUID(),
    conversationId: randomUUID(), rootSessionId: randomUUID(), startTime: Date.UTC(2024, 0, 1) });
  const first = identity(), second = identity();
  const a = new EvaluationChat({ ...first, path: join(root, 'a.sqlite') });
  const b = new EvaluationChat({ ...second, path: join(root, 'b.sqlite') });
  const copies: EvaluationChat[] = [];
  try {
    const body = 'CASE_A ' + 'long '.repeat(6000) + 'END_OF_ORIGINAL';
    const ids = a.importSession({ id: 'one', date: '2024/01/01', timestamp: first.startTime,
      turns: [{ role: 'user', content: body }, { role: 'assistant', content: 'Recorded.' }] });
    b.importSession({ id: 'one', date: '2024/01/01', timestamp: second.startTime, turns: [{ role: 'user', content: 'CASE_B' }] });
    a.append('user', 'CASE_A future correction', first.startTime + 86400000);
    const query = { action: 'search', target: first.conversationId, query: 'CASE_A', memory_after: first.startTime, memory_cutoff: first.startTime };
    const page = a.query(query);
    expect(page.messages).toHaveLength(1);
    expect(page.messages[0]).toMatchObject({ message_id: ids[0], created_at: '2024-01-01T00:00:00.000Z',
      sender: { id: first.ownerId, kind: 'user', is_owner: true }, version_scope: 'verified_at_cutoff', complete_message: false });
    expect(page.has_more).toBe(true);
    const next = a.query({ ...query, cursor: page.next_cursor });
    expect(next.has_more).toBe(false);
    expect(page.messages[0].content[0].text + next.messages[0].content[0].text).toBe(body);
    const assistant = a.query({ action: 'read', target: first.conversationId, message_id: ids[1] });
    expect(assistant.messages[0]).toMatchObject({ sender: { kind: 'agent', id: first.agentId }, content: [{ text: 'Recorded.' }] });
    expect(b.query({ action: 'search', query: 'CASE_A' }).messages).toEqual([]);
    expect(() => b.query({ action: 'read', target: first.conversationId })).toThrow('target_not_accessible');
    const sealed = join(root, 'sealed.sqlite');
    await a.snapshot(sealed);
    const [one, two] = [1, 2].map(index => new EvaluationChat({ ...first, snapshot: sealed, path: join(root, `copy-${index}.sqlite`) }));
    copies.push(one!, two!);
    expect(() => one!.query({ ...query, cursor: page.next_cursor })).toThrow('invalid_cursor');
    const ownCursor = one!.query(query).next_cursor;
    expect(() => two!.query({ ...query, cursor: ownCursor })).toThrow('invalid_cursor');
    one!.append('user', 'ANSWER_ONLY', first.startTime + 172800000);
    expect(two!.query({ action: 'search', query: 'ANSWER_ONLY' }).messages).toEqual([]);
    expect(a.query({ action: 'search', query: 'ANSWER_ONLY' }).messages).toEqual([]);
    one!.close(); copies.shift();
    expect(two!.query({ action: 'search', query: 'future correction' }).messages).toHaveLength(1);
  } finally { for (const copy of copies) copy.close(); a.close(); b.close(); await rm(root, { recursive: true, force: true }); }
});
