import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { expect, it, vi } from 'vitest';
import { apply } from '../src/features/memory-curation.js';
import { KnowledgeFiles } from '../src/knowledge/files.js';
import { reviewReadings } from '../src/knowledge/review-readings.js';

it('freezes memory lazily, inherits the fork snapshot, refreshes after compaction and never reads while disabled', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-memory-freeze-'));
  try {
    await mkdir(join(home, '.nanoassistant/memory'), { recursive: true });
    const file = join(home, '.nanoassistant/memory/MEMORY.md');
    await writeFile(file, 'BEFORE');
    const handlers = new Map<string, (...args: any[]) => any>();
    const files = new KnowledgeFiles(home);
    const read = vi.spyOn(files, 'memoryText');
    let enabled = true;
    const events: any[] = [];
    const parent = { session: { header: {}, snapshotEvents: () => events } } as unknown as Agent;
    const child = { session: { header: { parentSession: 'parent' }, snapshotEvents: () => events } } as unknown as Agent;
    apply({ on: (name: string, handler: (...args: any[]) => any) => handlers.set(name, handler),
      agents: { get: () => parent }, tools: { register: () => {} },
      nanoKnowledge: { subscribe: () => {}, config: () => ({ features: { memory_curation: enabled } }), files: () => files },
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
    { type: 'tool/call', data: { name: 'memory', callId: 'memory' } },
    { type: 'tool/result', data: { message: { toolCallId: 'memory', isError: true } } });
  expect(reviewReadings(events, 'memory')).toEqual({ current: 2, maintained: 0 });
  events.push({ type: 'tool/result', data: { message: { toolCallId: 'memory', isError: false } } }, { type: 'turn/end' });
  expect(reviewReadings(events, 'memory')).toEqual({ current: 2, maintained: 2 });
  expect(reviewReadings(events, 'skills')).toEqual({ current: 3, maintained: 0 });
  events.push({ type: 'tool/call', data: { name: 'skill_manage', callId: 'skill' } },
    { type: 'tool/result', data: { message: { toolCallId: 'skill', isError: false } } });
  expect(reviewReadings(events, 'skills')).toEqual({ current: 3, maintained: 3 });
});

it('retries a failed native review without spending the interval, then resets on completion', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-review-failure-'));
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), `export const name='review-failure';export const inject=['llm'];
export function apply(ctx){let failed=false;ctx.on('llm/stream',async function*(o){
 const review=o.messages.some(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&b.text.startsWith('Review the conversation')));
 if(review&&!failed){failed=true;throw new Error('intentional fixture failure');}
 yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home, [{ id:'llm-pi-ai', config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}],retryPolicy:{mode:'normal',maxRetries:0}}}} }, {insert:[{id:'review-failure',name:join(home,'fixture.mjs')}]}]);
    const config = {agentId:'a',revision:'1',provider:'fixture',model:'test',features:{memory_curation:true,skill_creation:false},knowledge:{memoryInterval:2},toolAllowlist:['memory']};
    const binding = {sessionId:'review-failure',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit = async (id: string) => {
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal).toBeTruthy();
    };
    const reviews = async () => (await client!.rpc.request('knowledge.facts',{}) as {reviews:{status:string}[]}).reviews;
    await submit('one'); expect(await reviews()).toHaveLength(0);
    await submit('two');
    await expect.poll(async()=>(await reviews()).filter(row=>row.status==='error').length).toBe(1);
    await submit('three');
    await expect.poll(async()=>(await reviews()).filter(row=>row.status==='completed').length).toBe(1);
    await submit('four'); expect(await reviews()).toHaveLength(2);
    await client.shutdown(); client=undefined;
  } catch(error) {throw new Error(`${error}\n${logs}`,{cause:error});}
  finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
}, 20000);
