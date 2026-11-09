import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer, type ServerResponse } from 'node:http';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '@nano/dsh-integration/client';
import { GlobalAgent, InboxStore, NodeStore, TaskContext, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';

it('coalesces Inbox notices during a model request and notifies again after consumption', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-inbox-batch-'));
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  const requests: { messages: any[]; response: ServerResponse }[] = [];
  const server = createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    requests.push({ messages: JSON.parse(body), response });
  });
  let client: RuntimeClient | undefined, product: GlobalAgent | undefined, logs = '';
  const errors: unknown[] = [];
  try {
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const { port } = server.address() as { port: number };
    await writeFile(join(home, 'model.mjs'), `export const name='batch-model';export const inject=['llm'];export function apply(ctx){ctx.on('llm/stream',async function*(o){
      const response=await fetch('http://127.0.0.1:${port}',{method:'POST',body:JSON.stringify(o.messages),signal:o.signal});
      for(const chunk of await response.json())yield chunk;
    });}`);
    await prepareProfile(home, [{ insert: [{ id: 'batch-model', name: join(home, 'model.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerEmptyTaskContext(client);
    const config: AgentConfiguration = { agentId: 'a', revision: '1', workspace: home, mode: 'global', provider: 'deepseek-official', model: 'deepseek-flash', approval: { dangerouslySkipPermissions: true } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox,
      runtime: client.rpc, image: async () => '', onError: error => errors.push(error),
      relay: { request: async (type, payload: any) => {
        if (type === 'agent.work.append') return { type: 'ack', payload: { through_seq: payload.events.at(-1).seq } };
        if (type === 'conversation.query' && payload.action === 'describe') {
          // Match production routing: only an all-external query is handled locally.
          expect(new Set(payload.targets.map((target: string) => target.startsWith('external:'))).size).toBe(1);
          return { type: 'ack', payload: { ok: true, result: { conversations: payload.targets.map((target: string) => ({ target, name: target === 'external:team' ? 'Team' : 'Owner' })) } } };
        }
        return { type: 'ack', payload: { ok: true, result: { target: payload.target, name: payload.target === 'external:team' ? 'Team' : 'Owner', type: payload.target === 'external:team' ? 'group' : 'direct', channel: 'web', members: [{ type: 'user', user_id: 'owner' }] } } };
      } },
    });
    client.rpc.handle('product.call', value => product!.call(value as ProductCall));
    client.rpc.handle('model.check', () => ({ published: false }));
    const input = (id: string, target = 'c_dm', mentions: string[] = []): RelayInput => ({ agent_id: 'a', conversation_id: target, relay_task_id: id, idempotency_key: id,
      metadata: { conversation_type: target === 'external:team' ? 'group' : 'direct', mentioned_agent_ids: mentions },
      message: { id, content: `BODY_${id}`, sender_type: 'user', sender_user_id: 'owner', attachments: [] } });
    const respond = (index: number, target?: string) => requests[index]!.response.end(JSON.stringify(target ? [
      { type: 'block-end', index: 0, block: { type: 'tool-call', id: `read-${index}`, name: 'inbox', arguments: JSON.stringify({ action: 'read', target }) } },
      { type: 'finish', reason: { kind: 'tool-calls' } },
    ] : [{ type: 'block-end', index: 0, block: { type: 'text', text: 'No public reply requested.' } }, { type: 'finish', reason: { kind: 'stop' } }]));
    const notices = (index: number) => requests[index]!.messages.filter(message => message.source?.channel === 'inbox').length;
    await product.receive(input('initial'));
    await expect.poll(() => requests.length).toBe(1);
    await product.receive(input('one', 'external:team', ['a']));
    await product.receive(input('two', 'external:team', ['other-agent']));
    await product.receive(input('three'));
    const binding = store.bindingFor('a', 'global:a')!;
    await client.rpc.request('session.submit', { sessionId: binding.sessionId, inputId: 'other-notice', mode: 'inject',
      content: [{ type: 'text', text: 'OTHER_NOTICE' }], source: { kind: 'system', actorId: 'a', channel: 'other', messageId: 'other-notice' } });
    const summary = (index: number) => JSON.parse(requests[index]!.messages.findLast(message => message.source?.channel === 'inbox').content[0].text.split('\n').at(-1));
    expect(summary(0).sources).toEqual([{ target: 'c_dm', name: 'Owner', unread: 1, mentions: 0, conversation_type: 'direct' }]);
    respond(0, summary(0).sources[0].target);
    await expect.poll(() => requests.length).toBe(2);
    expect(notices(1)).toBe(notices(0) + 1);
    expect(JSON.stringify(requests[1]!.messages)).toContain('OTHER_NOTICE');
    expect(summary(1).sources).toEqual([
      { target: 'c_dm', name: 'Owner', unread: 2, mentions: 0, conversation_type: 'direct' },
      { target: expect.stringMatching(/^c_f_/), name: 'Team', unread: 2, mentions: 1, conversation_type: 'group' },
    ]);
    const notice = requests[1]!.messages.findLast(message => message.source?.channel === 'inbox');
    expect(JSON.stringify(notice)).not.toContain('BODY_');
    respond(1, summary(1).sources.find((source: any) => source.name === 'Team').target);
    await expect.poll(() => requests.length).toBe(3);
    for (const id of ['initial', 'one', 'two', 'three']) expect(JSON.stringify(requests[2]!.messages)).toContain(`BODY_${id}`);
    expect(notices(2)).toBe(notices(1));
    await product.receive(input('later'));
    respond(2, 'c_dm');
    await expect.poll(() => requests.length).toBe(4);
    expect(notices(3)).toBe(notices(2) + 1);
    expect(summary(3).sources).toEqual([{ target: 'c_dm', name: 'Owner', unread: 1, mentions: 0, conversation_type: 'direct' }]);
    expect(JSON.stringify(requests[3]!.messages)).toContain('BODY_later');
    respond(3);
    await expect.poll(async () => (await client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as { status: string }).status).toBe('idle');
    expect(inbox.check('a').sources).toEqual([]);
    expect(errors).toEqual([]);
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    if (product) await product.stop();
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    inbox.close(); store.close(); await rm(home, { recursive: true, force: true });
  }
}, 20000);

// These native fixtures have no Task data; register their product context host explicitly.
function registerEmptyTaskContext(client: RuntimeClient): void {
  client.rpc.handle('product.task_context.prepare', () => ({ messages: [], revoked: [] }));
  client.rpc.handle('product.task_context.commit', () => null);
}

it('refreshes complete PA memory authority through Task preparation even with no unread messages', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-task-memory-authority-'));
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  let client: RuntimeClient | undefined, product: GlobalAgent | undefined;
  let excluded = false, logs = '';
  const queries: string[] = [];
  const config: AgentConfiguration = { agentId: 'pa', revision: '1', workspace: home, mode: 'global',
    provider: 'deepseek-official', model: 'deepseek-flash', features: { dreaming: false, task_graph: true },
    personal: { bindingId: 'binding', ownerId: 'owner', conversationId: 'owner-chat', epoch: 1 } };
  const binding = store.bind({ agentId: 'pa', sessionId: 'main', conversationId: 'global:pa', ownerId: 'owner', cwd: home, revision: '1' });
  try {
    await writeFile(join(home, 'model.mjs'), `import {appendFile,readFile} from 'node:fs/promises';
export const name='task-memory-observer';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(options){
 await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({messages:options.messages,authority:JSON.parse(await readFile(process.env.DSH_HOME+'/.nanoassistant/maintenance/documents.json','utf8'))})+'\\n');
 yield {type:'block-end',index:0,block:{type:'text',text:'Observed current context.'}};yield {type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home, [{ insert: [{ id: 'task-memory-observer', name: join(home, 'model.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    const runtime = { request: (method: string, params: unknown) => client!.rpc.request(method, params), onNotification: () => () => {} };
    const relay = { async request(type: string) {
      queries.push(type);
      if (type === 'pa.sources') return { type: 'result', payload: { ok: true, result: {
        policy: { revision: excluded ? 2 : 1 }, items: [{ id: 'historical-room', excluded }],
      } } };
      if (type === 'task.context.sync') return { type: 'result', payload: { ok: true, result: {
        through: 0, next: 0, items: [], revoked_message_ids: [],
      } } };
      throw new Error('Unexpected product request: ' + type);
    } };
    product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox, runtime, relay,
      image: async () => '', onError: error => { throw error; } });
    const taskContext = new TaskContext({ nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox, runtime, relay,
      refreshSources: async agentId => {
        try { await product!.prepareSystemContext(agentId); }
        catch (error) { logs += '\nSource refresh: ' + String(error); throw error; }
      } });
    client.rpc.handle('product.task_context.prepare', value => taskContext.prepare(value as Parameters<TaskContext['prepare']>[0]));
    client.rpc.handle('product.task_context.commit', value => taskContext.commit(value as Parameters<TaskContext['commit']>[0]));
    client.rpc.handle('product.task_execution.snapshot', () => ({ kind: 'quiescent', tasks: [], repair_task_ids: [] }));
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const submit = async (inputId: string) => {
      await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId, mode: 'followup',
        content: [{ type: 'text', text: 'Use current facts to answer this independent question.' }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId }) as any).terminal).toBeTruthy();
    };
    expect(inbox.check('pa').sources).toEqual([]);
    await submit('before-exclusion');
    excluded = true;
    await submit('after-exclusion');
    expect(inbox.check('pa').sources).toEqual([]);
    const requests = (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const current = (messages: any[]) => messages.findLast(message => message.source?.kind === 'runtime-context');
    expect(requests).toHaveLength(2);
    expect(requests[0].authority.generation).toBe(1);
    expect(JSON.stringify(current(requests[0].messages))).toContain('Personal memory');
    const after = JSON.stringify(current(requests[1].messages));
    expect(requests[1].authority.generation).toBe(2);
    expect(after).not.toContain('Source generation:');
    expect(after).not.toContain('entry_basis_stale');
    expect(after).toContain('Personal memory');
    expect(after).not.toContain('Current entry:');
    expect(queries).toEqual(['pa.sources', 'task.context.sync', 'pa.sources', 'task.context.sync']);
  } catch (error) { throw new Error(String(error) + '\n' + logs + '\nSource queries: ' + JSON.stringify(queries), { cause: error }); }
  finally { await product?.stop(); await client?.shutdown(); inbox.close(); store.close(); await rm(home, { recursive: true, force: true }); }
}, 20_000);

it('delivers a busy Inbox notice at the next native model request without injecting the body or bypassing send review', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-inbox-'));
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  let client: RuntimeClient | undefined, product: GlobalAgent | undefined;
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let entered = false, returned = false, logs = '';
  const errors: unknown[] = [], sent: string[] = [];
  const correction = 'CORRECTION: change only the frontend';
  try {
    await writeFile(join(home, 'model.mjs'), `import {appendFile} from 'node:fs/promises';
export const name='inbox-model'; export const inject=['llm']; export function apply(ctx){let step=0;ctx.on('llm/stream',async function*(o){
  await appendFile(${JSON.stringify(join(home, 'requests.jsonl'))},JSON.stringify(o.messages)+'\\n');
  const actions=[['inbox',{action:'read',target:'c_dm'}],['send_message',{target:'c_dm',text:'Old draft'}],['inbox',{action:'read',target:'c_dm'}],['send_message',{target:'c_dm',text:'Corrected result'}]];
  const action=actions[step++];
  if(action){yield {type:'block-end',index:0,block:{type:'tool-call',id:'call-'+step,name:action[0],arguments:JSON.stringify(action[1])}};yield {type:'finish',reason:{kind:'tool-calls'}};}
  else{yield {type:'block-end',index:0,block:{type:'text',text:'Result delivered.'}};yield {type:'finish',reason:{kind:'stop'}};}
});}`);
    await prepareProfile(home, [{ insert: [{ id: 'inbox-model', name: join(home, 'model.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerEmptyTaskContext(client);
    const config: AgentConfiguration = { agentId: 'a', revision: '1', workspace: home, mode: 'global', provider: 'deepseek-official', model: 'deepseek-flash', approval: { dangerouslySkipPermissions: true } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox,
      runtime: client.rpc, image: async () => '', onError: error => errors.push(error),
      relay: { request: async (type, payload) => {
        if (type === 'agent.work.append') return { type: 'ack', payload: { through_seq: (payload.events as { seq: number }[]).at(-1)!.seq } };
        if (type === 'conversation.query' && payload.action === 'describe') return { type: 'ack', payload: { ok: true, result: { conversations: (payload.targets as string[]).map(target => ({ target, name: 'Owner' })) } } };
        if (type === 'conversation.query') return { type: 'conversation.query.result', payload: { ok: true, result: { target: 'c_dm', name: 'Owner', type: 'direct', channel: 'web', members: [{ type: 'user', user_id: 'owner' }] } } };
        if (type === 'agent.message') { sent.push(String(payload.text)); return { type: 'ack', payload: { message_id: 'reply' } }; }
        return { type: 'ack', payload: {} };
      } },
    });
    client.rpc.handle('product.call', async value => {
      const call = value as ProductCall;
      if (call.method === 'send_message' && call.args.text === 'Old draft') { entered = true; await held; returned = true; }
      return product!.call(call);
    });
    client.rpc.handle('model.check', () => ({ published: false }));
    const input = (id: string, content: string): RelayInput => ({ agent_id: 'a', conversation_id: 'c_dm', relay_task_id: id, idempotency_key: id,
      metadata: { conversation_type: 'direct' }, message: { id, content, sender_type: 'user', sender_user_id: 'owner', attachments: [] } });
    await product.receive(input('initial', 'Start the large task'));
    await expect.poll(() => entered).toBe(true);
    await product.receive(input('correction', correction));
    await product.receive(input('more-context', 'Additional task context'));
    await product.receive(input('last-context', 'Final task context'));
    expect(returned).toBe(false);
    const requests = async () => (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(await requests()).toHaveLength(2);
    release();
    await expect.poll(async () => (await requests()).length).toBeGreaterThanOrEqual(5);
    const captured = await requests();
    const noticeCount = (messages: any[]) => messages.filter(message => message.source?.channel === 'inbox').length;
    expect(noticeCount(captured[2])).toBe(noticeCount(captured[1]) + 1);
    const summary = JSON.parse(captured[2].findLast((message: any) => message.source?.channel === 'inbox').content[0].text.split('\n').at(-1));
    expect(summary.sources).toEqual([{ target: 'c_dm', name: 'Owner', unread: 3, mentions: 0, conversation_type: 'direct' }]);
    expect(JSON.stringify(captured[2])).not.toContain(correction);
    expect(JSON.stringify(captured[2])).toContain('held_for_revalidation');
    expect(JSON.stringify(captured[3])).toContain(correction);
    expect(JSON.stringify(captured[3])).toContain('Additional task context');
    expect(JSON.stringify(captured[3])).toContain('Final task context');
    expect(sent).toEqual(['Corrected result']);
    const binding = store.bindingFor('a', 'global:a')!;
    await expect.poll(async () => (await client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as { status: string }).status).toBe('idle');
    expect(errors).toEqual([]);
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally {
    release();
    if (product) await product.stop();
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    inbox.close(); store.close(); await rm(home, { recursive: true, force: true });
  }
}, 20000);

it('keeps a due PA background batch outside a busy native turn and admits it once on idle',async()=>{
  const home=await mkdtemp(join(tmpdir(),'nano-pa-background-'));
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  let client:RuntimeClient|undefined,product:GlobalAgent|undefined;
  let release!:()=>void;const held=new Promise<void>(resolve=>{release=resolve;});
  let entered=false,logs='';const errors:unknown[]=[];
  try {
    await writeFile(join(home,'model.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='background-model';export const inject=['llm'];export function apply(ctx){let step=0;ctx.on('llm/stream',async function*(o){
  await appendFile(${JSON.stringify(join(home,'requests.jsonl'))},JSON.stringify(o.messages)+'\\n');
  if(step++===0){yield {type:'block-end',index:0,block:{type:'tool-call',id:'held-read',name:'inbox',arguments:JSON.stringify({action:'read',target:'background'})}};yield{type:'finish',reason:{kind:'tool-calls'}};}
  else{yield{type:'block-end',index:0,block:{type:'text',text:'No public reply needed.'}};yield{type:'finish',reason:{kind:'stop'}};}
});}`);
    await prepareProfile(home,[{insert:[{id:'background-model',name:join(home,'model.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    registerEmptyTaskContext(client);
    const config:AgentConfiguration={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'binding',ownerId:'owner',conversationId:'own',epoch:1},approval:{dangerouslySkipPermissions:true}};
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,runtime:client.rpc,image:async()=>'',onError:error=>errors.push(error),
      relay:{request:async(type,args:any)=>{
        if(type==='agent.work.append')return {type:'ack',payload:{through_seq:args.events.at(-1).seq}};
        if(type==='conversation.query')return {type:'ack',payload:{ok:true,result:{conversations:args.targets.map((target:string)=>({target,name:target==='own'?'Owner':'Background chat'}))}}};
        const result=type==='pa.source.admit'?{allowed:true,is_owner:true,delivery:args.conversation_id==='own'?'participant':'observer',conversation_type:'direct',channel:'web'}
          :type==='pa.observations.read'?{items:[]}:type==='pa.sources'?{policy:{revision:1},items:[{id:'background',excluded:false}]}:{};
        return {type:'ack',payload:{ok:true,result}};
      }}});
    client.rpc.handle('product.call',async value=>{
      const call=value as ProductCall;
      if(call.method==='inbox'){entered=true;await held;return {target:'background',messages:[]};}
      return product!.call(call);
    });
    client.rpc.handle('model.check',()=>({published:false}));
    const input=(id:string,target:string):RelayInput=>({agent_id:'pa',conversation_id:target,relay_task_id:id,idempotency_key:id,metadata:{},message:{id,content:id,sender_type:'user',sender_user_id:'owner',attachments:[]}});
    await product.receive(input('direct task','own'));
    await expect.poll(()=>entered).toBe(true);
    const observed=input('PRIVATE_OBSERVED_BODY','background');
    Object.assign(observed.metadata,{personal_delivery:'observer',personal_is_owner:true,conversation_type:'direct',channel:'web'});
    // Persist a due deadline without changing the native subprocess clock.
    inbox.receive(observed,false,Date.now()-600001);
    await product.recover();
    const binding=store.bindingFor('pa','global:pa')!;
    const state=()=>client!.rpc.request('session.observe',{sessionId:binding.sessionId}) as Promise<{status:string;events:any[]}>;
    expect(JSON.stringify((await state()).events)).not.toContain('inbox-background');
    release();
    await expect.poll(async()=>JSON.stringify((await state()).events).includes('inbox-background')).toBe(true);
    await expect.poll(async()=>(await state()).status).toBe('idle');
    const events=(await state()).events;
    expect(events.filter(e=>e.type==='user/message'&&e.data.source?.channel==='inbox-background')).toHaveLength(1);
    const requests=await readFile(join(home,'requests.jsonl'),'utf8');
    expect(requests).not.toContain('PRIVATE_OBSERVED_BODY');
    const backgroundNotice=requests.trim().split('\n').flatMap(line=>JSON.parse(line)).find(message=>message.source?.channel==='inbox-background');
    const summary=JSON.parse(backgroundNotice.content[0].text.split('\n').at(-1));
    expect(summary.sources).toContainEqual({target:'background',name:'Background chat',unread:1,mentions:0,conversation_type:'direct',delivery:'observer'});
    expect(summary.sources).toContainEqual({target:'own',name:'Owner',unread:1,mentions:0,conversation_type:'direct',delivery:'participant'});
    expect(inbox.check('pa',true).sources.find(s=>s.target==='background')?.unread).toBe(1);
    expect(errors).toEqual([]);
  }catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{release();if(product)await product.stop();if(client){client.process.kill('SIGKILL');await client.exited;}inbox.close();store.close();await rm(home,{recursive:true,force:true});}
},20000);

it('resumes a paged native child after runtime loss and pairs the complete tool result in Work', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-work-page-restart-'));
  const store=new NodeStore(join(home,'node.sqlite'),'owner'),inbox=new InboxStore(join(home,'inbox.sqlite'));
  const binding=store.bind({sessionId:'root',agentId:'a',conversationId:'global:a',ownerId:'owner',cwd:home,revision:'1'});
  const config:AgentConfiguration={agentId:'a',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',
    toolAllowlist:['subagent','work_probe'],approval:{dangerouslySkipPermissions:true}};
  let client:RuntimeClient|undefined,product:GlobalAgent|undefined,cut:number|undefined,childId:string|undefined;
  let cutAtReconnect:number|undefined,inject=true,logs='';
  const errors:unknown[]=[];
  try {
    const fixture=join(home,'fixture.mjs');
    await writeFile(fixture,`export const inject=['llm','tools'];export function apply(ctx){
      ctx.tools.register({name:'work_probe',description:'Work probe',parameters:{type:'object'},output:{schema:{type:'string'},render:()=>[{type:'text',text:'probe result'}]},execute:async()=>'result',
        presentCall:()=>({card:'generic',title:'probe'}),presentResult:()=>({card:'generic',title:'result',detail:'z'.repeat(1100000)})});
      const called=new Set();
      ctx.on('llm/stream',async function*(o){
        const id=o.sessionId;
        if(!called.has(id)){
          called.add(id);
          yield {type:'block-end',index:0,block:{type:'tool-call',id:'call-'+id,name:id==='root'?'subagent':'work_probe',
            arguments:id==='root'?JSON.stringify({prompt:'Use work_probe',description:'Child Work',run_in_background:false}):'{}'}};
          yield {type:'finish',reason:{kind:'tool-calls'}};return;
        }
        yield {type:'block-end',index:0,block:{type:'text',text:'DONE'}};yield {type:'finish',reason:{kind:'stop'}};
      });
    }`);
    await prepareProfile(home,[{insert:[{id:'work-probe',name:fixture}]}]);
    const start=async()=>{
      client=new RuntimeClient({home,cwd:home,onLog:line=>{logs+=line;}});
      registerEmptyTaskContext(client);
      client.rpc.handle('model.check',()=>({published:false}));
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});
    };
    await start();
    await client!.rpc.request('session.ensure',binding);
    await client!.rpc.request('session.submit',{sessionId:'root',inputId:'start',mode:'followup',content:[{type:'text',text:'Launch child'}],source:{kind:'human',channel:'test',actorId:'owner',messageId:'start'}});
    await expect.poll(async()=>await client!.rpc.request('session.lookup',{sessionId:'root',inputId:'start'})).toMatchObject({terminal:{kind:'completed'}});
    const create=()=>new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:error=>errors.push(error),
      relay:{request:async()=>({type:'ack',payload:{}})},
      runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
        if(method!=='session.work.child')return client!.rpc.request(method,args);
        childId=args.childId;
        if(!inject)cutAtReconnect??=args.afterSeq;
        if(inject && cut!==undefined){
          expect(args.afterSeq).toBe(cut);
          client!.process.kill('SIGKILL');await client!.exited;
          throw new Error('fixture runtime disconnected before the next Work page');
        }
        const page=await client!.rpc.request(method,args) as import('@nano/product-contracts').RuntimeWorkPage;
        if(inject && page.more && page.events.some(event=>event.type==='tool/call' && event.data.name==='work_probe'))cut=page.throughSeq;
        return page;
      }}});
    product=create();
    await product.recover();
    expect(cut).toBeDefined();
    expect(errors.map(String)).toContain('Error: fixture runtime disconnected before the next Work page');
    expect(inbox.workCut(childId!)?.throughSeq).toBe(cut);
    expect(inbox.workProcessingPending).toBe(true);
    await product.stop();product=undefined;
    inject=false;errors.length=0;
    await start();product=create();
    await product.recover();
    expect(cutAtReconnect).toBe(cut);
    expect(errors).toEqual([]);
    const rows=inbox.journal(0,1000).filter(row=>row.session_id===childId);
    expect(rows.filter(row=>row.type==='tool_start')).toHaveLength(1);
    expect(rows.filter(row=>row.type==='tool_end')).toHaveLength(1);
    expect(rows.find(row=>row.type==='tool_end')?.payload).toMatchObject({tool_name:'work_probe',presentation:{detail:{native_view:{detail:'z'.repeat(1100000)}}}});
    expect(rows.filter(row=>row.type==='turn_end')).toHaveLength(1);
    expect(inbox.workOpenEvents(childId!)).toEqual([]);
    expect(inbox.workProcessingPending).toBe(false);
  } catch(error) {throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally {await product?.stop();if(client?.process.exitCode===null&&client.process.signalCode===null){client.process.kill('SIGKILL');await client.exited;}
    inbox.close();store.close();await rm(home,{recursive:true,force:true});}
},25_000);
