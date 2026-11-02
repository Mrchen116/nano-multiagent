import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { TrajectoryRun } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

async function fixture() {
  const home = await mkdtemp(join(tmpdir(), 'nano-run-facts-'));
  const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  const configuration = { protocol: 1, agents: [{ agentId: 'a', revision: '1', mode: 'global', provider: 'fixture', model: 'test',
    toolAllowlist: ['subagent', 'subagent_fork', 'send_message', 'fixture_drain', 'fixture_release'], knowledge: { enabled: false } }], bindings: [binding] };
  let client: RuntimeClient, logs = '';
  await writeFile(join(home, 'fixture.mjs'), `export const name='run-facts-fixture';export const inject=['llm','tools','agents','subagents'];export function apply(ctx){
    ctx.tools.register({name:'fixture_drain',description:'Release resident fixture',parameters:{type:'object',properties:{id:{type:'string'}},required:['id']},
      output:{schema:{},render:()=>[{type:'text',text:'released'}]},execute:async(args,exec)=>{await ctx.subagents.drainContinuableChildren(exec.agent,[args.id]);return {};}});
    const held=new Map();ctx.tools.register({name:'fixture_release',description:'Release fixture work',parameters:{type:'object',properties:{}},output:{schema:{},render:()=>[{type:'text',text:'released'}]},execute:async()=>{for(const release of held.values())release();held.clear();return {};}});
    const concurrent=new Map();
    const seen=new Set();
    ctx.on('llm/stream',async function*(o){
      const user=o.messages.findLast(m=>m.role==='user'&&m.source?.kind!=='runtime-context');
      const text=user?.content.find(b=>b.type==='text')?.text??'';
      const key=o.sessionId+':'+user?.id;
      if(['nested','fork-leaf'].includes(text)&&!seen.has(key))await new Promise(resolve=>{concurrent.set(text,resolve);if(concurrent.size===2)for(const ready of concurrent.values())ready();});
      if(text==='child-fail')throw new Error('controlled child failure');
      if(text==='child-cancel'){ctx.agents.get(o.sessionId).cancel({kind:'hook',reason:'controlled cancellation'});}
      if(text==='resident'){await new Promise(resolve=>held.set(o.sessionId,resolve));}
      if(text==='child-hold'){await new Promise((resolve,reject)=>{o.signal.addEventListener('abort',()=>reject(o.signal.reason),{once:true});});}
      const call=(id,name,args)=>({type:'block-end',index:id==='fork-call'?1:0,block:{type:'tool-call',id,name,arguments:JSON.stringify(args)}});
      let calls=[];
      if(!seen.has(key)){
        seen.add(key);
        if(text==='parallel')calls=[call('spawn-call','subagent',{prompt:'nested',description:'Ordinary work',run_in_background:false}),call('fork-call','subagent_fork',{prompt:'fork-leaf',description:'Fork work'})];
        if(text==='nested')calls=[call('nested-call','subagent',{prompt:'leaf',description:'Nested work',run_in_background:false})];
        if(text==='leaf')calls=[call('too-deep','subagent',{prompt:'unreachable',description:'Third level',run_in_background:false})];
        if(text==='background')calls=[call('background-call','subagent',{prompt:'resident',description:'Resident work'})];
        if(text.startsWith('wake:'))calls=[call(user.id+'-wake','send_message',{agent_id:text.slice(5),message:'resident-again'})];
        if(text==='release')calls=[call(user.id+'-release','fixture_release',{})];
        if(text.startsWith('drain:'))calls=[call(user.id+'-drain','fixture_drain',{id:text.slice(6)})];
        if(['fail','cancel','crash'].includes(text))calls=[call(text+'-call','subagent_fork',{prompt:'child-'+({fail:'fail',cancel:'cancel',crash:'hold'})[text],description:text,run_in_background:text==='crash'})];
      }
      if(calls.length){for(const item of calls)yield item;yield{type:'finish',reason:{kind:'tool-calls'}};return;}
      yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
    });
  }`);
  await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test' }], retryPolicy: { mode: 'normal', maxRetries: 0 } } } } },
    { insert: [{ id: 'run-facts-fixture', name: join(home, 'fixture.mjs') }] }]);
  const start = async (ensure = true) => {
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', configuration);
    if (ensure) await client.rpc.request('session.ensure', binding);
  };
  const prepare = (sessionId = 'root') => client.rpc.request('trajectory.prepare', { observerId: sessionId, rootAgentId: 'a', rootSessionId: 'root', sessionId, ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 });
  const runs = async (sessionId = 'root') => (await client.rpc.request('trajectory.call', { observerId: sessionId, method: 'trajectory/runs' }) as { value: TrajectoryRun[] }).value;
  let counter = 0;
  const submit = async (text: string) => {
    const inputId = `input-${++counter}`;
    await client.rpc.request('session.submit', { sessionId: 'root', inputId, mode: 'followup', content: [{ type: 'text', text }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId } });
    await expect.poll(async () => (await client.rpc.request('session.lookup', { sessionId: 'root', inputId }) as any).terminal, { timeout: 10000 }).toBeTruthy();
  };
  const events = async (sessionId: string) => sessionId === 'root' ? (await client.rpc.request('session.observe', { sessionId }) as { events: any[] }).events : (await client.rpc.request('session.descendants', { sessionId: 'root' }) as { id: string; events: any[] }[]).find(child => child.id === sessionId)!.events;
  await start(); await prepare();
  return { start, prepare, runs, submit, events, logs: () => logs, client: () => client,
    close: async () => { if (client.process.exitCode === null) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); } };
}

it('records exact ordinary/fork bounds and parallel/nested causal links, then reads them cold after restart', async () => {
  const f = await fixture();
  try {
    await f.submit('seed completed parent history');
    await f.submit('parallel');
    const runs = await f.runs();
    expect(runs, f.logs()).toHaveLength(2);
    const rootEvents = await f.events('root');
    for (const run of runs) {
      expect(run).toMatchObject({ parentSessionId: 'root', kind: 'tool', delegation: 'foreground', state: 'completed', stopReason: 'completed' });
      expect(run.launchSeq).toBe(rootEvents.find(e => e.type === 'tool/call' && e.data.callId === run.callId).seq);
      const events = await f.events(run.sessionId);
      expect(run.startSeq).toBeDefined();
      expect(events.find(e => e.type === 'subagent/descriptor').seq).toBeGreaterThanOrEqual(run.startSeq!);
      expect(events.find(e => e.type === 'user/message').seq).toBeGreaterThanOrEqual(run.startSeq!);
      expect(run.endSeq).toBe(events.at(-1).seq);
      expect(events.filter(e => e.seq >= run.startSeq!).some(e => e.type === 'user/message')).toBe(true);
    }
    const fork = runs.find(run => run.provider === 'fork')!;
    const spawn = runs.find(run => run.provider === 'spawn')!;
    expect(fork.startSeq).toBeGreaterThan(spawn.startSeq!);
    expect(fork.startSeq).toBeGreaterThan(rootEvents.find(e => e.type === 'turn/end').seq);
    expect(fork.startedAt).toBeLessThanOrEqual(spawn.endedAt!);
    expect(spawn.startedAt).toBeLessThanOrEqual(fork.endedAt!);
    await f.prepare(spawn.sessionId);
    const childRuns = await f.runs(spawn.sessionId);
    expect(childRuns).toHaveLength(2);
    expect(childRuns).toContainEqual(spawn);
    const nested = childRuns.find(run => run.runId !== spawn.runId)!;
    expect(nested).toMatchObject({ parentSessionId: spawn.sessionId, callId: 'nested-call', state: 'completed' });
    await f.prepare(nested.sessionId);
    expect(await f.runs(nested.sessionId)).toEqual([nested]);
    const depthLimit = (await f.events(nested.sessionId)).find(event => event.type === 'tool/result' && event.data.message.toolCallId === 'too-deep');
    expect(depthLimit.data.message.isError).toBe(true);
    expect(JSON.stringify(depthLimit.data.message)).toMatch(/depth/i);
    await f.client().shutdown(); await f.start(false); await f.prepare();
    expect(await f.runs()).toEqual(runs);
    await f.prepare(spawn.sessionId); expect(await f.runs(spawn.sessionId)).toEqual(childRuns);
  } catch (error) { throw new Error(`${error}\n${f.logs()}`, { cause: error }); }
  finally { await f.close(); }
}, 30000);

it('keeps a continuable residency open across messages and records separate cold-wake epochs', async () => {
  const f = await fixture();
  try {
    await f.submit('background');
    const [first] = await f.runs();
    expect(first).toMatchObject({ kind: 'tool', delegation: 'background', state: 'running', callId: 'background-call' });
    expect(first!.endSeq).toBeUndefined();
    await f.submit(`wake:${first!.sessionId}`);
    expect(await f.runs()).toEqual([first]);
    await f.submit('release');
    await expect.poll(async () => (await f.runs())[0]?.state).toBe('completed');
    const [ended] = await f.runs();
    expect(ended).toMatchObject({ runId: first!.runId, state: 'completed' });
    expect(ended!.endSeq).toBe((await f.events(first!.sessionId)).at(-1).seq);
    await f.submit(`wake:${first!.sessionId}`);
    const repeated = await f.runs();
    expect(repeated).toHaveLength(2);
    const second = repeated.find(run => run.runId !== first!.runId)!;
    expect(second).toMatchObject({ sessionId: first!.sessionId, kind: 'tool', delegation: 'background' });
    expect(second.startSeq).toBeGreaterThan(ended!.endSeq!);
    expect(second.launchSeq).toBeGreaterThan(first!.launchSeq!);
    await f.submit(`drain:${first!.sessionId}`);
    expect((await f.runs()).every(run => run.state === 'completed')).toBe(true);
  } catch (error) { throw new Error(`${error}\n${f.logs()}`, { cause: error }); }
  finally { await f.close(); }
}, 30000);

it('preserves failed/cancelled terminals and reports a killed process run as unknown on restart', async () => {
  const f = await fixture();
  try {
    await f.submit('fail'); await f.submit('cancel');
    expect((await f.runs()).map(run => [run.stopReason, run.state])).toEqual([['error', 'failed'], ['aborted', 'cancelled']]);
    await f.submit('crash');
    await expect.poll(async () => (await f.runs()).length).toBe(3);
    const before = await f.runs();
    expect(before.at(-1)).toMatchObject({ state: 'running', delegation: 'background' });
    f.client().process.kill('SIGKILL'); await f.client().exited;
    await f.start(false); await f.prepare();
    expect(await f.runs()).toEqual(before.map(run => run.state === 'running' ? { ...run, state: 'unknown' } : run));
  } catch (error) { throw new Error(`${error}\n${f.logs()}`, { cause: error }); }
  finally { await f.close(); }
}, 30000);
