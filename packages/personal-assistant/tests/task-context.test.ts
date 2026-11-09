import {StatementSync} from 'node:sqlite';
import {expect,it,vi} from 'vitest';
import type {AgentConfiguration,RelayInput} from '@nano/product-contracts';
import {NodeStore} from '../src/store.js';
import {InboxStore} from '../src/inbox.js';
import {TaskContext} from '../src/task-context.js';
import {SingleThread} from '../src/single-thread.js';
const agent:AgentConfiguration={agentId:'a',mode:'global',workspace:'/tmp',revision:'1',provider:'p',model:'m'};
const original=(id:string):RelayInput=>({agent_id:'a',conversation_id:'chat',idempotency_key:id,relay_task_id:id,message:{id,content:'Original '+id,sender_type:'system',sender_user_id:'human',attachments:[],system_notice:{kind:'task_graph',attention_actor_ids:['a']}},metadata:{task_context:true}});
const runtime={request:async()=>({}),onNotification:()=>()=>{}};
it('persists a fixed multi-page cut, then revalidates all unread originals before admission',async()=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 const binding=store.bind({agentId:'a',sessionId:'s',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
 let receivedPages=0,refreshed=0;const requests:Record<string,unknown>[]=[];
 const service=new TaskContext({nodeId:'node',ownerId:'owner',agents:[agent],store,inbox,runtime,refreshSources:async()=>{refreshed++;},relay:{request:async(_type,args)=>{
   requests.push(args);const after=args.after as number,through=args.through??33,pending=args.pending as string[];
   if(pending.length)return {type:'result',payload:{ok:true,result:{through,next:after,items:[],revoked_message_ids:pending.includes('m1')?['m1']:[]}}};
   receivedPages++;const end=Math.min(after+32,33);
   return {type:'result',payload:{ok:true,result:{through,next:end,items:Array.from({length:end-after},(_,n)=>{const seq=after+n+1;return {seq,message_id:'m'+seq,conversation_id:'chat',allowed:true,input:original('m'+seq)};}),revoked_message_ids:[]}}};
 }}});
 try{
  const identity={agentId:'a',ownerId:'owner',sessionId:binding.sessionId};
  const prepared=await service.prepare(identity);
  expect(receivedPages).toBe(2);expect(refreshed).toBe(1);expect(requests[1]!.through).toBe(33);
  expect(prepared.messages).toHaveLength(32);expect(prepared.messages.some(message=>message.inputId==='m1')).toBe(false);expect(prepared.revoked).toContain('m1');
  expect(store.taskContextCursor('a')).toBe(33);expect(store.systemContextInputs('a').filter(row=>row.state==='consumed')).toHaveLength(0);
  const message=prepared.messages[0]!;
  await expect(service.commit({...identity,evidence:[{inputId:message.inputId,content:[{type:'text',text:'forged'}],turn:1,consumedSeq:10}]})).resolves.toEqual({confirmed:[]});
  expect(store.systemContextInputs('a').find(row=>row.message_id===message.inputId)?.state).toBe('prepared');
  await service.commit({...identity,evidence:[{inputId:message.inputId,content:message.content,turn:1,consumedSeq:10}]});
  expect(store.systemContextInputs('a').find(row=>row.message_id===message.inputId)?.state).toBe('consumed');
  expect(inbox.prepareSystemContext('a','s').some(item=>item.inputId===message.inputId)).toBe(false);
  // A delayed valid ACK cannot resurrect an original withdrawn before admission.
  await service.commit({...identity,evidence:[{inputId:'m1',content:[],turn:1,consumedSeq:11}]});
  expect(store.systemContextInputs('a').find(row=>row.message_id==='m1')?.state).toBe('revoked');
 }finally{inbox.close();store.close();}
});
it('keeps revoked-before-prepared references independent for multiple affected Agents',()=>{
 const store=new NodeStore(':memory:','owner');try{store.revokeSystemContext('a','original','chat');store.revokeSystemContext('b','original','chat');expect(store.systemContextInputs('a')[0]?.state).toBe('revoked');expect(store.systemContextInputs('b')[0]?.state).toBe('revoked');}finally{store.close();}
});
it('returns explicit unavailable while retaining pending originals, then recovers under current authority',async()=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');let offline=true;
 store.bind({agentId:'a',sessionId:'s',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
 inbox.receive(original('pending'),false);
 const service=new TaskContext({nodeId:'node',ownerId:'owner',agents:[agent],store,inbox,runtime,refreshSources:async()=>{},relay:{request:async()=>{
  if(offline)throw new Error('CENTER_OFFLINE');
  return {type:'result',payload:{ok:true,result:{through:0,next:0,items:[],revoked_message_ids:[]}}};
 }}});
 const identity={agentId:'a',sessionId:'s',ownerId:'owner'};
 try {
  expect(await service.prepare(identity)).toEqual({unavailable:true,messages:[],revoked:[],unavailableInputs:[{inputId:'pending',conversationId:'chat'}]});
  expect(inbox.prepareSystemContext('a','s')).toHaveLength(1);
  offline=false;expect((await service.prepare(identity)).messages).toHaveLength(1);
  await expect(service.prepare({...identity,ownerId:'wrong'})).rejects.toThrow('identity');
 }finally{inbox.close();store.close();}
});
it('does not submit a second SingleThread identity or wake for a passive indexed Task notice',async()=>{
 const store=new NodeStore(':memory:','owner'),receipts:unknown[]=[];
 const product=new SingleThread({nodeId:'node',ownerId:'owner',agents:[{...agent,mode:'single_thread'}],store,runtime:{...runtime,request:async()=>{throw new Error('unexpected native wake');}},relay:{request:async(type,args)=>{receipts.push({type,args});return {type:'result',payload:{ok:true}};}},image:async()=>'',onError:error=>{throw error;}});
 try{await product.receive(original('original'));expect(receipts).toHaveLength(1);expect(store.bindings()).toHaveLength(0);}finally{await product.stop();store.close();}
});

function replayFixture() {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  const identity={agentId:'a',sessionId:'s',ownerId:'owner'};
  store.bind({...identity,conversationId:'global:a',cwd:'/tmp',revision:'1'});
  const service=new TaskContext({nodeId:'node',ownerId:'owner',agents:[agent],store,inbox,runtime,refreshSources:async()=>{},
    relay:{request:async()=>({type:'result',payload:{ok:true,result:{through:0,next:0,items:[],revoked_message_ids:[]}}})}});
  return {store,inbox,identity,service};
}

it('bounds receipt reconciliation work when an idle session replays 300 consumed originals',async()=>{
  const {store,inbox,identity,service}=replayFixture();
  try {
    for(let i=0;i<300;i++){
      const id='task-'+i;
      inbox.receive(original(id),false);
    }
    const {messages}=await service.prepare(identity);
    expect(messages).toHaveLength(300);
    const replay={...identity,evidence:messages.map(({inputId,content},i)=>({inputId,content,turn:1,consumedSeq:2+i}))};
    await service.commit(replay);
    expect(store.systemContextInputs('a').every(row=>row.state==='consumed')).toBe(true);

    let reads=0,rows=0;
    const all=StatementSync.prototype.all;
    vi.spyOn(StatementSync.prototype,'all').mockImplementation(function(this:StatementSync,...args){
      const result=all.apply(this,args);
      if(this.sourceSQL.includes('FROM system_context_inputs')){reads++;rows+=result.length;}
      return result;
    });
    const inboxReads=vi.spyOn(inbox,'prepareSystemContext');
    const updates=vi.spyOn(store,'commitSystemContext');
    expect((await service.prepare(identity)).messages).toEqual([]);
    const prepare={reads,rows,inboxReads:inboxReads.mock.calls.length,updates:updates.mock.calls.length};
    reads=0;rows=0;inboxReads.mockClear();updates.mockClear();
    await service.commit(replay);
    const commit={reads,rows,inboxReads:inboxReads.mock.calls.length,updates:updates.mock.calls.length};
    expect(prepare.reads).toBeLessThanOrEqual(3);
    expect(prepare.rows).toBeLessThanOrEqual(600);
    expect(commit.rows).toBe(0);
    expect(prepare.inboxReads).toBeLessThanOrEqual(3);
    expect(prepare.updates).toBe(0);
    expect(commit.reads).toBeLessThanOrEqual(1);
    expect(commit.inboxReads).toBeLessThanOrEqual(1);
    expect(commit.updates).toBe(0);
  } finally {vi.restoreAllMocks();inbox.close();store.close();}
});

it('repairs either outstanding product acknowledgement on replay without changing a recorded turn',async()=>{
  const {store,inbox,identity,service}=replayFixture();
  try {
    for(const id of ['inbox-done','mapping-done'])inbox.receive(original(id),false);
    const {messages}=await service.prepare(identity);
    const evidence=messages.map(({inputId,content},i)=>({inputId,content,turn:2,consumedSeq:i+1}));
    const [first,second]=messages;
    inbox.commitSystemContext('a','s',first!.inputId,first!.content,2);
    const row=store.systemContextInputs('a').find(item=>item.input_id===second!.inputId)!;
    store.commitSystemContext('s',row.input_id,row.digest,1);
    expect(await service.commit({...identity,evidence})).toEqual({confirmed:[
      {inputId:first!.inputId,consumedSeq:evidence[0]!.consumedSeq,status:'consumed'},
    ]});
    expect(inbox.systemContextIngested('a','s',second!.inputId,2)).toBe(false);
    expect(await service.commit({...identity,evidence:[{...evidence[1]!,turn:1}]})).toEqual({confirmed:[
      {inputId:second!.inputId,consumedSeq:evidence[1]!.consumedSeq,status:'consumed'},
    ]});
    expect(await service.prepare(identity)).toEqual({messages:[],revoked:[]});
    expect(inbox.prepareSystemContext('a','s')).toHaveLength(0);
    expect(store.systemContextInputs('a')).toEqual(expect.arrayContaining([
      expect.objectContaining({input_id:'inbox-done',state:'consumed',turn:2}),
      expect.objectContaining({input_id:'mapping-done',state:'consumed',turn:1}),
    ]));
  } finally {inbox.close();store.close();}
});


it('shares only a queued authority cut, retains a live claim, and retires it on reset',async()=>{
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  const originalBinding={agentId:'a',sessionId:'first',conversationId:'chat',ownerId:'owner',cwd:'/tmp',revision:'1'};
  const other={...originalBinding,sessionId:'second',conversationId:'other'};
  const replacement={...originalBinding,sessionId:'replacement'};
  store.bind(originalBinding);store.bind(other);inbox.receive(original('transfer'),false);
  let reads=0;
  let unblock!:()=>void;
  const blocked=new Promise<void>(resolve=>{unblock=resolve;});
  const service=new TaskContext({nodeId:'node',ownerId:'owner',agents:[agent],store,inbox,runtime,refreshSources:async()=>{},
    relay:{request:async(_type,args)=>{
      if(++reads===1)await blocked;
      return {type:'result',payload:{ok:true,result:{through:0,next:0,items:[],revoked_message_ids:[]}}};
    }}});
  try {
    const first=service.prepare(originalBinding),second=service.prepare(other);
    await expect.poll(()=>reads).toBe(1);
    const later=service.prepare(other);
    unblock();
    const [{messages},contender]=await Promise.all([first,second]);
    expect(messages).toHaveLength(1);
    expect(contender.messages).toEqual([]);
    expect((await later).messages).toEqual([]);
    expect(reads).toBeGreaterThan(1);

    store.reset(originalBinding,replacement,'reset');
    expect((await service.prepare(originalBinding)).messages).toEqual([]);
    expect((await service.prepare(replacement)).messages).toEqual(messages);
    const evidence=messages.map(({inputId,content})=>({inputId,content,turn:1,consumedSeq:5}));
    expect(await service.commit({...originalBinding,evidence})).toEqual({confirmed:[{inputId:'transfer',consumedSeq:5,status:'discarded'}]});
    expect((await service.prepare(replacement)).messages).toEqual(messages);
    store.revokeSystemContext('a','transfer','chat');inbox.revokeSystemContext('a','transfer');
    expect(await service.commit({...replacement,evidence})).toEqual({confirmed:[{inputId:'transfer',consumedSeq:5,status:'discarded'}]});
    expect(inbox.systemContextIngested('a','replacement','transfer',1)).toBe(false);
  }finally{unblock();inbox.close();store.close();}
});
