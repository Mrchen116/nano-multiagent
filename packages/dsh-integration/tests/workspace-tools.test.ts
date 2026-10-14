import { mkdtemp, mkdir, writeFile, rm, realpath } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('installs workspace tools into existing chats, isolates dispatch, retries failed source and preserves restart choices', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-workspace-tools-'));
  const pnpm = await realpath(process.env.PATH!.split(delimiter).map(dir => join(dir, 'pnpm')).find(path => existsSync(path))!);
  const packageManager = { command: pnpm, args: [], env: { PATH: process.env.PATH! } };
  const a = join(home, 'a'); const b = join(home, 'b'); const source = join(a, 'my-tool');
  let client: RuntimeClient | undefined; let logs = '';
  await mkdir(source, { recursive: true }); await mkdir(b);
  await writeFile(join(source, 'package.json'), JSON.stringify({ name: 'workspace-echo', version: '1.0.0', type: 'module', dsh: { bundle: { patch: './cordis.patch.yml' } } }));
  await writeFile(join(source, 'cordis.patch.yml'), JSON.stringify([{ insert: [{ id: 'echo', name: './tool.mjs' }] }]));
  const goodSource = `export const inject=['tools']; export function apply(ctx) {
    ctx.tools.register({name:'workspace_echo',description:'Return a workspace value',parameters:{type:'object',properties:{value:{type:'string'}},required:['value']},
      output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},execute:async args=>({echo:args.value})});
  }`;
  await writeFile(join(source, 'tool.mjs'), 'throw new Error("BROKEN_WORKSPACE_SOURCE");');
  await writeFile(join(home, 'model.mjs'), `export const inject=['llm']; export function apply(ctx) { const steps=new Map();
    ctx.on('llm/stream',async function* (options) {
      const last=options.messages.findLast(m=>m.role==='user' && m.content.some(b=>b.type==='text' && b.text.startsWith('{"tool":')));
      const command=last && JSON.parse(last.content.find(b=>b.type==='text').text); const step=last ? steps.get(last.id)??0 : 2;
      const selected=step===0?command:step===1?command.next:undefined;
      if(!selected) {yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};return;}
      steps.set(last.id,step+1);
      yield {type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-tool-'+step,name:selected.tool,arguments:JSON.stringify(selected.args)}};
      yield {type:'finish',reason:{kind:'tool-calls'}};
    });
  }`);
  const agents = [
    { agentId: 'a', workspace: a, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['plugin_manager'] },
    { agentId: 'b', workspace: b, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['plugin_manager'] },
    { agentId: 'empty', workspace: a, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: [] },
  ];
  const bindings = [
    { sessionId: 'tools-a', agentId: 'a', revision: '1', ownerId: 'owner', cwd: a },
    { sessionId: 'tools-a2', agentId: 'a', revision: '1', ownerId: 'owner', cwd: a },
    { sessionId: 'tools-b', agentId: 'b', revision: '1', ownerId: 'owner', cwd: b },
    { sessionId: 'tools-empty', agentId: 'empty', revision: '1', ownerId: 'owner', cwd: a },
  ];
  const capabilities = async (sessionId: string) => (await client!.rpc.request('session.capabilities', { sessionId }) as { tools: string[] }).tools;
  const call = async (sessionId: string, tool: string, args: unknown, next?: { tool: string; args: unknown }) => {
    const inputId = randomUUID();
    await client!.rpc.request('session.submit', { sessionId, inputId, mode: 'followup', content: [{ type: 'text', text: JSON.stringify({ tool, args, next }) }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId } });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId, inputId }) as { terminal?: unknown }).terminal, { timeout: 20_000 }).toBeTruthy();
    const observed = await client!.rpc.request('session.observe', { sessionId }) as { events: { type: string; data: { message?: { isError?: boolean; content: unknown } } }[] };
    const result = observed.events.findLast(event => event.type === 'tool/result')!.data.message!;
    return { error: result.isError === true, text: JSON.stringify(result.content) };
  };
  const manage = (args: unknown) => call('tools-a', 'plugin_manager', args);
  try {
    await prepareProfile(home, [{ insert: [{ id: 'model', name: join(home, 'model.mjs') }] }]);
    const start = async (restore = false) => {
      client = new RuntimeClient({ home, cwd: home, env: { PATH: join(home, 'no-global-tools') }, onLog: text => { logs += text; } });
      await client.rpc.request('initialize', { protocol: 1, packageManager, agents, bindings: restore ? bindings : [] });
      for (const binding of bindings) await client.rpc.request('session.ensure', binding);
    };
    await start();
    expect(await capabilities('tools-a')).toContain('plugin_manager');
    expect(await capabilities('tools-empty')).toEqual([]);
    const bad = await manage({ action: 'install_bundle', target: source });
    expect(bad.text).toContain('BROKEN_WORKSPACE_SOURCE');
    expect(bad.text).toContain('failed');
    expect(await capabilities('tools-a')).not.toContain('workspace_echo');
    await writeFile(join(source, 'tool.mjs'), goodSource);
    const installed = await call('tools-a', 'plugin_manager', { action: 'install_bundle', target: source }, { tool: 'workspace_echo', args: { value: 'SAME_TURN_RESULT' } });
    expect(installed.error, installed.text).toBe(false);
    expect(installed.text).toContain('SAME_TURN_RESULT');
    expect(await capabilities('tools-a')).toContain('workspace_echo');
    expect(await capabilities('tools-a')).not.toContain('read');
    expect(await capabilities('tools-a2')).toContain('workspace_echo');
    const catalog = await client!.rpc.request('configuration.catalog', {agentId: 'a', cwd: a}) as {tools: {name: string; source_group?: string; enabled?: boolean}[]};
    expect(catalog.tools.find(tool => tool.name === 'workspace_echo')).toMatchObject({source_group: 'workspace', enabled: true});
    const emptyCatalog = await client!.rpc.request('configuration.catalog', {agentId: 'empty', cwd: a}) as typeof catalog;
    expect(emptyCatalog.tools.find(tool => tool.name === 'workspace_echo')).toMatchObject({source_group: 'workspace', enabled: false});
    const refreshedCatalog = await client!.rpc.request('configuration.catalog', {agentId: 'a', cwd: a}) as typeof catalog;
    expect(refreshedCatalog.tools.filter(tool => tool.source_group === 'workspace').map(tool => tool.name)).toEqual(['workspace_echo']);
    expect(await capabilities('tools-a')).not.toContain('schedule_create');
    expect(await capabilities('tools-b')).not.toContain('workspace_echo');
    expect(await capabilities('tools-empty')).toEqual([]);
    expect((await call('tools-a2', 'workspace_echo', { value: 'LIVE_WORKSPACE_RESULT' })).text).toContain('LIVE_WORKSPACE_RESULT');
    expect((await call('tools-b', 'workspace_echo', { value: 'denied' })).error).toBe(true);
    const selection = await client!.rpc.request('configuration.selection', { agentId: 'a', cwd: a }) as { tools: string[] };
    expect(selection.tools).toContain('workspace_echo');
    const other = join(a, 'broken-tool'); await mkdir(other);
    await writeFile(join(other, 'package.json'), JSON.stringify({ name: 'broken-workspace-tool', version: '1.0.0', type: 'module', dsh: { bundle: { patch: './cordis.patch.yml' } } }));
    await writeFile(join(other, 'cordis.patch.yml'), JSON.stringify([{ insert: [{ id: 'broken', name: './tool.mjs' }] }]));
    await writeFile(join(other, 'tool.mjs'), 'throw new Error("UNRELATED_BROKEN_SOURCE");');
    expect((await manage({ action: 'install_bundle', target: other })).text).toContain('failed');
    expect((await call('tools-a', 'workspace_echo', { value: 'SURVIVES_OTHER_FAILURE' })).text).toContain('SURVIVES_OTHER_FAILURE');
    await client!.shutdown(); client = undefined;
    // Runtime boot preparation must leave workspace bundle manifests intact.
    await prepareProfile(home, [{ insert: [{ id: 'model', name: join(home, 'model.mjs') }] }]);
    await start(true);
    expect(await capabilities('tools-a')).toContain('plugin_manager');
    expect((await call('tools-a', 'workspace_echo', { value: 'RESTART_RESULT' })).text).toContain('RESTART_RESULT');
    expect(await capabilities('tools-b')).not.toContain('workspace_echo');
    await manage({ action: 'set_bundle', target: 'workspace-echo', enabled: false });
    expect(await capabilities('tools-a')).not.toContain('workspace_echo');
    expect((await call('tools-a', 'workspace_echo', { value: 'disabled' })).error).toBe(true);
    await client!.shutdown(); client = undefined; await start(true);
    expect(await capabilities('tools-a')).not.toContain('workspace_echo');
    expect((await manage({ action: 'set_bundle', target: 'workspace-echo', enabled: true })).text).toContain('applied');
    expect((await call('tools-a', 'workspace_echo', { value: 'ENABLED_AGAIN' })).text).toContain('ENABLED_AGAIN');
    expect((await manage({ action: 'remove_bundle', target: 'workspace-echo' })).text).toContain('applied');
    expect((await manage({ action: 'remove_bundle', target: 'broken-workspace-tool' })).text).toContain('applied');
    expect(await capabilities('tools-a2')).not.toContain('workspace_echo');
    await client!.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 90_000);
