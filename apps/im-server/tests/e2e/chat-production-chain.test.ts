import { expect, it } from 'vitest';
import { join } from 'node:path';
import { start, bind, cleanups } from './helpers.js';
import { NodeStore } from '../../../../packages/personal-assistant/src/store.js';
import { InboxStore } from '../../../../packages/personal-assistant/src/inbox.js';
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
  const followup=await center.http('POST',`/im/v1/conversations/${cid}/messages`,{sender_user_id:'alice',content:'展开这个',reply_to_message_id:reply.id},center.tokens.alice,{'Idempotency-Key':'quoted-followup'});
  expect(followup.status,followup.body).toBe(201);
  const quotedInput=await node.frames.next(frame=>frame.type==='relay.message'&&frame.payload.message.id===followup.body.id);
  await product.receive(quotedInput.payload);
  const delivered = submitted.at(-1)!.content;
  expect(delivered).toEqual(expect.arrayContaining([
    { type: 'text', text: expect.stringContaining(`IM message ID ${reply.id}:\n> 已经核对。`) },
    { type: 'text', text: '展开这个' },
  ]));
  expect(JSON.stringify(delivered)).not.toContain('is_stale');

  const shortCard = 'root = Title("周六值班：木槿")';
  const row = `Text("${'值班登记待复核。'.repeat(18)}"),`;
  const longCard = `root = Col([${row.repeat(12)}Title("最终代号：玉兰")])`;
  const cases = [
    { key: 'short-card', source: shortCard, quotedSource: shortCard },
    { key: 'long-card', source: longCard, quotedSource: longCard.slice(0, 1200) + '\n\n[Rest of original message omitted.]' },
  ];
  const inbox = new InboxStore(':memory:'); cleanups.push(() => inbox.close());
  for (const {key, source, quotedSource} of cases) {
    const card = await node.frames.send('agent.message', {node_id:node.node,to:`conversation:${cid}`,text:'',
      from_session_id:`assistant|tool_call:${key}`,interactive:{format:'openui',catalog_version:'nano-iui-1',source}});
    const messageId = card.payload.message_id;
    expect(messageId).toEqual(expect.any(String));
    const cardReply = await center.http('POST', `/im/v1/conversations/${cid}/messages`, {
      sender_user_id: 'alice', content: '这张卡片里的代号是什么？', reply_to_message_id: messageId,
    }, center.tokens.alice);
    expect(cardReply.status, cardReply.body).toBe(201);
    const cardInput = await node.frames.next(frame => frame.type === 'relay.message' && frame.payload.message.id === cardReply.body.id);
    inbox.receive(cardInput.payload, true);
    const page = inbox.read('assistant', 'inbox-session', key, {target:cid});
    const quote = page.messages.find((message: {id:string}) => message.id === cardReply.body.id)!;
    expect(quote.reply_to).toEqual({message_id:messageId,
      sender:{name:cardReply.body.reply_to.sender.display_name,type:'agent'},interactive:{source:quotedSource}});
    expect(quote.content).toEqual([{type:'text',text:'这张卡片里的代号是什么？'}]);
    await product.receive(cardInput.payload);
    expect(submitted.at(-1)!.content).toEqual(expect.arrayContaining([
      {type:'text',text:expect.stringContaining(`[Interactive UI content from the quoted message]\n${JSON.stringify({source:quotedSource})}`)},
      {type:'text',text:'这张卡片里的代号是什么？'},
    ]));
    if (quotedSource !== source) {
      expect(JSON.stringify(submitted.at(-1)!.content)).toContain(`message_id=${messageId}`);
      const history = await node.frames.send('conversation.query', {
        node_id:node.node,agent_id:'assistant',session_id:'history',request_id:key,action:'read',target:cid,message_id:messageId,
      });
      expect(history.payload).toMatchObject({ok:true,result:{messages:[{message_id:messageId,interactive:{source},content:[]}]}});
    }
  }
  expect(errors).toEqual([]);
}, 20000);
