import { expect, it } from 'vitest';
import { once } from 'node:events';
import { join } from 'node:path';
import { start, bind, cleanups } from './helpers.js';
import { NodeStore } from '../../../../packages/personal-assistant/src/store.js';
import { InboxStore } from '../../../../packages/personal-assistant/src/inbox.js';
import { GlobalAgent } from '../../../../packages/personal-assistant/src/global-agent.js';
import { WorkSync } from '../../../../packages/personal-assistant/src/work-sync.js';
import type { RuntimeEvent, RuntimePort } from '@nano/product-contracts';

// Compose real product owners at the integration boundary; only native execution is a fixture.
it('projects real PA main/child facts through its durable journal and HTTP uploader into refreshable Work', async () => {
  const center = await start(), node = await bind(center);
  const store = new NodeStore(join(center.dir, 'node.db'), 'alice');
  const inbox = new InboxStore(join(center.dir, 'inbox.db'));
  cleanups.push(() => store.close(), () => inbox.close());
  store.bind({agentId: 'global', sessionId: 'main', conversationId: 'global:global', ownerId: 'alice', cwd: center.dir, revision: '1'});
  const content = '中文😀\n"原始参数"'.repeat(6000), output = '完整工具结果\n'.repeat(5000);
  const source: RuntimeEvent[] = [
    {seq: 0, time: 1000, type: 'request/header', data: {header: {config: {model: 'fixture-model'}}}},
    {seq: 1, time: 1001, type: 'request/context', data: {contextWindow: 8192}},
    {seq: 2, time: 1002, type: 'turn/start', data: {turn: 1}},
    {seq: 3, time: 1003, type: 'user/message', data: {turn: 1, source: {kind: 'human'}, content: []}},
    {seq: 4, time: 1004, type: 'tool/call', data: {turn: 1, callId: 'write', name: 'write', arguments: JSON.stringify({path: 'report.txt', content})}},
    {seq: 5, time: 1008, type: 'tool/result', data: {turn: 1, message: {toolCallId: 'write', content: [{type: 'text', text: output}], isError: false}}},
    {seq: 6, time: 1009, type: 'assistant/message', data: {turn: 1, message: {id: 'answer', content: [{type: 'text', text: '主执行正文'}]}, usage: {inputTokens: 10, outputTokens: 3, cacheReadTokens: 2}}},
    {seq: 7, time: 1010, type: 'turn/end', data: {turn: 1, reason: {kind: 'completed'}}},
  ];
  const child: RuntimeEvent[] = [
    {seq: 1, time: 1004, type: 'turn/start', data: {turn: 1}},
    {seq: 2, time: 1005, type: 'user/message', data: {source: {kind: 'subagent'}, content: []}},
    {seq: 3, time: 1006, type: 'assistant/message', data: {turn: 1, message: {id: 'child-answer', content: [{type: 'text', text: '子执行正文'}]}}},
    {seq: 4, time: 1007, type: 'turn/end', data: {turn: 1, reason: {kind: 'completed'}}},
  ];
  const errors: unknown[] = [];
  const runtime: RuntimePort = {
    onNotification: () => () => {},
    request: async (method, input) => {
      const args = input as {afterSeq?: number; cursors?: Record<string, number>};
      if (method === 'session.descendants') return [{kind: 'child', id: 'child', parentId: 'main', throughSeq: 4, modelVersion: 'done', events: child.filter(event => event.seq > (args.cursors?.child ?? -1))}];
      return {events: source.filter(event => event.seq > (args.afterSeq ?? -1)), durable: true, status: 'idle', throughSeq: 7};
    },
  };
  const makeProduct = (online: boolean) => new GlobalAgent({nodeId: node.node, ownerId: 'alice', agents: [{agentId: 'global', workspace: center.dir, revision: '1', provider: 'fixture', model: 'fixture-model', mode: 'global'}],
    store, inbox, runtime, relay: {ready: online, request: (type, payload) => node.frames.send(type, payload)}, image: async () => '', onError: error => errors.push(error)});
  let product = makeProduct(true);
  cleanups.push(() => product.stop());
  await product.recover();
  const produced = inbox.journalSeq;
  expect(inbox.journal(0).some(event => event.type === 'tool_end')).toBe(true);
  expect(inbox.workCheckpoints('main')).toMatchObject({main: {throughSeq: 7}, child: {throughSeq: 4}});
  const makeSync = (url: string) => new WorkSync({nodeId: node.node, inbox, url, credentials: () => node.runtime, onError: error => errors.push(error)});
  let sync = makeSync(center.base); cleanups.push(() => sync.stop()); sync.start();
  await expect.poll(() => inbox.throughSeq, {timeout: 10000}).toBe(produced);
  expect(errors).toEqual([]);
  const read = () => center.http('GET', '/im/v1/agents/global/work', undefined, center.tokens.alice);
  const first = await read(); expect(first.status, first.body).toBe(200);
  expect(first.body).toMatchObject({main_session_id: 'main', main_execution: 'idle', record_sync_state: 'current'});
  expect(first.body.turns[0]).toMatchObject({status: 'completed', usage: {context_used: 12, output: 3, context_window: 8192}, elapsed_ms: 8});
  expect(first.body.turns[0].usage.total_tokens).toBeUndefined();
  const tool = first.body.turns[0].items.find((item: {item_id: string}) => item.item_id === 'tool:write');
  expect(tool.payload).toMatchObject({input: {path: 'report.txt', content}, detail: {content: output}, status: 'completed', duration_ms: 4});
  expect(first.body.other_executions).toContainEqual(expect.objectContaining({session_id: 'child', parent_session_id: 'main', scope: 'subagent'}));
  const childPage = await center.http('GET', '/im/v1/agents/global/work/sessions/child/turns', undefined, center.tokens.alice);
  expect(childPage.body.turns[0]).toMatchObject({status: 'completed', usage: null});
  expect((await read()).body).toEqual(first.body);

  // The retained WS route rejects the same malformed stable fields without committing.
  const invalid = await node.frames.send('agent.work.append', {node_id: node.node, journal_id: inbox.journalId, from_seq: produced + 1,
    events: [{seq: produced + 1, event_id: 'malformed', root_agent_id: 'global', session_id: 'main', turn_id: '1', type: 'tool_end', payload: {presentation: {summary: 7}}}]});
  expect(invalid.type).toBe('error');
  const path = `/im/v1/gateway/work-sync/journals/${inbox.journalId}`;
  expect((await center.http('GET', path, undefined, node.runtime)).body.through_seq).toBe(produced);

  await sync.stop(); await product.stop(); node.socket.terminate();
  center.child.kill('SIGTERM'); await once(center.child, 'exit');
  const restarted = await start(center.dbPath);
  product = makeProduct(false); await product.recover();
  expect(inbox.journalSeq).toBe(produced);
  sync = makeSync(restarted.base); sync.start();
  const small = inbox.journal(0).filter(event => !['tool_start', 'tool_end'].includes(event.type));
  for (const event of small) {
    const duplicate = await restarted.http('POST', `${path}/events`, {from_seq: event.seq, events: [event]}, node.runtime);
    expect(duplicate.status, duplicate.body).toBe(200);
    expect(duplicate.body.through_seq).toBe(produced);
  }
  const restored = await restarted.http('GET', '/im/v1/agents/global/work', undefined, restarted.tokens.alice);
  expect(restored.body.turns).toEqual(first.body.turns);
  expect(restored.body.other_executions).toEqual(first.body.other_executions);
  expect(restored.body.revision).toBe(first.body.revision);
  expect(errors).toEqual([]);
}, 30000);
