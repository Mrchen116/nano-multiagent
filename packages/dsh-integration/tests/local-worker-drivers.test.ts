import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { RuntimeClient } from '../src/client.js';
import { cliEnvironmentRestoration, nativeCliEnvironment } from '../src/local-workers/cli-environment.js';
import { cwd, details, fakeCli, frames, mcp, onEnd, onReport, turnTotals, turnUsages } from './helpers/local-worker-cli.js';

it('restores CLI settings shadowed by DSH and strips runtime-only keys', () => {
  vi.stubEnv('ANTHROPIC_BASE_URL', 'http://native');
  vi.stubEnv('OTHER_MODEL_TOKEN', undefined);
  vi.stubEnv('NANO_PROVIDER_41_KEY', 'router');
  const overrides = { ANTHROPIC_BASE_URL: 'http://router', OTHER_MODEL_TOKEN: 'router-only' };
  for (const [key, value] of Object.entries({ ...cliEnvironmentRestoration(overrides), ...overrides }))
    vi.stubEnv(key, value);
  const env = nativeCliEnvironment();
  expect(env.ANTHROPIC_BASE_URL).toBe('http://native');
  expect(env.OTHER_MODEL_TOKEN).toBeUndefined();
  expect(Object.keys(env).some((key) => key.startsWith('NANO_') || key.startsWith('DSH_'))).toBe(false);
});

it('passes the native CLI settings through the real DSH launch boundary', async () => {
  vi.stubEnv('ANTHROPIC_BASE_URL', 'http://cli.test');
  vi.stubEnv('ROUTER_ONLY_TOKEN', undefined);
  const preload = `import {writeFileSync} from 'node:fs';
    const original = JSON.parse(process.env.NANO_WORKER_ENV_ORIGINALS);
    writeFileSync('observed',JSON.stringify([process.env.ANTHROPIC_BASE_URL, original.ANTHROPIC_BASE_URL, original.ROUTER_ONLY_TOKEN]));
    process.exit(0);`;
  const runtime = new RuntimeClient({
    home: cwd,
    cwd,
    env: {
      NODE_OPTIONS: `--import=data:text/javascript;base64,${Buffer.from(preload).toString('base64')}`,
      ANTHROPIC_BASE_URL: 'http://router.test',
      ROUTER_ONLY_TOKEN: 'temporary',
    },
  });
  expect((await runtime.exited).code).toBe(0);
  expect(JSON.parse(await readFile(join(cwd, 'observed'), 'utf8'))).toEqual([
    'http://router.test',
    'http://cli.test',
    null,
  ]);
});

it('binds Codex review, steering and confirmed interruption to the original thread and turn', async () => {
  const worker = await fakeCli(
    'codex',
    `
    const answer = result => emit({id:m.id, result});
    const notify = (method,p) => emit({method, params:{threadId:'saved',turnId:'turn-1', ...p}});
    if(m.method==='initialize') answer({});
    if(m.method==='thread/resume') answer({thread:{id:'saved'}});
    if(m.method==='turn/start') {
      answer({turn:{id:'turn-1'}});
      emit({id:78,method:'item/commandExecution/requestApproval',params:{threadId:'saved',turnId:'turn-1',itemId:'tool',command:'ls',cwd:'/tmp',reason:'extra access'}});
      notify('item/autoApprovalReview/completed',{reviewId:'audit',review:{status:'denied',rationale:'outside original scope'},action:{type:'networkAccess',host:'local.test'}});
    }
    if(m.method==='turn/steer') answer({turnId:'turn-1'});
    if(m.method==='turn/interrupt') {answer({});setTimeout(()=>notify('turn/completed',{turn:{id:'turn-1',status:'interrupted'}}),30);}
  `,
    'saved',
  );
  await worker.send('Inspect');
  await expect.poll(() => onReport.mock.calls.length).toBe(2);
  await worker.send('Only inspect the listing');
  await worker.stop();
  const wire = await frames();
  const common = wire.find((f) => f.method === 'thread/resume').params;
  expect(common).toMatchObject({
    threadId: 'saved',
    sandbox: 'workspace-write',
    approvalPolicy: 'on-request',
    approvalsReviewer: 'auto_review',
    cwd,
  });
  expect(common.model).toBeUndefined();
  expect(common.modelProvider).toBeUndefined();
  expect(common.config['mcp_servers.nano-parent']).toMatchObject(mcp);
  expect(wire).toContainEqual({ id: 78, result: { decision: 'decline' } });
  expect(wire.find((f) => f.method === 'turn/steer').params).toMatchObject({
    expectedTurnId: 'turn-1',
    threadId: 'saved',
  });
  expect(onReport.mock.calls.map(([, text]) => text).join('\n')).toMatch(
    /extra access[\s\S]*outside original scope/,
  );
  expect(onEnd.mock.calls).toEqual([['turn-1', 'interrupted', 'Codex turn interrupted']]);
  expect(turnTotals()).toEqual([['turn-1', null]]);
  expect(
    details().flatMap(({ fact }) =>
      fact.type === 'message' && fact.payload.role === 'user' ? [fact.payload.text] : [],
    ),
  ).toEqual(['Inspect', 'Only inspect the listing']);
});

it('attributes Codex thread totals to finished turns across resume, repeats and multiple model requests', async () => {
  const worker = await fakeCli(
    'codex',
    `
    const answer = result => emit({id:m.id, result});
    const notify = (method, params) => emit({method, params:{threadId:'original', ...params}});
    const usage = (turnId, total, last) => notify('thread/tokenUsage/updated', {
      turnId, tokenUsage:{total:{totalTokens:total},last:{totalTokens:last}}});
    if(m.method==='initialize') answer({});
    if(m.method==='thread/resume') {
      answer({thread:{id:'original'}});
      usage('previous', 200, 45);
    }
    if(m.method==='turn/start') {
      const id=m.params.input[0].text;
      answer({turn:{id}});
      notify('turn/started', {turn:{id}});
      if(id==='a') {usage(id, 220, 20);usage(id, 220, 20);usage(id, 260, 40);}
      if(id==='b') usage(id, 275, 15);
      const turn={id, status:id==='b'?'failed':'completed'};
      notify('turn/completed',{turn});notify('turn/completed',{turn});
    }
  `,
    'original',
  );
  for (const [index, id] of ['a', 'b', 'c'].entries()) {
    await worker.send(id);
    await expect.poll(() => onEnd.mock.calls.length).toBe(index + 1);
  }
  expect(turnTotals()).toEqual([
    ['a', 60],
    ['b', 15],
    ['c', null],
  ]);
});

it('forwards a Claude control denial, native denial and final answer once while consuming a queued correction', async () => {
  const worker = await fakeCli(
    'claude',
    `
    if(m.type==='control_request') emit({type:'control_response',response:{subtype:'success',request_id:m.request_id,response:{}}});
    if(m.type==='user' && m.message.content==='first') {
      emit({type:'user',isReplay:true,uuid:m.uuid,session_id:'original'});
      emit({type:'control_request',request_id:'q',request:{subtype:'can_use_tool',tool_use_id:'one',tool_name:'Read',input:{file_path:'/work/a'},blocked_path:'/work/a',decision_reason:'outside workspace'}});
    }
    if(m.type==='user' && m.message.content==='amend') {
      const first={type:'result',session_id:'original',uuid:'r1',subtype:'success',result:'partial',num_turns:3,usage:{input_tokens:12,output_tokens:5,cache_read_input_tokens:20,cache_creation_input_tokens:10,cache_creation:{ephemeral_5m_input_tokens:10}},permission_denials:[{tool_use_id:'one',tool_name:'Read',tool_input:{}}]};
      emit(first);emit(first);
      emit({type:'user',isReplay:true,uuid:m.uuid,session_id:'original'});
      emit({type:'result',session_id:'original',uuid:'r2',subtype:'success',result:'done',num_turns:2,usage:{input_tokens:7,output_tokens:4},modelUsage:{mock:{inputTokens:38,outputTokens:17}},permission_denials:[{tool_use_id:'two',tool_name:'Write',tool_input:{path:'file',content:'private body'}}]});
    }
  `,
    'original',
  );
  await worker.send('first');
  await expect.poll(() => onReport.mock.calls.length).toBe(1);
  await worker.send('amend');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(onEnd.mock.calls).toEqual([['r2', 'completed', 'done']]);
  const inputs = (await frames()).filter((f) => f.type === 'user');
  expect(turnTotals()).toEqual([
    [inputs[0].uuid, 47],
    [inputs[1].uuid, 11],
  ]);
  expect(
    details().flatMap(({ turnId, fact }) =>
      fact.type === 'message' && fact.payload.role === 'user' ? [[turnId, fact.payload.text]] : [],
    ),
  ).toEqual([
    [inputs[0].uuid, 'first'],
    [inputs[1].uuid, 'amend'],
  ]);
  expect(onReport.mock.calls.map(([id]) => id)).toEqual(['request:one', 'r1', 'request:two']);
  expect(onReport.mock.calls.at(-1)?.[1]).toContain('file');
  expect(onReport.mock.calls.at(-1)?.[1]).not.toContain('private body');
  const wire = await frames();
  expect(wire.some((f) => f.request?.subtype === 'set_permission_mode' && f.request.mode === 'auto')).toBe(
    true,
  );
  expect(wire.find((f) => f.type === 'control_response')).toMatchObject({
    response: { request_id: 'q', subtype: 'success', response: { behavior: 'deny' } },
  });
  expect(wire.filter((f) => f.type === 'user').map((f) => f.session_id)).toEqual(['original', 'original']);
  const args: string[] = JSON.parse(await readFile(join(cwd, 'args'), 'utf8'));
  expect(args[args.indexOf('--resume') + 1]).toBe('original');
  expect(args[args.indexOf('--permission-mode') + 1]).toBe('auto');
  expect(args).not.toContain('--model');
  expect(args).not.toContain('--strict-mcp-config');
});

it('confirms exit after Claude acknowledges interruption and blocks queued input', async () => {
  const worker = await fakeCli(
    'claude',
    `
    if(m.type==='control_request') emit({type:'control_response',response:{subtype:'success',request_id:m.request_id}});
  `,
  );
  await worker.send('work');
  await worker.stop();
  expect((await frames()).at(-1).request.subtype).toBe('interrupt');
  expect(onEnd.mock.calls).toHaveLength(1);
  expect(onEnd.mock.calls[0]?.[1]).toBe('interrupted');
  expect(turnTotals()).toEqual([[(await frames()).find((f) => f.type === 'user').uuid, null]]);
  await expect(worker.send('late')).rejects.toThrow(/exited|closing/);
});

it('surfaces a native resume error without opening a replacement session', async () => {
  await expect(
    fakeCli(
      'codex',
      `
    if(m.method==='initialize') emit({id:m.id,result:{}});
    if(m.method==='thread/resume') emit({id:m.id,error:{message:'Original thread missing'}});
  `,
      'original',
    ),
  ).rejects.toThrow('Original thread missing');
  expect((await frames()).map((f) => f.method)).toEqual(['initialize', 'initialized', 'thread/resume']);
});

it('projects live Codex commands, complete output and MCP failure before the final turn receipt', async () => {
  const worker = await fakeCli(
    'codex',
    `
    const answer = result => emit({id:m.id, result});
    const notify = (method, params) => emit({method, params:{threadId:'thread',turnId:'t', ...params}});
    const cmd={type:'commandExecution',id:'c',command:'cat report.txt',cwd:'/work',status:'inProgress'};
    if(m.method==='initialize') answer({});
    if(m.method==='thread/start') answer({thread:{id:'thread'},model:'actual-model'});
    if(m.method==='turn/start') {
      notify('turn/started',{turn:{id:'t'}});
      answer({turn:{id:'t'}});
      notify('item/started',{item:cmd});
    }
    if(m.method==='turn/steer') {
      answer({turnId:'t'});
      const done={...cmd,status:'completed',aggregatedOutput:'first line\\nlast line',exitCode:0,durationMs:71};
      const mcp={type:'mcpToolCall',id:'m',server:'test',tool:'inspect',arguments:{path:'file'},status:'failed',error:{message:'denied'}};
      notify('item/completed',{item:done});
      notify('item/started',{item:mcp});
      notify('item/completed',{item:mcp});
      const msg={type:'agentMessage',id:'msg',phase:'final_answer',text:'answer'};
      notify('item/completed',{item:msg});
      notify('turn/completed',{turn:{id:'t',status:'completed',items:[done,mcp,msg]}});
    }
  `,
  );
  await worker.send('Inspect file');
  await expect
    .poll(() => details().map((d) => d.fact.type))
    .toEqual(['turn_started', 'message', 'tool_start']);
  expect(details()[2]?.fact.payload).toMatchObject({
    call_id: 'c',
    tool_name: 'commandExecution',
    arguments: { command: 'cat report.txt', cwd: '/work' },
  });
  await worker.send('Check both lines');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(details().map((d) => d.fact.type)).toEqual([
    'turn_started',
    'message',
    'tool_start',
    'message',
    'tool_end',
    'tool_start',
    'tool_end',
    'message',
    'turn_end',
  ]);
  expect(details()[4]?.fact.payload).toMatchObject({
    call_id: 'c',
    duration_ms: 71,
    is_error: false,
    presentation: { detail: { content: { output: 'first line\nlast line', exitCode: 0 } } },
  });
  expect(details()[5]?.fact.payload).toMatchObject({
    call_id: 'm',
    tool_name: 'test.inspect',
    arguments: { path: 'file' },
  });
  expect(details()[6]?.fact.payload).toMatchObject({
    is_error: true,
    presentation: { detail: { content: { message: 'denied' } } },
  });
  expect(details()[7]?.fact.payload).toMatchObject({ role: 'assistant', text: 'answer' });
  expect(details().every((d) => d.turnId === 't')).toBe(true);
});

it('pairs Claude tool_use and tool_result by id, records complete text and closes on process failure', async () => {
  const worker = await fakeCli(
    'claude',
    `
    if(m.type==='control_request') emit({type:'control_response',response:{subtype:'success',request_id:m.request_id}});
    if(m.type==='user' && m.message.content==='go') {
      emit({type:'user',isReplay:true,uuid:m.uuid});
      emit({type:'assistant',uuid:'a',message:{content:[
        {type:'text',text:'Checking'}, {type:'thinking',thinking:'private'},
        {type:'tool_use',id:'call',name:'Read',input:{file_path:'notes.txt'}}]}});
    }
    if(m.type==='user' && m.message.content==='amend') {
      emit({type:'user',isReplay:true,uuid:m.uuid});
      emit({type:'user',message:{content:[{type:'tool_result',tool_use_id:'call',content:'no such file',is_error:true}]}});
      emit({type:'assistant',parent_tool_use_id:'child',uuid:'nested',message:{content:[{type:'text',text:'nested message'}]}});
      emit({type:'assistant',uuid:'b',message:{content:[{type:'tool_use',id:'pending',name:'Bash',input:{command:'pwd'}}]}});
      process.exitCode=1;process.stdin.destroy();
    }
  `,
  );
  await worker.send('go');
  await expect
    .poll(() => details().map((d) => d.fact.type))
    .toEqual(['turn_started', 'message', 'message', 'tool_start']);
  expect(details()[3]?.fact.payload).toMatchObject({
    call_id: 'call',
    tool_name: 'Read',
    arguments: { file_path: 'notes.txt' },
  });
  await worker.send('amend');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(details()[4]?.fact.payload).toMatchObject({ role: 'user', text: 'amend' });
  expect(details()[5]?.fact.payload).toMatchObject({
    call_id: 'call',
    tool_name: 'Read',
    is_error: true,
    presentation: { detail: { content: 'no such file' } },
  });
  expect(details().at(-2)?.fact.payload).toMatchObject({
    call_id: 'pending',
    is_error: true,
    reason_code: 'failed',
  });
  expect(details().at(-1)?.fact.payload).toMatchObject({
    status: 'failed',
    error: {message:expect.stringMatching(/exited/)},
  });
  expect(new Set(details().map((d) => d.turnId)).size).toBe(1);
  expect(JSON.stringify(details())).not.toMatch(/private|nested message/);
});


it('drives Antigravity ACP auto mode, parent MCP whitelist, cached permission denials, steering, context usage and TMPDIR cleanup', async () => {
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
        emit({jsonrpc:'2.0',id:11,method:'session/request_permission',params:{
          sessionId:'agy-s1',
          toolCall:{toolCallId:'parent-msg',title:'Run mcp_nano-parent_send_message?',kind:'other',rawInput:{message:'need context'}},
          options:[{optionId:'allow-1',kind:'allow_once',name:'Allow once'},{optionId:'deny-1',kind:'reject_once',name:'Deny'}],
        }});
        update({sessionUpdate:'tool_call',toolCallId:'edit-1',title:'Run edit_file?',kind:'edit'});
        update({sessionUpdate:'tool_call_update',toolCallId:'edit-1',rawInput:{Path:'/etc/hosts',Content:'secret-body',toolSummary:'Edit hosts'}});
        emit({jsonrpc:'2.0',id:12,method:'session/request_permission',params:{
          sessionId:'agy-s1',
          toolCall:{toolCallId:'edit-1'},
          options:[{optionId:'allow-2',kind:'allow_once',name:'Allow once'},{optionId:'deny-2',kind:'reject_once',name:'Deny'}],
        }});
        emit({jsonrpc:'2.0',id:13,method:'session/request_permission',params:{
          sessionId:'agy-s1',
          toolCall:{toolCallId:'interaction_1',title:'Pick target branch'},
          options:[{optionId:'opt-a',kind:'allow_once',name:'develop'},{optionId:'opt-b',kind:'reject_once',name:'main'}],
        }});
        update({sessionUpdate:'usage_update',used:4000,size:100000});
      } else if(text==='steer correction') {
        answer(globalThis.firstPrompt, {stopReason:'end_turn', usage:{inputTokens:100, cachedReadTokens:50, outputTokens:20}});
        update({sessionUpdate:'tool_call_update',toolCallId:'edit-1',status:'failed',content:[
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
  expect(wire).toContainEqual({ jsonrpc: '2.0', id: 11, result: { outcome: { outcome: 'selected', optionId: 'allow-1' } } });
  expect(wire).toContainEqual({ jsonrpc: '2.0', id: 12, result: { outcome: { outcome: 'selected', optionId: 'deny-2' } } });
  expect(wire).toContainEqual({ jsonrpc: '2.0', id: 13, result: { outcome: { outcome: 'cancelled' } } });

  const reports = onReport.mock.calls.map(([, text]) => text).join('\n');
  expect(reports).toContain('/etc/hosts');
  expect(reports).not.toContain('secret-body');
  expect(reports).toContain('Pick target branch');
  expect(reports).toContain('develop');

  const toolEnd = details().find((d) => d.fact.type === 'tool_end');
  expect(toolEnd?.fact.payload).toMatchObject({
    call_id: 'edit-1',
    tool_name: 'edit_file',
    is_error: true,
    arguments: { Path: '/etc/hosts', Content: 'secret-body', toolSummary: 'Edit hosts' },
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
