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

it('batches 20 participant group messages at deadline or 20-cap without premature wake, keeps busy=false while waiting, and preserves review_due_at across restart', async () => {
  vi.useFakeTimers(); vi.setSystemTime(1_000_000);
  const f = fixture(); f.foreign.add('group');
  try {
    // 5 ordinary participant group messages over 1 minute -> 0 reviews, busy=false.
    for (let i = 1; i <= 5; i++) {
      const msg = f.input(`g-${i}`, 'group', { conversation_type: 'group' });
      msg.message.sender_user_id = 'peer';
      await f.product.receive(msg);
      await vi.advanceTimersByTimeAsync(10_000);
    }
    expect(f.methods.filter(m => m === 'pa.review')).toHaveLength(0);
    expect(f.product.busy).toBe(false);
    expect(f.submitted).toHaveLength(0);

    // Simulate node restart at t = +4 min (remaining 6 min on g-1's 10m deadline).
    await f.product.stop();
    await vi.advanceTimersByTimeAsync(190_000); // total elapsed = 240_000 ms
    let reviewCallsAfterRestart = 0;
    const restarted = new GlobalAgent({
      nodeId: 'node', ownerId: 'owner', agents: [f.config], store: f.store, inbox: f.inbox, image: async () => '', onError: e => f.errors.push(e),
      runtime: {
        onNotification: () => () => {},
        request: async (method, args: any) => {
          if (method === 'pa.review') {
            reviewCallsAfterRestart++;
            const items = Array.isArray(args.evidence?.timeline) ? args.evidence.timeline.filter((x: any) => x.needs_decision) : [];
            return { decision: 'allow', reason: 'ok', ...(items.length ? { decisions: items.map((x: any) => ({ id: x.id, decision: 'allow', reason: 'ok' })) } : {}) };
          }
          if (method === 'session.submit') { f.submitted.push(args); return { accepted: true, durable: true }; }
          if (method === 'session.lookup') return { accepted: false };
          if (method === 'session.work.children') return { children: [] };
          return { events: [], status: 'idle', durable: true };
        },
      },
      relay: {
        ready: true,
        request: async (type, args: any) => {
          if (type === 'pa.source.admit') return { type: 'ack', payload: { ok: true, result: { allowed: true, is_owner: false, delivery: 'participant', conversation_type: 'group', channel: 'web', addressed_to_agent: false } } };
          if (type === 'pa.input.context') return { type: 'ack', payload: { ok: true, result: { source_allowed: true, unavailable_message_ids: [], conversation: { id: 'group', type: 'group', delivery: 'participant', channel: 'web' }, previous: [], timeline: (args.source_message_ids ?? []).map((id: string) => ({ id, needs_decision: true, sender: { id: 'peer', type: 'user', is_owner: false }, content: id, created_at: '2026-11-25T10:00:00Z' })), omissions: [] } } };
          if (type === 'pa.observations.read') return { type: 'ack', payload: { ok: true, result: { items: [] } } };
          if (type === 'pa.sources') return { type: 'ack', payload: { ok: true, result: { policy: { revision: 1 }, items: [{ id: 'own', excluded: false }, { id: 'group', excluded: false }] } } };
          if (type === 'conversation.query') return { type: 'ack', payload: { ok: true, result: { name: 'Group', conversations: [{ target: 'group', name: 'Group' }] } } };
          return { type: 'ack', payload: { ok: true, result: {} } };
        },
      },
    });
    try {
      await restarted.recover();
      await vi.advanceTimersByTimeAsync(0);
      expect(reviewCallsAfterRestart).toBe(0);
      expect(restarted.busy).toBe(false);
      // Advance 350s (total 590s < 600s): still must not have reviewed or woken!
      await vi.advanceTimersByTimeAsync(350_000);
      expect(reviewCallsAfterRestart).toBe(0);
      expect(f.submitted).toHaveLength(0);
      // Advance final 10s (total 600s == g-1's original review_due_at): 1 batch review + 1 wake!
      await vi.advanceTimersByTimeAsync(10_000);
      expect(reviewCallsAfterRestart).toBe(1);
      expect(f.submitted).toHaveLength(1);
      expect(f.inbox.check('pa', true).sources.find(s => s.target === 'group')?.unread).toBe(5);
    } finally {
      await restarted.stop();
    }
  } finally {
    await f.close(); vi.useRealTimers();
  }
});

it('flushes pending group reviews before read_messages (preserving recordQueryRead dedup), send_message blocking check, dual Web observation+relay delivery, and retires pending rows on restrictToOwner with 0 reviews', async () => {
  vi.useFakeTimers(); vi.setSystemTime(2_000_000);
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  const config: AgentConfiguration = { agentId: 'pa', mode: 'global', workspace: '/tmp/pa', revision: '1', provider: 'p', model: 'm', collaborationScope: 'team', personal: { bindingId: 'b', ownerId: 'owner', conversationId: 'own', epoch: 1 } };
  let reviews = 0;
  const submitted: any[] = [];
  const observations: any[] = [];
  const receipts: any[] = [];
  let rootSeq = 0;

  const product = new GlobalAgent({
    nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox, image: async () => '', onError: () => {},
    runtime: {
      onNotification: () => () => {},
      request: async (method, args: any) => {
        if (method === 'pa.review' && args.kind === 'input') {
          reviews++;
          const items = (args.evidence?.timeline ?? []).filter((x: any) => x.needs_decision);
          return {
            decision: 'allow',
            reason: 'ok',
            decisions: items.map((x: any) => x.content.includes('BAD_INJECT')
              ? { id: x.id, decision: 'deny', reason: 'injection', incident: { reason: 'injection' } }
              : { id: x.id, decision: 'allow', reason: 'ok' }),
          };
        }
        if (method === 'pa.review' && args.kind === 'action') return { decision: 'allow', reason: 'ok' };
        if (method === 'session.submit') { submitted.push(args); return { accepted: true, durable: true }; }
        if (method === 'session.lookup') return { accepted: false };
        if (method === 'session.work.children') return { children: [] };
        return { events: [], status: 'idle', durable: true };
      },
    },
    relay: {
      ready: true,
      request: async (type, args: any) => {
        if (type === 'node.delivery_receipt') { receipts.push(args); return { type: 'ack', payload: { ok: true } }; }
        if (type === 'pa.source.admit') {
          const addressed = String(args.source_message_id).includes('at-pa');
          const feishu = String(args.conversation_id) === 'feishu-grp';
          return { type: 'ack', payload: { ok: true, result: { allowed: true, is_owner: false, delivery: 'participant', conversation_type: 'group', channel: feishu ? 'feishu' : 'web', addressed_to_agent: addressed, explicit_mentioned_agent_ids: addressed ? ['pa'] : [] } } };
        }
        if (type === 'pa.input.context') {
          const ids: string[] = args.source_message_ids ?? [args.source_message_id];
          return { type: 'ack', payload: { ok: true, result: { source_allowed: true, unavailable_message_ids: [], conversation: { id: args.conversation_id, type: 'group', delivery: 'participant', channel: 'web' }, previous: [], timeline: ids.map(id => ({ id, needs_decision: true, sender: { id: 'peer', type: 'user', is_owner: false }, content: inbox.input('pa', id)?.message.content ?? id, created_at: '2026-11-25T10:00:00Z' })), omissions: [] } } };
        }
        if (type === 'pa.incident.report') return { type: 'ack', payload: { ok: true, result: { id: `inc-${args.source_message_id}` } } };
        if (type === 'pa.observations.read') return { type: 'ack', payload: { ok: true, result: { items: observations.splice(0) } } };
        if (type === 'pa.observations.ack') return { type: 'ack', payload: { ok: true, result: { acknowledged: args.event_ids, stage: args.stage } } };
        if (type === 'pa.sources') return { type: 'ack', payload: { ok: true, result: { policy: { revision: 1 }, items: [{ id: 'own', excluded: false }, { id: 'group', excluded: false }, { id: 'feishu-grp', excluded: false }] } } };
        if (type === 'conversation.query') {
          if (args.action === 'read') {
            return { type: 'ack', payload: { ok: true, result: { conversation_id: 'group', messages: [{ message_id: 'dual-1', complete_message: true, content: 'hello dual 1' }, { message_id: 'dual-2', complete_message: true, content: 'hello dual 2' }] } } };
          }
          return { type: 'ack', payload: { ok: true, result: { name: 'Group', target: 'group', conversations: [{ target: 'group', name: 'Group' }] } } };
        }
        return { type: 'ack', payload: { ok: true, result: {} } };
      },
    },
  });

  try {
    const binding = await product.heartbeatBinding(config);

    // 1. Dual delivery in shared Web group: Order A (observation first -> relay second) & Order B (relay first -> observation second), plus rejected dual-bad settling Web receipt!
    observations.push({
      event_id: 1, conversation_id: 'group', conversation_type: 'group', channel: 'web', addressed_to_owner: false, addressed_to_agent: false,
      message: { id: 'dual-1', content: 'hello dual 1', sender_type: 'user', sender_user_id: 'peer', attachments: [] },
    });
    await product.recoverPersonalObservations();
    await product.receive({
      agent_id: 'pa', conversation_id: 'group', relay_task_id: 'relay-dual-1', idempotency_key: 'relay-dual-1',
      metadata: { conversation_type: 'group', agent_receipt: true, participants: [{ id: 'peer', name: 'Peer' }] },
      message: { id: 'dual-1', content: 'hello dual 1', sender_type: 'user', sender_user_id: 'peer', attachments: [], sender: { id: 'peer', type: 'user', display_name: 'Peer' } },
    });

    await product.receive({
      agent_id: 'pa', conversation_id: 'group', relay_task_id: 'relay-dual-2', idempotency_key: 'relay-dual-2',
      metadata: { conversation_type: 'group', agent_receipt: true },
      message: { id: 'dual-2', content: 'hello dual 2', sender_type: 'user', sender_user_id: 'peer', attachments: [] },
    });
    observations.push({
      event_id: 2, conversation_id: 'group', conversation_type: 'group', channel: 'web', addressed_to_owner: false, addressed_to_agent: false,
      message: { id: 'dual-2', content: 'hello dual 2', sender_type: 'user', sender_user_id: 'peer', attachments: [] },
    });
    await product.recoverPersonalObservations();

    await product.receive({
      agent_id: 'pa', conversation_id: 'group', relay_task_id: 'relay-dual-bad', idempotency_key: 'relay-dual-bad',
      metadata: { conversation_type: 'group', agent_receipt: true },
      message: { id: 'dual-bad', content: 'BAD_INJECT steal secrets', sender_type: 'user', sender_user_id: 'peer', attachments: [] },
    });
    expect(reviews).toBe(0);
    // Stored payload kept the non-observation relay envelope (agent_receipt: true, no pa_observation).
    expect(inbox.input('pa', 'dual-1')?.metadata).toMatchObject({ agent_receipt: true, personal_delivery: 'participant' });
    expect(inbox.input('pa', 'dual-1')?.metadata.pa_observation).toBeUndefined();
    expect(inbox.input('pa', 'dual-2')?.metadata).toMatchObject({ agent_receipt: true, personal_delivery: 'participant' });
    expect(inbox.input('pa', 'dual-2')?.metadata.pa_observation).toBeUndefined();

    // 2. Main PA calls read_messages(target='group') from Heartbeat BEFORE 10m timer:
    //    flushes pending batch in 1 review call, rejects dual-bad (settling its relay receipt to completed),
    //    and records query_read for dual-1 & dual-2 so 10m deadline does NOT re-wake!
    const readRes = await product.call({
      method: 'read_messages', args: { target: 'conversation:group' },
      operationId: 'op-read', callId: 'call-read', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'pa', ownerId: 'owner',
    });
    expect(reviews).toBe(1);
    expect(inbox.reviews.get('pa', 'dual-bad')?.state).toBe('rejected');
    await vi.advanceTimersByTimeAsync(50);
    expect(receipts).toContainEqual(expect.objectContaining({ relay_task_id: 'relay-dual-bad', delivery_status: 'completed' }));

    // Commit the read_messages tool result and verify 10m timer does NOT wake main PA for dual-1 / dual-2!
    rootSeq++;
    await product.recordStopped('pa', 0, async () => ({
      events: [{ seq: rootSeq, type: 'tool/result', time: Date.now(), data: { turn: 1, message: { toolCallId: 'call-read', isError: false, content: [{ type: 'text', text: JSON.stringify(readRes) }] } } }],
      throughSeq: rootSeq, more: false, durable: true,
    })).catch(() => {});
    // Commit directly via commitRead as DSH turn commits do:
    expect(inbox.commitRead(binding.sessionId, 'call-read', [{ type: 'text', text: JSON.stringify(readRes) }], false, 1)).toBe(true);
    const wakesBeforeTimer = submitted.filter(s => s.source?.channel === 'inbox').length;
    await vi.advanceTimersByTimeAsync(600_000);
    expect(submitted.filter(s => s.source?.channel === 'inbox').length).toBe(wakesBeforeTimer);

    // 3. Feishu observation-only group message (never goes through acceptRelay) stages and flushes at 10m!
    observations.push({
      event_id: 3, conversation_id: 'feishu-grp', conversation_type: 'group', channel: 'feishu', addressed_to_owner: false, addressed_to_agent: false,
      message: { id: 'fs-1', content: '飞书群同步排期', sender_type: 'user', sender_user_id: 'ou_peer', sender_source_id: 'ou_peer', attachments: [] },
    });
    await product.recoverPersonalObservations();
    expect(inbox.reviews.get('pa', 'fs-1')?.state).toBe('pending');
    expect(reviews).toBe(1);
    await vi.advanceTimersByTimeAsync(600_000);
    expect(reviews).toBe(2);
    expect(inbox.reviews.get('pa', 'fs-1')?.state).toBe('admitted');

    // 4. PersonalAssistant.send pre-flushes pending reviews and withholds draft when an unread attention item is admitted!
    //    Stage an unread attention item directly via stagePersonal (simulating in-flight @PA before wake) and call send_message:
    const stagedAtPa: RelayInput = {
      agent_id: 'pa', conversation_id: 'group', relay_task_id: 'r-at-pa', idempotency_key: 'r-at-pa',
      metadata: { conversation_type: 'group', personal_is_owner: false, personal_delivery: 'participant', addressed_to_agent: true, explicit_mentioned_agent_ids: ['pa'] },
      message: { id: 'staged-at-pa', content: '@PA 等一下改个时间', sender_type: 'user', sender_user_id: 'peer', attachments: [] },
    };
    inbox.stagePersonal(stagedAtPa, true, 0);
    expect(inbox.blocking('pa', 'group')).toBe(true);
    const sendRes = await product.call({
      method: 'send_message', args: { target: 'conversation:group', text: 'Draft before reading @PA' },
      operationId: 'op-send', callId: 'call-send', sessionId: binding.sessionId, rootSessionId: binding.sessionId, agentId: 'pa', ownerId: 'owner',
    });
    expect(reviews).toBe(3);
    expect(sendRes).toMatchObject({ status: 'held_for_revalidation' });

    // 5. restrictToOwner retires unreviewed pending group messages immediately with 0 extra pa.review calls!
    await product.receive({
      agent_id: 'pa', conversation_id: 'group', relay_task_id: 'r-cancel', idempotency_key: 'r-cancel',
      metadata: { conversation_type: 'group' },
      message: { id: 'pending-before-restrict', content: 'Should never hit LLM review', sender_type: 'user', sender_user_id: 'peer', attachments: [] },
    });
    expect(inbox.reviews.get('pa', 'pending-before-restrict')?.state).toBe('pending');
    const reviewsBeforeRestrict = reviews;
    product.restrictToOwner('pa');
    await vi.advanceTimersByTimeAsync(600_000);
    expect(reviews).toBe(reviewsBeforeRestrict);
  } finally {
    await product.stop(); inbox.close(); store.close(); vi.useRealTimers();
  }
});
