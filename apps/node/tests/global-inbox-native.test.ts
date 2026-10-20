import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '@nano/dsh-integration/client';
import { GlobalAgent, InboxStore, NodeStore, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';

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
    const config: AgentConfiguration = { agentId: 'a', revision: '1', workspace: home, mode: 'global', provider: 'deepseek-official', model: 'deepseek-flash', approval: { dangerouslySkipPermissions: true } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    product = new GlobalAgent({ nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox,
      runtime: client.rpc, image: async () => '', onError: error => errors.push(error),
      relay: { request: async (type, payload) => {
        if (type === 'agent.work.append') return { type: 'ack', payload: { through_seq: (payload.events as { seq: number }[]).at(-1)!.seq } };
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
    expect(returned).toBe(false);
    const requests = async () => (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(await requests()).toHaveLength(2);
    release();
    await expect.poll(async () => (await requests()).length).toBeGreaterThanOrEqual(5);
    const captured = await requests();
    const noticeCount = (messages: any[]) => messages.filter(message => message.source?.channel === 'inbox').length;
    expect(noticeCount(captured[2])).toBe(noticeCount(captured[1]) + 1);
    expect(JSON.stringify(captured[2])).not.toContain(correction);
    expect(JSON.stringify(captured[2])).toContain('held_for_revalidation');
    expect(JSON.stringify(captured[3])).toContain(correction);
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
    const config:AgentConfiguration={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'binding',ownerId:'owner',conversationId:'own',epoch:1},approval:{dangerouslySkipPermissions:true}};
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,runtime:client.rpc,image:async()=>'',onError:error=>errors.push(error),
      relay:{request:async(type,args:any)=>{
        if(type==='agent.work.append')return {type:'ack',payload:{through_seq:args.events.at(-1).seq}};
        const result=type==='pa.source.admit'?{allowed:true,is_owner:true,delivery:args.conversation_id==='own'?'participant':'observer',conversation_type:'direct',channel:'web'}
          :type==='pa.observations.read'?{items:[]}:type==='pa.sources'?{items:[{id:'background',excluded:false}]}:{};
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
    expect(inbox.check('pa',true).sources.find(s=>s.target==='background')?.unread).toBe(1);
    expect(errors).toEqual([]);
  }catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally{release();if(product)await product.stop();if(client){client.process.kill('SIGKILL');await client.exited;}inbox.close();store.close();await rm(home,{recursive:true,force:true});}
},20000);
