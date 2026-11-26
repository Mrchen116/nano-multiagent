import { expect, it, vi } from 'vitest';
import type { CliWorkerOptions } from '../src/local-workers/drivers.js';
import { fakeCli, frames, onEnd, onReport } from './helpers/local-worker-cli.js';

type Permission = NonNullable<CliWorkerOptions['onPermission']>;
const allowed = { allow: true, reason: 'Owner approved this action.' };

const codexSetup = `
  const answer = result => emit({id:m.id,result});
  const send = (id,method,params) => emit({id,method,params:{threadId:'saved',turnId:'t',...params}});
  if (m.method==='initialize') answer({});
  if (m.method==='thread/resume') answer({thread:{id:'saved'}});
`;

it('selects only bound, identifiable, one-shot Codex decisions and returns question options to the parent', async () => {
  const approve = vi.fn<Permission>(async () => allowed);
  const worker = await fakeCli(
    'codex',
    codexSetup +
      `
    if (m.method==='turn/start') {
      answer({turn:{id:'t'}});
      send(11,'item/commandExecution/requestApproval',{itemId:'cmd',command:'pwd',availableDecisions:['accept','acceptForSession']});
      send(12,'item/commandExecution/requestApproval',{itemId:'persistent',command:'pwd',availableDecisions:['acceptForSession']});
      send(13,'item/commandExecution/requestApproval',{itemId:'wrong',command:'pwd',threadId:'other'});
      send(14,'item/commandExecution/requestApproval',{itemId:'wrong',command:'pwd',turnId:'other'});
      send(undefined,'item/started',{item:{id:'edit',type:'fileChange',changes:[{path:'/a',kind:{type:'update',move_path:'/b'},diff:'private patch'}]}});
      send(15,'item/fileChange/requestApproval',{itemId:'edit',reason:'file update'});
      send(16,'item/fileChange/requestApproval',{itemId:'unknown'});
      send(17,'item/fileChange/requestApproval',{itemId:'edit',grantRoot:'/outside'});
      send(18,'item/permissions/requestApproval',{itemId:'generic',permissions:{fileSystem:{write:['/outside']}}});
      emit({id:19,method:'execCommandApproval',params:{conversationId:'saved',callId:'old',command:['pwd'],cwd:'/tmp'}});
      emit({id:20,method:'applyPatchApproval',params:{conversationId:'saved',callId:'patch',fileChanges:{'/new':{type:'add',content:'private body'}}}});
      send(21,'item/tool/requestUserInput',{questions:[{question:'Choose?',options:[{label:'Blue'}]}]});
      send(undefined,'item/autoApprovalReview/completed',{targetItemId:'blocked',reviewId:'rev',review:{status:'denied',rationale:'blocked by Auto'},action:{type:'command',command:'whoami'}});
      send(22,'item/commandExecution/requestApproval',{itemId:'blocked',command:'whoami'});
    }`,
    'saved',
    approve,
  );
  await worker.send('go');
  await expect.poll(async () => (await frames()).filter((f) => f.result).length).toBe(12);
  const wire = await frames();
  expect(
    wire.find((f) => f.method === 'thread/resume').params.config['mcp_servers.nano-parent'].tools,
  ).toEqual({ send_message: { approval_mode: 'approve' } });
  const replies = Object.fromEntries(wire.filter((f) => f.result).map((f) => [f.id, f.result]));
  expect(replies).toMatchObject({
    11: { decision: 'accept' },
    12: { decision: 'decline' },
    13: { decision: 'decline' },
    14: { decision: 'decline' },
    15: { decision: 'accept' },
    16: { decision: 'decline' },
    17: { decision: 'decline' },
    18: { permissions: {}, scope: 'turn' },
    19: { decision: 'approved' },
    20: { decision: 'approved' },
    21: { answers: {} },
    22: { decision: 'decline' },
  });
  expect(approve).toHaveBeenCalledTimes(4);
  const summaries = approve.mock.calls.map(([a]) => a.summary);
  expect(summaries[1]).toMatchObject({ files: ['/a', '/b'] });
  expect(JSON.stringify(summaries)).not.toMatch(/private patch|private body/);
  expect(JSON.stringify(onReport.mock.calls)).toMatch(/Blue/);
});

it('keeps concurrent Codex decisions independent and invalidates slow answers on withdrawal and stop', async () => {
  const pending = Promise.withResolvers<typeof allowed>();
  const approve = vi.fn<Permission>(async (action) =>
    action.summary.command === 'fast' ? { allow: false, reason: 'Owner rejected.' } : pending.promise,
  );
  const worker = await fakeCli(
    'codex',
    codexSetup +
      `
    if (m.method==='turn/start') {
      answer({turn:{id:'t'}});
      for (const [id,command] of [[11,'withdraw'],[12,'fast'],[13,'stop']])
        send(id,'item/commandExecution/requestApproval',{itemId:command,command});
    }
    if (m.id===12 && m.result) send(undefined,'serverRequest/resolved',{requestId:11});
    if (m.method==='turn/interrupt') {
      answer({});send(undefined,'turn/completed',{turn:{id:'t',status:'interrupted'}});
    }`,
    'saved',
    approve,
  );
  await worker.send('go');
  await expect.poll(() => approve.mock.calls[0]?.[1].aborted).toBe(true);
  expect(approve.mock.calls[2]?.[1].aborted).toBe(false);
  await worker.stop();
  expect(approve.mock.calls[2]?.[1].aborted).toBe(true);
  pending.resolve(allowed);
  const wire = await frames();
  expect(wire.filter((f) => f.result).map((f) => f.result.decision)).toEqual([
    'decline',
    'decline',
    'decline',
  ]);
  expect(onReport.mock.calls.some(([, text]) => text.includes('Owner rejected.'))).toBe(true);
});

const claudeSetup = `
  if(m.type==='control_request') emit({type:'control_response', response:{subtype:'success',request_id:m.request_id}});
  const ask = (id,tool,input,extra={}) => emit({type:'control_request',request_id:id,
    request:{subtype:'can_use_tool',tool_name:tool,tool_use_id:id,input},...extra});
`;

it('returns original Claude input once, forwards AskUserQuestion, and invalidates cancelled or exited requests', async () => {
  const pending = Promise.withResolvers<typeof allowed>();
  const approve = vi.fn<Permission>(async (a) =>
    a.name === 'Write' ? { ...allowed, report: true } : pending.promise,
  );
  const worker = await fakeCli(
    'claude',
    claudeSetup +
      `
    if(m.type==='user') {
      ask('write','Write',{file_path:'/tmp/doc',content:'private body'});
      ask('question','AskUserQuestion',{questions:[{question:'Format?',options:[{label:'CSV'}]}]});
      ask('wrong','Read',{file_path:'/foreign'},{session_id:'elsewhere'});
      ask('cancel','Read',{file_path:'/later'});
      ask('exit','Read',{file_path:'/last'});
      emit({type:'control_cancel_request',request_id:'cancel'});
    }
    if(m.type==='control_response' && m.response.request_id==='write') process.stdin.destroy();
    `,
    'saved',
    approve,
  );
  await worker.send('go');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(approve.mock.calls.map(([a]) => a.name)).toEqual(['Write', 'Read', 'Read']);
  expect(approve.mock.calls.slice(1).map(([, signal]) => signal.aborted)).toEqual([true, true]);
  pending.resolve(allowed);
  const wire = (await frames()).filter((f) => f.type === 'control_response').map((f) => f.response);
  expect(wire.find((f) => f.request_id === 'write')?.response).toEqual({
    behavior: 'allow',
    updatedInput: { file_path: '/tmp/doc', content: 'private body' },
  });
  for (const id of ['wrong', 'cancel', 'question'])
    expect(wire.find((f) => f.request_id === id)?.response.behavior).toBe('deny');
  expect(wire.filter((f) => f.response.behavior === 'allow')).toHaveLength(1);
  expect(JSON.stringify(onReport.mock.calls)).toMatch(/CSV/);
  expect(JSON.stringify(onReport.mock.calls)).not.toContain('private body');
});

const acpSetup = `
  const answer = result => emit({jsonrpc:'2.0',id:m.id,result});
  if(m.method==='initialize') answer({agentCapabilities:{sessionCapabilities:{resume:{}}}});
  if(m.method==='session/resume') answer({sessionId:'saved',modes:{availableModes:[{id:'auto'}]}});
  if(m.method==='session/set_mode') answer({});
  const opts = [{kind:'allow_always',optionId:'forever'}, {kind:'allow_once',optionId:'once'}, {kind:'reject_once',optionId:'no'}];
  const ask = (id,toolCall,options=opts,sessionId='saved') => emit({jsonrpc:'2.0',id,method:'session/request_permission',params:{sessionId,toolCall,options}});
  const update = upd => emit({jsonrpc:'2.0',method:'session/update',params:{sessionId:'saved',update:upd}});
`;

it('reviews complete ACP arguments from the matching call and grants only exact host tools or allow_once', async () => {
  const pending = Promise.withResolvers<typeof allowed>();
  const approve = vi.fn<Permission>(async (a) => (a.name === 'write_file' ? allowed : pending.promise));
  const worker = await fakeCli(
    'antigravity',
    acpSetup +
      `
    if(m.method==='session/prompt') {
      update({sessionUpdate:'tool_call',toolCallId:'write',name:'write_file',kind:'edit',rawInput:{Path:'/etc/example',Content:'private body'}});
      ask(11,{toolCallId:'write',kind:'edit',rawInput:{Path:'/etc/example'}});
      ask(12,{toolCallId:'write',kind:'edit'},opts,'foreign');
      ask(13,{toolCallId:'no-once',kind:'edit',rawInput:{Path:'/tmp/f'}},[opts[0],opts[2]]);
      ask(14,{toolCallId:'internal',title:'Run mcp_nano-parent_send_message?',kind:'other',rawInput:{message:'ok'}});
      ask(15,{toolCallId:'conflict',title:'Run mcp_nano-parent_send_message',name:'run_command',rawInput:{command:'pwd'}});
      ask(16,{toolCallId:'proxy',title:'MCP Tool send_message?',rawInput:{ServerName:'nano-parent',ToolName:'send_message'}});
      ask(17,{toolCallId:'fake',name:'unknown',rawInput:{ServerName:'nano-parent',ToolName:'send_message'}});
      ask(18,{toolCallId:'interaction_menu',title:'Choose an account'},opts);
      ask(19,{toolCallId:'later',name:'read_file',rawInput:{Path:'/later'}});
      update({sessionUpdate:'tool_call_update',toolCallId:'later',status:'cancelled'});
      ask(20,{toolCallId:'bare',name:'write_file',kind:'edit'});
    }`,
    'saved',
    approve,
  );
  await worker.send('go');
  await expect.poll(async () => (await frames()).filter((f) => f.result).length).toBe(10);
  expect(approve.mock.calls.map(([a]) => a.name)).toEqual(['write_file', 'read_file']);
  expect(approve.mock.calls[0]?.[0].input).toMatchObject({
    rawInput: { Path: '/etc/example', Content: 'private body' },
  });
  expect(JSON.stringify(approve.mock.calls[0]?.[0].summary)).not.toContain('private body');
  expect(approve.mock.calls[1]?.[1].aborted).toBe(true);
  pending.resolve(allowed);
  const outcomes = Object.fromEntries(
    (await frames()).filter((f) => f.result).map((f) => [f.id, f.result.outcome.optionId ?? 'cancelled']),
  );
  expect(outcomes).toEqual({
    11: 'once',
    12: 'no',
    13: 'no',
    14: 'once',
    15: 'no',
    16: 'once',
    17: 'no',
    18: 'cancelled',
    19: 'no',
    20: 'no',
  });
  expect(JSON.stringify(onReport.mock.calls)).toContain('Choose an account');
});
