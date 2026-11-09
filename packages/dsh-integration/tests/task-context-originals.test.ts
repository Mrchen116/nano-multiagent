import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it,vi} from 'vitest';
import {TaskContextDriver} from '../src/task-context.js';
import {stripContextItemId} from 'dsh-agent-context';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
interface Evidence {inputId:string;content:unknown[];turn:number;consumedSeq:number}
async function fixture(){
  const home=await mkdtemp(join(tmpdir(),'nano-task-originals-'));let logs='';
  await writeFile(join(home,'fixture.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='originals-fixture';export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:'checked'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
  await prepareProfile(home,[{insert:[{id:'originals-fixture',name:join(home,'fixture.mjs')}]}]);
  const agent={agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:false,intelligent_ui:false,memory_curation:false,skill_creation:false}};
  const binding={sessionId:'root',agentId:'a',ownerId:'owner',revision:'1',cwd:home};
  const client=()=>new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
  const start=async(c:RuntimeClient)=>{await c.rpc.request('initialize',{protocol:1,agents:[agent],bindings:[binding]});await c.rpc.request('session.ensure',binding);};
  const submit=async(c:RuntimeClient,id:string)=>{await c.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});await expect.poll(async()=>(await c.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as {terminal?:unknown}).terminal).toBeTruthy();};
  const observe=async(c:RuntimeClient)=>await c.rpc.request('session.observe',{sessionId:'root'}) as {events:{type:string;data:any;seq:number}[]};
  return {home,client,start,submit,observe,logs:()=>logs,calls:async()=>{const value=await readFile(join(home,'calls'),'utf8').catch(()=>'');return value.trim().split('\n').filter(Boolean).map(line=>JSON.parse(line));}};
}
it('records original IDs as native executed messages and repairs a lost product consumption ACK after restart',async()=>{
  const f=await fixture();let c=f.client();const original={inputId:'business-original',conversationId:'fixed-chat',content:[{type:'text',text:'原始任务更正，保留语言'}]};let consumed=false;const receipts:Evidence[]=[];
  const prepare=()=>({messages:consumed?[]:[original],revoked:[]});
  const commit=({evidence}:{evidence:Evidence[]})=>({confirmed:evidence.flatMap(item=>{
    if(item.inputId!==original.inputId)return [];
    receipts.push(item);consumed=true;
    return [{inputId:item.inputId,consumedSeq:item.consumedSeq,status:'consumed'}];
  })});
  try{
    c.rpc.handle('product.task_context.prepare',prepare);
    c.rpc.handle('product.task_context.commit',()=>{throw new Error('simulate lost product receipt');});
    await f.start(c);await f.submit(c,'first human');
    const first=(await f.observe(c)).events.filter(event=>event.type==='user/message'&&event.data.id===original.inputId);
    expect(first).toHaveLength(1);expect(first[0]!.data).toMatchObject({source:{kind:'nano-system',channel:'task-context',conversationId:'fixed-chat',messageId:original.inputId}});
    expect(stripContextItemId(first[0]!.data.content)).toEqual(original.content);
    expect(consumed).toBe(false);
    await c.shutdown();c=f.client();
    c.rpc.handle('product.task_context.prepare',prepare);c.rpc.handle('product.task_context.commit',value=>commit(value as {evidence:Evidence[]}));
    await f.start(c);await f.submit(c,'after restart');
    expect(consumed).toBe(true);expect(receipts[0]).toMatchObject({inputId:original.inputId,content:original.content,turn:1,consumedSeq:first[0]!.seq});
    expect((await f.observe(c)).events.filter(event=>event.type==='user/message'&&event.data.id===original.inputId)).toHaveLength(1);
    await f.submit(c,'warm turn');
    expect(receipts).toHaveLength(1);
    expect(JSON.stringify(await f.calls())).toContain('原始任务更正，保留语言');
  }catch(error){throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally{await c.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);
it.each([{revoked:['stale-original']},{revoked:[]}])('withholds an unclaimed passive original while independent input continues ($revoked)',async({revoked})=>{
  const f=await fixture(),c=f.client();
  try{
    c.rpc.handle('product.task_context.prepare',()=>({messages:[],revoked}));c.rpc.handle('product.task_context.commit',()=>null);
    await f.start(c);
    await c.rpc.request('session.submit',{sessionId:'root',inputId:'stale-original',mode:'inject',source:{kind:'system',actorId:'a',channel:'task-context',messageId:'stale-original'},content:[{type:'text',text:'NO_LONGER_AUTHORIZED_SECRET'}]});
    await f.submit(c,'independent human');
    expect(JSON.stringify(await f.calls())).not.toContain('NO_LONGER_AUTHORIZED_SECRET');
    expect(JSON.stringify(await f.calls())).toContain('independent human');
    expect((await f.observe(c)).events.some(event=>event.type==='user/message'&&event.data.id==='stale-original')).toBe(false);
  }catch(error){throw new Error(String(error)+'\n'+f.logs(),{cause:error});}
  finally{await c.shutdown();await rm(f.home,{recursive:true,force:true});}
},25_000);


it('continues an already-admitted human turn when the native cut cannot be read',async()=>{
  type Driver=ConstructorParameters<typeof TaskContextDriver>;
  const hooks=new Map<string,Function>();
  const session={id:'root'};
  const agent={id:'root',session,inbox:{remove:vi.fn()}};
  new TaskContextDriver({
    on:(name:string,handler:Function)=>hooks.set(name,handler),
    sessions:{flush:async()=>true},
    sessionQuery:{observeSession:async()=>{throw new Error('read failed');}},
  } as unknown as Driver[0],{
    bindings:new Map([['root',{sessionId:'root',agentId:'a',ownerId:'owner',cwd:'/tmp',revision:'1'}]]),
    peer:{request:async()=>({messages:[],revoked:[]})} as unknown as Driver[1]['peer'],
    availability:vi.fn(),
    lifecycleRevision:()=>1,
  });
  const signal=new AbortController().signal;
  hooks.get('session/event')!(session,{type:'turn/start',data:{turn:1}});
  await hooks.get('system-prompt/assemble')!({}, {agent,signal},()=>{});
  await hooks.get('agent/pre-step')!({agent,messages:[{id:'human',source:{kind:'user'}}],signal},()=>{});
  hooks.get('session/event')!(session,{type:'user/message',data:{source:{kind:'user'}}});
  await hooks.get('system-prompt/assemble')!({}, {agent,signal},()=>{});
  const next=vi.fn();
  await hooks.get('agent/pre-step')!({agent,messages:[],signal},next);
  expect(next).toHaveBeenCalledOnce();
});
