import {createServer} from 'node:http';
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

it('recycles a live process with stalled asynchronous FS and retains old and new input identities', async () => {
  const {writeFile} = await import('node:fs/promises');
  const home=await mkdtemp(join(tmpdir(),'nano-fs-stall-'));
  const binding={sessionId:'fs-recover',agentId:'test',revision:'1',ownerId:'owner',cwd:home};
  let generations=0;const errors:string[]=[];const requests:string[]=[];
  const server=createServer(async(req,res)=>{
    let body='';for await(const chunk of req)body+=chunk;requests.push(body);
    res.writeHead(200,{'content-type':'text/event-stream'});
    res.end('data: '+JSON.stringify({id:'fixture',object:'chat.completion.chunk',choices:[{index:0,delta:{role:'assistant',content:'recovered both inputs'},finish_reason:null}]})+'\n\ndata: '+JSON.stringify({id:'fixture',object:'chat.completion.chunk',choices:[{index:0,delta:{},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n');
  });
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=(server.address() as {port:number}).port;
  const supervisor=new RuntimeSupervisor({home,cwd:home,env:{NANO_FS_TEST_KEY:'fixture'},health:{tickMs:25,intervalMs:50,timeoutMs:500},
    initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[{agentId:'test',revision:'1',provider:'fixture',model:'fixture',toolAllowlist:[],features:{dreaming:false}}],bindings:[binding]});await rpc.request('session.ensure',binding);},
    onReady:async()=>{generations++;},onError:error=>errors.push(String(error))});
  supervisor.handle('product.task_context.prepare',()=>({messages:[],revoked:[]}));
  supervisor.handle('product.task_context.commit',()=>null);
  supervisor.handle('product.task_execution.snapshot',()=>({kind:'quiescent',tasks:[],repair_task_ids:[]}));
  try {
    // Patch only the test subprocess's public builtin. The second process can
    // read normally; stdio and JavaScript remain responsive in the stalled one.
    await writeFile(join(home,'fs-fixture.mjs'), `import fs from 'node:fs';import fsp from 'node:fs/promises';import {syncBuiltinESMExports} from 'node:module';
      const marker=${JSON.stringify(join(home,'stall'))}; const recovered=fs.existsSync(marker); if(recovered)fs.unlinkSync(marker);
      const stat=fsp.stat; fsp.stat=function(...args){if(!recovered&&fs.existsSync(marker))return new Promise(()=>{});return stat(...args)};syncBuiltinESMExports();export function apply(){}`);
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:`http://127.0.0.1:${port}/v1`,apiKeyEnv:'NANO_FS_TEST_KEY',models:[{id:'fixture',contextWindow:100000}]}}}},{insert:[{id:'fs-fixture',name:join(home,'fs-fixture.mjs')}]}]);
    await supervisor.start();const pid=supervisor.process!.pid;
    const submit=(id:string,mode='inject')=>supervisor.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode,content:[{type:'text',text:id}],source:{kind:'system',actorId:'owner',channel:'inbox',messageId:id}});
    await submit('original-task');
    await writeFile(join(home,'stall'),'1');
    await expect.poll(()=>generations,{timeout:15000}).toBe(2);
    expect(supervisor.process!.pid).not.toBe(pid);
    expect(errors.some(error=>error.includes('filesystem health'))).toBe(true);
    expect(await supervisor.request('session.lookup',{sessionId:binding.sessionId,inputId:'original-task'})).toMatchObject({accepted:true,pending:true});
    await submit('new-inbox','followup');
    await expect.poll(async()=>{const result:any=await supervisor.request('session.lookup',{sessionId:binding.sessionId,inputId:'new-inbox'});if(result.terminal?.kind==='error')throw new Error(JSON.stringify(result.terminal));return result;},{timeout:10000}).toMatchObject({accepted:true,terminal:{kind:'completed'}});
    expect(requests.some(body=>body.includes('original-task')&&body.includes('new-inbox'))).toBe(true);
  } finally {await supervisor.shutdown();server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));await rm(home,{recursive:true,force:true});}
},30000);

it('cleans up a runtime when onReady fails', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-ready-failed-'));let unavailable=0;
  const supervisor=new RuntimeSupervisor({home,cwd:home,
    initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents:[],bindings:[]});},
    onReady:async()=>{throw new Error('recovery failed');},onUnavailable:async()=>{unavailable++;},onError:()=>{}});
  try {await prepareProfile(home);await expect(supervisor.start()).rejects.toThrow('recovery failed');expect(supervisor.available).toBe(false);expect(unavailable).toBe(1);expect(supervisor.process!.exitCode!==null||supervisor.process!.signalCode!==null).toBe(true);}
  finally {await supervisor.shutdown();await rm(home,{recursive:true,force:true});}
},15000);
