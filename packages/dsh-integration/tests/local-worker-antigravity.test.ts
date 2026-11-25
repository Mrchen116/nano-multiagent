import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { cwd, details, fakeCli, frames, mcp, onEnd, onReport, turnUsages } from './helpers/local-worker-cli.js';

it('drives Antigravity ACP auto mode, parent MCP whitelist, file-title permission denials, steering, context usage and TMPDIR cleanup', async () => {
  vi.stubEnv('SSH_CONNECTION', '10.0.0.1 22 10.0.0.2 22');
  vi.stubEnv('SSH_TTY', '/dev/pts/1');
  vi.stubEnv('BROWSER', '/usr/bin/open');
  const worker = await fakeCli(
    'antigravity',
    `
    const answer = (id, result) => emit({jsonrpc:'2.0', id, result});
    const update = upd => emit({jsonrpc:'2.0', method:'session/update', params:{sessionId:'agy-s1', update:upd}});
    if(m.method==='initialize') answer(m.id, {
      protocolVersion:1,
      agentCapabilities:{sessionCapabilities:{resume:{}}, _meta:{antigravity:{systemPrompt:{append:true}}}},
    });
    if(m.method==='session/new') answer(m.id, {
      sessionId:'agy-s1',
      modes:{currentModeId:'default', availableModes:[{id:'default'},{id:'auto'}]},
      configOptions:[{id:'model',category:'model',currentValue:'gemini-4-neon'}],
    });
    if(m.method==='session/set_mode') answer(m.id, {});
    if(m.method==='session/prompt') {
      const text=m.params.prompt[0].text;
      if(text==='first') {
        globalThis.firstPrompt = m.id;
        emit({jsonrpc:'2.0',id:'perm:1',method:'session/request_permission',params:{
          sessionId:'agy-s1',
          toolCall:{toolCallId:'parent-msg',name:'mcp_nano-parent_send_message',title:'Run mcp_nano-parent_send_message',kind:'other',rawInput:{message:'need context'}},
          options:[{optionId:'allow-1',kind:'allow_once',name:'Allow once'},{optionId:'deny-1',kind:'reject_once',name:'Deny'}],
        }});
        update({sessionUpdate:'tool_call',toolCallId:'write-1',name:'write_file',title:'File ../hosts',kind:'edit',locations:[{path:'/etc/hosts'}]});
        update({sessionUpdate:'tool_call_update',toolCallId:'write-1',rawInput:{Path:'/etc/hosts',Content:'secret-body',toolSummary:'Write hosts'}});
        emit({jsonrpc:'2.0',id:'perm:2',method:'session/request_permission',params:{
          sessionId:'agy-s1',
          toolCall:{toolCallId:'write-1',title:'File ../hosts',kind:'edit',locations:[{path:'/etc/hosts'}]},
          options:[{optionId:'allow-2',kind:'allow_once',name:'Allow once'},{optionId:'deny-2',kind:'reject_once',name:'Deny'}],
        }});
        emit({jsonrpc:'2.0',id:'perm:3',method:'session/request_permission',params:{
          sessionId:'agy-s1',
          toolCall:{toolCallId:'interaction_1',title:'Pick target branch'},
          options:[{optionId:'opt-a',kind:'allow_once',name:'develop'},{optionId:'opt-b',kind:'reject_once',name:'main'}],
        }});
        update({sessionUpdate:'usage_update',used:4000,size:100000});
      } else if(text==='steer correction') {
        answer(globalThis.firstPrompt, {stopReason:'end_turn', usage:{inputTokens:100, cachedReadTokens:50, outputTokens:20}});
        update({sessionUpdate:'tool_call_update',toolCallId:'write-1',status:'failed',content:[
          {type:'content',content:{type:'image',data:'AAAA',mimeType:'image/png'}},
          {type:'content',content:{type:'text',text:'denied by host'}},
        ]});
        update({sessionUpdate:'tool_call',toolCallId:'ask-1',name:'ask_question',status:'pending',rawInput:{questions:[{question:'Confirm target branch?',options:['develop','main']}]}});
        update({sessionUpdate:'agent_message_chunk',content:{type:'text',text:'steered '}});
        update({sessionUpdate:'agent_message_chunk',content:{type:'text',text:'final answer'}});
        update({sessionUpdate:'usage_update',used:4500,size:100000});
        answer(m.id, {stopReason:'end_turn', usage:{inputTokens:120, cachedReadTokens:80, outputTokens:30}});
      } else if(text==='quota turn') {
        update({sessionUpdate:'config_option_update',configOptions:[{id:'model',currentValue:'gemini-4-carbon'}]});
        update({sessionUpdate:'tool_call_update',toolCallId:'ask-1',name:'ask_question',status:'completed'});
        answer(m.id, {stopReason:'refusal'});
      }
    }
    `,
  );
  expect(worker.sessionId).toBe('agy-s1');
  const spawnedEnv = JSON.parse(await readFile(join(cwd, 'env'), 'utf8')) as Record<string, string>;
  expect(spawnedEnv.SSH_CONNECTION).toBeUndefined();
  expect(spawnedEnv.SSH_TTY).toBeUndefined();
  expect(spawnedEnv.BROWSER).toBeUndefined();
  expect(spawnedEnv.AGY_CLI_DISABLE_AUTO_UPDATE).toBe('true');
  const runtimeTmp = spawnedEnv.TMPDIR ?? spawnedEnv.TEMP;
  expect(runtimeTmp).toBeTruthy();
  expect(existsSync(runtimeTmp!)).toBe(true);

  await worker.send('first');
  await expect.poll(() => onReport.mock.calls.length).toBe(2);
  expect(onEnd.mock.calls).toHaveLength(0);
  await worker.send('steer correction');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(onEnd.mock.calls[0]).toEqual([expect.any(String), 'completed', 'steered final answer']);

  const wire = await frames();
  expect(wire.find((f) => f.method === 'session/new').params).toMatchObject({
    cwd,
    mcpServers: [{ name: 'nano-parent', command: mcp.command, args: mcp.args, env: [] }],
    _meta: { antigravity: { systemPrompt: { append: 'Help the parent' } } },
  });
  expect(wire).toContainEqual({ jsonrpc: '2.0', id: 'perm:1', result: { outcome: { outcome: 'selected', optionId: 'allow-1' } } });
  expect(wire).toContainEqual({ jsonrpc: '2.0', id: 'perm:2', result: { outcome: { outcome: 'selected', optionId: 'deny-2' } } });
  expect(wire).toContainEqual({ jsonrpc: '2.0', id: 'perm:3', result: { outcome: { outcome: 'cancelled' } } });

  const deniedReport = onReport.mock.calls[0]?.[1] ?? '';
  expect(deniedReport).toContain('Antigravity declined write_file.');
  expect(deniedReport).toContain('"kind":"edit"');
  expect(deniedReport).toContain('/etc/hosts');
  expect(deniedReport).not.toContain('secret-body');
  expect(deniedReport).not.toContain('"locations"');
  const questionReport = onReport.mock.calls[1]?.[1] ?? '';
  expect(questionReport).toContain('Pick target branch');
  expect(questionReport).toContain('develop');

  const toolEnd = details().find((d) => d.fact.type === 'tool_end');
  expect(toolEnd?.fact.payload).toMatchObject({
    call_id: 'write-1',
    tool_name: 'write_file',
    is_error: true,
    arguments: { Path: '/etc/hosts', Content: 'secret-body', toolSummary: 'Write hosts' },
  });
  expect(JSON.stringify(toolEnd?.fact.payload.presentation)).not.toContain('AAAA');
  expect(JSON.stringify(toolEnd?.fact.payload.presentation)).toContain('denied by host');

  expect(turnUsages()[0]?.[1]).toEqual({
    context_used: 4500,
    context_window: 100000,
    output: 50,
    cache_read_tokens: 130,
    cache_total_input_tokens: 350,
    total_tokens: 400,
  });

  await worker.send('quota turn');
  await expect.poll(() => onEnd.mock.calls.length).toBe(2);
  expect(onEnd.mock.calls[1]?.[1]).toBe('failed');
  expect(turnUsages()[1]?.[1]).toBeUndefined();
  const askEnds = details().filter((d) => d.fact.type === 'tool_end' && d.fact.payload.call_id === 'ask-1');
  expect(askEnds).toHaveLength(1);
  expect(askEnds[0]?.fact.payload).toMatchObject({
    call_id: 'ask-1',
    tool_name: 'ask_question',
    is_error: false,
    presentation: { summary: 'Confirm target branch?' },
  });
  expect(details().at(-1)?.fact).toMatchObject({ type: 'turn_end', payload: { status: 'failed', model: 'gemini-4-carbon' } });

  await worker.close();
  expect(existsSync(runtimeTmp!)).toBe(false);
});

it('omits partial token usage when a steered prompt is cancelled and settles out-of-order steer failures without hanging', async () => {
  const worker = await fakeCli(
    'antigravity',
    `
    const answer = (id, result) => emit({jsonrpc:'2.0', id, result});
    const reject = (id, message) => emit({jsonrpc:'2.0', id, error:{code:-32603, message}});
    const update = upd => emit({jsonrpc:'2.0', method:'session/update', params:{sessionId:'agy-steer', update:upd}});
    if(m.method==='initialize') answer(m.id, {protocolVersion:1, agentCapabilities:{}});
    if(m.method==='session/new') answer(m.id, {
      sessionId:'agy-steer',
      modes:{currentModeId:'default', availableModes:[{id:'default'},{id:'auto'}]},
    });
    if(m.method==='session/set_mode') answer(m.id, {});
    if(m.method==='session/prompt') {
      const text=m.params.prompt[0].text;
      if(text.includes('turn1-first')) {
        globalThis.p1 = m.id;
        update({sessionUpdate:'usage_update',used:3200,size:100000});
      } else if(text==='turn1-steer') {
        globalThis.p2 = m.id;
        answer(globalThis.p1, {stopReason:'end_turn', usage:{inputTokens:80, cachedReadTokens:20, outputTokens:15}});
      } else if(text==='turn2-first') {
        globalThis.q1 = m.id;
      } else if(text==='turn2-steer-fail-first') {
        reject(m.id, 'Steer prompt rejected immediately');
        setTimeout(() => answer(globalThis.q1, {stopReason:'end_turn', usage:{inputTokens:40, outputTokens:10}}), 30);
      }
    }
    if(m.method==='session/cancel' && globalThis.p2) {
      answer(globalThis.p2, {stopReason:'cancelled'});
      globalThis.p2 = undefined;
    }
    `,
  );

  await worker.send('turn1-first');
  await worker.send('turn1-steer');
  await worker.stop();
  expect(onEnd.mock.calls[0]?.[1]).toBe('interrupted');
  // Partial tokens from p1 must not be emitted as complete turn totals when p2 settled without usage.
  expect(turnUsages()[0]?.[1]).toEqual({ context_used: 3200, context_window: 100000 });

  await worker.send('turn2-first');
  await worker.send('turn2-steer-fail-first');
  await expect.poll(() => onEnd.mock.calls.length).toBe(2);
  expect(onEnd.mock.calls[1]).toEqual([expect.any(String), 'failed', 'Steer prompt rejected immediately']);
  expect(turnUsages()[1]?.[1]).toBeUndefined();
});

it('rejects Antigravity startup when signed out or missing auto mode and cleans up TMPDIR', async () => {
  await expect(
    fakeCli(
      'antigravity',
      `
      if(m.method==='initialize') console.log('Open the following link to authenticate the ACP server: https://accounts.google.com/o/oauth2/v2/auth');
      `,
    ),
  ).rejects.toThrow(/not signed in|authenticate/i);
  const firstEnv = JSON.parse(await readFile(join(cwd, 'env'), 'utf8')) as Record<string, string>;
  expect(existsSync((firstEnv.TMPDIR ?? firstEnv.TEMP)!)).toBe(false);

  await expect(
    fakeCli(
      'antigravity',
      `
      const answer = (id, result) => emit({jsonrpc:'2.0', id, result});
      if(m.method==='initialize') answer(m.id, {protocolVersion:1, agentCapabilities:{}});
      if(m.method==='session/new') answer(m.id, {sessionId:'no-auto', modes:{currentModeId:'default', availableModes:[{id:'default'}]}} );
      `,
    ),
  ).rejects.toThrow(/auto/i);
  const secondEnv = JSON.parse(await readFile(join(cwd, 'env'), 'utf8')) as Record<string, string>;
  expect(existsSync((secondEnv.TMPDIR ?? secondEnv.TEMP)!)).toBe(false);
});
