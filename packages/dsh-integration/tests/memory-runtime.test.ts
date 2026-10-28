import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';

it('uses current documents in consecutive real runtime requests without a memory feature or legacy tool', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-document-runtime-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const entry = join(home, '.nanoassistant/memory/MEMORY.md');
  const page = join(home, '.nanoassistant/memory/knowledge/preferences.md');
  const calls = [['read', { file_path: entry }], ['read', { file_path: page }], ['write', { file_path: page, content: 'Private updates only; urgent incidents may interrupt.' }], ['write', { file_path: entry, content: '# Expert memory\n\n[Preferences](knowledge/preferences.md): private updates, with urgent incident exception.' }], ['memory_maintenance', { action: 'checkpoint', generation: 0 }]];
  const {Context}=await import('@deepseek-ai/cordis');
  const {LocalFileSystem}=await import('@deepseek-ai/dsh-fs-local');
  const {MemoryDocuments}=await import('../src/knowledge/memory-documents.js');
  const seed=await MemoryDocuments.open(home,'expert',new LocalFileSystem(new Context(),{cwd:home,diffBasisMaxBytes:10485760}));
  await seed.apply({operationId:'unrelated',path:'knowledge/unrelated.md',beforeHash:null,content:'An unrelated already verified topic.'});
  await seed.checkpoint(await seed.versions(),0); await seed.close();
  await writeFile(join(home, 'fixture.mjs'), `import {appendFileSync} from 'node:fs'; export const name='memory-fixture'; export const inject=['llm']; export function apply(ctx) { const steps=new Map(); ctx.on('llm/stream',async function*(o) { appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n'); const last=o.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&m.source.actorId);const n=steps.get(last?.id)||0;steps.set(last?.id,n+1);const calls=${JSON.stringify(calls)};if(last?.content.some(b=>b.text==='learn')&&n<calls.length){const [name,args]=calls[n];yield {type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield {type:'finish',reason:{kind:'tool-calls'}};}else{yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};} }); }`);
  try {
    await prepareProfile(home, [{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}}, {insert:[{id:'memory-fixture',name:join(home,'fixture.mjs')}]}]);
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    const binding={sessionId:'memory-root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',provider:'fixture',model:'test',features:{dreaming:false,memory_curation:false,skill_creation:false},toolAllowlist:['read','write','edit','memory','memory_maintenance']}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit = async (id: string) => {
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal,{timeout:8000}).toBeTruthy();
    };
    await submit('learn');
    const observed=await client.rpc.request('session.observe',{sessionId:binding.sessionId}) as {events:any[]};
    const checkpoint=observed.events.find(e=>e.type==='tool/result'&&e.data.message.toolCallId==='learn-4');
    expect(JSON.stringify(observed)).toContain('synchronized');
    expect(JSON.stringify(observed)).toContain('Document receipt:');
    expect(await readFile(page,'utf8')).toContain('urgent incidents');
    await writeFile(page,'Never interrupt, including urgent incidents.');
    await submit('use-new-memory');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const latest=requests.at(-1);
    expect(JSON.stringify(requests)).toContain('Document receipt:');
    expect(JSON.stringify(requests)).toContain('versionRecorded');
    expect(latest.tools.map((tool:any)=>tool.name)).not.toContain('memory');
    expect(JSON.stringify(latest.messages)).toContain('entry_basis_stale');
    expect(JSON.stringify(latest.messages)).toContain('knowledge/preferences.md');
    expect(JSON.stringify(latest.messages)).toContain('built-in skill-creator');
    expect((await client.rpc.request('knowledge.facts',{}) as {reviews:unknown[]}).reviews).toEqual([]);
    await client.shutdown();client=undefined;
  } catch(error) { throw new Error(`${String(error)}\n${logs}`,{cause:error}); }
  finally { if(client){client.process.kill('SIGKILL');await client.exited;} await rm(home,{recursive:true,force:true}); }
},20000);
