import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('keeps tool-only schedules alive across restart and fences Cron shutdown against new schedules', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-cron-'));
  let client: RuntimeClient | undefined;
  const off = {intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false, cron_scheduling: false, heartbeat: false};
  const agent = {knowledge:{memoryMode:'legacy'}, agentId: 'a', workspace: home, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', features: off, toolAllowlist: ['schedule_create', 'task_graph', 'skill_manage', 'memory']};
  const binding = {sessionId: 'session-a', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home};
  const start = async () => {
    client = new RuntimeClient({home, cwd: home});
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', {protocol: 1, agents: [agent], bindings: [binding]});
    await client.rpc.request('session.ensure', binding);
  };
  try {
    await writeFile(join(home, 'fixture.mjs'), `export const name='tool-only'; export const inject=['llm'];
export function apply(ctx) { const steps=new Map(); ctx.on('llm/stream', async function*(o) {
  const human=o.messages.findLast(message=>message.role==='user' && message.source?.kind==='user');
  const key=human?.id; const step=steps.get(key)||0; steps.set(key,step+1);
  if(key==='tool-only' && step<3) {
    const calls=[['memory',{action:'add',target:'memory',content:'Environment fact from an explicit tool call.'}],
      ['skill_manage',{action:'create',name:'tool-only-method',content:'---\\nname: tool-only-method\\ndescription: Explicit tool call\\n---\\nCheck the result.'}],
      ['schedule_create',{title:'Tool only',prompt:'Tool-only reminder',after_seconds:1}]];
    const [name,args]=calls[step]; yield {type:'block-end',index:0,block:{type:'tool-call',id:'tool-only-'+step,name,arguments:JSON.stringify(args)}};
    yield {type:'finish',reason:{kind:'tool-calls'}};
  } else { yield {type:'block-end',index:0,block:{type:'text',text:'done'}}; yield {type:'finish',reason:{kind:'stop'}}; }
}); }`);
    await prepareProfile(home, [{insert:[{id:'tool-only',name:join(home,'fixture.mjs')}]}]); await start();
    const view = await client!.rpc.request('session.capabilities', {sessionId: binding.sessionId}) as {tools: string[]; prompt: {sections: {name: string}[]}};
    expect(view.tools).toEqual(expect.arrayContaining(['schedule_create', 'task_graph', 'skill_manage', 'memory']));
    expect(view.tools).not.toContain('schedule_list');
    expect(JSON.stringify(view.prompt)).not.toContain('nano-cron');
    expect(JSON.stringify(view.prompt)).not.toContain('nano-task-graphs');
    expect(JSON.stringify(view.prompt)).toContain('built-in skill-creator');
    await client!.rpc.request('session.submit', {sessionId: binding.sessionId, inputId: 'tool-only', mode: 'followup', content: [{type:'text',text:'Call the three selected tools'}], source:{kind:'human',actorId:'owner',channel:'test',messageId:'tool-only'}});
    await expect.poll(async () => (await client!.rpc.request('schedule.command', {agentId:'a',action:'catalog'}) as unknown[]).length).toBe(1);
    const [task] = await client!.rpc.request('schedule.command', {agentId:'a',action:'catalog'}) as {id:string}[];
    expect(await readFile(join(home,'.nanoassistant/memory-legacy/MEMORY.md'),'utf8')).toContain('Environment fact');
    expect(await readFile(join(home,'.nanoassistant/skills/tool-only-method/SKILL.md'),'utf8')).toContain('Check the result');
    expect(await client!.rpc.request('knowledge.facts', {})).toMatchObject({reviews: []});
    await expect.poll(async () => await client!.rpc.request('schedule.evidence', {sessionId: binding.sessionId}), {timeout: 6000}).toEqual(expect.arrayContaining([expect.objectContaining({scheduleId: task!.id, accepted: true})]));
    const future = await client!.rpc.request('schedule.command', {agentId: 'a', sessionId: binding.sessionId, action: 'create', args: {title: 'Future', prompt: 'Future', after_seconds: 3600}}) as {id: string};
    expect(await client!.rpc.request('schedule.wait.inspect', {agentId: 'a', sessionId: binding.sessionId, scheduleId: future.id})).toMatchObject({valid: true});
    await client!.shutdown(); client = undefined; await start();
    expect(await client!.rpc.request('schedule.command', {agentId: 'a', action: 'catalog'})).toEqual(expect.arrayContaining([expect.objectContaining({id: future.id, status: 'active'})]));
    const cronTools = ['schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'];
    const enabled = {...agent, revision: '2', features: {...off, cron_scheduling: true}, toolAllowlist: [...agent.toolAllowlist, ...cronTools]};
    expect(await client!.rpc.request('configuration.apply', enabled)).toMatchObject({effective: true});
    const candidate = {...agent, revision: '3'};
    expect(await client!.rpc.request('configuration.prepare', {operationId: 'blocked', fingerprint: '3', config: candidate})).toMatchObject({ready: false, blocks: [{code: 'active_schedules'}]});
    expect(await client!.rpc.request('configuration.usage', {agentId: 'a'})).toMatchObject({active_schedules: 1});
    await client!.rpc.request('schedule.command', {agentId: 'a', sessionId: binding.sessionId, action: 'delete', args: {id: future.id}});
    expect(await client!.rpc.request('configuration.prepare', {operationId: 'close', fingerprint: '3', config: candidate})).toMatchObject({ready: true});
    await expect(client!.rpc.request('schedule.command', {agentId: 'a', sessionId: binding.sessionId, action: 'create', args: {title: 'Race', prompt: 'Race', after_seconds: 60}})).rejects.toThrow('reserved');
    await expect(client!.rpc.request('schedule.enabled', {agentId: 'a', enabled: false})).rejects.toThrow('configuration.prepare');
    await expect(client!.rpc.request('configuration.features', {agentId: 'a', features: off})).rejects.toThrow('configuration.prepare');
    expect(await client!.rpc.request('configuration.apply', {...candidate, operationId: 'close', fingerprint: '3'})).toMatchObject({effective: true});
    expect((await client!.rpc.request('session.capabilities', {sessionId: binding.sessionId}) as {tools: string[]}).tools).toContain('schedule_create');
    await client!.shutdown(); client = undefined;
  } finally { if (client) {client.process.kill('SIGKILL'); await client.exited;} await rm(home, {recursive: true, force: true}); }
}, 30_000);

it('recovers admitted schedule identity when the process dies before the timer receipt commits', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-cron-gap-'));
  let client: RuntimeClient | undefined;
  const agent = { agentId: 'gap', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', features: { cron_scheduling: true } };
  const binding = { sessionId: 'gap-session', agentId: 'gap', revision: '1', ownerId: 'owner', cwd: home };
  try {
    const { writeFile } = await import('node:fs/promises');
    const fault = join(home, 'flush-fault.mjs');
    // Hold one public flush participant so the native timer cannot commit its
    // receipt. The real persistence listener runs independently; cold recovery
    // below proves that the actual schedule input reached its durable log.
    await writeFile(fault, `import {writeFileSync} from 'node:fs'; export const name='flush-fault'; export function apply(ctx) {
      ctx.on('session/flush', session => {
        if (!session.snapshotEvents().some(event => event.type==='agent/inbox/spliced' && event.data.inserted.some(message => message.source?.kind==='schedule'))) return;
        const original=session.snapshotEvents().filter(event=>event.type==='agent/inbox/spliced').flatMap(event=>event.data.inserted).find(message=>message.source?.kind==='schedule');
        if(original)writeFileSync(process.env.DSH_HOME+'/original-admission',original.id);
        return new Promise(() => setTimeout(() => process.kill(process.pid, 'SIGKILL'), 100));
      });
    }`);
    await prepareProfile(home, [{ insert: [{ id: 'flush-fault', name: fault }] }]);
    client = new RuntimeClient({ home, cwd: home });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', { protocol: 1, agents: [agent], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const task = await client.rpc.request('schedule.command', { agentId: 'gap', sessionId: binding.sessionId, action: 'create', args: { title: 'gap', prompt: 'gap', after_seconds: 1 } }) as { id: string };
    expect((await client.exited).signal).toBe('SIGKILL'); client = undefined;
    await prepareProfile(home); agent.features.cron_scheduling = false;
    client = new RuntimeClient({ home, cwd: home });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', { protocol: 1, agents: [agent], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const catalog = await client.rpc.request('schedule.command', { agentId: 'gap', action: 'catalog' });
    expect(catalog).toMatchObject([{ id: task.id }]);
    // Service recovery may already have reconciled its saved admission receipt.
    const evidence = await client.rpc.request('schedule.evidence', { sessionId: binding.sessionId });
    // Native timers may redeliver after a crash before their receipt commits.
    // The product must still expose the exact admission already persisted before the crash.
    const original = await readFile(join(home,'original-admission'),'utf8');
    expect(evidence).toEqual(expect.arrayContaining([expect.objectContaining({ scheduleId: task.id, messageId: original, trigger: 'timed', accepted: true })]));
    expect((evidence as { messageId: string }[])[0]!.messageId).toBeTruthy();
    await client.shutdown(); client = undefined;
  } finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 20_000);
