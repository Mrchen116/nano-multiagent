import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { RuntimeClient, prepareProfile } from '../lib/client.js';
import { PersonalMemoryStore } from '../src/knowledge/personal-memory.js';

it('rejects a real maintenance write after an owner correction and denies publishing private facts globally', async () => {
  const home = await mkdtemp(join(tmpdir(), 'pa-maintenance-race-'));
  let client: RuntimeClient | undefined, logs = '';
  const binding = { sessionId: 'root', agentId: 'pa', ownerId: 'owner', revision: '1', cwd: home };
  const store = new PersonalMemoryStore(home, { ownerId: 'owner', agentId: 'pa', bindingId: 'binding' });
  try {
    await writeFile(join(home, 'fixture.mjs'), `import {readFileSync,writeFileSync,appendFileSync,existsSync} from 'node:fs';
export const name='pa-maintenance-race';export const inject=['llm','tools'];
export function apply(ctx){const counts=new Map();ctx.on('tools/result',(exec,result)=>appendFileSync(process.env.DSH_HOME+'/results.jsonl',JSON.stringify({sessionId:exec.agent.id,name:exec.name,result})+'\\n'));ctx.on('llm/stream',async function*(o){
 const last=o.messages.findLast(m=>m.role==='user'&&['user','nano-human'].includes(m.source?.kind));
 const text=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');
 const key=o.sessionId+last.id,n=counts.get(key)||0;counts.set(key,n+1);let call;
 if(text.startsWith('Review the conversation')){
  if(n===0)call=['memory',{action:'search',subject_ref:'owner'}];
  if(n===1){writeFileSync(process.env.DSH_HOME+'/maintenance-read.json',JSON.stringify({sessionId:o.sessionId,messages:o.messages}));
   while(!existsSync(process.env.DSH_HOME+'/release')){if(o.signal.aborted)return;await new Promise(r=>setTimeout(r,10));}
   const record=JSON.parse(readFileSync(process.env.DSH_HOME+'/initial.json','utf8'));
   call=['memory',{action:'upsert',id:record.id,expected_revision:1,kind:'preference',subject_ref:'owner',content:'Prefers afternoons',certainty:'confirmed',source_refs:['seed'],idempotency_key:'stale-maintenance'}];
  }
  if(n===2)call=['skill_manage',{action:'create',scope:'global',name:'private-owner-preference',content:'---\\nname: private-owner-preference\\ndescription: Private fact\\n---\\nPrefers afternoons'}];
 }else if(n===0&&text==='correct'){
  const correction=text==='correct';const record=correction?JSON.parse(readFileSync(process.env.DSH_HOME+'/initial.json','utf8')):undefined;
  call=['memory',{action:'upsert',...(record?{id:record.id,expected_revision:1}:{}),kind:'preference',subject_ref:'owner',content:correction?'Prefers mornings':'Prefers afternoons',certainty:'confirmed',source_refs:[text],idempotency_key:text}];
 }
 const block=call?{type:'tool-call',id:o.sessionId+'-'+n+'-'+last.id,name:call[0],arguments:JSON.stringify(call[1])}:{type:'text',text:'done'};
 yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:call?'tool-calls':'stop'}};
});}`);
    await prepareProfile(home, [{ insert: [{ id: 'pa-maintenance-race', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    client.rpc.handle('product.call', value => {
      const call = value as { method: string; args: { source_refs: string[] } };
      expect(call.method).toBe('pa.memory.sources');
      return { sources: call.args.source_refs.map(id => ({ id, verified: true, authorId: 'owner', subjectRef: 'owner' })) };
    });
    const config = { agentId: 'pa', revision: '1', workspace: home, provider: 'deepseek-official', model: 'deepseek-flash', mode: 'global',
      personal: { bindingId: 'binding', ownerId: 'owner', conversationId: 'dm', epoch: 1 },
      features: { intelligent_ui: false, task_graph: false, memory_curation: true, skill_creation: true },
      knowledge: { memoryInterval: 1, skillInterval: 1, globalSkillRoot: join(home, 'global-skills') }, toolAllowlist: ['memory', 'skill_manage', 'read'], approval: { dangerouslySkipPermissions: true } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const submit = async (text: string) => {
      await client!.rpc.request('session.submit', { sessionId: 'root', inputId: text, mode: 'followup', content: [{ type: 'text', text }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: text } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: text }) as any).terminal).toMatchObject({ kind: 'completed' });
    };
    await store.execute({ action: 'upsert', kind: 'preference', subject_ref: 'owner', content: 'Prefers afternoons', certainty: 'confirmed', source_refs: ['seed'], idempotency_key: 'initial' }, { sessionId: 'root', sources: [{ id: 'seed', authorId: 'owner', subjectRef: 'owner', verified: true }] });
    const original = (await store.search({ action: 'search' })).records[0]!;
    await writeFile(join(home, 'initial.json'), JSON.stringify(original));
    await submit('seed');
    await expect.poll(() => readFile(join(home, 'maintenance-read.json'), 'utf8').catch(() => ''), { timeout: 12000 }).not.toBe('');
    const frozen = JSON.parse(await readFile(join(home, 'maintenance-read.json'), 'utf8'));
    expect(JSON.stringify(frozen.messages)).toContain('Prefers afternoons');
    await submit('correct');
    await writeFile(join(home, 'release'), 'release actual stale read');
    const results = async () => (await readFile(join(home, 'results.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line)).filter(row => row.sessionId === frozen.sessionId);
    await expect.poll(async () => JSON.stringify(await results()), { timeout: 12000 }).toContain('Memory scope revision conflict');
    await expect.poll(async () => JSON.stringify(await results())).toContain('cannot publish private knowledge to shared Skills');
    expect((await store.get(original.id)).records[0]).toMatchObject({ revision: 2, content: 'Prefers mornings' });
    await expect(readFile(join(home, 'global-skills/private-owner-preference/SKILL.md'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
  } catch (error) { throw new Error(`${error}\n${logs}`, { cause: error }); }
  finally { await client?.shutdown().catch(() => {}); await rm(home, { recursive: true, force: true }); }
}, 30000);
