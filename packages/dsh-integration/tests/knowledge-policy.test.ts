import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { expect, it, vi } from 'vitest';
import { apply } from '../src/features/memory-curation.js';
import { KnowledgeFiles } from '../src/knowledge/files.js';
import { reviewReadings } from '../src/knowledge/review-readings.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('freezes memory lazily, inherits the fork snapshot, refreshes after compaction and never reads while disabled', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-memory-freeze-'));
  try {
    await mkdir(join(home, '.nanoassistant/memory-legacy'), { recursive: true });
    const file = join(home, '.nanoassistant/memory-legacy/MEMORY.md');
    await writeFile(file, 'BEFORE');
    const handlers = new Map<string, (...args: any[]) => any>();
    const files = new KnowledgeFiles(home, undefined, 'memory-legacy');
    const read = vi.spyOn(files, 'memoryText');
    let enabled = true;
    const events: any[] = [];
    const parent = { session: { header: {}, snapshotEvents: () => events } } as unknown as Agent;
    const child = { session: { header: { parentSession: 'parent' }, snapshotEvents: () => events } } as unknown as Agent;
    apply({ on: (name: string, handler: (...args: any[]) => any) => handlers.set(name, handler),
      agents: { get: () => parent }, tools: { register: () => {} },
      nanoKnowledge: { subscribe: () => {}, config: () => ({ knowledge: { memoryMode: enabled ? 'legacy' : 'document' } }), files: () => files },
    } as unknown as Context, { agentId: 'a' });
    const assemble = (agent = parent) => handlers.get('system-prompt/assemble')!({}, { scope: agent }, async () => ({ contexts: [] }));
    expect(read).not.toHaveBeenCalled();
    expect(JSON.stringify(await assemble())).toContain('BEFORE');
    await writeFile(file, 'AFTER');
    expect(JSON.stringify(await assemble())).not.toContain('AFTER');
    handlers.get('agent/created')!({ agent: child });
    expect(JSON.stringify(await assemble(child))).toContain('BEFORE');
    expect(read).toHaveBeenCalledTimes(2);
    events.push({ type: 'compaction/end', seq: 7 });
    expect(JSON.stringify(await assemble())).toContain('AFTER');
    expect(read).toHaveBeenCalledTimes(4);
    enabled = false;
    expect((await assemble()).contexts).toEqual([]);
    expect(read).toHaveBeenCalledTimes(4);
    enabled = true;
    const fresh = { session: { header: {}, snapshotEvents: () => [] } } as unknown as Agent;
    expect(JSON.stringify(await assemble(fresh))).toContain('AFTER');
  } finally { await rm(home, { recursive: true, force: true }); }
});

it('counts a parallel tool round once and resets only successful foreground maintenance in its own turn', () => {
  const events: any[] = [
    { type: 'turn/start' }, { type: 'step/start' },
    ...['a', 'b', 'c'].map(callId => ({ type: 'tool/call', data: { name: 'read', callId } })),
    { type: 'step/start' }, { type: 'turn/end' },
  ];
  expect(reviewReadings(events, 'skills')).toEqual({ current: 2, maintained: 0 });
  events.push({ type: 'turn/start' }, { type: 'step/start' },
    { type: 'tool/call', data: { name: 'memory', callId: 'memory', arguments: '{"action":"add"}' } },
    { type: 'tool/result', data: { message: { toolCallId: 'memory', isError: true } } });
  expect(reviewReadings(events, 'memory')).toEqual({ current: 2, maintained: 0 });
  events.push({ type: 'tool/result', data: { message: { toolCallId: 'memory', isError: false } } }, { type: 'turn/end' });
  expect(reviewReadings(events, 'memory')).toEqual({ current: 2, maintained: 2 });
  expect(reviewReadings(events, 'skills')).toEqual({ current: 3, maintained: 0 });
  events.push({ type: 'tool/call', data: { name: 'skill_manage', callId: 'skill', arguments: '{"action":"patch"}' } },
    { type: 'tool/result', data: { message: { toolCallId: 'skill', isError: false } } });
  expect(reviewReadings(events, 'skills')).toEqual({ current: 3, maintained: 3 });
});

it.each(['provider', 'step-limit'])('preserves native %s failure after partial reads and retries without spending the interval', async (failure) => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-review-failure-'));
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), `export const name='review-failure';export const inject=['llm'];
export function apply(ctx){let first;let reads=0;ctx.on('llm/stream',async function*(o){
 const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));
 const review=last.content.some(b=>b.type==='text'&&b.text.startsWith('Review the conversation'));
 if(review){first??=last.id;if(last.id===first){
  if(reads++>0&&${JSON.stringify(failure)}==='provider')throw new Error('intentional fixture failure');
  yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+reads,name:'read',arguments:JSON.stringify({file_path:${JSON.stringify(join(home, '.nanoassistant/memory-legacy/USER.md'))}})}};
  yield{type:'finish',reason:{kind:'tool-calls'}};return;
 }}
 yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home, [{ id:'llm-pi-ai', config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}],retryPolicy:{mode:'normal',maxRetries:0}}}} }, {insert:[{id:'review-failure',name:join(home,'fixture.mjs')}]}]);
    const config = {agentId:'a',revision:'1',provider:'fixture',model:'test',mode:'global',features:{memory_curation:true,skill_creation:false},knowledge:{memoryMode:'legacy',legacyMemory:{enabled:true,interval:2}},toolAllowlist:['read','memory']};
    const binding = {sessionId:'review-failure',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit = async (id: string) => {
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal).toBeTruthy();
    };
    const reviews = async () => (await client!.rpc.request('knowledge.facts',{}) as {reviews:{status:string;diagnostic?:string}[]}).reviews;
    await submit('one'); expect(await reviews()).toHaveLength(0);
    await submit('two');
    const status = failure === 'provider' ? 'error' : 'aborted';
    // Native step-limit cancellation settles after several tool steps; do not race its async receipt.
    await expect.poll(async()=>(await reviews()).filter(row=>row.status===status).length,{timeout:8000}).toBe(1);
    expect((await reviews())[0]?.diagnostic).not.toBe('memory_read_incomplete');
    await client.rpc.request('trajectory.prepare',{observerId:binding.sessionId,rootAgentId:'a',rootSessionId:binding.sessionId,sessionId:binding.sessionId,ownerId:'owner',nodeId:'node',nodeEpoch:1});
    const runs=await client.rpc.request('trajectory.call',{observerId:binding.sessionId,method:'trajectory/runs'}) as {value:{stopReason:string;state:string}[]};
    expect(runs.value).toEqual([expect.objectContaining({stopReason:status,state:failure==='provider'?'failed':'cancelled'})]);
    await submit('three');
    await expect.poll(async()=>(await reviews()).filter(row=>row.status==='completed').length,{timeout:8000}).toBe(1);
    await submit('four'); expect(await reviews()).toHaveLength(2);
    await client.shutdown(); client=undefined;
  } catch(error) {throw new Error(`${error}\n${logs}`,{cause:error});}
  finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
}, 20000);

it('requires complete current raw files, accumulates pages and advances only confirmed writes', async () => {
  const { ReviewFiles } = await import('../src/knowledge/review-files.js');
  const home=await mkdtemp(join(tmpdir(),'nano-review-reads-')); const files=new KnowledgeFiles(home,join(home,'shared'));
  const path=join(files.skillRoot,'verified/SKILL.md');
  const text='---\nname: verified\ndescription: A verified method\n---\nOriginal method.';
  const user=join(files.memoryRoot,'USER.md'), memory=join(files.memoryRoot,'MEMORY.md');
  const reads=new ReviewFiles(home,[user,memory],[files.skillRoot]);
  const guard={reads,check:()=>{}};
  const observe=(file:string,content:string,offset=1,limit=100)=>{
    const all=content.split('\n');const lines=all.slice(offset-1,offset-1+limit).map((text,i)=>({number:offset+i,text}));
    reads.observe({name:'read',arguments:{file_path:file}} as any,{isError:false,value:{path:file,totalLines:all.length,lines},content:[{type:'text',text:lines.map(l=>l.text).join('\n')}]});
  };
  const patch={action:'patch' as const,name:'verified',old_string:'Original method.',new_string:'Verified method.'};
  try {
    await files.skill({action:'create',name:'verified',content:text},'F3');
    await expect(files.skill(patch,'F3',undefined,guard)).rejects.toThrow('complete original');
    observe(path,text,1,2);
    await expect(files.skill(patch,'F3',undefined,guard)).rejects.toThrow('complete original');
    observe(path,text,3);
    await writeFile(path,text.replace('Original','Changed'));
    await expect(files.skill(patch,'F3',undefined,guard)).rejects.toThrow('changed after');
    observe(path,text.replace('Original','Changed'));
    await files.skill({...patch,old_string:'Changed method.'},'F3',undefined,guard);
    await files.skill({...patch,old_string:'Verified method.',new_string:'Final method.'},'F3',undefined,guard);
    await expect(files.skill({...patch,action:'edit',content:text},'F4',undefined,{...guard,target:{root:files.skillRoot,name:'verified'}})).rejects.toThrow('only patch');
    const target = {...guard,target:{root:files.skillRoot,name:'verified'}};
    for (const action of ['create','write_file','remove_file'] as const) {
      await expect(files.skill({...patch,action,content:text},'F4',undefined,target)).rejects.toThrow('only patch');
    }
    await expect(files.skill({...patch,name:'other'},'F4',undefined,target)).rejects.toThrow('only patch');
    await files.skill({action:'create',scope:'global',name:'verified',content:text},'F3');
    await expect(files.skill({...patch,scope:'global'},'F4',undefined,target)).rejects.toThrow('only patch');
    // Source can change after selection; the write boundary must recheck it.
    const usagePath=join(files.skillRoot,'.usage.json');
    const usage=JSON.parse(await readFile(usagePath,'utf8'));
    usage.verified.source='F1';await writeFile(usagePath,JSON.stringify(usage));
    await expect(files.skill({...patch,old_string:'Final method.'},'F4',undefined,target)).rejects.toThrow('manual or unknown-source');
    expect(await readFile(path,'utf8')).toContain('Final method.');
    expect(await readFile(join(home,'shared/verified/SKILL.md'),'utf8')).toBe(text);
    const support=join(files.skillRoot,'verified/references/guide.md');
    await files.skill({action:'write_file',name:'verified',file_path:'references/guide.md',file_content:''},'F1');
    await expect(files.skill({action:'remove_file',name:'verified',file_path:'references/guide.md'},'F3',undefined,guard)).rejects.toThrow('complete original');
    reads.observe({name:'read',arguments:{file_path:support}} as any,{isError:false,value:{path:support,totalLines:0,lines:[]},content:[{type:'text',text:'empty file'}]});
    await files.skill({action:'remove_file',name:'verified',file_path:'references/guide.md'},'F3',undefined,guard);
    // A denied read cannot confirm absence, even when the file is absent on disk.
    reads.observe({name:'read',arguments:{file_path:user}} as any,{isError:true,error:{message:'denied',info:{code:'FS_PERMISSION_DENIED'}},content:[]} as any);
    expect(reads.memoryIncomplete).toBe(true);
    for(const file of [user,memory]) reads.observe({name:'read',arguments:{file_path:file}} as any,{isError:true,error:{message:'not found',info:{code:'FS_NOT_FOUND'}},content:[]} as any);
    expect(reads.memoryIncomplete).toBe(false);
  }finally{await rm(home,{recursive:true,force:true});}
});
