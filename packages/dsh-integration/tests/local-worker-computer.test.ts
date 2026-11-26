import {readFile, stat} from 'node:fs/promises';
import {join} from 'node:path';
import {expect, it, vi} from 'vitest';
import {openMcp} from '../src/computer/mcp.js';
import {workerReportBridge} from '../src/local-workers/report-bridge.js';
import {WorkerTurnDetails} from '../src/local-workers/work-details.js';
import {cwd, fakeCli, frames, mcp, onEnd} from './helpers/local-worker-cli.js';

const launch = {command: 'fixture-computer-mcp', args: ['bound-socket'], env: {}};

it('binds the Codex exception to exactly one host computer tool', async () => {
  await fakeCli('codex', `
    if (m.method === 'initialize') emit({id:m.id,result:{}});
    if (m.method === 'thread/start') emit({id:m.id,result:{thread:{id:'owned'}}});
  `, undefined, launch);
  const config = (await frames()).find(f => f.method === 'thread/start').params;
  expect(config.approvalsReviewer).toBe('auto_review');
  expect(config.config['mcp_servers.nano-computer']).toEqual({...launch,required:true,tools:{computer_use:{approval_mode:'approve'}}});
  expect(config.config['mcp_servers.nano-parent']).toMatchObject(mcp);
});

it('mounts Claude computer MCP alongside the exact parent reporting permission', async () => {
  await fakeCli('claude', `
    if (m.type === 'control_request') emit({type:'control_response', response:{subtype:'success',request_id:m.request_id}});
  `, undefined, launch);
  const args: string[] = JSON.parse(await readFile(join(cwd, 'args'), 'utf8'));
  expect(args.slice(args.indexOf('--allowedTools')+1,args.indexOf('--mcp-config')))
    .toEqual(['mcp__nano-parent__send_message','mcp__nano-computer__computer_use']);
  const config = args[args.indexOf('--mcp-config')+1]!;
  expect((await stat(config)).mode & 0o777).toBe(0o600);
  expect(JSON.parse(await readFile(config, 'utf8'))).toEqual({mcpServers:{'nano-parent':mcp,'nano-computer':launch}});
  expect(args[args.indexOf('--permission-mode')+1]).toBe('auto');
});

it('only selects a single-use ACP permission for the bound tool and session', async () => {
  const worker = await fakeCli('antigravity', `
    const answer = result => emit({jsonrpc:'2.0',id:m.id,result});
    if(m.method === 'initialize') answer({protocolVersion:1,agentCapabilities:{}});
    if(m.method === 'session/new') answer({sessionId:'owned',modes:{currentModeId:'auto',availableModes:[{id:'auto'}]}});
    if(m.method === 'session/set_mode') answer({});
    if(m.method === 'session/prompt') {
      let order=0;
      for(const [sessionId,name,title] of [
        ['owned','mcp_nano-computer_computer_use','Run mcp_nano-computer_computer_use'],
        ['other','mcp_nano-computer_computer_use','Run mcp_nano-computer_computer_use'],
        ['owned','another_tool','Run mcp_nano-computer_computer_use']]) {
        emit({jsonrpc:'2.0',method:'session/request_permission',id:++order+100,params:{
          sessionId,toolCall:{toolCallId:'call'+order,name,title,kind:'other'},options:[
          {kind:'allow_always',optionId:'always'},{kind:'allow_once',optionId:'once'},{kind:'reject_once',optionId:'deny'}]}});
      }
      answer({stopReason:'end_turn'});
    }
  `, undefined, launch);
  await worker.send('inspect assigned window');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  await expect.poll(async () => (await frames()).filter(f => [101,102,103].includes(f.id) && f.result).length).toBe(3);
  const wire = await frames();
  expect(wire.find(f => f.method === 'session/new').params.mcpServers[1]).toEqual({name:'nano-computer',command:launch.command,args:launch.args,env:[]});
  expect([101,102,103].map(id => wire.find(f => f.id === id && f.result).result.outcome.optionId)).toEqual(['once','deny','deny']);
});

it('routes a real stdio call once to the bound host and rejects caller-provided request identity', async () => {
  const call = vi.fn(async () => [{type:'text' as const,text:'synthetic window'}]);
  const bridge = await workerReportBridge(vi.fn(), call);
  let client;
  try {
    const launch = bridge.computer!;
    client = await openMcp(launch.command, launch.args, launch.env);
    const signal = new AbortController().signal;
    const args = {surface:'desktop', action:'state'};
    expect(await client.call('computer_use', args, signal)).toEqual([{type:'text',text:'synthetic window'}]);
    await expect(client.call('computer_use', {...args, request_ref:'another-owner-message'}, signal)).rejects.toThrow();
    expect(call).toHaveBeenCalledTimes(1);
  } finally {
    await client?.close();
    await bridge.close();
  }
});

it('cancels a pending host operation when the MCP client cancels its call', async () => {
  const started = Promise.withResolvers<void>();
  const aborted = Promise.withResolvers<void>();
  const bridge = await workerReportBridge(vi.fn(), async (_args, signal) => {
    started.resolve();
    await new Promise<void>((_,reject) => signal.addEventListener('abort', () => {
      aborted.resolve();
      reject(new Error('cancelled'));
    }, {once:true}));
    return [];
  });
  let client;
  try {
    const launch = bridge.computer!;
    client = await openMcp(launch.command, launch.args, launch.env);
    const controller = new AbortController();
    const pending = client.call('computer_use', {surface:'desktop',action:'status'}, controller.signal);
    await started.promise;
    controller.abort();
    await expect(pending).rejects.toThrow();
    await aborted.promise;
  } finally {
    await client?.close();
    await bridge.close();
  }
});

it('keeps computer contents out of the Worker Work projection', () => {
  const emit = vi.fn();
  const work = new WorkerTurnDetails(emit);
  work.begin('turn');
  work.toolStart('read', 'mcp__nano-computer__computer_use', {surface:'desktop',action:'read_clipboard'});
  work.toolEnd('read', undefined, 'synthetic clipboard contents', false);
  const facts = JSON.stringify(emit.mock.calls);
  expect(facts).toContain('read_clipboard');
  expect(facts).not.toContain('synthetic clipboard contents');
});
