import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { KnowledgeFiles } from '../src/knowledge/files.js';

it('preserves memory assets, source comments, limits and concurrent updates in one workspace', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-knowledge-'));
  try {
    const files = new KnowledgeFiles(home, join(home, 'shared'));
    await mkdir(join(home, '.nanoassistant/memory'), { recursive: true });
    await writeFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'Existing environment note');
    await Promise.all(['alpha', 'beta'].map(content => files.memory({ action: 'add', target: 'memory', content }, 'session')));
    let text = await files.memoryText('memory');
    expect(text).toContain('Existing environment note'); expect(text).toContain('alpha'); expect(text).toContain('beta'); expect(text).toContain('"session_id":"session"');
    await files.memory({ action: 'replace', target: 'memory', old_text: 'alpha', content: 'updated fact' }, 'second');
    await files.memory({ action: 'remove', target: 'memory', old_text: 'beta' }, 'second');
    text = await files.memoryText('memory'); expect(text).toContain('updated fact'); expect(text).not.toContain('beta');
    await expect(files.memory({ action: 'add', target: 'user', content: 'x'.repeat(1400) }, 'second')).rejects.toThrow('limit');
    expect(await files.memoryText('user')).toBe('');
  } finally { await rm(home, { recursive: true, force: true }); }
});

it('controls Skill writes, keeps creation source stable, deduplicates use and archives automatic assets', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-knowledge-'));
  try {
    const files = new KnowledgeFiles(home, join(home, 'shared'));
    const content = '---\nname: useful\ndescription: Reusable fixture\n---\n\nUse the observed evidence.';
    await files.skill({ action: 'create', name: 'useful', content }, 'F3');
    await files.skill({ action: 'write_file', name: 'useful', file_path: 'references/example.md', file_content: 'observed' }, 'F1');
    await expect(files.skill({ action: 'write_file', name: 'useful', file_path: '../outside', file_content: 'bad' }, 'F1')).rejects.toThrow('support');
    await expect(files.skill({ action: 'create', name: 'useful', content }, 'F1')).rejects.toThrow('exists');
    const root = join(home, '.nanoassistant/skills'); const location = join(root, 'useful/SKILL.md');
    for (let i = 0; i < 20; i++) {
      const result = await files.use(root, 'useful', 'a', 'session', `call-${i}`, location, '2026-01-01T00:00:00Z');
      expect(result.batch).toBe(i === 19);
    }
    expect((await files.use(root, 'useful', 'a', 'session', 'call-19', location)).counted).toBe(false);
    const usage = JSON.parse(await readFile(join(root, '.usage.json'), 'utf8')).useful;
    expect(usage).toMatchObject({ source: 'F3', use_count: 20 });
    const accepted = await files.batchCandidate(root, 'useful');
    expect(accepted?.count).toBe(20);
    await files.use(root, 'useful', 'a', 'later-session', 'later-use', location, '2026-01-01T00:00:00Z');
    await files.batchAccepted(root, 'useful', accepted!.count);
    expect(JSON.parse(await readFile(join(root, '.usage.json'), 'utf8')).useful.uses_since_last_B).toBe(1);
    await files.skill({action:'create',name:'manual',content:content.replace('name: useful','name: manual')},'F1');
    expect(await files.batchCandidate(root, 'manual')).toBeUndefined();
    await files.curate(root, '2026-02-05T00:00:00Z');
    expect(JSON.parse(await readFile(join(root, '.usage.json'), 'utf8')).useful.state).toBe('stale');
    await files.curate(root, '2026-05-05T00:00:00Z');
    expect(await readFile(join(root, '.archive/useful/SKILL.md'), 'utf8')).toBe(content);
    expect(JSON.parse(await readFile(join(root, '.usage.json'), 'utf8')).useful.state).toBe('archived');
  } finally { await rm(home, { recursive: true, force: true }); }
});

it('keeps fresh per-Agent totals and daily counts after evidence eviction and window rollover', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-skill-statistics-'));
  try {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-01T12:00:00Z'));
    const files = new KnowledgeFiles(home, join(home, 'shared'));
    const root = files.skillRoot, shared = files.globalSkillRoot!;
    const content = '---\nname: useful\ndescription: Fixture\n---\nUse evidence.';
    await files.skill({ action: 'create', name: 'useful', content }, 'F3');
    await files.skill({ action: 'create', scope: 'global', name: 'useful', content }, 'F1');
    // An existing legacy count and sample must remain available to maintenance, but never seed new statistics.
    const legacy = JSON.parse(await readFile(join(root, '.usage.json'), 'utf8'));
    legacy.useful.use_count = 999;
    legacy.useful.session_refs = [{session_id:'legacy',tool_call_id:'old',timestamp:'2026-09-30T12:00:00Z',location:'old'}];
    await writeFile(join(root, '.usage.json'), JSON.stringify(legacy));
    expect((await files.usage([root], 'a')).skills[0]).toMatchObject({use_count:0,statistics_since:null,session_refs:[]});
    for (const target of [root, shared]) {
      for (let i = 0; i < 75; i++) await files.use(target, 'useful', 'a', 'session-a', `call-${i}`, 'location');
      expect((await files.use(target, 'useful', 'a', 'session-a', 'call-74', 'location')).counted).toBe(false);
    }
    for (let i = 0; i < 65; i++) await files.use(shared, 'useful', 'b', 'session-b', `call-${i}`, 'location');
    const restarted = new KnowledgeFiles(home, shared);
    const a = await restarted.usage([root, shared], 'a');
    expect(a).toMatchObject({statistics_since:'2026-10-01T12:00:00.000Z',period_start:'2026-09-02',period_end:'2026-10-01'});
    expect(a.skills.map(skill => skill.use_count)).toEqual([75,75]);
    expect(a.heatmap_data.reduce((sum, count) => sum + count, 0)).toBe(150);
    expect(a.skills[1]!.session_refs).toEqual([]);
    expect(a.skills[0]).not.toHaveProperty('statistics');
    expect((await restarted.usage([shared], 'b')).skills[0]).toMatchObject({use_count:65});
    expect((await restarted.usage([shared], 'unused')).skills).toEqual([]);
    const saved = JSON.parse(await readFile(join(root, '.usage.json'), 'utf8')).useful;
    expect(saved).toMatchObject({use_count:1074,uses_since_last_B:75});
    expect(saved.session_refs).toHaveLength(60);
    expect(await files.references('session-a', [root])).toEqual([{name:'useful',location:'location'}]);
    vi.setSystemTime(new Date('2026-11-01T00:01:00Z'));
    await files.use(shared, 'useful', 'a', 'session-a', 'new-month', 'location');
    const later = await restarted.usage([shared], 'a');
    expect(later.skills[0]!.use_count).toBe(76);
    expect(later.heatmap_data.reduce((sum, count) => sum + count, 0)).toBe(1);
    expect((await restarted.usage([shared], 'b')).skills[0]!.use_count).toBe(65);
    expect(Object.keys(JSON.parse(await readFile(join(shared, '.usage.json'), 'utf8')).useful.statistics.a.days)).toEqual(['2026-11-01']);
  } finally { vi.useRealTimers(); await rm(home, {recursive:true,force:true}); }
});

it('runs independent native maintenance children, persists successful facts and withdraws each Feature', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-knowledge-profile-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const workspaceA = join(home, 'a'); const workspaceB = join(home, 'b');
  await mkdir(workspaceA); await mkdir(workspaceB);
  const content = '---\nname: reviewed-workflow\ndescription: Reuse the verified approach\n---\n\nVerify the requested outcome against the original evidence.';
  await writeFile(join(home, 'fixture.mjs'), `import {existsSync,writeFileSync} from 'node:fs';
export const name='knowledge-fixture'; export const inject=['llm','tools'];
export function apply(ctx) {
 ctx.tools.register({ name:'fixture_observation', description:'Observe fixture state', parameters:{type:'object',properties:{}}, output:{schema:{},render:()=>[{type:'text',text:'observed'}]},execute:()=>({observed:true}) });
 const seen=new Map();
 ctx.on('llm/stream',async function* (options) {
  const last=options.messages.findLast(m=>m.role==='user' && ['nano-human','user'].includes(m.source?.kind));
  const prompt=last.content.filter(b=>b.type==='text').map(b=>b.text).join('');
  let name,args;
  const step=seen.get(last.id)||0;seen.set(last.id,step+1);
  if (step===0 || prompt.includes('consider saving to memory') && step<3) {
   if (prompt.startsWith('Review the conversation')) {
    writeFileSync(${JSON.stringify(join(home, 'review-started'))},'started');
    while(!existsSync(${JSON.stringify(join(home, 'release-review'))}))await new Promise(resolve=>setTimeout(resolve,20));
    if(options.maxTokens!==8192)throw new Error('Review output budget was overwritten');
    if (prompt.includes('consider saving to memory')) {if(step<2){name='read';args={file_path:${JSON.stringify(join(workspaceA,'.nanoassistant/memory/'))}+(step===0?'USER.md':'MEMORY.md')};}else{name='memory';args={action:'add',target:'user',content:'The user prefers evidence-backed concise responses.'};}}
    else {name='skill_manage';args={action:'create',name:'reviewed-workflow',content:${JSON.stringify(content)}};}
   } else if (prompt==='skill fixture') {name='fixture_observation';args={};}
  }
  if (name) {yield {type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-call-'+step,name,arguments:JSON.stringify(args)}};yield {type:'finish',reason:{kind:'tool-calls'}};}
  else {yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};}
 });
}`);
  const agents = [
    { agentId: 'a', revision: '1', mode: 'global', provider: 'fixture', model: 'test', features: { intelligent_ui: false, task_graph: false, memory_curation: true, skill_creation: false }, knowledge: { memoryInterval: 1 }, toolAllowlist: ['read', 'memory'] },
    { agentId: 'b', revision: '1', mode: 'global', provider: 'fixture', model: 'test', features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: true }, knowledge: { skillInterval: 1 }, toolAllowlist: ['fixture_observation', 'read', 'skill_manage', 'skill'], skillRoots: [{ path: join(workspaceB, '.nanoassistant/skills'), source: 'workspace' }] },
  ];
  const bindings = agents.map(config => ({ sessionId: `knowledge-${config.agentId}`, agentId: config.agentId, revision: '1', ownerId: 'owner', cwd: config.agentId === 'a' ? workspaceA : workspaceB }));
  try {
    await prepareProfile(home, [{ id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}} },{insert:[{id:'knowledge-fixture',name:join(home,'fixture.mjs')}]}]);
    const start = async () => {
      client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
      await client.rpc.request('initialize', { protocol: 1, agents, bindings });
      for (const binding of bindings) await client.rpc.request('session.ensure', binding);
    };
    await start();
    const advertised:Promise<{reviews:{status:string;childSessionId?:string}[]}>[]=[];
    const unwatch=client!.rpc.onNotification(method=>{
      if(method==='knowledge.changed')advertised.push(client!.rpc.request('knowledge.facts',{}) as Promise<{reviews:{status:string;childSessionId?:string}[]}>);
    });
    for (const [index, binding] of bindings.entries()) await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId: binding.sessionId, mode: 'followup', content: [{ type: 'text', text: index ? 'skill fixture' : 'memory fixture' }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: binding.sessionId } });
    const facts = async () => await client!.rpc.request('knowledge.facts', {}) as { facts: { kind: string; reviewId?: string; agentId: string }[]; reviews: { status: string; kind: string }[] };
    await expect.poll(()=>readFile(join(home,'review-started'),'utf8').catch(()=>''),{timeout:8000}).toBe('started');
    await expect.poll(()=>advertised.length).toBeGreaterThan(0);unwatch();
    expect((await Promise.all(advertised)).some(state=>state.reviews.some(review=>review.status==='running'&&review.childSessionId))).toBe(true);
    expect(await client!.rpc.request('update.prepare',{operationId:'background-review'})).toEqual({ready:false});
    await writeFile(join(home,'release-review'),'continue');
    await expect.poll(async () => (await facts()).reviews.filter(review => review.status === 'completed').length, { timeout: 8000 }).toBe(2);
    for (const [index, binding] of bindings.entries()) {
      // Explicit launch provenance must survive opaque review labels for both maintenance kinds.
      await client!.rpc.request('trajectory.prepare', { observerId: binding.sessionId, rootAgentId: binding.agentId, rootSessionId: binding.sessionId, sessionId: binding.sessionId, ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 });
      const runs = await client!.rpc.request('trajectory.call', { observerId: binding.sessionId, method: 'trajectory/runs' }) as { value: import('@nano/product-contracts').TrajectoryRun[] };
      expect(runs.value).toHaveLength(1);
      expect(runs.value[0]).toMatchObject({ kind: index ? 'skills' : 'memory', delegation: 'background', provider: 'fork', state: 'completed' });
      expect(runs.value[0]!.launchSeq).toBeTypeOf('number');
      expect(runs.value[0]!.startSeq).toBeGreaterThan(0);
      expect(runs.value[0]!.endSeq).toBeGreaterThan(runs.value[0]!.startSeq!);
      expect(runs.value[0]!.callId).toBeUndefined();
    }
    expect((await facts()).facts.map(fact => [fact.agentId, fact.kind, !!fact.reviewId]).sort()).toEqual([['a','memory',true],['b','skills',true]]);
    expect(await readFile(join(workspaceA,'.nanoassistant/memory/USER.md'),'utf8')).toContain('evidence-backed');
    expect(await readFile(join(workspaceB,'.nanoassistant/skills/reviewed-workflow/SKILL.md'),'utf8')).toBe(content);
    expect(JSON.parse(await readFile(join(workspaceB,'.nanoassistant/skills/.usage.json'),'utf8'))['reviewed-workflow'].source).toBe('F3');
    expect(await client!.rpc.request('knowledge.usage', { agentId: 'b' })).toMatchObject({ health: { created_auto_total: 1, active_auto_total: 1, used_auto_total: 0 } });
    agents[0]!.features.memory_curation = false; agents[1]!.features.skill_creation = false;
    for (const config of agents) await client!.rpc.request('configuration.apply', config);
    for (const binding of bindings) {
      const view = await client!.rpc.request('configuration.preview', { config: agents.find(config => config.agentId === binding.agentId), cwd: binding.cwd }) as { tools: string[] };
      expect(view.tools).toContain(binding.agentId === 'a' ? 'memory' : 'skill_manage');
    }
    await client!.shutdown(); client=undefined; await start();
    expect((await facts()).facts).toHaveLength(2); expect((await facts()).reviews.every(review=>review.status==='completed')).toBe(true);
    const invoke = async (inputId: string) => {
      await client!.rpc.request('session.submit', { sessionId:'knowledge-b',inputId,mode:'followup',content:[{type:'text',text:'/skill:reviewed-workflow'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId} });
      await expect.poll(async () => (await client!.rpc.request('session.lookup',{sessionId:'knowledge-b',inputId}) as {terminal?:unknown}).terminal).toBeTruthy();
    };
    await invoke('invoke-selected');
    const invoked = await client!.rpc.request('session.observe',{sessionId:'knowledge-b'}) as {events:{type:string;data:{source?:{kind?:string}}}[]};
    expect(invoked.events.filter(event=>event.type==='user/message' && event.data.source?.kind==='skill-invocation')).toHaveLength(1);
    await client!.rpc.request('configuration.apply',{...agents[1],skillSelection:{mode:'explicit_allowlist',names:[]}});
    await invoke('invoke-excluded');
    const excluded = await client!.rpc.request('session.observe',{sessionId:'knowledge-b'}) as typeof invoked;
    expect(excluded.events.filter(event=>event.type==='user/message' && event.data.source?.kind==='skill-invocation')).toHaveLength(1);
    await client!.rpc.request('configuration.apply',{...agents[1],features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:true},knowledge:{skillInterval:100000}});
    for(let i=0;i<19;i++) await invoke(`batch-use-${i}`);
    expect((await facts()).reviews.filter(review=>review.status==='completed')).toHaveLength(2);
    expect(await readFile(join(workspaceB,'.nanoassistant/skills/reviewed-workflow/SKILL.md'),'utf8')).toBe(content);
    expect((await facts()).facts).not.toContainEqual(expect.objectContaining({source:'F4'}));
    await client!.rpc.request('configuration.apply',{...agents[0],features:{intelligent_ui:false,task_graph:false,memory_curation:true,skill_creation:false}});
    const restored=await client!.rpc.request('configuration.preview',{config:{...agents[0],features:{intelligent_ui:false,task_graph:false,memory_curation:true,skill_creation:false}},cwd:workspaceA}) as {tools:string[];prompt:string};
    expect(restored.tools).toContain('memory'); expect(restored.prompt).toContain('evidence-backed');
    await client!.shutdown(); client=undefined;
  } catch(error) { throw new Error(`${String(error)}\n${logs}\n${await readFile(join(workspaceB,'.nanoassistant/skills/.usage.json'),'utf8').catch(()=> '')}\n${JSON.stringify(client ? await client.rpc.request('knowledge.facts', {}).catch(()=>null) : null)}`, { cause:error }); }
  finally { if(client) {client.process.kill('SIGKILL'); await client.exited;} await rm(home,{recursive:true,force:true}); }
},30000);

it.each([false, true])('invokes live human Inbox Skills once without promoting other sources (native pruning=%s)', async (prune) => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-global-skill-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const skills = join(home, 'skills'); await mkdir(join(skills, 'selected'), { recursive: true });
  await writeFile(join(skills, 'selected/SKILL.md'), '---\nname: selected\ndescription: Selected instructions\n---\nSELECTED_SKILL_INSTRUCTIONS');
  await writeFile(join(home, 'fixture.mjs'), `export const name='global-skill-fixture';export const inject=['llm','toolResultPruner'];export function apply(ctx){if(${prune})ctx.on('agent/pre-step',({agent},next)=>{ctx.toolResultPruner.pruneSession(agent.session);return next();});const seen=new Set();ctx.on('llm/stream',async function*(o){const last=o.messages.findLast(m=>m.role==='user'&&m.source.kind==='nano-system');if(!seen.has(last.id)){seen.add(last.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-read',name:'inbox',arguments:JSON.stringify({action:'read',target:last.id})}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});}`);
  const config = { agentId:'a', revision:'1', provider:'fixture',model:'test',mode:'global',toolAllowlist:['inbox','skill'],features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false},skillRoots:[{path:skills,source:'workspace'}] };
  const binding = {sessionId:'global-skill',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try {
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'global-skill-fixture',name:join(home,'fixture.mjs')}]}]);
    const start = async () => {
      client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
      client.rpc.handle('product.call', value=>{const call=value as {method:string;args:{target:string}};return call.method==='inbox'?{messages:[{id:call.args.target+'-message',sender:{type:call.args.target==='other-agent'?'agent':'user'},partial:call.args.target==='partial-human',content:[{type:'text',text:'/skill:selected'+(prune?' '+ 'a'.repeat(12000):'')}]}]}:{};});
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);
    };
    await start();
    for(const inputId of ['human','other-agent','partial-human']) {
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId,mode:'followup',content:[{type:'text',text:'Inbox wake'}],source:{kind:'system',actorId:'a',channel:'inbox',messageId:inputId}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId})as{terminal?:unknown}).terminal).toBeTruthy();
    }
    const read=async()=>await client!.rpc.request('session.observe',{sessionId:binding.sessionId})as{events:{type:string;data:{id?:string;source?:{kind:string}}}[]};
    if (prune) expect((await read()).events.some(e=>e.type==='compaction/prune')).toBe(true);
    expect((await read()).events.filter(e=>e.type==='turn/end').map(e=>(e.data as {reason:{kind:string}}).reason.kind)).toEqual(['completed','completed','completed']);
    expect((await read()).events.filter(e=>e.type==='user/message'&&e.data.source?.kind==='skill-invocation').map(e=>e.data.id)).toEqual(['nano-skill:human-message:selected']);
    await expect.poll(()=>client!.rpc.request('knowledge.usage',{agentId:'a'})).toMatchObject({skills:[{name:'selected',use_count:1,statistics_since:expect.any(String),session_refs:[{session_id:binding.sessionId}]}]});
    await client!.shutdown();client=undefined;await start();
    expect((await read()).events.filter(e=>e.type==='user/message'&&e.data.source?.kind==='skill-invocation')).toHaveLength(1);
    expect(await client!.rpc.request('knowledge.usage',{agentId:'a'})).toMatchObject({skills:[{name:'selected',use_count:1}]});
    await client!.shutdown();client=undefined;
  }catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},20000);
