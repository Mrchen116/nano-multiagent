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

it('reports a cleanup deadline without killing or replacing the shared host', async () => {
  const { writeFile } = await import('node:fs/promises');
  const home=await mkdtemp(join(tmpdir(),'nano-disable-deadline-'));
  const supervisor=new RuntimeSupervisor({home,cwd:home,stopTimeoutMs:200,
    initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[],bindings:[]});},
    onReady:async()=>{},onError:()=>{},
  });
  try {
    await writeFile(join(home,'block.mjs'), `export function apply(ctx){setTimeout(()=>{while(true){}},1500);}`);
    await prepareProfile(home,[{insert:[{id:'block',name:join(home,'block.mjs')}]}]);
    await supervisor.start();
    const pid=supervisor.process!.pid,id=supervisor.processInstanceId;
    await new Promise(resolve=>setTimeout(resolve,1600));
    const started=Date.now();const result=await supervisor.disableAgent('a',2);
    expect(result.confirmed).toBe(false);
    expect(Date.now()-started).toBeLessThan(800);
    expect(supervisor.available).toBe(true);
    expect(supervisor.process!.pid).toBe(pid);expect(supervisor.process!.signalCode).toBeNull();
    expect(await supervisor.disableAgent('a',2)).toEqual(result);
    expect(supervisor.processInstanceId).toBe(id);
  } finally {const closing=supervisor.shutdown().catch(()=>{});supervisor.process?.kill('SIGKILL');await closing;await rm(home,{recursive:true,force:true});}
},10000);
