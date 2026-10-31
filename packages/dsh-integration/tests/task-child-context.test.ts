import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskContext } from './helpers/noop-task-context.js';

type Event = { seq: number; type: string; data: any; surfaceOp?: any; sourceEventSeqs?: number[] };
type Request = { session: string; body: any };
const privateChannels = ['task-execution', 'task-reminder', 'task-context-limitation', 'task-wait-repair'];
const text = (message: any): string => typeof message.content === 'string' ? message.content : (message.content ?? []).filter((block: any) => block.type === 'text').map((block: any) => block.text).join('');
const fixture = [
  "import {writeFile} from 'node:fs/promises';",
  "import {freezeMessage} from " + JSON.stringify(pathToFileURL(createRequire(import.meta.url).resolve('@deepseek-ai/dsh-llm')).href) + ';',
  "export const name='task-child-context-fixture'; export const inject=['agents','tools','sessionQuery','sessions','subagents'];",
  'export function apply(ctx){let seeded=false;const children=new Set();',
  "ctx.tools.register({name:'visibility_continuable',description:'Fixture: establish a native continuable fork',parameters:{type:'object',properties:{prompt:{type:'string'}},required:['prompt']},output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},execute:async(args,exec)=>{const child=await ctx.subagents.startContinuable({provider:'fork',label:'Retain findings',request:{parent:exec.agent,prompt:[{type:'text',text:args.prompt}],agentOptions:{provider:'wire',model:'fixture'}},signal:exec.signal});return {childId:child.childId};}});",
  "ctx.tools.register({name:'visibility_resume',description:'Fixture: use native adjacent cold-resume delivery',parameters:{type:'object',properties:{agent_id:{type:'string'},message:{type:'string'}},required:['agent_id','message']},output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},execute:async(args,exec)=>({messageId:await ctx.subagents.sendMessage(exec.agent,args.agent_id,[{type:'text',text:args.message}],{signal:exec.signal})})});",
  "ctx.on('agent/created',({agent})=>{agent.ctx.tools.presentAs('native');",
  " if(agent.id!=='root')children.add(agent.id);",
  " if(agent.id==='root'||agent.session.snapshotEvents().some(e=>e.type==='user/message'&&e.data.id==='child-local-schedule'))return;",
  " for(const [id,channel,body] of [['child-local-schedule','schedule-change','CHILD_LOCAL_SCHEDULE'],['child-local-private','task-context-limitation','CHILD_LOCAL_DIAGNOSTIC']])agent.inject(freezeMessage({id,role:'user',source:{kind:'nano-system',actorId:'a',channel,messageId:id},content:[{type:'text',text:body}]}));",
  '});',
  "ctx.on('agent/turn-stopping',async({agent})=>{if(agent.id==='root'){for(const id of children)try{using observation=await ctx.sessionQuery.observeSession(id);}catch(error){await writeFile(process.env.DSH_HOME+'/'+id+'.query-error',String(error)+'\\n'+error.stack+'\\n'+String(error.cause)+'\\n'+error.cause?.stack);}return;}await writeFile(process.env.DSH_HOME+'/'+agent.id+'.canonical.json',JSON.stringify(agent.session.snapshotEvents()));try{await ctx.sessions.flush(agent.session);using observation=await ctx.sessionQuery.observeSession(agent.id);}catch(error){await writeFile(process.env.DSH_HOME+'/'+agent.id+'.query-error',String(error)+'\\n'+error.stack+'\\n'+JSON.stringify(error.cause));}});",
  "ctx.on('session/event',(session,event)=>{if(session.id!=='root'||event.type!=='turn/end'||seeded||session.snapshotEvents().some(e=>e.type==='user/message'&&e.data.id==='private-task-execution'))return;seeded=true;queueMicrotask(()=>{",
  " for(const channel of ['task-execution','task-reminder','task-context-limitation','task-wait-repair'])session.append('user/message',freezeMessage({id:'private-'+channel,role:'user',source:{kind:'nano-system',actorId:'a',channel,messageId:'private-'+channel},content:[{type:'text',text:'ROOT_PRIVATE_'+channel+' D4 D5 D7 D9 D10 Current Task context: PRIVATE_SNAPSHOT'}]}),{surfaceOp:'append'});",
  " for(const [id,channel,body] of [['business-d3','task-context','BUSINESS_D3_TASK_FACT'],['authorization','task-human-control','PARENT_AUTHORIZATION_EVIDENCE'],['parent-schedule','schedule-change','PARENT_SCHEDULE_EVIDENCE']])session.append('user/message',freezeMessage({id,role:'user',source:{kind:'nano-system',actorId:'a',channel,messageId:id},content:[{type:'text',text:body}]}),{surfaceOp:'append'});",
  '});});}',
].join('\n');

it('retains inherited Task context and the parent system on fork wire and cold resume', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-task-child-context-'));
  let client: RuntimeClient | undefined, logs = '';
  const requests: Request[] = [], issued = new Set<string>();
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(Buffer.from(chunk));
    const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    const session = String(req.headers['x-agent-session-id']);
    requests.push({ session, body });
    const human = body.messages.findLast((message: any) => message.role === 'user' && text(message).includes('ROOT_COMMAND_'));
    const command = human && text(human).match(/ROOT_COMMAND_(FORK|RESUME:[^\s<]+)/)?.[1];
    const fresh = session === 'root' && command && !issued.has(command);
    let calls: [string, object][] = [];
    if (fresh) {
      issued.add(command);
      if (command === 'FORK') calls = [
        ['subagent_fork', { prompt: 'PARENT_DELEGATION_ONESHOT', description: 'Check independent facts', run_in_background: false }],
        ['visibility_continuable', { prompt: 'PARENT_DELEGATION_CONTINUABLE' }],
      ];
      else calls = [['visibility_resume', { agent_id: command.slice(7), message: 'PARENT_RESUME_DELEGATION' }]];
    }
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write('event: ' + type + '\ndata: ' + JSON.stringify({ type, ...data }) + '\n\n');
    emit('message_start', { message: { id: 'fixture-' + requests.length, type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
    if (calls.length) for (const [index, [name, input]] of calls.entries()) {
      emit('content_block_start', { index, content_block: { type: 'tool_use', id: 'visibility-' + requests.length + '-' + index, name, input: {} } });
      emit('content_block_delta', { index, delta: { type: 'input_json_delta', partial_json: JSON.stringify(input) } });
      emit('content_block_stop', { index });
    } else {
      emit('content_block_start', { index: 0, content_block: { type: 'text', text: '' } });
      emit('content_block_delta', { index: 0, delta: { type: 'text_delta', text: session === 'root' ? 'ROOT_WIRE_DONE' : 'CHILD_WIRE_DONE' } });
      emit('content_block_stop', { index: 0 });
    }
    emit('message_delta', { delta: { stop_reason: calls.length ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 4 } });
    emit('message_stop', {}); res.end();
  });
  const config = { agentId: 'a', displayName: 'P · 产品与体验', revision: '1', mode: 'global', workspace: home, provider: 'wire', model: 'fixture', systemPrompt: 'VISIBILITY_SYSTEM_HEAD',
    toolAllowlist: ['subagent_fork', 'visibility_continuable', 'visibility_resume', 'skill'], knowledge: { memoryMode: 'legacy' },
    skillRoots: [{ path: join(home, 'skills'), source: 'workspace' }], skillSelection: { mode: 'explicit_allowlist', names: ['evidence'] },
    features: { task_graph: false, intelligent_ui: false, memory_curation: false, skill_creation: false, cron_scheduling: false, heartbeat: false } };
  const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  const start = async () => {
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture-only' }, onLog: value => { logs += value; } });
    registerNoopTaskContext(client);
    client.rpc.handle('product.task_execution.snapshot', () => ({ kind: 'quiescent', tasks: [], repair_task_ids: [] }));
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
  };
  const submit = async (inputId: string, value: string) => {
    await client!.rpc.request('session.submit', { sessionId: 'root', inputId, mode: 'followup', content: [{ type: 'text', text: value }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId } });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId }) as any).terminal, { timeout: 15_000 }).toBeTruthy();
  };
  const observe = async (): Promise<Event[]> => (await client!.rpc.request('session.observe', { sessionId: 'root' }) as any).events;
  const descendants = async (): Promise<{ id: string; kind:string;mode?:string;events?:Event[] }[]> => await client!.rpc.request('session.descendants', { sessionId: 'root' }) as any;
  const canonical=async(id:string):Promise<Event[]>=>JSON.parse(await readFile(join(home,id+'.canonical.json'),'utf8'));
  const omissions = (events: Event[]) => events.filter(event => event.type === 'system/message' && event.data.message.content.length === 0 && event.sourceEventSeqs?.length === 1 && events.some(target => target.seq === event.sourceEventSeqs![0] && target.type === 'user/message' && privateChannels.includes(target.data.source?.channel)));
  const assertWire = (request: Request, events: Event[]) => {
    const raw = JSON.stringify(request.body);
    for (const channel of privateChannels) expect(raw).toContain('ROOT_PRIVATE_' + channel);
    for (const retained of ['BUSINESS_D3_TASK_FACT', 'PARENT_AUTHORIZATION_EVIDENCE', 'PARENT_SCHEDULE_EVIDENCE', 'PARENT_ORDINARY_AUTHORIZATION', 'QUOTED Current Task context: PRIVATE_SNAPSHOT', 'CHILD_LOCAL_SCHEDULE', 'CHILD_LOCAL_DIAGNOSTIC']) expect(raw).toContain(retained);
    expect(JSON.stringify(request.body.system)).toContain('VISIBILITY_SYSTEM_HEAD');
    expect(JSON.stringify(request.body.system)).not.toContain('You are an internal execution agent');
    expect(JSON.stringify(request.body.system)).not.toContain('You are an internal subagent of this product Agent:');
    expect(JSON.stringify(request.body.system)).toContain(config.displayName);
    expect(JSON.stringify(request.body.system)).toContain('Your Agent name:');
    const visible = request.body.messages.map((message: any) => text(message)).join('\n');
    const runtime = events.find(event => event.type === 'user/message' && event.data.source.kind === 'runtime-context');
    const catalog = events.find(event => event.type === 'user/message' && event.data.source.kind === 'skill-catalog');
    expect(runtime).toBeDefined(); expect(catalog).toBeDefined();
    const runtimePosition = visible.indexOf(text(runtime!.data));
    const catalogPosition = visible.indexOf(text(catalog!.data));
    expect(runtimePosition).toBeGreaterThanOrEqual(0); expect(catalogPosition).toBeGreaterThanOrEqual(0);
    expect(runtimePosition).toBeLessThan(catalogPosition);
    expect(catalogPosition).toBeLessThan(visible.indexOf('PARENT_ORDINARY_AUTHORIZATION'));
  };
  try {
    await mkdir(join(home, 'skills', 'evidence'), { recursive: true });
    await writeFile(join(home, 'skills', 'evidence', 'SKILL.md'), '---\nname: evidence\ndescription: Verify delegated evidence.\n---\nSkill evidence body');
    await writeFile(join(home, 'fixture.mjs'), fixture);
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const port = (server.address() as { port: number }).port;
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { wire: { api: 'anthropic-messages', apiKeyEnv: 'NANO_TEST_KEY', baseURL: 'http://127.0.0.1:' + port, models: [{ id: 'fixture', contextWindow: 100000 }], retryPolicy: { mode: 'normal', maxRetries: 0 } } } } },
      // Native fork remains one-shot; a separately configured public fork-backed continuable
      // tool exercises the same inherited surface after actual process recreation.
      { id: 'tool-subagent', config: { provider: 'fork' } },
      { insert: [{ id: 'task-child-context-fixture', name: join(home, 'fixture.mjs') }] },
    ]);
    await start(); await submit('warmup', 'Prepare independent verification');
    await expect.poll(async () => (await observe()).some(event => event.type === 'user/message' && event.data.id === 'private-task-execution')).toBe(true);
    await submit('consume', 'PARENT_ORDINARY_AUTHORIZATION: verify only; QUOTED Current Task context: PRIVATE_SNAPSHOT');
    const parentBefore = await observe();
    const privateEvents = parentBefore.filter(event => event.type === 'user/message' && String(event.data.id).startsWith('private-'));
    expect(privateEvents).toHaveLength(4);
    const consumed = requests.filter(request => request.session === 'root').at(-1)!;
    for (const channel of privateChannels) expect(JSON.stringify(consumed.body)).toContain('ROOT_PRIVATE_' + channel);
    await submit('fork', 'ROOT_COMMAND_FORK');
    await expect.poll(() => new Set(requests.filter(request => request.session !== 'root').map(request => request.session)).size, { timeout: 15_000 }).toBe(2);
    const childIds=[...new Set(requests.filter(request=>request.session!=='root').map(request=>request.session))];
    await expect.poll(async()=>Promise.all(childIds.map(id=>canonical(id).catch(()=>[]))).then(children=>children.filter(events=>events.some(event=>event.type==='assistant/message'&&text(event.data.message)==='CHILD_WIRE_DONE')).length)).toBe(2);
    await submit('inspect','ROOT_COMMAND_INSPECT');
    const children = await descendants();expect(children.every(child=>child.kind==='child')).toBe(true);
    for (const child of children) {
      const events=await canonical(child.id);
      for (const original of parentBefore) expect(events.find(event => event.seq === original.seq)).toEqual(original);
      expect(child.events!.filter(event=>parentBefore.some(original=>original.seq===event.seq))).toEqual([]);
      expect(omissions(events)).toHaveLength(0);
      assertWire(requests.find(request => request.session === child.id)!, events);
      expect(JSON.stringify(requests.find(request => request.session === child.id)!.body)).toContain('PARENT_DELEGATION_');
    }
    const parentAfter = await observe();
    for (const event of parentBefore) expect(parentAfter.find(current => current.seq === event.seq)).toEqual(event);
    expect(omissions(parentAfter)).toHaveLength(0);
    const continuable = children.find(child => child.mode==='continuable')!;
    expect(continuable).toBeDefined();
    const beforeCount = requests.filter(request => request.session === continuable.id).length;
    const originalEvents=await canonical(continuable.id),originalOmissions = omissions(originalEvents);
    await client!.shutdown(); client = undefined;
    await start(); await submit('resume', 'ROOT_COMMAND_RESUME:' + continuable.id);
    await expect.poll(() => requests.filter(request => request.session === continuable.id).length, { timeout: 15_000 }).toBeGreaterThan(beforeCount);
    await expect.poll(async()=>(await canonical(continuable.id)).length).toBeGreaterThan(originalEvents.length);
    const resumed=await canonical(continuable.id);
    expect((await descendants()).find(child=>child.id===continuable.id)?.kind).toBe('child');
    expect(omissions(resumed)).toEqual(originalOmissions);
    for (const original of originalEvents) expect(resumed.find(event => event.seq === original.seq)).toEqual(original);
    assertWire(requests.filter(request => request.session === continuable.id).at(-1)!, resumed);
    expect(JSON.stringify(requests.filter(request => request.session === continuable.id).at(-1)!.body)).toContain('PARENT_RESUME_DELEGATION');
    expect(logs).not.toContain('Method not found');
  } catch (error) {
    const queryErrors=await Promise.all([...new Set(requests.filter(request=>request.session!=='root').map(request=>request.session))].map(id=>readFile(join(home,id+'.query-error'),'utf8').catch(()=>'')));
    throw new Error(String(error) + '\nQuery errors: '+JSON.stringify(queryErrors) + '\nDescendants: ' + JSON.stringify((await descendants()).map(({events,...entry}:any)=>({...entry,eventCount:events?.length}))) + '\nTool events: ' + JSON.stringify((await observe()).filter(event=>event.type==='tool/result'&&event.data.message.isError)) + '\n' + logs + '\nWire requests: ' + JSON.stringify(requests.map(request => ({ session: request.session, messageCount:request.body.messages?.length }))), { cause: error });
  } finally {
    if (client) await client.shutdown();
    await new Promise<void>(resolve => { server.close(() => resolve()); server.closeAllConnections(); });
    await rm(home, { recursive: true, force: true });
  }
}, 60_000);
