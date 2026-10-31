import { mkdtemp, mkdir, writeFile, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

const contextTools = ['get_context_remaining', 'history', 'new_context', 'notes'];

it('keeps empty business tools and Skills empty while retaining context management, and restores a subset', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-capabilities-')); let client: RuntimeClient | undefined; let logs = '';
  const root = join(home, 'skills'); await mkdir(join(root, 'local-skill'), { recursive: true });
  await writeFile(join(root, 'local-skill', 'SKILL.md'), '---\nname: local-skill\ndescription: Selected test guidance\n---\nLOCAL_SKILL_BODY');
  const config = { agentId: 'a', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: [] as string[],
    skillSelection: { mode: 'explicit_allowlist', names: [] as string[] }, skillRoots: [{ path: root, source: 'workspace' }], features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false, cron_scheduling: false, heartbeat: false } };
  try {
    await writeFile(join(home, 'hang.mjs'), `export const name = 'hang'; export const inject = ['llm']; export function apply(ctx) { ctx.on('llm/stream', async function* (options) { if (options.signal.aborted) return; await new Promise(resolve => options.signal.addEventListener('abort', resolve, { once: true })); }); }`);
    await prepareProfile(home, [{ insert: [{ id: 'hang', name: join(home, 'hang.mjs') }] }]); client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents: [config, { ...config, agentId: 'g', mode: 'global' }, { ...config, agentId: 'b', toolAllowlist: undefined, skillSelection: { mode: 'default_discovery', names: [] } }], bindings: [] });
    for (const agentId of ['a', 'b', 'g']) await client.rpc.request('session.ensure', { sessionId: `session-${agentId}`, agentId, revision: '1', ownerId: 'owner', cwd: home });
    const read = (id: string) => client!.rpc.request('session.capabilities', { sessionId: `session-${id}` }) as Promise<{ tools: string[]; skills: { name: string }[]; prompt: unknown }>;
    expect((await read('a')).tools.sort()).toEqual(contextTools);
    expect((await read('g')).tools.sort()).toEqual([...contextTools, 'conversations', 'inbox', 'send_message', 'subagent'].sort());
    expect((await read('a')).skills).toEqual([]);
    const catalog = await client.rpc.request('configuration.catalog', { agentId: 'a', cwd: home }) as { tools: { name: string }[]; skills: { name: string }[] };
    expect(catalog.tools.map(tool => tool.name)).toEqual(expect.arrayContaining(['read', 'schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history']));
    const disabledCatalog = await client.rpc.request('configuration.catalog', { config: { ...config, agentId: 'new-agent', features: { task_graph: false, memory_curation: false, skill_creation: false, cron_scheduling: false } }, cwd: home }) as typeof catalog;
    expect(disabledCatalog.tools.map(tool => tool.name)).toEqual(expect.arrayContaining(['task_graph', 'memory', 'skill_manage', 'schedule_create', 'schedule_history']));
    expect(catalog.skills.map(skill => skill.name)).toContain('local-skill');
    const preview = await client.rpc.request('configuration.preview', { config: { ...config, systemPrompt: 'PREVIEW_ONLY_581' }, cwd: home }) as { prompt: string; tools: string[]; skills: unknown[] };
    expect(preview.prompt).toContain('PREVIEW_ONLY_581');
    expect(preview.tools.sort()).toEqual(contextTools);
    expect(preview.skills).toEqual([]);
    expect(JSON.stringify((await read('a')).prompt)).not.toContain('PREVIEW_ONLY_581');
    expect((await read('b')).tools).toContain('task_graph');
    expect((await read('b')).skills.map(skill => skill.name)).toContain('local-skill');
    await client.rpc.request('configuration.apply', { ...config, revision: '2', toolAllowlist: ['read', 'skill'], skillSelection: { mode: 'explicit_allowlist', names: ['local-skill'] } });
    expect((await read('a')).tools.sort()).toEqual([...contextTools, 'read', 'skill'].sort());
    expect((await read('a')).skills.map(skill => skill.name)).toEqual(['local-skill']);
    const selectedPreview = await client.rpc.request('configuration.preview', {config:{...config,revision:'2',toolAllowlist:['read','skill'],skillSelection:{mode:'explicit_allowlist',names:['local-skill']}},cwd:home}) as {tools:string[];skills:{name:string}[]};
    const selected = await read('a');
    expect(selectedPreview.tools.sort()).toEqual((selected.prompt as {tools:{name:string}[]}).tools.map(tool=>tool.name).sort());
    expect(selectedPreview.skills.map(skill=>skill.name)).toEqual(selected.skills.map(skill=>skill.name));

    expect((await read('b')).tools).toContain('task_graph');
    await client.rpc.request('session.submit', { sessionId: 'session-a', inputId: 'busy', mode: 'followup', content: [{ type: 'text', text: 'wait' }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'busy' } });
    await expect.poll(async () => (await client!.rpc.request('session.observe', { sessionId: 'session-a' }) as { status: string }).status).toBe('running');
    let renamed = false;
    const rename = client.rpc.request('configuration.apply', { ...config, revision: '2-renamed', toolAllowlist: ['read', 'skill'], skillSelection: { mode: 'explicit_allowlist', names: ['local-skill'] } }).then(() => { renamed = true; });
    void rename.catch(() => {}); // The failure cleanup closes the runtime before a blocked apply can finish.
    await expect.poll(() => renamed, {timeout: 8000}).toBe(true);
    await rename;
    expect((await client.rpc.request('session.observe', {sessionId:'session-a'}) as {status:string}).status).toBe('running');
    expect((await read('a')).tools.sort()).toEqual([...contextTools, 'read', 'skill'].sort());
    let applied = false;
    const pending = client.rpc.request('configuration.apply', { ...config, revision: '3', toolAllowlist: ['write'], systemPrompt: 'AFTER_IDLE_581' }).then(() => { applied = true; });
    await expect.poll(async () => (await read('a')).tools.sort(), {timeout:8000}).toEqual(contextTools);
    expect((await read('a')).skills).toEqual([]);
    expect(JSON.stringify((await read('a')).prompt)).not.toContain('AFTER_IDLE_581');
    expect(applied).toBe(false);
    await client.rpc.request('session.cancel', { sessionId: 'session-a' }); await pending;
    expect((await read('a')).tools.sort()).toEqual([...contextTools, 'write'].sort());
    expect(JSON.stringify((await read('a')).prompt)).toContain('AFTER_IDLE_581');
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 40_000);

it('shadows owner tools in one workspace, constrains actual dispatch, and rebuilds after restart', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-extension-')); let client: RuntimeClient | undefined; let logs = '';
  const global = join(home, 'global.json'); const workspace = join(home, 'workspace.json');
  await writeFile(join(home, 'plugin.mjs'), `export const name = 'fixture-tools'; export const inject = ['tools'];
export function apply(ctx, config) {
  if (config.mode) ctx.tools.presentAs(config.mode);
  ctx.tools.register({ name: 'fixture_echo', description: config.value, parameters: { type: 'object', properties: {} },
    output: { schema: {}, render: (_args, value) => value },
    async execute() { return [{ type: 'text', text: config.value }]; } });
}`);
  await writeFile(global, JSON.stringify([{ module: './plugin.mjs', config: { value: 'global' } }]));
  await writeFile(workspace, JSON.stringify([{ module: './plugin.mjs', config: { value: 'workspace', mode: 'both' } }]));
  await writeFile(join(home, 'probe.mjs'), `import { writeFile } from 'node:fs/promises';
export const name = 'fixture-probe'; export const inject = ['tools', 'llm'];
export function apply(ctx) {
  ctx.on('agent/created', ({agent}) => { setTimeout(async () => {
    const result = await ctx.tools.execute({ name: 'fixture_echo', callId: 'fixture-call', arguments: {}, agent, signal: new AbortController().signal });
    await writeFile(process.env.DSH_HOME + '/' + agent.id + '.json', JSON.stringify(result));
  }, 0); });
  const seen = new Set();
  ctx.on('llm/stream', async function* (options) {
    const last = options.messages.findLast(message => message.role === 'user' && message.source?.kind === 'user' && 'actorId' in message.source);
    if (seen.has(last.id)) { yield { type: 'block-end', index: 0, block: { type: 'text', text: 'done' } }; yield { type: 'finish', reason: { kind: 'stop' } }; return; }
    seen.add(last.id);
    yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: last.id + '-call', name: 'run_code', arguments: JSON.stringify({ description: 'Check selected SDK', code: 'return { echo: await tools.fixture_echo({}), missing: typeof tools.read };' }) } };
    yield { type: 'finish', reason: { kind: 'tool-calls' } };
  });
  ctx.on('tools/result', (exec, result) => { if (exec.name === 'run_code') void writeFile(process.env.DSH_HOME + '/' + exec.agent.id + '.ptc.json', JSON.stringify(result)); });
}`);
  const agents = [
    { agentId: 'a', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['fixture_echo'], extensions: { global, workspace } },
    { agentId: 'b', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['fixture_echo'], extensions: { global } },
    { agentId: 'c', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: [], extensions: { global, workspace } },
  ];
  const bindings = agents.map(agent => ({ sessionId: 'extension-' + agent.agentId, agentId: agent.agentId, revision: '1', ownerId: 'owner', cwd: home }));
  const { readFile } = await import('node:fs/promises');
  try {
    await prepareProfile(home, [{ insert: [{ id: 'fixture-probe', name: join(home, 'probe.mjs') }] }]);
    for (let run = 0; run < 2; run++) {
      client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
      await client.rpc.request('initialize', { protocol: 1, agents, bindings: run ? bindings : [] });
      for (const binding of bindings) await client.rpc.request('session.ensure', binding);
      for (const [id, expected] of [['a', 'workspace'], ['b', 'global'], ['c', 'UNKNOWN_TOOL']]) {
        await expect.poll(async () => readFile(join(home, `extension-${id}.json`), 'utf8').catch(() => '')).toContain(expected);
      }
      for (const id of ['a', 'c']) {
        await client.rpc.request('session.submit', { sessionId: 'extension-' + id, inputId: `ptc-${run}-${id}`, mode: 'followup', content: [{ type: 'text', text: 'PTC fixture' }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: `ptc-${run}-${id}` } });
        await expect.poll(async () => readFile(join(home, `extension-${id}.ptc.json`), 'utf8').catch(() => '')).not.toBe('');
        await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'extension-' + id, inputId: `ptc-${run}-${id}` }) as { terminal?: unknown }).terminal).toBeTruthy();
      }
      const a = JSON.parse(await readFile(join(home, 'extension-a.ptc.json'), 'utf8'));
      expect(a.isError).not.toBe(true);
      expect(JSON.stringify(a)).toContain('workspace');
      expect(JSON.stringify(a)).toContain('undefined');
      const c = JSON.parse(await readFile(join(home, 'extension-c.ptc.json'), 'utf8'));
      expect(JSON.stringify(c)).toContain('UNKNOWN_TOOL');
      for (const id of ['a', 'c']) await rm(join(home, `extension-${id}.ptc.json`));
      await client.shutdown(); client = undefined;
      for (const binding of bindings) await rm(join(home, binding.sessionId + '.json'));
    }
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 25_000);

 it('discovers copied skills in the same session while disabled names survive reload', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-skill-import-')); let client: RuntimeClient | undefined; let logs = '';
  const root = join(home, 'skills'); await mkdir(root);
  const writeSkill = async (name: string) => { await mkdir(join(root, name), {recursive:true}); await writeFile(join(root, name, 'SKILL.md'), `---\nname: ${name}\ndescription: Import fixture\n---\nBODY_${name}`); };
  await writeSkill('blocked');
  await writeFile(join(home, 'load.mjs'), `export const name='load'; export const inject=['llm']; export function apply(ctx) { const seen=new Set(); ctx.on('llm/stream', async function* (options) { const last=options.messages.findLast(m=>m.role==='user' && m.content.some(b=>b.type==='text' && ['imported','blocked'].includes(b.text))); if(seen.has(last.id)){yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};return;}seen.add(last.id);const name=last.content.find(b=>b.type==='text').text;yield {type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-load',name:'skill',arguments:JSON.stringify({name})}};yield {type:'finish',reason:{kind:'tool-calls'}}; }); }`);
  const config = {agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['skill'],skillSelection:{mode:'explicit_denylist',names:['blocked']},skillRoots:[{path:root,source:'workspace'}]};
  const binding={sessionId:'imports',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  try {
    await prepareProfile(home,[{insert:[{id:'load',name:join(home,'load.mjs')}]}]);
    for(let restart=0;restart<2;restart++) {
      client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:restart?[binding]:[]});
      await client.rpc.request('session.ensure',binding);
      const skills=async()=>((await client!.rpc.request('session.capabilities',{sessionId:'imports'})) as {skills:{name:string}[]}).skills.map(s=>s.name);
      expect(await skills()).not.toContain('blocked');
      await writeSkill('imported');
      await expect.poll(skills,{timeout:10000}).toContain('imported');
      for(const name of ['imported','blocked']) {
        const inputId=`${restart}-${name}`;
        await client.rpc.request('session.submit',{sessionId:'imports',inputId,mode:'followup',content:[{type:'text',text:name}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
        await expect.poll(async()=>((await client!.rpc.request('session.lookup',{sessionId:'imports',inputId})) as {terminal?:unknown}).terminal).toBeTruthy();
        const observed=await client.rpc.request('session.observe',{sessionId:'imports'}) as {events:{type:string;data:{message?:{toolCallId:string;isError?:boolean;content:unknown}}}[]};
        const result=observed.events.findLast(e=>e.type==='tool/result')?.data.message;
        expect(result?.isError, JSON.stringify(result)).toBe(name==='blocked');
        if(name==='imported')expect(JSON.stringify(result?.content)).toContain('BODY_imported');
      }
      await client.shutdown();client=undefined;
    }
  } catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},30000);

it('rejects withdrawal during a native tool execution without blocking unrelated capabilities', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-capability-busy-'));
  let client: RuntimeClient | undefined;
  const config = {agentId: 'busy', revision: '1', workspace: home, provider: 'deepseek-official', model: 'deepseek-flash',
    features: {intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false, cron_scheduling: false, heartbeat: false}, toolAllowlist: ['fixture_hold', 'read']};
  try {
    await writeFile(join(home, 'fixture.mjs'), `import {writeFile,access} from 'node:fs/promises';
export const name='capability-busy'; export const inject=['tools','llm']; export function apply(ctx) {
 ctx.tools.register({name:'fixture_hold',description:'Held operation',parameters:{type:'object',properties:{}},output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},execute:async(_args,exec)=>{
  await writeFile(process.env.DSH_HOME+'/entered','yes');
  while(!exec.signal.aborted){if(await access(process.env.DSH_HOME+'/release').then(()=>true,()=>false))break;await new Promise(resolve=>setTimeout(resolve,20));}
  return 'done';
 }});
 let called=false;ctx.on('llm/stream',async function*(){if(!called){called=true;yield{type:'block-end',index:0,block:{type:'tool-call',id:'hold',name:'fixture_hold',arguments:'{}'}};yield{type:'finish',reason:{kind:'tool-calls'}};}else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}});
}`);
    await prepareProfile(home, [{insert: [{id: 'capability-busy', name: join(home, 'fixture.mjs')}]}]);
    client = new RuntimeClient({home, cwd: home});
    await client.rpc.request('initialize', {protocol: 1, agents: [config], bindings: []});
    await client.rpc.request('session.ensure', {agentId: 'busy', revision: '1', sessionId: 'busy-session', ownerId: 'owner', cwd: home});
    await client.rpc.request('session.submit', {sessionId: 'busy-session', inputId: 'work', mode: 'followup', content: [{type:'text',text:'Execute the selected tool'}], source:{kind:'human',actorId:'owner',channel:'test',messageId:'work'}});
    await expect.poll(async () => (await client!.rpc.request('configuration.usage', {agentId:'busy'}) as {busy: unknown[]}).busy).toContainEqual({kind:'tool', name:'fixture_hold'});
    expect(await client.rpc.request('configuration.prepare', {operationId:'withdraw',fingerprint:'2',config:{...config,revision:'2',toolAllowlist:['read']}})).toMatchObject({ready:false,blocks:[{code:'capability_busy',target:{kind:'tool',name:'fixture_hold'}}]});
    expect(await client.rpc.request('configuration.prepare', {operationId:'other',fingerprint:'3',config:{...config,revision:'3',toolAllowlist:['fixture_hold']}})).toMatchObject({ready:true});
    await client.rpc.request('configuration.release', {agentId:'busy',operationId:'other'});
    await writeFile(join(home,'release'),'yes');
    await expect.poll(async () => (await client!.rpc.request('configuration.usage', {agentId:'busy'}) as {busy: unknown[]}).busy).toEqual([]);
    await client.shutdown(); client = undefined;
  } finally { if (client) {client.process.kill('SIGKILL'); await client.exited;} await rm(home, {recursive:true,force:true}); }
}, 30_000);


it('reclaims temporary catalog Sessions without adding them to the execution home', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-catalog-lifecycle-'));
  let client: RuntimeClient | undefined;
  try {
    await prepareProfile(home);
    client = new RuntimeClient({home, cwd:home});
    await client.rpc.request('initialize', {protocol:1, agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'}], bindings:[]});
    for (let i=0; i<3; i++) await client.rpc.request('configuration.catalog', {agentId:'a',cwd:home});
    const sessions = await readdir(join(home,'sessions'), {recursive:true}).catch(error => {if(error.code==='ENOENT')return [];throw error;});
    expect(sessions.filter(name=>/(^|[/\\])preview-/.test(name))).toEqual([]);
  } finally {
    if(client){client.process.kill('SIGKILL');await client.exited;}
    await rm(home,{recursive:true,force:true});
  }
}, 30_000);
