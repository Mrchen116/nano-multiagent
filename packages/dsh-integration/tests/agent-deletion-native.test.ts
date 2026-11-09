import { access, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { RuntimeClient, prepareProfile } from '../src/client.js';
import type { SessionDeletionPlan } from '../src/agent-deletion.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('purges cold A history and projection cache while B executes and reads in the same ordinary DSH host', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-delete-runtime-'));
  const agents = ['a', 'b'].map(agentId => ({
    agentId, workspace: home, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash',
    knowledge: {memoryMode: 'legacy'}, features: {task_graph: false, memory_curation: false, skill_creation: false},
  }));
  const bindings = agents.map(({agentId}) => ({sessionId: `root-${agentId}`, agentId, revision: '1', ownerId: 'owner', cwd: home}));
  const operation = {agentId: 'a', revision: 2, operationId: 'delete-a'};
  const submit = (sessionId: string, inputId: string, mode: 'followup' | 'inject') => ({
    sessionId, inputId, mode, content: [{type: 'text', text: inputId}],
    source: {kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId},
  });
  let runtime: RuntimeClient | undefined;
  let logs = '';
  const file = (name: string) => join(home, name);
  const start = async (disabled = false) => {
    runtime = new RuntimeClient({home, cwd: home, onLog: text => {logs += text;}});
    registerNoopTaskHosts(runtime);
    expect(await runtime.rpc.request('initialize', {
      protocol: 1, agents, bindings, lifecycle: disabled ? {a: {revision: 2, disabled: true, disabledThroughRevision: 2}} : undefined,
    })).toMatchObject({agentDeletion: true});
    return runtime.rpc;
  };
  const kill = async () => {
    if (runtime && runtime.process.exitCode === null) {
      runtime.process.kill('SIGKILL');
      await runtime.exited;
    }
    runtime = undefined;
  };
  try {
    await writeFile(file('fixture.mjs'), `
      import {access,writeFile} from 'node:fs/promises';
      const home=process.env.DSH_HOME;
      export const inject=['llm','sessionProjectionCache','sessionPersistence'];
      export function apply(ctx) {
        ctx.on('llm/stream', async function*(o) {
          if (o.sessionId==='root-b') {
            await writeFile(home+'/b-started','');
            while (!o.signal.aborted && !await access(home+'/b-release').then(()=>true,()=>false))
              await new Promise(resolve=>setTimeout(resolve,20));
            o.signal.throwIfAborted();
          }
          yield {type:'text',text:'finished'};
          yield {type:'finish',reason:{kind:'stop'}};
        });
        ctx.on('session/event', (session,event)=>{
          if(session.id==='root-a' && event.type==='turn/end')
            void ctx.sessionProjectionCache.write(session).then(()=>writeFile(home+'/a-cached','')).catch(err=>writeFile(home+'/fixture-error',String(err)));
        });
      }
    `);
    await prepareProfile(home, [{insert: [{id: 'deletion-fixture', name: file('fixture.mjs')}]}], {agentDeletion: true});
    const rpc = await start();
    for (const binding of bindings) await rpc.request('session.ensure', binding);
    await expect(rpc.request('agent.deletion.plan', operation)).rejects.toThrow('stop has not been confirmed');
    await rpc.request('session.submit', submit('root-a', 'a-initial', 'followup'));
    await expect.poll(() => access(file('a-cached')).then(() => true, () => false), {timeout: 5000}).toBe(true);
    await rpc.request('session.export', {sessionId: 'root-a'});
    await rpc.request('session.submit', submit('root-b', 'b-initial', 'followup'));
    await expect.poll(() => access(file('b-started')).then(() => true, () => false), {timeout: 5000}).toBe(true);
    const pid = runtime!.process.pid;
    await expect(rpc.request('agent.disable', operation)).resolves.toMatchObject({confirmed: true});
    const plan = await rpc.request('agent.deletion.plan', operation) as SessionDeletionPlan;
    expect(plan.sessionIds).toEqual(['root-a']);
    const [target] = plan.entries;
    expect(target!.artifacts.length).toBeGreaterThan(0);
    const log = join(home, 'sessions', target!.directory, target!.artifacts[0]!.name);
    const cache = file('storages/session_projcache/sessions/root-a.json');
    await expect(access(log)).resolves.toBeUndefined();
    await expect(access(cache)).resolves.toBeUndefined();
    const purge = rpc.request('agent.deletion.purge', {...operation, plan});
    await expect(rpc.request('session.submit', submit('root-b', 'b-new', 'inject'))).resolves.toMatchObject({accepted: true});
    await expect(rpc.request('session.observe', {sessionId: 'root-b'})).resolves.toMatchObject({events: expect.any(Array)});
    await expect(purge).resolves.toMatchObject({purged: true, sessionIds: ['root-a']});
    await expect(access(log)).rejects.toHaveProperty('code', 'ENOENT');
    await expect(access(cache)).rejects.toHaveProperty('code', 'ENOENT');
    await expect(access(file('exports/cm9vdC1h.jsonl'))).rejects.toHaveProperty('code', 'ENOENT');
    expect(await readdir(file('deletion-staging'))).toEqual([]);
    await expect(rpc.request('session.observe', {sessionId: 'root-a'})).rejects.toThrow();
    expect(runtime!.process.pid).toBe(pid);
    await writeFile(file('b-release'), '');
    await expect.poll(async () => {
      const observed = await rpc.request('session.observe', {sessionId: 'root-b'}) as {events: {type: string}[]};
      return observed.events.some(event => event.type === 'turn/end');
    }, {timeout: 5000}).toBe(true);
    await kill();
    const restarted = await start(true);
    await expect(restarted.request('agent.deletion.purge', {...operation, plan})).resolves.toMatchObject({purged: true});
    await expect(restarted.request('agent.enable', {...operation, revision: 3})).rejects.toThrow('being deleted');
    await expect(restarted.request('session.observe', {sessionId: 'root-b'})).resolves.toMatchObject({events: expect.any(Array)});
  } catch (error) {
    const fixture = await readFile(file('fixture-error'), 'utf8').catch(() => '');
    throw new Error(`${String(error)}\n${fixture}\n${logs}`, {cause: error});
  } finally {
    await kill();
    await rm(home, {recursive: true, force: true});
  }
}, 30_000);
