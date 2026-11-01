import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('restores native goal authority through later steps and resets repetition only for direct humans', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-human-source-'));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    await writeFile(join(home, 'input.txt'), 'fixture input');
    await writeFile(join(home, 'fixture.mjs'), `
export const name='human-source-fixture';export const inject=['llm'];
export function apply(ctx){
  ctx.on('agent/created',({agent})=>{
    if(agent.id==='scheduled'||agent.id==='peer')agent.followup({id:'native-'+agent.id,role:'user',content:[{type:'text',text:'goal-'+agent.id}],source:agent.id==='scheduled'?{kind:'schedule'}:{kind:'agent-message',form:'relay',senderSessionId:'other'}});
  });
  const steps=new Map();
  ctx.on('llm/stream',async function*(o){
    const input=o.messages.findLast(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&/^(goal-|repeat-|spawn)/.test(b.text)));
    const text=input.content.find(b=>b.type==='text'&&/^(goal-|repeat-|spawn)/.test(b.text)).text;
    const step=steps.get(input.id)??0;steps.set(input.id,step+1);
    let name,args;
    if(text==='spawn'&&step===0){name='subagent';args={prompt:'goal-child',description:'Check child authority',run_in_background:false};}
    if(text.startsWith('goal-')){
      if(step===0){name='read';args={file_path:${JSON.stringify(join(home, 'input.txt'))}};}
      if(step===1){name='create_goal';args={objective:'Finish the explicitly requested fixture goal',max_goal_rounds:1};}
      if(step===2){const last=o.messages.findLast(m=>m.role==='tool');if(!last.isError){const value=JSON.parse(last.content.find(b=>b.type==='text').text);name='update_goal';args={goal_id:value.goal.id,revision:value.goal.revision,action:'complete'};}}
    }
    if(text.startsWith('repeat-')&&step<(text==='repeat-human'?1:2)){name='read';args={file_path:${JSON.stringify(join(home, 'input.txt'))}};}
    if(name){yield{type:'block-end',index:0,block:{type:'tool-call',id:input.id+'-'+step,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};}
    else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}
  });
}`);
    await prepareProfile(home, [{ insert: [{ id: 'human-source-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    const config = { agentId: 'a', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash',
      toolAllowlist: ['read', 'create_goal', 'update_goal', 'subagent'], features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    const ensure = (sessionId: string) => client!.rpc.request('session.ensure', { sessionId, agentId: 'a', revision: '1', ownerId: 'owner', cwd: home });
    const observe = (sessionId: string) => client!.rpc.request('session.observe', { sessionId }) as Promise<{ events: any[] }>;
    const submit = async (sessionId: string, inputId: string, kind = 'human') => {
      await client!.rpc.request('session.submit', { sessionId, inputId, mode: 'followup',
        content: [{ type: 'text', text: 'CONTEXT_ENVELOPE' }, { type: 'text', text: inputId }],
        source: { kind, actorId: 'owner', channel: 'test', messageId: inputId, contextEnvelope: 'CONTEXT_ENVELOPE', background_returns: [{ sessionId: 'background' }] } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId, inputId }) as { terminal?: unknown }).terminal).toBeTruthy();
    };
    await ensure('direct'); await submit('direct', 'goal-human');
    const direct = (await observe('direct')).events;
    expect(direct.find(e => e.type === 'user/message' && e.data.id === 'goal-human')?.data.source).toMatchObject({
      kind: 'user', actorId: 'owner', channel: 'test', messageId: 'goal-human', contextEnvelope: 'CONTEXT_ENVELOPE', background_returns: [{ sessionId: 'background' }],
    });
    const effects = direct.filter(e => e.type === 'tool/result').map(e => e.data.message);
    expect(effects).toHaveLength(3);
    expect(effects.every(message => !message.isError)).toBe(true);
    expect(direct.filter(e => e.type === 'turn/start')).toHaveLength(1);
    expect(direct.filter(e => e.type === 'step/start')).toHaveLength(4);
    await ensure('system'); await submit('system', 'goal-system', 'system');
    for (const sessionId of ['scheduled', 'peer']) {
      await ensure(sessionId);
      await expect.poll(async () => (await observe(sessionId)).events.some(e => e.type === 'turn/end')).toBe(true);
    }
    for (const sessionId of ['system', 'scheduled', 'peer']) {
      const observation = await observe(sessionId);
      const results = observation.events.filter(e => e.type === 'tool/result').map(e => e.data.message);
      expect(results, sessionId).toHaveLength(2);
      expect(results[0].isError ?? false).toBe(false);
      expect(results[1].isError).toBe(true);
      expect(JSON.stringify(results[1])).toContain('this goal operation requires a direct human turn on a top-level agent');
    }
    await ensure('parent'); await submit('parent', 'spawn');
    const children = await client.rpc.request('session.descendants', { sessionId: 'parent' }) as any[];
    expect(children).toHaveLength(1);
    const child = children[0].events;
    // Runtime snapshots now precede input: identify the child prompt, not the first user-role message.
    const childPrompts = child.filter((e: any) => e.type === 'user/message' && e.data.content.some((block: any) => block.type === 'text' && block.text === 'goal-child'));
    expect(childPrompts).toHaveLength(1);
    expect(childPrompts[0].data.source).toEqual({ kind: 'user' });
    expect(JSON.stringify(child.filter((e: any) => e.type === 'tool/result'))).toContain('this goal operation requires a direct human turn on a top-level agent');
    await ensure('repeat');
    await submit('repeat', 'repeat-start'); await submit('repeat', 'repeat-human');
    const reminders = async () => (await observe('repeat')).events.filter(e => e.type === 'user/message' && e.data.source.kind === 'repeat-tool-reminder');
    expect(await reminders()).toHaveLength(0);
    await submit('repeat', 'repeat-system', 'system');
    expect(await reminders()).toHaveLength(1);
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30_000);

it('uses native direct Skill gestures and injects compatibility forms only once', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-human-skills-'));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    await mkdir(join(home, 'skills/selected'), { recursive: true });
    await writeFile(join(home, 'skills/selected/SKILL.md'), '---\nname: selected\ndescription: Selected fixture\n---\nSELECTED_BODY');
    await writeFile(join(home, 'fixture.mjs'), `export const name='skill-source-fixture';export const inject=['llm'];export function apply(ctx){ctx.on('agent/created',({agent})=>{if(agent.id==='legacy'&&!agent.session.snapshotEvents().some(e=>e.type==='user/message'))agent.followup({id:'legacy-input',role:'user',content:[{type:'text',text:'/selected'}],source:{kind:'nano-human',actorId:'owner',channel:'test',messageId:'old'}});});ctx.on('llm/stream',async function*(){yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home, [{ insert: [{ id: 'skill-source-fixture', name: join(home, 'fixture.mjs') }] }]);
    const config = { agentId: 'a', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['skill'],
      features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false }, skillRoots: [{ path: join(home, 'skills'), source: 'workspace' }] };
    const binding = { sessionId: 'skills', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
    const start = async () => {
      client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
      registerNoopTaskHosts(client);
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
      await client.rpc.request('session.ensure', binding);
    };
    await start();
    const legacyBinding = { ...binding, sessionId: 'legacy' };
    await client!.rpc.request('session.ensure', legacyBinding);
    const legacy = async () => (await client!.rpc.request('session.observe', { sessionId: 'legacy' }) as { events: any[] }).events;
    await expect.poll(async () => (await legacy()).some(e => e.type === 'turn/end')).toBe(true);
    expect((await legacy()).filter(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation')).toHaveLength(1);
    const read = async () => (await client!.rpc.request('session.observe', { sessionId: 'skills' }) as { events: any[] }).events;
    const submit = async (inputId: string, text: string, kind = 'human') => {
      await client!.rpc.request('session.submit', { sessionId: 'skills', inputId, mode: 'followup', content: [{ type: 'text', text }],
        source: { kind, actorId: 'owner', channel: 'test', messageId: inputId } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'skills', inputId }) as { terminal?: unknown }).terminal).toBeTruthy();
    };
    for (const [id, text] of [['native', '/selected'], ['compat', '/skill:selected'], ['tagged', '[IM]/selected'], ['mixed', '/skill:selected /selected'], ['inline', 'Please use /selected /selected']]) {
      await submit(id!, text!);
      expect((await read()).filter(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation')).toHaveLength(['native', 'compat', 'tagged', 'mixed', 'inline'].indexOf(id!) + 1);
    }
    // Standard /name is supplied by DSH rather than Nano's compatibility injector.
    expect((await read()).filter(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation')[0].data.id).not.toMatch(/^nano-skill:/);
    await submit('system', '/selected /skill:selected', 'system');
    await client!.rpc.request('configuration.apply', { ...config, skillSelection: { mode: 'explicit_allowlist', names: [] } });
    await submit('excluded', '/selected /skill:selected');
    expect((await read()).filter(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation')).toHaveLength(5);
    await client!.shutdown(); client = undefined; await start();
    await client!.rpc.request('session.ensure', legacyBinding);
    expect((await legacy()).filter(e => e.type === 'user/message' && e.data.source.kind === 'nano-human')).toHaveLength(1);
    expect((await legacy()).filter(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation')).toHaveLength(1);
    await submit('mixed', '/skill:selected /selected');
    expect((await read()).filter(e => e.type === 'user/message' && e.data.source.kind === 'skill-invocation')).toHaveLength(5);
    await client!.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 20_000);

it('still reviews and can deny a goal with native human source eligibility', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-goal-consent-'));
  let client: RuntimeClient | undefined;
  try {
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile}from'node:fs/promises';export const name='goal-consent-fixture';export const inject=['llm'];export function apply(ctx){const seen=new Set();ctx.on('llm/stream',async function*(o){
      if(o.system){await appendFile(process.env.DSH_HOME+'/reviews',o.messages[0].content[0].text);yield{type:'block-end',index:0,block:{type:'text',text:'<block>yes</block><reason>No user intent for this objective</reason>'}};yield{type:'finish',reason:{kind:'stop'}};return;}
      const input=o.messages.findLast(m=>m.role==='user'&&m.source.kind==='user');
      if(!seen.has(input.id)){seen.add(input.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:input.id+'-goal',name:'create_goal',arguments:JSON.stringify({objective:'An unrelated goal',max_goal_rounds:1})}};yield{type:'finish',reason:{kind:'tool-calls'}};}
      else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}
    });}`);
    await prepareProfile(home, [{ insert: [{ id: 'goal-consent-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home });
    registerNoopTaskHosts(client);
    const requests: string[] = [];
    client.rpc.onNotification((method, value) => {
      if (method !== 'approval.request') return;
      const request = value as { requestId: string; sessionId: string };
      requests.push(request.sessionId);
      void client!.rpc.request('approval.answer', { requestId: request.requestId, decision: 'rejected' });
    });
    await client.rpc.request('initialize', { protocol: 1, agents: ['automatic', 'manual'].map(agentId => ({
      agentId, knowledge:{memoryMode:'legacy'}, revision: '1', mode: agentId === 'automatic' ? 'global' : 'single_thread', provider: 'deepseek-official', model: 'deepseek-flash',
      features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false }, toolAllowlist: ['create_goal'],
      approval: { ...approvalDefaults, rules: 'nano', enabled: agentId === 'automatic', denyLimit: 1, globalRoot: home },
    })), bindings: [] });
    for (const sessionId of ['automatic', 'manual']) {
      await client.rpc.request('session.ensure', { sessionId, agentId: sessionId, revision: '1', ownerId: 'owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId, inputId: sessionId, mode: 'followup', content: [{ type: 'text', text: 'Hello' }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: sessionId } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId, inputId: sessionId }) as { terminal?: unknown }).terminal).toBeTruthy();
      const observation = await client.rpc.request('session.observe', { sessionId }) as { events: any[] };
      expect(observation.events.find(e => e.type === 'tool/result')?.data.message.isError).toBe(true);
      expect(observation.events.some(e => e.type === 'goal/created')).toBe(false);
    }
    expect(requests).toEqual(['manual']);
    const review = await readFile(join(home, 'reviews'), 'utf8');
    expect(review).toContain('"kind":"human"');
    expect(review).toContain('An unrelated goal');
    await client.shutdown(); client = undefined;
  } finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 20_000);
