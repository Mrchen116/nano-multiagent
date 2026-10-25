import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeSupervisor } from '../src/client.js';

it('keeps the node port stable across a runtime crash and recovers persisted input without replay', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-supervisor-'));
  const binding = { sessionId: 'recover', agentId: 'test', revision: '1', ownerId: 'owner', cwd: join(home, 'workspace') };
  let recovered!: () => void;
  const restarted = new Promise<void>(resolve => { recovered = resolve; });
  let generations = 0;
  const supervisor = new RuntimeSupervisor({ home, cwd: home,
    initialize: async rpc => {
      await rpc.request('initialize', { protocol: 1, agents: [{ agentId: 'test', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash' }], bindings: [binding] });
      await rpc.request('session.ensure', binding);
    },
    onReady: async () => { if (++generations === 2) recovered(); },
    onError: () => {},
  });
  try {
    await prepareProfile(home);
    await supervisor.start();
    const pid = supervisor.process!.pid;
    await supervisor.request('session.submit', { sessionId: 'recover', inputId: 'one', mode: 'inject',
      content: [{ type: 'text', text: 'retained' }], source: { kind: 'system', actorId: 'owner', channel: 'test', messageId: 'one' } });
    supervisor.process!.kill('SIGKILL');
    await restarted;
    expect(supervisor.process!.pid).not.toBe(pid);
    expect(await supervisor.request('session.lookup', { sessionId: 'recover', inputId: 'one' })).toMatchObject({ accepted: true, pending: true });
  } finally {
    await supervisor.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);

it('fences a pending launch synchronously and requires explicit enable for a new process identity', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-disable-start-'));
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let initialized!: () => void;
  const reached = new Promise<void>(resolve => { initialized = resolve; });
  let ready = 0;
  const supervisor = new RuntimeSupervisor({ home, cwd: home,
    initialize: async rpc => { await rpc.request('initialize', {protocol:1,agents:[],bindings:[]}); initialized(); await held; },
    onReady: async () => { ready++; }, onError: () => {},
  });
  try {
    await prepareProfile(home);
    const starting = supervisor.start();
    await reached;
    const id = supervisor.processInstanceId;
    const stopped = supervisor.disable();
    expect(supervisor.available).toBe(false);
    release();
    await starting;
    expect(await stopped).toMatchObject({confirmed:true,processInstanceId:id});
    expect(ready).toBe(0);
    await expect(supervisor.start()).rejects.toThrow('disabled');
    supervisor.enable();
    await supervisor.start();
    expect(supervisor.processInstanceId).not.toBe(id);
    expect(ready).toBe(1);
  } finally { release(); await supervisor.shutdown(); await rm(home,{recursive:true,force:true}); }
}, 30_000);

it('does not claim cleanup when the runtime event loop is blocked and preserves the failed stop across retry', async () => {
  const { writeFile } = await import('node:fs/promises');
  const home=await mkdtemp(join(tmpdir(),'nano-disable-deadline-'));
  const supervisor=new RuntimeSupervisor({home,cwd:home,stopTimeoutMs:200,
    initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[],bindings:[]});},
    onReady:async()=>{},onError:()=>{},
  });
  try {
    await writeFile(join(home,'block.mjs'), `export function apply(ctx){setTimeout(()=>{while(true){}},1500);}`);
    await prepareProfile(home,[{insert:[{id:'block',name:join(home,'block.mjs')}]}]);
    await supervisor.start(); supervisor.enable();
    await new Promise(resolve=>setTimeout(resolve,1600));
    const started=Date.now();const result=await supervisor.disable();
    expect(result.confirmed).toBe(false);
    expect(Date.now()-started).toBeLessThan(800);
    expect(supervisor.available).toBe(false);
    expect(await supervisor.disable()).toEqual(result);
    await expect(supervisor.start()).rejects.toThrow('disabled');
  } finally {supervisor.process?.kill('SIGKILL');await rm(home,{recursive:true,force:true});}
},10000);
