import { expect, it, vi } from 'vitest';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';
import { GlobalAgent } from '../src/global-agent.js';
import { InboxStore } from '../src/inbox.js';
import { NodeStore } from '../src/store.js';

function fixture() {
  const store=new NodeStore(':memory:','owner'), inbox=new InboxStore(':memory:');
  const config:AgentConfiguration={agentId:'pa',mode:'global',workspace:'/tmp/pa',revision:'1',provider:'p',model:'m',collaborationScope:'team',personal:{bindingId:'b',ownerId:'owner',conversationId:'own',epoch:1}};
  const submitted:Record<string,any>[]=[];const methods:string[]=[];const seen=new Set<string>();
  const observations:Record<string,any>[]=[];const errors:unknown[]=[];const excluded=new Set<string>(),foreign=new Set<string>();let loseAck=false;
  let running=false;
  const source=(target:unknown)=>({allowed:true,is_owner:!foreign.has(String(target)),delivery:String(target).startsWith('background')?'observer':'participant',conversation_type:target==='group'?'group':'direct',channel:'web'});
  const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,image:async()=>'',onError:error=>{errors.push(error);},
    runtime:{onNotification:()=>()=>{},request:async(method,args:any)=>{
      methods.push(method);
      if(method==='pa.review')return {decision:'allow',reason:'ordinary input'};
      if(method==='session.submit'){
        if(!seen.has(args.inputId)){submitted.push(args);seen.add(args.inputId);}
        if(loseAck){loseAck=false;throw new Error('ACK lost');}
        return {accepted:true,durable:true};
      }
      if(method==='session.lookup')return {accepted:seen.has(args.inputId)};
      if(method==='session.work.children')return {children:[]};
      return {events:[],status:running?'running':'idle',durable:true};
    }},
    relay:{ready:true,request:async(type,args:any)=>{
      if(type==='agent.work.append')return {type:'ack',payload:{through_seq:args.events.at(-1).seq}};
      const result=type==='pa.source.admit'?source(args.conversation_id):type==='pa.observations.read'?{items:observations.splice(0)}:type==='pa.sources'?{policy:{revision:1},items:['own','group','background','background-keep'].map(id=>({id,excluded:excluded.has(id)}))}:type==='conversation.query'?{name:'Chat',conversations:[]} : {};
      return {type:'ack',payload:{ok:true,result}};
    }}});
  const input=(id:string,target='background',metadata:Record<string,unknown>={}):RelayInput=>({agent_id:'pa',conversation_id:target,relay_task_id:id,idempotency_key:id,metadata,
    message:{id,content:id,sender_type:'user',sender_user_id:'owner',attachments:[]}});
  return {product,inbox,store,config,submitted,methods,input,observations,errors,excluded,foreign,loseAck:()=>{loseAck=true;},busy:()=>{running=true;},close:async()=>{await product.stop();inbox.close();store.close();}};
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
    expect(f.submitted[0]).toMatchObject({mode:'steer',source:{kind:'system',channel:'inbox'}});
    expect(f.submitted[0].content[0].text).not.toContain('first');
    expect(f.inbox.check('pa',true).sources[0].unread).toBe(2);
    await vi.advanceTimersByTimeAsync(1200000);
    expect(f.submitted).toHaveLength(1);
  } finally {await f.close();vi.useRealTimers();}
});
it('steers a busy root when due and piggybacks later background on the next direct wake',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    f.busy();await f.product.receive(f.input('background fact'));
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(1);expect(f.submitted[0]).toMatchObject({mode:'steer',source:{channel:'inbox'}});
    expect(f.submitted[0]).not.toHaveProperty('onlyIfIdle');
    await f.product.receive(f.input('another fact','background-keep'));
    await f.product.receive(f.input('change the date','own'));
    expect(f.submitted).toHaveLength(2);
    expect(f.submitted[1].content[0].text).toContain('background-keep');
    await vi.advanceTimersByTimeAsync(1200000);expect(f.submitted).toHaveLength(2);
  } finally {await f.close();vi.useRealTimers();}
});
it('does not wake for background already read before the deadline',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    await f.product.receive(f.input('new budget'));
    const body=f.inbox.read('pa','main','read',{target:'background'});
    f.inbox.commitRead('main','read',[{type:'text',text:JSON.stringify(body)}],false);
    await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(0);
    await f.product.receive(f.input('later update'));await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(1);
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


it('delivers source withdrawal as a stop-use constraint with Dreaming-owned document repair',async()=>{
  const f=fixture();
  try {
    f.excluded.add('background');
    f.observations.push({event_id:1,kind:'source.revoked',conversation_id:'background',payload:{conversation_id:'background'}});
    await f.product.recoverPersonalObservations();
    const event=f.submitted.find(item=>item.source.channel==='personal-state');
    expect(event).toMatchObject({source:{kind:'system'}});
    const text=event!.content[0].text;
    expect(text).toContain('stop using old copies');
    expect(text).toContain('Only Dreaming');
    expect(text).toContain('original running children');
    expect(text).not.toContain('checkpoint');
    expect(text).not.toContain('Dreaming does not perform');
    expect(f.errors).toEqual([]);
  }finally{await f.close();}
});


it('drops revoked sources at the deadline before steering the busy root',async()=>{
  vi.useFakeTimers();vi.setSystemTime(0);const f=fixture();
  try {
    await f.product.receive(f.input('secret','background'));
    await f.product.receive(f.input('retained','background-keep'));
    f.busy();f.excluded.add('background');await vi.advanceTimersByTimeAsync(600000);
    expect(f.submitted).toHaveLength(1);
    const summary = JSON.parse(f.submitted[0].content[0].text.split('\n').at(-1));
    expect(summary.sources).toHaveLength(1);
    expect(summary.sources[0].target).toMatch(/^c_[a-f0-9]{6}$/);
    expect(f.inbox.check('pa', true).sources.map(source => source.target)).toEqual(['background-keep']);
  }finally{await f.close();vi.useRealTimers();}
});

it('steers on a private message to the owner while keeping the PA an observer',async()=>{
  const f=fixture();
  try {
    f.observations.push({event_id:1,conversation_id:'background',conversation_type:'direct',addressed_to_owner:true,addressed_to_agent:false,
      message:{...f.input('Peer asks the owner').message,sender_user_id:'peer',created_at:'2026-11-18T01:00:00Z'}});
    await f.product.recoverPersonalObservations();
    expect(f.submitted).toHaveLength(1);
    const text=f.submitted[0].content[0].text;
    expect(text).toContain('"addressed_to":"owner"');expect(text).toContain('"delivery":"observer"');
    expect(text).toContain('"latest_message_at":"2026-11-18T01:00:00.000Z"');
    expect(text).not.toContain('Peer asks the owner');
    expect(f.inbox.blocking('pa','background')).toBe(false);
  }finally{await f.close();}
});

it('skips group commands and other people’s DMs in owner-only scope, including retries after reopening to the team',async()=>{
  const f=fixture();
  try {
    f.config.collaborationScope='owner_only';
    const group=f.input('group-stop','group',{conversation_type:'group',owner_direct:false,mentioned_agent_ids:['pa']});
    group.message.content='/stop';
    const peer=f.input('other DM','peer',{conversation_type:'direct',owner_direct:false});
    await f.product.receive(group);await f.product.receive(peer);
    expect(f.methods).not.toContain('session.cancel');
    expect(f.inbox.check('pa',true).sources).toEqual([]);expect(f.submitted).toHaveLength(0);
    expect(f.inbox.pendingRelays().map(r=>r.status)).toEqual(['skipped','skipped']);
    await f.product.receive(f.input('my DM','own',{conversation_type:'direct',owner_direct:true}));
    f.config.collaborationScope='team';await f.product.receive(group);
    expect(f.inbox.check('pa',true).sources.map(s=>s.target)).toEqual(['own']);expect(f.submitted).toHaveLength(1);
  }finally{await f.close();}
});
