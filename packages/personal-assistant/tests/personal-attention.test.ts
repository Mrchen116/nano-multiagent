import { expect, it, vi } from 'vitest';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';
import { GlobalAgent } from '../src/global-agent.js';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';

function fixture(onObserve?: () => void) {
  const store=new NodeStore(':memory:','owner'), inbox=new InboxStore(':memory:');
  const config:AgentConfiguration={agentId:'pa',mode:'global',workspace:'/tmp/pa',revision:'1',provider:'p',model:'m',groupReplyPolicy:'mention_only',personal:{bindingId:'b',ownerId:'owner',conversationId:'own',epoch:1}};
  const submitted:Record<string,any>[]=[];const methods:string[]=[];const seen=new Set<string>();
  const observations:Record<string,any>[]=[];const errors:unknown[]=[];const excluded=new Set<string>(),foreign=new Set<string>();let loseAck=false;
  let running=false, race=false;let listener:(method:string,data:any)=>void=()=>{};
  const source=(target:unknown)=>({allowed:true,is_owner:!foreign.has(String(target)),delivery:target==='background'?'observer':'participant',conversation_type:target==='group'?'group':'direct',channel:'web'});
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:error=>{errors.push(error);},
    runtime:{onNotification:fn=>{listener=fn;return()=>{};},request:async(method,args:any)=>{
      methods.push(method);
      if(method==='pa.review')return {decision:'allow',reason:'ordinary input'};
      if(method==='session.submit'){
        if(args.onlyIfIdle && (running||race)){race=false;return {accepted:false,busy:true};}
        if(!seen.has(args.inputId)){submitted.push(args);seen.add(args.inputId);}
        if(args.onlyIfIdle && loseAck){loseAck=false;throw new Error('ACK lost');}
        return {accepted:true,durable:true};
      }
      if(method==='session.lookup')return {accepted:seen.has(args.inputId)};
      if(method==='session.descendants')return [];
      if(method==='session.observe')onObserve?.();
      return {events:[],status:running?'running':'idle',durable:true};
    }},
    relay:{ready:true,request:async(type,args:any)=>{
      if(type==='agent.work.append')return {type:'ack',payload:{through_seq:args.events.at(-1).seq}};
      const result=type==='pa.source.admit'?source(args.conversation_id):type==='pa.observations.read'?{items:observations.splice(0)}:type==='pa.sources'?{items:['own','group','background'].map(id=>({id,excluded:excluded.has(id)}))}:type==='conversation.query'?{name:'Chat',conversations:[]} : {};
      return {type:'ack',payload:{ok:true,result}};
    }}});
  const input=(id:string,target='background',metadata:Record<string,unknown>={}):RelayInput=>({agent_id:'pa',conversation_id:target,relay_task_id:id,idempotency_key:id,metadata,
    message:{id,content:id,sender_type:'user',sender_user_id:'owner',attachments:[]}});
  const idle=()=>{running=false;listener('session.status',{sessionId:store.bindingFor('pa','global:pa')!.sessionId,status:'idle'});};
  return {product,inbox,store,submitted,methods,input,idle,observations,errors,excluded,foreign,loseAck:()=>{loseAck=true;},busy:()=>{running=true;},race:()=>{race=true;},close:async()=>{await product.stop();inbox.close();store.close();}};
}
it('notifies one observer batch at a fixed deadline without another message and never checks it as a direct request',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    await f.product.receive(f.input('first'));
    await vi.advanceTimersByTimeAsync(120000);
    await f.product.receive(f.input('second'));
    expect(f.submitted).toHaveLength(0);expect(f.methods).not.toContain('pa.review');
    await vi.advanceTimersByTimeAsync(480000);
    expect(f.submitted).toHaveLength(1);
    expect(f.submitted[0]).toMatchObject({onlyIfIdle:true,source:{kind:'system',channel:'inbox-background'}});
    expect(f.submitted[0].content[0].text).not.toContain('first');
    expect(f.inbox.check('pa',true).sources[0].unread).toBe(2);
    await vi.advanceTimersByTimeAsync(1200000);
    expect(f.submitted).toHaveLength(1);
  } finally {await f.close();vi.useRealTimers();}
});
it('defers busy background, including an admission race, while a direct correction is steered immediately',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    await f.product.receive(f.input('background'));f.race();
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(0);
    f.busy();await f.product.receive(f.input('change the date','own'));
    expect(f.submitted).toHaveLength(1);expect(f.submitted[0]).toMatchObject({mode:'steer',source:{channel:'inbox'}});
    await f.product.receive(f.input('more background'));
    await vi.advanceTimersByTimeAsync(1200000);expect(f.submitted).toHaveLength(1);
    f.idle();await vi.advanceTimersByTimeAsync(0);
    expect(f.submitted).toHaveLength(2);expect(f.submitted[1].source.channel).toBe('inbox-background');
  } finally {await f.close();vi.useRealTimers();}
});
it.each(['before deadline','during idle observation'])('does not wake for background consumed %s',async timing=>{
  vi.useFakeTimers();vi.setSystemTime(0);let consumeOnObserve=false;
  const f=fixture(()=>{if(consumeOnObserve){consumeOnObserve=false;consume();}});
  function consume() {
    const body=f.inbox.read('pa','main','read',{target:'background'});
    expect(body).toMatchObject({delivery:'observer',messages:[{content:[{text:'new budget'}]}]});
    f.inbox.commitRead('main','read',[{type:'text',text:JSON.stringify(body)}],false);
  }
  try {
    await f.product.receive(f.input('new budget'));
    await f.product.receive(f.input('use that budget','own'));
    expect(f.submitted).toHaveLength(1);
    if(timing==='before deadline')consume();else consumeOnObserve=true;
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(1);
    expect(f.inbox.check('pa',true).sources.map(source=>source.target)).toEqual(['own']);
    await f.product.receive(f.input('later update'));
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(2);
    expect(f.submitted[1].source.channel).toBe('inbox-background');
    expect(f.errors).toEqual([]);
  } finally {await f.close();vi.useRealTimers();}
});
it('keeps observed slash commands as background and applies the existing participant group trigger',async()=>{
  vi.useFakeTimers();const f=fixture();
  try {
    await f.product.receive(f.input('/stop'));
    await f.product.receive(f.input('ordinary update','group'));
    expect(f.methods).not.toContain('session.cancel');expect(f.submitted).toHaveLength(0);
    await f.product.receive(f.input('addressed task','group',{mentioned_agent_ids:['pa']}));
    expect(f.submitted).toHaveLength(1);
  } finally {await f.close();vi.useRealTimers();}
});

it('drains stored observations before a direct wake and preserves previously admitted observer facts',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    const old=f.input('old observed');old.metadata={personal_delivery:'observer',personal_is_owner:true,conversation_type:'direct'};
    f.inbox.receive(old,false);
    const historical=f.inbox.read('pa','old-main','old-read',{target:'background'});
    await f.product.recover();
    expect(f.submitted).toHaveLength(0);
    expect(f.inbox.read('pa','old-main','old-read',{target:'background'})).toEqual(historical);
    expect(f.inbox.read('pa','main','new-read',{target:'background'})).toMatchObject({delivery:'observer',messages:[{sender:{is_owner:true}}]});
    f.observations.push({event_id:1,conversation_id:'background',message:f.input('fresh fact').message});
    await f.product.receive(f.input('direct question','own'));
    expect(f.inbox.check('pa',true).sources.find(s=>s.target==='background')?.unread).toBe(2);
    expect(f.submitted).toHaveLength(1);expect(f.errors).toEqual([]);
  } finally {await f.close();vi.useRealTimers();}
});
it('recovers an uncertain background ACK with its original identity and drops revoked candidates',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    await f.product.receive(f.input('first'));f.loseAck();
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(1);expect(f.errors).toHaveLength(1);
    await f.product.recover();
    expect(f.submitted).toHaveLength(1);
    await f.product.receive(f.input('second'));
    f.excluded.add('background');
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(1);expect(f.inbox.check('pa',true).sources).toEqual([]);
    expect(f.product.busy).toBe(false);
    f.excluded.delete('background');
    await f.product.receive(f.input('new accessible batch'));
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(2);
  } finally {await f.close();vi.useRealTimers();}
});
it('stops the deadline timer without consuming stored background',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    await f.product.receive(f.input('waiting'));expect(f.product.busy).toBe(false);
    await f.product.stop();await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(0);expect(f.inbox.check('pa',true).sources[0].unread).toBe(1);
  } finally {await f.close();vi.useRealTimers();}
});

it('treats a non-owner participant stop as ordinary input without reserving a blocking owner control',async()=>{
 const f=fixture();f.foreign.add('group');
 try {
  const input=f.input('peer-stop','group',{mentioned_agent_ids:['pa']});input.message.content='/stop';input.message.sender_user_id='peer';
  await Promise.race([f.product.receive(input),new Promise((_,reject)=>setTimeout(()=>reject(Error('peer control blocked Inbox')),300))]);
  expect(f.methods).not.toContain('session.cancel');expect(f.inbox.pendingControls()).toEqual([]);expect(f.submitted).toHaveLength(1);expect(f.inbox.check('pa',true).sources[0]?.unread).toBe(1);
 }finally{await f.close();}
});
