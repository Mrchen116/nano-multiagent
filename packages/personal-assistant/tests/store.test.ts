import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { tokenUsage, toolPresentation } from '../src/presentation.js';
import { projectWorkEvent } from '../src/work-projection.js';

it('recovers input attribution and confirmed delivery without creating a second send', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-node-store-'));
  const path = join(directory, 'node.sqlite3');
  const binding = { sessionId: 's1', conversationId: 'c1', agentId: 'a1', ownerId: 'o1', cwd: directory, revision: '1' };
  const input = { relay_task_id: 'r1', agent_id: 'a1', conversation_id: 'c1', idempotency_key: 'upstream1', metadata: {}, message: {
    id: 'm1', content: 'hello', sender_user_id: 'o1', sender_type: 'user', attachments: [],
  } };
  let store = new NodeStore(path, 'o1');
  try {
    store.bind(binding);
    const inputId = store.receive('s1', input);
    store.inputEvidence(inputId, { accepted: true, turn: 1, terminal: { kind: 'completed' } });
    const send = store.prepareDelivery('s1', 1);
    store.updateDelivery(send.operationId, 'confirmed', 'im-result', 'hello back');
    store.close();
    store = new NodeStore(path, 'o1');
    expect(store.receive('s1', input)).toBe(inputId);
    expect(store.inputs('s1')).toHaveLength(1);
    expect(store.inputForTurn('s1', 1)?.id).toBe(inputId);
    expect(store.prepareDelivery('s1', 1)).toMatchObject({ operationId: send.operationId, state: 'confirmed', messageId: 'im-result' });
    expect(() => new NodeStore(path, 'another-owner')).toThrow('different owner');
  } finally { store.close(); await rm(directory, { recursive: true, force: true }); }
});

it('adds cache buckets to uncached input once and keeps unknown cache fields absent', () => {
  const event = (seq: number, type: string, data: Record<string, unknown>) => ({ seq, type, time: seq, data });
  expect(tokenUsage([
    event(0, 'request/context', { contextWindow: 1000 }),
    event(1, 'assistant/message', { turn: 1, usage: { inputTokens: 10, cacheReadTokens: 20, cacheWriteTokens: 5, outputTokens: 3, totalTokens: 38 } }),
    event(2, 'request/context', { contextWindow: 2000 }),
  ], 1)).toEqual({ context_used: 35, output: 3, total: 38, cache_read_tokens: 20, cache_total_input_tokens: 35, context_window: 1000 });
  expect(tokenUsage([event(0, 'assistant/message', { turn: 2, usage: { inputTokens: 10, outputTokens: 3 } })], 2)).toEqual({ context_used: 10, output: 3 });
});

it('projects native schedule admission with its original message identity across replay', () => {
  const store = new NodeStore(':memory:', 'o');
  store.bind({ sessionId: 's', conversationId: 'chat', agentId: 'a', ownerId: 'o', cwd: '/tmp', revision: '1' });
  const message = { id: 'native-schedule-id', content: [{ type: 'text', text: 'reminder' }], source: { kind: 'schedule' } };
  const events = [{ seq: 1, time: 1, type: 'agent/inbox/spliced', data: { inserted: [message] } }];
  try {
    store.recordEvents('s', events); store.recordEvents('s', events);
    expect(store.inputs('s')).toHaveLength(1);
    expect(store.inputs('s')[0]).toMatchObject({ id: message.id, accepted: true,
      input: { conversation_id: 'chat', metadata: { runtime_input_id: message.id, origin: 'schedule' } } });
  } finally { store.close(); }
});

it.each(['List available commands', ''])('keeps Bash descriptions and command output in separate presentation fields (%s)', description => {
  const command = 'pwd; compgen -c | sort -u | head -100';
  const output = '/workspace\n' + 'available-command\n'.repeat(100);
  const call = {seq: 1, time: 1, type: 'tool/call', data: {callId: 'bash', name: 'bash', arguments: JSON.stringify({description, command})}};
  const native = {card: 'terminal', output, exitCode: 0};
  const result = {seq: 2, time: 2, type: 'tool/result', data: {
    message: {toolCallId: 'bash', content: [{type: 'text', text: output}], isError: false},
    nanoToolView: {call: {card: 'terminal', title: command, description}, result: native},
  }};
  expect(toolPresentation(call, [call])?.output).toBe(description || command);
  expect(toolPresentation(result, [call, result])).toMatchObject({output: description || command, detail: {content: output, native_view: native}});
});

it.each([
  ['read', {file_path: 'report.md'}, 'Read report.md', {card: 'read', path: 'report.md'}],
  ['write', {file_path: 'report.md'}, 'Write report.md', {card: 'diff', diffs: []}],
  ['edit', {file_path: 'report.md'}, 'Edit report.md', {card: 'diff', diffs: []}],
  ['grep', {pattern: 'report'}, 'Search report', {card: 'search', shape: 'matches', matches: [], total: 0}],
  ['web_fetch', {url: 'https://example.com'}, 'Fetch example.com', {card: 'web', kind: 'fetch', url: 'https://example.com', statusCode: 200}],
  ['subagent', {description: 'Research topic'}, 'Research topic', {card: 'generic'}],
  ['custom', {}, 'Owner tool summary', {card: 'generic'}],
] as const)('preserves %s presenter summaries separately from full detail', (name, input, title, native) => {
  const output = 'FULL_RESULT\n'.repeat(100);
  const call = {seq: 1, time: 1, type: 'tool/call', data: {callId: 'c', name, arguments: JSON.stringify(input), nanoToolView: {call: {card: 'generic', title}}}};
  const result = {seq: 2, time: 2, type: 'tool/result', data: {message: {toolCallId: 'c', content: [{type: 'text', text: output}]}, nanoToolView: {call: {card: 'generic', title}, result: native}}};
  expect(toolPresentation(call, [call])?.output).toBe(title);
  expect(toolPresentation(result, [call, result])).toMatchObject({output: title, detail: {content: output, native_view: native}});
});

it('bounds presenter-less summaries without losing their complete output', () => {
  const output = 'Custom tool output\n'.repeat(100);
  const call = {seq: 1, time: 1, type: 'tool/call', data: {callId: 'c', name: 'custom', arguments: '{}'}};
  const result = {seq: 2, time: 2, type: 'tool/result', data: {message: {toolCallId: 'c', content: [{type: 'text', text: output}]}}};
  expect(toolPresentation(result, [call, result])?.output).toHaveLength(80);
  expect(toolPresentation(result, [call, result])?.detail).toMatchObject({content: output});
});


it('retains cumulative cache hit counts and denominator in Work turn usage', () => {
  const events = [
    {seq:1,time:1,type:'assistant/message',data:{turn:1,usage:{inputTokens:10,cacheReadTokens:20,outputTokens:3}}},
    {seq:2,time:2,type:'assistant/message',data:{turn:1,usage:{inputTokens:5,cacheReadTokens:15,outputTokens:2}}},
    {seq:3,time:3,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}},
  ];
  expect(projectWorkEvent('main',events[2]!,events)?.payload.usage).toMatchObject({context_used:20,output:5,cache_read_tokens:35,cache_total_input_tokens:50});
});


it('maps native reasoning, model carry-forward, child messages and terminal duration', () => {
  const events = [
    {seq:1,time:1,type:'request/header',data:{header:{config:{model:'provider:model'}}}},
    {seq:2,time:10,type:'turn/start',data:{turn:2}},
    {seq:3,time:11,type:'user/message',data:{id:'child-return',source:{kind:'subagent-settled',senderSessionId:'child'},content:[{type:'text',text:'Child result'}]}},
    {seq:4,time:12,type:'assistant/message',data:{turn:2,message:{id:'answer',content:[{type:'reasoning',text:'Visible reasoning'},{type:'text',text:'Answer'}]}}},
    {seq:5,time:50,type:'turn/end',data:{turn:2,reason:{kind:'error',error:{code:'AUTH',message:'Rejected'}}}},
  ];
  expect(projectWorkEvent('main',events[1]!,events)?.payload).toMatchObject({model:'provider:model',trigger:{kind:'background_task'}});
  expect(projectWorkEvent('main',events[2]!,events)).toMatchObject({turn:2,payload:{text:'Child result',source_session_id:'child',role:'system'}});
  expect(projectWorkEvent('main',events[3]!,events)?.payload).toMatchObject({text:'Answer',reasoning_content:'Visible reasoning'});
  expect(projectWorkEvent('main',events[4]!,events)?.payload).toMatchObject({status:'failed',elapsed_ms:40,error:{code:'AUTH'}});
});
it('preserves pending native arguments and classifies native tool cancellation', () => {
  const call={seq:1,time:10,type:'tool/call',data:{callId:'c',name:'bash',arguments:'{"command":"pwd"}',nanoToolView:{call:{card:'terminal',title:'pwd',cwd:'/workspace'}}}};
  const result={seq:2,time:20,type:'tool/result',data:{error:{name:'AbortError',code:'ABORTED_BEFORE_DISPATCH'},message:{toolCallId:'c',isError:true,content:[{type:'text',text:'Cancelled'}]}}};
  expect(toolPresentation(call,[call])?.detail).toMatchObject({native_call:{title:'pwd',cwd:'/workspace'}});
  expect(toolPresentation(result,[call,result])).toMatchObject({reason:'interrupted',duration_ms:10,detail:{error:{code:'ABORTED_BEFORE_DISPATCH'}}});
});
it('distinguishes pi-ai zero cache counters from absent provider accounting', () => {
  const answers=[{seq:1,time:1,type:'assistant/message',data:{turn:1,usage:{inputTokens:10,outputTokens:2},stream:[{type:'chunk',chunk:{type:'finish',replayState:{response:{kind:'pi-ai'}}}}]}}];
  expect(tokenUsage(answers,1)).toMatchObject({cache_read_tokens:0,cache_total_input_tokens:10});
  expect(tokenUsage([{...answers[0]!,data:{...answers[0]!.data,stream:[]}}],1)).not.toHaveProperty('cache_read_tokens');
});
