import { afterEach, expect, it, vi } from 'vitest';
import { CHAT_BACKGROUND_DELAY_MS, type AgentConfiguration, type RelayInput } from '@nano/product-contracts';
import { SingleThread } from '../src/single-thread.js';
import { NodeStore } from '../src/store.js';

function message(id:string, chat:string, metadata:RelayInput['metadata'] = {}):RelayInput {
  return {agent_id:'a',conversation_id:chat,relay_task_id:id,idempotency_key:id,
    message:{id,content:id,sender_type:'user',sender_user_id:'guest',attachments:[],created_at:'2026-11-01T12:34:00Z'},
    metadata:{conversation_type:'group',agent_receipt:true,...metadata}};
}

function fixture(store:NodeStore) {
  const config:AgentConfiguration={agentId:'a',revision:'1',model:'test',provider:'test',mode:'single_thread',workspace:'/tmp',collaborationScope:'team'};
  const submissions:{sessionId:string;inputId:string;mode:string;source:Record<string,unknown>;content:Record<string,unknown>[];attachmentSources:unknown[]}[]=[];
  const frames:Record<string,unknown>[]=[];
  const receipts:string[]=[];
  const evidence:{providerDelivered?:boolean;turn?:number;consumedSeq?:number}={};
  const product=new SingleThread({nodeId:'n',ownerId:'owner',store,agents:[config],onError:error=>{throw error;},
    image:async()=> 'image-bytes',relay:{async request(type,frame){frames.push({type,...frame});return {type:'ack',payload:{message_id:'m'}};}},
    queueMessageReceipt:(input,read)=>receipts.push(`${input.message.id}:${read?'read':'received'}`),
    runtime:{onNotification:()=>()=>{},async request(method,params){
      if(method==='session.submit')submissions.push(params as typeof submissions[number]);
      if(method==='session.lookup')return {...evidence, accepted:submissions.some(item=>item.inputId===(params as {inputId:string}).inputId)};
      return {durable:true,events:[]};
    }}});
  return {config,product,submissions,receipts,frames,evidence};
}

afterEach(()=>vi.useRealTimers());

it('restores a never-bound chat at its first live deadline and leaves imported history dormant',async()=>{
  vi.useFakeTimers();
  const store=new NodeStore(':memory:','owner');
  let f=fixture(store);
  try {
    await f.product.receive(message('historical','other',{context_only:true}));
    await f.product.receive(message('first','g'));
    await vi.advanceTimersByTimeAsync(CHAT_BACKGROUND_DELAY_MS-10_000);
    await f.product.receive(message('second','g'));
    await f.product.stop();
    expect(store.bindings()).toHaveLength(0);
    f=fixture(store);
    await f.product.recover();
    await vi.advanceTimersByTimeAsync(9_999);
    expect(f.submissions).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(f.submissions).toHaveLength(1);
    expect(f.submissions[0]).toMatchObject({inputId:'a:second',mode:'steer',source:{kind:'system',channel:'chat-background',actorId:'a',nanoTeamChat:true}});
    const body=JSON.stringify(f.submissions[0]!.content);
    expect(body).toContain('first');
    expect(body).toContain('second');
    expect(body).not.toContain('historical');
    await vi.advanceTimersByTimeAsync(2*CHAT_BACKGROUND_DELAY_MS);
    expect(f.submissions).toHaveLength(1);
    expect(store.bindingFor('a','other')).toBeUndefined();
  } finally {await f.product.stop();store.close();}
});

it('groups alias and external traffic into one native step with original image and human authority',async()=>{
  vi.useFakeTimers();
  const store=new NodeStore(':memory:','owner'),f=fixture(store);
  try {
    const earlier=message('photo','shadow');
    earlier.message.attachments=[{url:'/image',file_name:'drawing.png',content_type:'image/png'}];
    await f.product.receive(earlier);
    store.aliasConversation('a','shadow','external:feishu:room');
    await f.product.receive(message('unrelated','other'));
    const high=message('question','external:feishu:room',{channel:'feishu',mentioned_agent_ids:['a'],external_reply:'external:q',owner_user_id:'owner'});
    high.message.sender_user_id='feishu-owner';
    await f.product.receive(high);
    expect(f.submissions).toHaveLength(1);
    expect(f.submissions[0]).toMatchObject({inputId:'a:question',source:{kind:'human',messageId:'question',actorId:'feishu-owner',roleAccountId:'owner',directHumanText:'question'}});
    expect(f.submissions[0]!.attachmentSources.filter(Boolean)).toEqual([{kind:'chat',conversationId:'shadow',messageId:'photo',url:'/image'}]);
    expect(JSON.stringify(f.submissions[0]!.content)).not.toContain('unrelated');
    await f.product.receive(message('later','shadow'));
    await f.product.receive(high);
    expect(f.submissions).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(CHAT_BACKGROUND_DELAY_MS);
    expect(f.submissions.map(item=>item.inputId).sort()).toEqual(['a:later','a:question','a:unrelated']);
  } finally {await f.product.stop();store.close();}
});

it('skips team backlog, team controls and rejected DMs across reopening while the owner can still chat',async()=>{
  vi.useFakeTimers();
  const store=new NodeStore(':memory:','owner'),f=fixture(store);
  try {
    const low=message('low','g');
    const guest=message('guest','dm',{conversation_type:'direct',owner_direct:false});
    const high=message('high','g',{reply_to_agent_id:'a'});
    await f.product.receive(low);
    await f.product.receive(high);
    await f.product.receive(message('parked','other'));
    const keys=f.product.restrictToOwner('a');
    expect(keys).toEqual([{sessionId:store.bindingFor('a','g')!.sessionId,inputId:'a:high'}]);
    expect(f.product.restrictToOwner('a')).toEqual(keys);
    f.product.confirmRestricted(keys);
    f.config.collaborationScope='owner_only';
    await f.product.receive(guest);
    const command=message('group-command','fresh',{mentioned_agent_ids:['a']});
    command.message.content='/new';
    await f.product.receive(command);
    expect(store.bindingFor('a','fresh')).toBeUndefined();
    const owner=message('owner-in','direct-owner',{conversation_type:'direct',owner_direct:true});
    owner.message.sender_user_id='owner';
    await f.product.receive(owner);
    expect(f.submissions.at(-1)).toMatchObject({inputId:'a:owner-in',source:{kind:'human',actorId:'owner'}});
    expect(f.submissions.at(-1)?.source.nanoTeamChat).toBeUndefined();
    expect(f.frames).toContainEqual(expect.objectContaining({relay_task_id:'guest',delivery_status:'skipped'}));
    f.config.collaborationScope='team';
    for(const input of [low,high,guest,command,message('parked','other')])await f.product.receive(input);
    await f.product.recover();
    await vi.advanceTimersByTimeAsync(CHAT_BACKGROUND_DELAY_MS);
    expect(f.submissions.map(item=>item.inputId)).toEqual(['a:high','a:owner-in']);
  } finally {await f.product.stop();store.close();}
});

it('holds group read receipts and provisional replies across the native pre-step before provider delivery',async()=>{
  const store=new NodeStore(':memory:','owner'),f=fixture(store);
  try {
    Object.assign(f.evidence,{providerDelivered:false,turn:1,consumedSeq:2});
    await f.product.receive(message('background','g'));
    await f.product.receive(message('addressed','g',{mentioned_agent_ids:['a']}));
    expect(f.receipts).toEqual(['background:received','addressed:received']);
    expect(f.frames.some(frame=>frame.kind==='turn_start')).toBe(false);
    f.evidence.providerDelivered=true;
    await f.product.recover();
    expect(f.receipts).toEqual(['background:received','addressed:received','background:read','addressed:read']);
    expect(f.frames.filter(frame=>frame.kind==='turn_start')).toHaveLength(1);
  } finally {await f.product.stop();store.close();}
});
