import { mkdtemp, mkdir, readFile, writeFile, rm, realpath, cp } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('installs workspace tools into existing chats, isolates dispatch, retries failed source and preserves restart choices', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-workspace-tools-'));
  const pnpm = await realpath(process.env.PATH!.split(delimiter).map(dir => join(dir, 'pnpm')).find(path => existsSync(path))!);
  const packageManager = { command: pnpm, args: [], env: { PATH: process.env.PATH! } };
  const a = join(home, 'a'); const b = join(home, 'b'); const source = join(a, 'my-tool');
  let client: RuntimeClient | undefined; let logs = '';
  await mkdir(source, { recursive: true }); await mkdir(b);
  await writeFile(join(source, 'package.json'), JSON.stringify({ name: 'workspace-echo', version: '1.0.0', type: 'module', peerDependencies: {'@deepseek-ai/cordis':'*','@deepseek-ai/dsh-llm':'*'}, dsh: { bundle: { patch: './cordis.patch.yml' } } }));
  await writeFile(join(source, 'cordis.patch.yml'), JSON.stringify([{ insert: [{ id: 'echo', name: './tool.mjs' }] }]));
  const goodSource = `import { Context, symbols } from '@deepseek-ai/cordis';
    import { createUserMessage } from '@deepseek-ai/dsh-llm';
    if (!symbols.original || typeof createUserMessage !== 'function') throw new Error('HOST_PEERS_MISSING');
    export const inject=['tools']; export function apply(ctx) {
    if (!(ctx.root instanceof Context)) throw new Error('DUPLICATE_HOST_CORDIS');
    ctx.tools.register({name:'workspace_echo',description:'Return a workspace value',parameters:{type:'object',properties:{value:{type:'string'}},required:['value']},
      output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},execute:async args=>({echo:args.value})});
  }`;
  await writeFile(join(source, 'tool.mjs'), 'throw new Error("BROKEN_WORKSPACE_SOURCE");');
  await writeFile(join(home, 'model.mjs'), `export const inject=['llm']; export function apply(ctx) { const steps=new Map();
    ctx.on('llm/stream',async function* (options) {
      const last=options.messages.findLast(m=>m.role==='user' && m.content.some(b=>b.type==='text' && b.text.startsWith('{"tool":')));
      const command=last && JSON.parse(last.content.find(b=>b.type==='text').text); const step=last ? steps.get(last.id)??0 : 2;
      if(command?.tool==='hold') {await new Promise(resolve=>setTimeout(resolve,2000));yield {type:'block-end',index:0,block:{type:'text',text:'hold finished'}};yield {type:'finish',reason:{kind:'stop'}};return;}
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
    { agentId: 'peer', workspace: a, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['plugin_manager'] },
    { agentId: 'empty', workspace: a, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: [] },
  ];
  const bindings = [
    { sessionId: 'tools-a', agentId: 'a', revision: '1', ownerId: 'owner', cwd: a },
    { sessionId: 'tools-a2', agentId: 'a', revision: '1', ownerId: 'owner', cwd: a },
    { sessionId: 'tools-b', agentId: 'b', revision: '1', ownerId: 'owner', cwd: b },
    { sessionId: 'tools-peer', agentId: 'peer', revision: '1', ownerId: 'owner', cwd: a },
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
    for (const topic of ['tool', 'prompt', 'service', 'events', 'compaction']) {
      const api = await manage({ action: 'describe_api', topic });
      expect(api.error, api.text).toBe(false);
      const value = JSON.parse(JSON.parse(api.text)[0].text);
      expect(value).toMatchObject({workspace: await realpath(a), topic, runtimeVersion: expect.any(String)});
      expect(value.packages.length).toBeGreaterThan(0);
      for (const pkg of value.packages) {
        expect(pkg.types.length).toBeGreaterThan(0);
        for (const entry of pkg.types) expect(await readFile(entry.path, 'utf8')).toContain('export');
      }
      expect(api.text).not.toContain(b);
    }
    expect((await manage({ action: 'describe_api' })).error).toBe(true);
    expect((await manage({ action: 'describe_api', topic: 'client' })).error).toBe(true);
    const bad = await manage({ action: 'install_bundle', target: source });
    expect(bad.text).toContain('BROKEN_WORKSPACE_SOURCE');
    expect(bad.text).toContain('failed');
    expect(await capabilities('tools-a')).not.toContain('workspace_echo');
    await writeFile(join(source, 'tool.mjs'), goodSource);
    const installed = await manage({ action: 'install_bundle', target: source });
    expect(installed.error, installed.text).toBe(false);
    expect(installed.text).toContain('restart-required');
    await client!.shutdown(); client = undefined; await start(true);
    expect(await capabilities('tools-a'), (await manage({action:'list_bundles'})).text).toContain('workspace_echo');
    expect((await call('tools-a', 'workspace_echo', {value:'REPAIRED_AFTER_RESTART'})).text).toContain('REPAIRED_AFTER_RESTART');
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
    await writeFile(join(source, 'tool.mjs'), goodSource.replace('echo:args.value', "echo:'UPDATED:'+args.value"));
    const updated = await manage({action:'install_bundle',target:source});
    expect(updated.error, updated.text).toBe(false);
    expect(updated.text).toContain('restart-required');
    expect((await call('tools-a','workspace_echo',{value:'BEFORE_RESTART'})).text).not.toContain('UPDATED:');
    await manage({action:'set_bundle',target:'workspace-echo',enabled:false});
    await manage({action:'set_bundle',target:'workspace-echo',enabled:true});
    expect((await call('tools-a','workspace_echo',{value:'TOGGLE_IS_NOT_UPGRADE'})).text).not.toContain('UPDATED:');
    await client!.shutdown(); client = undefined; await start(true);
    expect((await call('tools-a','workspace_echo',{value:'AFTER_RESTART'})).text).toContain('UPDATED:AFTER_RESTART');
    expect((await call('tools-peer','workspace_echo',{value:'PEER_UPDATE'})).text).toContain('UPDATED:PEER_UPDATE');
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
    const held = call('tools-a', 'hold', {});
    await expect.poll(async () => (await client!.rpc.request('session.observe', {sessionId:'tools-a'}) as {status:string}).status).toBe('running');
    const control = (command: Record<string, unknown>) => client!.rpc.request('plugins.manage', {agentId:'a', ...command}) as Promise<{pending?: unknown; entries:{name:string;enabled:boolean}[]}>;
    const pending = await control({action:'set_bundle',target:'workspace-echo',enabled:false});
    expect(pending.pending).toMatchObject({target:'workspace-echo',enabled:false});
    expect(pending.entries.find(entry=>entry.name==='workspace-echo')?.enabled).toBe(true);
    expect((await control({action:'list_bundles'})).pending).toBeTruthy();
    expect((await call('tools-peer', 'plugin_manager', {action:'describe_api',topic:'tool'})).error).toBe(false);
    expect((await call('tools-peer','plugin_manager',{action:'set_bundle',target:'workspace-echo',enabled:true})).text).toContain('busy');
    await held;
    await expect.poll(async()=> (await control({action:'list_bundles'})).pending, {timeout:10_000}).toBeUndefined();
    expect((await call('tools-a', 'workspace_echo', {value:'DISABLED_BY_USER'})).error).toBe(true);
    expect(await capabilities('tools-peer')).not.toContain('workspace_echo');
    await manage({action:'install_bundle',target:source});
    expect(await capabilities('tools-a')).not.toContain('workspace_echo');
    const namedUpdate = await manage({action:'install_bundle',target:`workspace-echo@file:${source}`});
    expect(namedUpdate.error, namedUpdate.text).toBe(false);
    expect((await control({action:'list_bundles'})).entries.find(entry=>entry.name==='workspace-echo')?.enabled).toBe(false);
    const interruptedId = randomUUID();
    await client!.rpc.request('session.submit', {sessionId:'tools-a',inputId:interruptedId,mode:'followup',content:[{type:'text',text:JSON.stringify({tool:'hold',args:{}})}],source:{kind:'human',actorId:'owner',channel:'test',messageId:interruptedId}});
    await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'tools-a'}) as {status:string}).status).toBe('running');
    expect((await control({action:'set_bundle',target:'workspace-echo',enabled:true})).pending).toBeTruthy();
    client!.process.kill('SIGKILL'); await client!.exited; client=undefined; await start(true);
    expect((await control({action:'list_bundles'})).pending).toBeUndefined();
    expect(await capabilities('tools-a')).not.toContain('workspace_echo');
    await control({action:'set_bundle',target:'workspace-echo',enabled:true});
    await expect.poll(async()=> (await control({action:'list_bundles'})).pending, {timeout:10_000}).toBeUndefined();
    expect((await call('tools-a', 'workspace_echo', {value:'USER_ENABLED_AGAIN'})).text).toContain('USER_ENABLED_AGAIN');
    const style = join(a, 'report-style'); await mkdir(style);
    await writeFile(join(style, 'package.json'), JSON.stringify({name:'report-style',version:'1.0.0',type:'module',description:'Format expense reports',dsh:{bundle:{patch:'./cordis.patch.yml'}}}));
    await writeFile(join(style, 'provider.mjs'), `export function apply(ctx) {ctx.provide('reportStyle', 'STYLE_ISOLATED_610');}`);
    await writeFile(join(style, 'cordis.patch.yml'), JSON.stringify([{insert:[{id:'style-provider',name:'./provider.mjs'}]}]));
    expect((await manage({action:'install_bundle',target:style})).text).toContain('root services');
    await writeFile(join(style, 'consumer.mjs'), `import {existsSync} from 'node:fs'; import {writeFile,readFile} from 'node:fs/promises';
      export const inject=['reportStyle','systemPrompt']; export function apply(ctx) {
        ctx.systemPrompt.section({name:'report-style',order:850,text:ctx.reportStyle});
        ctx.effect(()=>async()=> { if(!existsSync(${JSON.stringify(join(a,'hold-cleanup'))})) return;
          await writeFile(${JSON.stringify(join(a,'cleanup-started'))},'yes');
          while(!existsSync(${JSON.stringify(join(a,'release-cleanup'))})) await new Promise(resolve=>setTimeout(resolve,20));
          await readFile(new URL(import.meta.url)); await writeFile(${JSON.stringify(join(a,'cleanup-done'))},'yes');
        });
      }`);
    await writeFile(join(style, 'cordis.patch.yml'), JSON.stringify([{insert:[{id:'style-group',name:'cordis:group',group:true,isolate:{reportStyle:true},config:[{id:'style-provider',name:'./provider.mjs'},{id:'style-consumer',name:'./consumer.mjs'}]}]}]));
    expect((await manage({action:'install_bundle',target:style})).text).toContain('restart-required');
    await client!.shutdown(); client = undefined; await start(true);
    expect(await capabilities('tools-a'), (await manage({action:'list_bundles'})).text).toContain('workspace_echo');
    const prompt = async (sessionId: string) => JSON.stringify((await client!.rpc.request('session.capabilities',{sessionId}) as {prompt:unknown}).prompt);
    expect(await prompt('tools-a')).toContain('STYLE_ISOLATED_610');
    expect(await prompt('tools-peer')).toContain('STYLE_ISOLATED_610');
    expect(await prompt('tools-b')).not.toContain('STYLE_ISOLATED_610');
    expect((await control({action:'list_bundles'})).entries.find(entry=>entry.name==='report-style')).toMatchObject({enabled:true});
    await writeFile(join(a,'hold-cleanup'),'yes');
    await control({action:'remove_bundle',target:'report-style'});
    await expect.poll(()=>existsSync(join(a,'cleanup-started'))).toBe(true);
    expect((await control({action:'list_bundles'})).pending).toBeTruthy();
    // A new input stays in the native inbox during async teardown; B keeps running.
    let newTurnFinished=false;
    const queued=call('tools-a','workspace_echo',{value:'AFTER_CLEANUP'}).then(result=>{newTurnFinished=true;return result;});
    const otherWorkspace = await call('tools-b','plugin_manager',{action:'list_bundles'});
    expect(otherWorkspace.error, otherWorkspace.text).toBe(false);
    expect(newTurnFinished).toBe(false);
    expect(existsSync(join(a,'cleanup-done'))).toBe(false);
    await writeFile(join(a,'release-cleanup'),'yes');
    await expect.poll(async()=> (await control({action:'list_bundles'})).pending,{timeout:10_000}).toBeUndefined();
    expect(existsSync(join(a,'cleanup-done'))).toBe(true);
    expect((await queued).text, (await manage({action:'list_bundles'})).text).toContain('AFTER_CLEANUP');
    expect(await prompt('tools-a')).not.toContain('STYLE_ISOLATED_610');
    expect((await control({action:'list_bundles'})).entries.some(entry=>entry.name==='report-style')).toBe(false);
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
    // Shipped authoring templates must work through the real workspace installer,
    // not just parse as JavaScript or resemble the documentation examples.
    const templates = fileURLToPath(new URL('../../personal-assistant/assets/skills/nano-plugin-development/templates/', import.meta.url));
    for (const template of ['tool', 'prompt', 'service']) {
      const dir = join(a, `template-${template}`);
      await cp(join(templates, template), dir, {recursive:true});
      expect((await manage({action:'install_bundle',target:dir})).text).toContain('applied');
    }
    expect((await call('tools-a', 'workspace_total', {cents:[1250,3750,-500]})).text).toContain('4500');
    expect(await prompt('tools-a')).toContain('待核对事项');
    expect(await prompt('tools-b')).not.toContain('待核对事项');
    expect((await call('tools-a', 'workspace_counted_echo', {text:'A_ONLY'})).text).toContain('A_ONLY');
    expect(JSON.parse(JSON.parse((await call('tools-a','workspace_counter_status',{})).text)[0].text)).toBe(1);
    const bService = join(b, 'template-service');
    await cp(join(templates, 'service'), bService, {recursive:true});
    await call('tools-b','plugin_manager',{action:'install_bundle',target:bService});
    await call('tools-b','workspace_counted_echo',{text:'B_ONLY'});
    expect(JSON.parse(JSON.parse((await call('tools-a','workspace_counter_status',{})).text)[0].text)).toBe(1);
    await manage({action:'set_bundle',target:'workspace-call-counter',enabled:false});
    expect((await call('tools-a','workspace_counted_echo',{text:'DISABLED'})).error).toBe(true);
    expect((await call('tools-b','workspace_counted_echo',{text:'B_CONTINUES'})).error).toBe(false);
    await manage({action:'set_bundle',target:'workspace-call-counter',enabled:true});
    await call('tools-a','workspace_counted_echo',{text:'ONE_LISTENER'});
    expect(JSON.parse(JSON.parse((await call('tools-a','workspace_counter_status',{})).text)[0].text)).toBe(1);
    for (const name of ['workspace-total','workspace-report-format','workspace-call-counter']) {
      await manage({action:'remove_bundle',target:name});
    }
    expect(await prompt('tools-a')).not.toContain('待核对事项');
    expect(await capabilities('tools-a')).not.toContain('workspace_total');
    expect(await capabilities('tools-a')).not.toContain('workspace_counter_status');
    const engine = join(a, 'scoped-compaction'); await mkdir(engine);
    const marker = join(a, 'compaction-owner');
    await writeFile(join(engine, 'package.json'), JSON.stringify({name:'scoped-compaction',version:'1.0.0',type:'module',peerDependencies:{'@deepseek-ai/dsh-compaction-basic':'*'},dsh:{bundle:{patch:'./cordis.patch.yml'}}}));
    await writeFile(join(engine, 'engine.mjs'), `import {appendFile} from 'node:fs/promises';
      import {BasicCompactionEngine} from '@deepseek-ai/dsh-compaction-basic';
      export default class extends BasicCompactionEngine {async summarize(...args) {
        await appendFile(${JSON.stringify(marker)}, 'preset\\n'); return super.summarize(...args);
      }}`);
    await writeFile(join(engine, 'cordis.patch.yml'), JSON.stringify([{insert:[{id:'scoped-compaction',name:'./engine.mjs',isolate:{compaction:true},config:{auto:false,retainTokens:0,headroomTokens:100,maxTokens:256}}]}]));
    expect((await manage({action:'install_bundle',target:engine})).text).toContain('applied');
    const compact = async (sessionId: string, id: string) => {
      await call(sessionId, 'plugin_manager', {action:'list_bundles', evidence:'preserve this evidence '.repeat(300)});
      const result = await client!.rpc.request('session.command', {sessionId,id,action:'compact',argument:'preserve evidence'});
      expect(result, JSON.stringify(result)).toMatchObject({success:true});
      const observed = await client!.rpc.request('session.observe', {sessionId}) as {events:{type:string}[]};
      expect(observed.events.some(event => event.type === 'compaction/summary')).toBe(true);
    };
    await compact('tools-a', 'preset-compact');
    expect(await readFile(marker,'utf8')).toBe('preset\n');
    await compact('tools-b', 'other-workspace-compact');
    expect(await readFile(marker,'utf8')).toBe('preset\n');
    await manage({action:'set_bundle',target:'scoped-compaction',enabled:false});
    await compact('tools-a', 'fallback-compact');
    expect(await readFile(marker,'utf8')).toBe('preset\n');
    await client!.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 90_000);
