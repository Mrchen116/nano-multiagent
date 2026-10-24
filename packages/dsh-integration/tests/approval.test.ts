import { expect, it } from 'vitest';
import { parseNanoDecision, parseDshDecision, buildPolicy } from '../src/policy/rules.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('parses only valid verdicts and keeps malformed reviews distinct from denials', () => {
  expect(parseNanoDecision('<thinking><block>yes</block></thinking><block>no</block>')).toEqual({ behavior: 'allow', reason: 'Allowed by classifier' });
  expect(parseNanoDecision('<block>yes</block><reason>scope missing</reason>')).toEqual({ behavior: 'deny', reason: 'scope missing' });
  expect(parseNanoDecision('maybe')).toBeUndefined();
  expect(parseDshDecision('{"risk":"high","decision":"allow"}')).toBeUndefined();
  expect(parseDshDecision('{"risk":"medium","decision":"allow"}')).toMatchObject({ behavior: 'allow' });
});

it('uses one selected rule set and inserts configured rule text without interpreting it', async () => {
  const config = { ...approvalDefaults, rules: 'nano' as const, globalRoot: '/owner/.nanoassistant', allow: ['$defaults', 'Keep <nano_workspace_root> literal in this custom rule'] };
  const nano = await buildPolicy(config, '/workspace');
  expect(nano).toContain('Keep <nano_workspace_root> literal in this custom rule');
  expect(nano).toContain('/workspace/.nanoassistant');
  const dsh = await buildPolicy({ ...config, rules: 'dsh' }, '/workspace');
  expect(dsh).toContain('REVIEW_POLICY');
  expect(dsh).not.toContain('Keep <nano_workspace_root>');
});

it('skips the reviewer only for verified owner messages and reviews other public recipients with host facts', async () => {
  const {mkdtemp,writeFile,readFile,rm}=await import('node:fs/promises');
  const {tmpdir}=await import('node:os');const {join}=await import('node:path');
  const {prepareProfile,RuntimeClient}=await import('../lib/client.js');
  const home=await mkdtemp(join(tmpdir(),'nano-message-approval-'));let client:InstanceType<typeof RuntimeClient>|undefined;
  try{
    await writeFile(join(home,'fixture.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='message-approval-fixture';export const inject=['llm'];
export function apply(ctx){const steps=new Set();ctx.on('tools/pre-execute',(exec,next)=>exec.name==='send_message'&&exec.arguments.target==='owner-blocked'?{kind:'deny',reason:'Explicit tool restriction'}:next());ctx.on('llm/stream',async function*(options){
 if(options.system){await appendFile(process.env.DSH_HOME+'/reviews.jsonl',JSON.stringify({system:options.system,prompt:options.messages[0].content[0].text})+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:options.system.startsWith('REVIEW_POLICY')?'{"risk":"high","decision":"deny","reason":"not authorized"}':'<block>yes</block><reason>not authorized</reason>'}};yield{type:'finish',reason:{kind:'stop'}};return;}
 const human=options.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&'actorId'in m.source);
 if(!steps.has(human.id)){steps.add(human.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:'send-'+human.id,name:'send_message',arguments:JSON.stringify({target:human.content[0].text,text:'This is a reply to myself'})}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
 yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'fixture'}]}}}},{insert:[{id:'message-approval-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'}});
    const sent:string[]=[];
    client.rpc.handle('product.call',value=>{
      const call=value as {method:string;args:{target:string};agentId:string};
      if(call.method==='send_message.context')return {target:call.args.target,sender:{type:'agent',agent_id:call.agentId},recipient:{kind:call.args.target.startsWith('owner')?'owner':call.args.target},channel:'web'};
      if(call.method==='send_message'){sent.push(call.args.target);return{status:'sent'};}
      throw new Error('Unexpected product request');
    });
    const cases=[['owner-global','global','nano'],['owner-single','single_thread','nano'],['owner-dsh','global','dsh'],['owner-blocked','global','nano'],['user','global','nano'],['group','global','nano'],['unknown','global','nano']] as const;
    const agents=cases.map(([agentId,mode,rules])=>({agentId,revision:'1',mode,provider:'fixture',model:'fixture',toolAllowlist:['send_message'],approval:{...approvalDefaults,globalRoot:home,rules,denyLimit:20,alwaysAllowTools:['send_message']}}));
    await client.rpc.request('initialize',{protocol:1,agents,bindings:[]});
    for(const [agentId] of cases){
      await client.rpc.request('session.ensure',{sessionId:agentId,agentId,revision:'1',ownerId:'owner',cwd:home});
      await client.rpc.request('session.submit',{sessionId:agentId,inputId:agentId,mode:'followup',content:[{type:'text',text:agentId}],source:{kind:'human',actorId:'owner',channel:'test',messageId:agentId}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:agentId,inputId:agentId}) as {terminal?:unknown}).terminal).toBeTruthy();
    }
    expect(sent).toEqual(['owner-global','owner-single','owner-dsh']);
    const reviews=(await readFile(join(home,'reviews.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    expect(reviews).toHaveLength(6);
    for(const review of reviews){
      const rows=review.prompt.split('\n').filter((line:string)=>line.startsWith('{')).map((line:string)=>JSON.parse(line));
      const context=rows.find((row:any)=>row.meta?.nano_message)?.meta.nano_message;
      expect(context.sender.type).toBe('agent');
      expect(['user','group','unknown']).toContain(context.recipient.kind);
    }
  }finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);

it('uses the dedicated reviewer once per stage, escalates valid denials, and distinguishes unattended faults', async () => {
  const { mkdtemp, writeFile, readFile, rm } = await import('node:fs/promises');
  const { tmpdir } = await import('node:os'); const { join } = await import('node:path');
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-approval-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  await writeFile(join(home, 'fixture.mjs'), `import { appendFile } from 'node:fs/promises';
export const name = 'approval-fixture'; export const inject = ['llm', 'tools'];
export function apply(ctx) {
  ctx.tools.register({ name: 'fixture_effect', description: 'Perform a test mutation', parameters: { type: 'object', properties: { scenario: { type: 'string' } }, required: ['scenario'] }, output: { schema: {}, render: (_args, value) => [{ type: 'text', text: value }] }, async execute(args) { await appendFile(process.env.DSH_HOME + '/effects.jsonl', JSON.stringify(args) + '\\n'); return 'executed'; } });
  const steps = new Map();
  ctx.on('llm/stream', async function* (options) {
    let content;
    if (options.system) {
      const prompt = options.messages[0].content[0].text;
      const pending = JSON.parse(prompt.split('\\n').findLast(line => line.startsWith('{')));
      const scenario = pending.fixture_effect.scenario;
      await appendFile(process.env.DSH_HOME + '/reviews.jsonl', JSON.stringify({ model: options.model, provider: options.provider, reasoningEffort: options.reasoningEffort, scenario, stop: options.stop, prompt }) + '\\n');
      content = scenario === 'fault' ? 'no valid verdict' : scenario === 'allow' ? '<block>no</block>' : '<block>yes</block><reason>scope missing</reason>';
      if (options.system.startsWith('REVIEW_POLICY')) content = '{"risk":"high","decision":"deny","reason":"sensitive exfiltration"}';
    } else {
      const last = options.messages.findLast(message => message.role === 'user' && ['user', 'nano-system'].includes(message.source?.kind)); const scenario = last.content[0].text;
      const step = steps.get(last.id) ?? 0; steps.set(last.id, step + 1);
      if (step < (scenario === 'threshold' ? 3 : 1)) {
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: last.id + '-' + step, name: 'fixture_effect', arguments: JSON.stringify({ scenario }) } };
        yield { type: 'finish', reason: { kind: 'tool-calls' } }; return;
      }
      content = 'done';
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: content } }; yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);
  const agents = ['allow', 'threshold', 'fault', 'global', 'system', 'dsh', 'reject', 'cancel', 'timeout'].map(agentId => ({ agentId, revision: '1', provider: 'fixture', model: 'main-model', features: {intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false}, mode: agentId === 'global' ? 'global' : 'single_thread',
    approval: { ...approvalDefaults, globalRoot: home, askTimeoutSec: agentId === 'timeout' ? 0.05 : 600, rules: agentId === 'dsh' ? 'dsh' : 'nano', denyLimit: agentId === 'dsh' ? 1 : 3, reviewer: { provider: 'fixture', model: 'review-model' } } }));
  try {
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main-model' }, { id: 'review-model' }] } } } }, { insert: [{ id: 'approval-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    const requests: Record<string, unknown>[] = [];
    client.rpc.onNotification((method, value) => { if (method === 'approval.request') { requests.push(value as Record<string, unknown>); const request = value as { requestId: string; sessionId: string };
      if (['approval-timeout', 'approval-threshold'].includes(request.sessionId)) return;
      if (request.sessionId === 'approval-cancel') { void client!.rpc.request('session.cancel', { sessionId: request.sessionId }); return; }
      void client!.rpc.request('approval.answer', { requestId: request.requestId, decision: request.sessionId === 'approval-reject' ? 'rejected' : 'allowed-once', ...(request.sessionId === 'approval-reject' ? { reason: 'Do not overwrite the report' } : {}) }); } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    for (const config of agents) {
      const sessionId = `approval-${config.agentId}`;
      await client.rpc.request('session.ensure', { sessionId, agentId: config.agentId, revision: '1', ownerId: 'owner', cwd: home });
      const scenario = ['system', 'global', 'reject', 'cancel', 'timeout'].includes(config.agentId) ? 'fault' : config.agentId;
      await client.rpc.request('session.submit', { sessionId, inputId: config.agentId, mode: 'followup', content: [{ type: 'text', text: scenario }], source: { kind: config.agentId === 'system' ? 'system' : 'human', actorId: 'owner', channel: config.agentId === 'system' ? 'heartbeat' : 'test', messageId: config.agentId } });
      if (config.agentId === 'threshold') {
        await expect.poll(() => requests.find(request => request.sessionId === sessionId)).toBeTruthy();
        const original = requests.find(request => request.sessionId === sessionId)!;
        let applied = false;
        const next = { ...config, revision: '2', approval: { ...config.approval, rules: 'codex' } };
        const update = client.rpc.request('configuration.apply', next).then(() => { applied = true; });
        await new Promise(resolve => setTimeout(resolve, 50));
        expect(applied).toBe(false);
        await client.rpc.request('approval.answer', { requestId: original.requestId, decision: 'allowed-once' });
        await update;
        const observation = await client.rpc.request('session.observe', { sessionId }) as { approvals: Record<string, unknown>[] };
        expect(observation.approvals.filter(row => row.source === 'classifier_block').every(row => row.rules === 'nano')).toBe(true);
        expect(observation.approvals.at(-1)).toMatchObject({ source: 'human', decision: 'allow', callId: 'threshold-2' });
        await expect(client.rpc.request('approval.answer', { requestId: original.requestId, decision: 'allowed-once' })).rejects.toThrow('no longer pending');
      }
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId, inputId: config.agentId }) as { terminal?: unknown }).terminal, { timeout: 5000 }).toBeTruthy();
    }
    const effects = (await readFile(join(home, 'effects.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line).scenario);
    expect(effects).toEqual(['allow', 'threshold', 'fault']);
    expect(requests).toHaveLength(5);
    const rejected = await client.rpc.request('session.observe', { sessionId: 'approval-reject' }) as { events: { type: string; data: unknown }[] };
    expect(JSON.stringify(rejected.events)).toContain('Do not overwrite the report');
    const rejection = requests.find(request => request.sessionId === 'approval-reject')!;
    await expect(client.rpc.request('approval.answer', { requestId: rejection.requestId, decision: 'allowed-once' })).rejects.toThrow('no longer pending');
    const reviews = (await readFile(join(home, 'reviews.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(reviews.every(review => review.model === 'review-model')).toBe(true);
    expect(reviews.every(review => review.reasoningEffort === 'low')).toBe(true);
    expect(reviews.every(review => !('stop' in review))).toBe(true);
    expect(reviews.filter(review => review.scenario === 'threshold')).toHaveLength(6);
    const fault = await client.rpc.request('session.observe', { sessionId: 'approval-fault' }) as { approvals: Record<string, unknown>[] };
    expect(fault.approvals.filter(event => event.source === 'classifier_unavailable')).toEqual([expect.objectContaining({ decision: 'no_verdict', consecutive: 0, total: 0 })]);
    await client.shutdown(); client = undefined;
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    const bindings = agents.map(config => ({ sessionId: `approval-${config.agentId}`, agentId: config.agentId, revision: config.revision, ownerId: 'owner', cwd: home }));
    await client.rpc.request('initialize', { protocol: 1, agents, bindings });
    await client.rpc.request('session.ensure', bindings.find(binding => binding.agentId === 'threshold'));
    const recovered = await client.rpc.request('session.observe', { sessionId: 'approval-threshold' }) as { approvals: Record<string, unknown>[] };
    expect(recovered.approvals.at(-1)).toMatchObject({ source: 'human', decision: 'allow', consecutive: 0, total: 3 });
    await client.shutdown(); client = undefined;
  } catch (error) { const evidence = client ? await client.rpc.request('session.observe', { sessionId: 'approval-allow' }).catch(() => null) : null; throw new Error(`${String(error)}\n${logs}\n${JSON.stringify(evidence?.events?.filter(event => ['nano/approval', 'approval/asked', 'approval/decided', 'tool/result', 'turn/end'].includes(event.type)))}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30_000);

it('bypasses the classifier for selected Nano Auto queries while retaining writes, manual mode, and tool restrictions', async () => {
  const { mkdtemp, writeFile, readFile, rm } = await import('node:fs/promises');
  const { tmpdir } = await import('node:os'); const { join } = await import('node:path');
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const queries = [
    { name: 'skill_manage', args: { action: 'list' } },
    { name: 'task_graph', args: { action: 'list' } },
    { name: 'task_graph', args: { action: 'get', graph_id: 'graph' } },
    { name: 'schedule_list', args: {} },
    { name: 'schedule_history', args: { id: 'schedule' } },
    { name: 'workflow', args: { action: 'list' } },
    { name: 'workflow', args: { action: 'read' } },
    { name: 'get_goal', args: {} },
    { name: 'todo_write', args: { todos: [] } },
  ];
  const reviewed = [
    ...['create', 'edit', 'patch', 'write_file', 'remove_file'].map(action => ({ name: 'skill_manage', args: { action } })),
    ...['create', 'apply', 'delete'].map(action => ({ name: 'task_graph', args: { action } })),
    ...['create', 'update', 'delete', 'run'].map(action => ({ name: `schedule_${action}`, args: { id: 'schedule' } })),
    ...['launch', 'save', 'control'].map(action => ({ name: 'workflow', args: { action } })),
    { name: 'workflow', args: {} },
    { name: 'create_goal', args: { objective: 'A persistent objective' } },
    { name: 'update_goal', args: { action: 'resume' } },
    { name: 'bash', args: { command: 'pwd' } },
    { name: 'send_message', args: { target: 'group', text: 'A synthetic reply' } },
  ];
  const home = await mkdtemp(join(tmpdir(), 'nano-query-approval-'));
  let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), `import { appendFile } from 'node:fs/promises';
export const name='query-approval-fixture'; export const inject=['llm','tools'];
export function apply(ctx) {
 const seen=new Set();
 ctx.on('tools/pre-execute',(exec,next)=>exec.agent?.id==='blocked'?{kind:'deny',reason:'Explicit tool restriction'}:next());
 ctx.on('llm/stream',async function*(options) {
  if(options.system) {
   const prompt=options.messages[0].content[0].text;
   const row=JSON.parse(prompt.split('\\n').findLast(line=>line.startsWith('{')));
   const [name,args]=Object.entries(row).find(([key])=>key!=='id');
   const pending={name,arguments:args};
   await appendFile(process.env.DSH_HOME+'/reviews.jsonl',JSON.stringify({name:pending.name,action:pending.arguments.action??null})+'\\n');
   yield {type:'block-end',index:0,block:{type:'text',text:options.system.startsWith('REVIEW_POLICY')?'{"risk":"high","decision":"deny","reason":"Synthetic denial"}':'<block>yes</block><reason>Synthetic denial</reason>'}};
   yield {type:'finish',reason:{kind:'stop'}};return;
  }
  const human=options.messages.findLast(message=>message.role==='user'&&message.source?.kind==='user'&&'actorId'in message.source);
  if(!seen.has(human.id)) {
   seen.add(human.id);
   for(const [index,call] of JSON.parse(human.content[0].text).entries())yield {type:'block-end',index,block:{type:'tool-call',id:human.id+'-'+index,name:call.name,arguments:JSON.stringify(call.args)}};
   yield {type:'finish',reason:{kind:'tool-calls'}};return;
  }
  yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};
 });
}`);
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'fixture' }] } } } },
      { insert: [{ id: 'query-approval-fixture', name: join(home, 'fixture.mjs') }] },
    ]);
    const toolAllowlist = [...new Set([...queries, ...reviewed].map(call => call.name))];
    const agents = ['queries', 'writes', 'dsh', 'manual', 'blocked', 'hidden'].map(agentId => ({
      agentId, revision: '1', mode: 'global', provider: 'fixture', model: 'fixture',
      toolAllowlist: agentId === 'hidden' ? [] : toolAllowlist,
      features: { task_graph: true, skill_creation: true, memory_curation: false, cron_scheduling: true },
      knowledge: { enabled: false, globalSkillRoot: join(home, 'skills') },
      approval: { ...approvalDefaults, enabled: agentId !== 'manual', globalRoot: home, rules: agentId === 'dsh' ? 'dsh' : 'nano' },
    }));
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    const effects: { method: string; sessionId: string }[] = [];
    client.rpc.handle('product.call', value => {
      const call = value as { method: string; sessionId: string };
      if (call.method === 'send_message.context') return { target: 'group', recipient: { kind: 'group' }, sender: { type: 'agent' }, channel: 'web' };
      effects.push(call); return { ok: true };
    });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    const reviewLog = async () => readFile(join(home, 'reviews.jsonl'), 'utf8').then(text => text.trim().split('\n').map(line => JSON.parse(line) as { name: string; action: string | null }), error => {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    });
    for (const config of agents) {
      const calls = config.agentId === 'writes' ? reviewed : queries;
      const prior = (await reviewLog()).length;
      await client.rpc.request('session.ensure', { sessionId: config.agentId, agentId: config.agentId, revision: '1', ownerId: 'owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId: config.agentId, inputId: config.agentId, mode: 'followup', content: [{ type: 'text', text: JSON.stringify(calls) }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: config.agentId } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: config.agentId, inputId: config.agentId }) as { terminal?: unknown }).terminal, { timeout: 10000 }).toBeTruthy();
      const reviews = (await reviewLog()).slice(prior);
      const observed = await client.rpc.request('session.observe', { sessionId: config.agentId }) as { events: { type: string; data: any }[]; approvals: { source: string }[] };
      const results = observed.events.filter(event => event.type === 'tool/result');
      expect(results).toHaveLength(calls.length);
      if (['writes', 'dsh'].includes(config.agentId)) {
        expect(new Set(reviews.map(review => `${review.name}:${review.action}`))).toEqual(new Set(calls.map(call => `${call.name}:${'action' in call.args ? call.args.action : null}`)));
        expect(results.every(event => event.data.message.isError)).toBe(true);
      } else {
        expect(reviews).toEqual([]);
        if (config.agentId === 'queries') {
          expect(results.every(event => !event.data.message.isError)).toBe(true);
          expect(observed.approvals.map(entry => entry.source)).toEqual(calls.map(() => 'safe_tool'));
        } else {
          expect(results.every(event => event.data.message.isError)).toBe(true);
          if (config.agentId === 'manual') expect(JSON.stringify(results)).toContain('manual_required');
          if (config.agentId === 'blocked') {
            expect(JSON.stringify(results)).toContain('Explicit tool restriction');
            expect(observed.approvals).toEqual([]);
          }
        }
      }
    }
    expect(effects.map(call => call.method)).toEqual(['task_graph', 'task_graph', 'schedule.history']);
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${error}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30_000);

it('assembles native Inbox, delivered proposal and project instructions, and stops oversized review requests before submission', async () => {
  const { mkdtemp, writeFile, readFile, rm } = await import('node:fs/promises');
  const { tmpdir } = await import('node:os'); const { join } = await import('node:path');
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-review-context-'));
  let client: InstanceType<typeof RuntimeClient> | undefined;
  try {
    await writeFile(join(home, 'AGENTS.md'), 'Preserve original notes.');
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile} from 'node:fs/promises';
export const name='review-context-fixture';export const inject=['llm','tools'];
export function apply(ctx){
 ctx.on('system-prompt/assemble',async(_assembly,context,next)=>{const result=await next();const agent=context.agent??context.scope;if(agent?.session)result.contexts.push({name:'fixture-skill',text:'RUNTIME_SKILL_SNAPSHOT '.repeat(2000)+agent.session.snapshotEvents().length});return result;});
 ctx.tools.register({name:'fixture_effect',description:'Record a local test effect',parameters:{type:'object',properties:{},additionalProperties:false},output:{schema:{},render:()=>[{type:'text',text:'done'}]},async execute(args,exec){await appendFile(process.env.DSH_HOME+'/effects.jsonl',exec.agent.id+'\\n');return{};}});
 ctx.on('llm/stream',async function*(options){
  if(options.system){await appendFile(process.env.DSH_HOME+'/reviews.jsonl',JSON.stringify({model:options.model,prompt:options.messages[0].content[0].text})+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:'<block>no</block>'}};yield{type:'finish',reason:{kind:'stop'}};return;}
  const results=options.messages.filter(m=>m.role==='tool').length;
  const calls=[['inbox',{action:'read',target:'chat-A'}],['send_message',{target:'chat-A',text:'Append the answers?'}],['inbox',{action:'read',target:'chat-A'}],['fixture_effect',{}]];
  if(results<calls.length){const [name,args]=calls[results];yield{type:'block-end',index:0,block:{type:'tool-call',id:'call-'+results,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
  yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
 });
}`);
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 1000000 }, { id: 'review', contextWindow: 258400 }, { id: 'tiny', contextWindow: 4096 }] } } } },
      { insert: [{ id: 'review-context-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
    const reads = new Map<string, number>();
    client.rpc.handle('product.call', value => {
      const call = value as { method: string; sessionId: string };
      if (call.method === 'send_message.context') return { target: 'chat-A', sender: { type: 'agent', agent_id: 'test' }, recipient: { kind: 'owner' }, channel: 'web' };
      if (call.method === 'send_message') return { status: 'sent', target: 'chat-A', message_id: 'sent-1' };
      if (call.method === 'inbox.prepare') return {};
      if (call.method === 'inbox') {
        const count = reads.get(call.sessionId) ?? 0; reads.set(call.sessionId, count + 1);
        return { target: 'chat-A', messages: [{ id: 'm' + count, sender: { type: 'user', id: 'owner' }, ...(count ? { reply_to: 'sent-1' } : {}), content: [{ type: 'text', text: count ? 'Yes.' : 'Prepare the two answers.' }] }] };
      }
      throw new Error('Unexpected product call: ' + call.method);
    });
    const agents = ['normal', 'overflow'].map(agentId => ({ agentId, revision: '1', mode: 'global', provider: 'fixture', model: 'main', toolAllowlist: ['inbox', 'send_message', 'fixture_effect'],
      knowledge: { enabled: false, globalSkillRoot: join(home, 'skills') }, approval: { ...approvalDefaults, rules: 'nano', globalRoot: home, reviewer: { provider: 'fixture', model: agentId === 'normal' ? 'review' : 'tiny' } } }));
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    for (const config of agents) {
      await client.rpc.request('session.ensure', { sessionId: config.agentId, agentId: config.agentId, revision: '1', ownerId: 'owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId: config.agentId, inputId: config.agentId, mode: 'followup', content: [{ type: 'text', text: 'Check Inbox' }], source: { kind: 'system', channel: 'inbox' } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: config.agentId, inputId: config.agentId }) as { terminal?: unknown }).terminal).toBeTruthy();
    }
    const observedNormal = await client.rpc.request('session.observe', { sessionId: 'normal' });
    const effects = await readFile(join(home, 'effects.jsonl'), 'utf8').catch(() => JSON.stringify(observedNormal));
    expect(effects.trim()).toBe('normal');
    const reviews = (await readFile(join(home, 'reviews.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(reviews).toHaveLength(1);
    const prompt = reviews[0].prompt as string;
    expect(prompt.match(/Preserve original notes\./g)).toHaveLength(1);
    expect(prompt).not.toContain('RUNTIME_SKILL_SNAPSHOT');
    const rows = prompt.split('\n').filter(line => line.startsWith('{')).map(line => JSON.parse(line));
    expect(rows.filter(row => row.inbox_result)).toHaveLength(2);
    expect(rows.filter(row => row.inbox_result).every(row => row.observation === 'live')).toBe(true);
    expect(rows.find(row => row.send_message_result)?.send_message_result).toMatchObject({ status: 'sent', message_id: 'sent-1' });
    expect(rows.at(-1)).toMatchObject({ fixture_effect: {}, id: 'call-3' });
    const observed = await client.rpc.request('session.observe', { sessionId: 'overflow' }) as { approvals: { source: string; decision: string; reason: string }[] };
    expect(observed.approvals.find(row => row.source === 'classifier_unavailable')).toMatchObject({ decision: 'no_verdict', reason: expect.stringContaining('Review context exceeds configured window') });
  } finally { if (client) await client.shutdown(); await rm(home, { recursive: true, force: true }); }
}, 30_000);
