import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { PersonalMemoryStore } from '../src/knowledge/personal-memory.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('refreshes corrected PA memory at the next model request and fences forgotten context across restart', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-pa-memory-context-'));
  let client: InstanceType<typeof RuntimeClient> | undefined, logs = '';
  const secret = 'SUNFLOWER-PRIVATE-17';
  const store = new PersonalMemoryStore(home, { agentId: 'pa', ownerId: 'owner', bindingId: 'binding' });
  const requests = async () => (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
  try {
    await writeFile(join(home, 'fixture.mjs'), `import{readFileSync,appendFileSync}from'node:fs';
export const name='memory-context-fixture';export const inject=['llm'];
export function apply(ctx){const steps=new Map();ctx.on('llm/stream',async function*(o){
 const phase=readFileSync(process.env.DSH_HOME+'/phase','utf8');const key=o.sessionId+phase,n=steps.get(key)||0;steps.set(key,n+1);
 appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({phase,n,sessionId:o.sessionId,messages:o.messages,tools:o.tools})+'\\n');
 const control=JSON.parse(readFileSync(process.env.DSH_HOME+'/control.json','utf8'));let calls=[];
 if(phase==='seed')calls=[['memory',{action:'upsert',target:'user',kind:'preference',subject_ref:'owner',domain:'meetings',content:${JSON.stringify(secret + ' usually prefers afternoons.')},certainty:'confirmed',source_refs:['owner-seed'],idempotency_key:'seed'}]];
 if(phase==='wrong-subject')calls=[['memory',{action:'upsert',kind:'preference',subject_ref:'owner',content:'FORGED-OWNER-PREFERENCE',certainty:'confirmed',source_refs:['outsider'],idempotency_key:'forged'}]];
 if(phase==='owner-reports-other')calls=[['memory',{action:'upsert',kind:'preference',subject_ref:'peer',content:'Peer avoids seafood',certainty:'confirmed',source_refs:['owner-seed'],idempotency_key:'peer'}]];
 if(phase==='correct')calls=[['memory',{action:'upsert',id:control.id,expected_revision:control.revision,target:'user',kind:'preference',subject_ref:'owner',domain:'meetings',content:${JSON.stringify(secret + ' now prefers mornings.')},certainty:'confirmed',source_refs:['owner-correct'],idempotency_key:'correct'}]];
 if(phase.startsWith('unsafe-'))calls=[['memory',{action:'forget',id:control.id,expected_revision:control.revision,idempotency_key:phase,owner_instruction_id:'owner-forget',continuation:control.continuation}]];
 if(phase==='forget')calls=[['notes',{action:'write',path:'private.md',text:${JSON.stringify(secret.repeat(100))}}],['memory',{action:'forget',id:control.id,expected_revision:control.revision,idempotency_key:'forget',owner_instruction_id:'owner-forget',continuation:'Update the separate peer dietary preference to avoids peanuts, then acknowledge both completed actions privately.'}],['history',{action:'search',query:'meetings'}]];
 if(phase==='probe')calls=[['history',{action:'search',query:'meetings'}],['memory',{action:'search',query:'meetings'}],['notes',{action:'read',path:'private.md'}]];
 if(n<calls.length){const[name,args]=calls[n];yield{type:'block-end',index:0,block:{type:'tool-call',id:phase+'-'+n,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}
 else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}
});}`);
    await writeFile(join(home, 'control.json'), '{}');
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test', contextWindow: 100000 }] } } } }, { insert: [{ id: 'memory-context-fixture', name: join(home, 'fixture.mjs') }] }]);
    const config = { agentId: 'pa', revision: '1', workspace: home, provider: 'fixture', model: 'test', mode: 'global',
      personal: { bindingId: 'binding', ownerId: 'owner', conversationId: 'dm', epoch: 1 },
      features: { memory_curation: true, skill_creation: false, task_graph: false, intelligent_ui: false }, knowledge: { memoryInterval: 0 },
      toolAllowlist: ['memory', 'notes', 'history'], approval: { ...approvalDefaults, dangerouslySkipPermissions: true, globalRoot: home } };
    const binding = { sessionId: 'memory-root', agentId: 'pa', ownerId: 'owner', revision: '1', cwd: home };
    const start = async () => {
      client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
      client.rpc.handle('product.call', (value: unknown) => {
        const call = value as { method: string; args: { source_refs: string[]; owner_instruction_id?: string } };
        if (call.method !== 'pa.memory.sources') throw new Error(`Unexpected method ${call.method}`);
        return { sources: call.args.source_refs.map(id => ({ id, verified: true, authorId: id === 'outsider' ? 'outsider' : 'owner', subjectRef: id === 'outsider' ? 'outsider' : 'owner' })), ...(call.args.owner_instruction_id ? { owner_instruction: { id: call.args.owner_instruction_id } } : {}) };
      });
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
      await client.rpc.request('session.ensure', binding);
    };
    const submit = async (phase: string) => {
      await writeFile(join(home, 'phase'), phase);
      await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId: phase, mode: 'followup', content: [{ type: 'text', text: `Run fixture ${phase}` }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: phase } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: phase }) as { terminal?: { kind: string } }).terminal, { timeout: 12000 }).toMatchObject({ kind: 'completed' });
    };
    await start(); await submit('wrong-subject');
    expect((await store.search({action:'search',query:'FORGED'})).records).toEqual([]);
    await submit('owner-reports-other');
    expect((await store.search({action:'search',subject_ref:'peer'})).records).toHaveLength(1);
    await submit('seed');
    let record = (await store.search({ action: 'search', query: secret })).records[0]!;
    expect(record,JSON.stringify((await client!.rpc.request('session.observe',{sessionId:binding.sessionId}) as {events:any[]}).events.filter(e=>e.type==='tool/result'))).toBeDefined();
    expect(record.content).toContain('afternoons');
    await writeFile(join(home, 'control.json'), JSON.stringify(record));
    await submit('correct');
    record = (await store.get(record.id)).records[0]!;
    expect(record.content).toContain('mornings');
    const corrected = (await requests()).find(row => row.phase === 'correct' && row.n === 1);
    expect(JSON.stringify(corrected.messages)).toContain('now prefers mornings');
    expect(JSON.stringify(corrected.messages.findLast((message: any) => message.source?.kind === 'runtime-context'))).not.toContain('usually prefers afternoons');
    await writeFile(join(home, 'control.json'), JSON.stringify(record));
    for (const [phase, content] of [['unsafe-current', record.content], ['unsafe-prior', secret + ' usually prefers afternoons.']]) {
      await writeFile(join(home, 'control.json'), JSON.stringify({...record, continuation:'Remaining work: '+content+' Then reply.'}));
      await submit(phase!);
      const rejected = await client!.rpc.request('session.observe', {sessionId:binding.sessionId}) as {events:any[]};
      const result=rejected.events.findLast(event=>event.type==='tool/result'&&event.data.message.toolCallId===phase+'-0').data.message;
      expect(result.isError).toBe(true);expect(JSON.stringify(result.content)).toContain('continuation contains erased content');
      expect((await store.get(record.id)).records[0]?.content).toBe(record.content);
      expect((await store.snapshot()).pendingForgets).toEqual([]);
    }
    await writeFile(join(home, 'control.json'), JSON.stringify(record));
    await submit('forget');
    const afterForget = (await requests()).find(row => row.phase === 'forget' && row.n === 2);
    expect(JSON.stringify(afterForget.messages)).not.toContain(secret);
    expect(JSON.stringify(afterForget.messages)).toContain('Update the separate peer dietary preference to avoids peanuts');
    expect(JSON.stringify(afterForget.messages)).toContain('dm');
    expect((await store.snapshot()).pendingForgets).toEqual([]);
    const trace = await client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as { events: any[] };
    expect(trace.events.findLast(event => event.type === 'tool/result' && event.data.message.toolCallId === 'forget-2').data.message).toMatchObject({ isError: true });
    await client!.shutdown(); client = undefined;
    await start(); await submit('probe');
    expect(JSON.stringify((await requests()).find(row => row.phase === 'probe' && row.n === 0).messages)).not.toContain(secret);
    const restored = await client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as { events: any[] };
    const note = restored.events.findLast(event => event.type === 'tool/result' && event.data.message.toolCallId === 'probe-2').data.message;
    expect(note.isError).not.toBe(true);
    expect(JSON.stringify(note.content)).not.toContain(secret);
    expect((await store.search({ action: 'search', query: secret })).records).toEqual([]);
  } catch (error) { throw new Error(`${error}\n${logs}`, { cause: error }); }
  finally { if (client) await client.shutdown().catch(()=>{}); await rm(home, { recursive: true, force: true }); }
}, 45000);
