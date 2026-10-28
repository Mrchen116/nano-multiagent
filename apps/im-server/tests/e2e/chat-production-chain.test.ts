import { expect, it } from 'vitest';
import { join } from 'node:path';
import { start, bind, cleanups } from './helpers.js';
import { NodeStore } from '../../../../packages/personal-assistant/src/store.js';
import { SingleThread } from '../../../../packages/personal-assistant/src/single-thread.js';
import type { RuntimeEvent, RuntimePort } from '@nano/product-contracts';

it('preserves real SingleThread facts through relay and persistent chat history', async () => {
  const center = await start(), node = await bind(center);
  const created = await center.http('POST', '/im/v1/conversations', {title: 'Production', type: 'direct', participants: [{type: 'agent', id: 'assistant'}]}, center.tokens.alice);
  const cid = created.body.id;
  const sent = await center.http('POST', `/im/v1/conversations/${cid}/messages`, {sender_user_id: 'alice', content: '核对工具结果'}, center.tokens.alice, {'Idempotency-Key': 'production-input'});
  expect(sent.status, sent.body).toBe(201);
  const inbound = await node.frames.next(frame => frame.type === 'relay.message');
  const store = new NodeStore(join(center.dir, 'node.db'), 'alice'); cleanups.push(() => store.close());
  const submitted: Record<string, unknown>[] = [], errors: unknown[] = [];
  let events: RuntimeEvent[] = [];
  const runtime: RuntimePort = {onNotification: () => () => {}, request: async (method, value) => {
    const args = value as Record<string, unknown>;
    if (method === 'session.submit') submitted.push(args);
    if (method === 'session.lookup') return {accepted: submitted.some(input => input.inputId === args.inputId), turn: 1};
    return {durable: true, events, status: 'idle'};
  }};
  const product = new SingleThread({nodeId: node.node, ownerId: 'alice', store, runtime,
    agents: [{agentId: 'assistant', revision: '1', workspace: center.dir, provider: 'fixture', model: 'fixture-model', mode: 'single_thread'}],
    relay: {request: (type, payload) => node.frames.send(type, payload)}, image: async () => '', onError: error => errors.push(error)});
  cleanups.push(() => product.stop());
  await product.receive(inbound.payload);
  expect(submitted[0].content).toContainEqual({type: 'text', text: '核对工具结果'});
  const toolOutput = '中文😀\n"结果"';
  events = [
    {seq: 1, time: 1000, type: 'turn/start', data: {turn: 1}},
    {seq: 2, time: 1001, type: 'tool/call', data: {turn: 1, callId: 'read', name: 'read', arguments: '{"path":"report.txt"}'}},
    {seq: 3, time: 1002, type: 'tool/result', data: {turn: 1, message: {toolCallId: 'read', content: [{type: 'text', text: toolOutput}], isError: false}}},
    {seq: 4, time: 1003, type: 'assistant/message', data: {turn: 1, message: {id: 'answer', content: [{type: 'reasoning', text: '核实原始结果'}, {type: 'text', text: '已经核对。'}]}, usage: {inputTokens: 10, outputTokens: 3, cacheReadTokens: 2}}},
    {seq: 5, time: 1004, type: 'turn/end', data: {turn: 1, reason: {kind: 'completed'}}},
  ];
  await product.recover();
  const read = () => center.http('GET', `/im/v1/conversations/${cid}/messages`, undefined, center.tokens.alice);
  const first = await read();
  expect(first.status, first.body).toBe(200);
  const reply = first.body.items.map((item: {message: {sender_type: string}}) => item.message).find((message: {sender_type: string}) => message.sender_type === 'agent');
  expect(reply).toMatchObject({content: '已经核对。', delivery_status: 'completed', token_usage: {context_used: 12, output: 3}, tool_calls: [{id: 'read', input: {path: 'report.txt'}, status: 'completed', output: toolOutput}]});
  expect(reply.token_usage.total).toBeUndefined();
  await product.recover();
  expect((await read()).body.items).toEqual(first.body.items);
  expect(errors).toEqual([]);
}, 20000);
