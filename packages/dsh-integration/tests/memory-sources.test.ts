import { describe, expect, it } from 'vitest';
import { MemorySources, renderMaterial } from '../src/knowledge/memory-sources.js';

const event = (seq: number, type: string, data: unknown = {}) => ({ seq, type, data });
const human = (seq: number, text: string) => event(seq, 'user/message', { id: `m-${seq}`, source: { kind: 'user', actorId: 'owner', channel: 'test', messageId: `m-${seq}` }, content: [{ type: 'text', text }] });
function fixture(events: any[], options: { inherited?: number; onFlush?: (count: number) => void; cold?: boolean } = {}) {
  let count = 0; let leases = 0;
  const session = {};
  const ctx = {
    sessions: { get: () => options.cold ? undefined : session, flush: async () => { options.onFlush?.(++count); return true; } },
    sessionQuery: { observeSession: async () => {
      const copy = structuredClone(events); leases++;
      return { source: options.cold ? 'prepared' : 'live', revision: options.cold ? 'durable' : undefined, header: { cwd: '/owner', origin: 'root' }, inheritedEventCount: options.inherited ?? 0, events: copy, cursor: copy.at(-1)?.seq ?? -1, [Symbol.dispose]: () => { leases--; } };
    } },
  };
  const binding = { agentId: 'a', sessionId: 's', ownerId: 'owner', cwd: '/owner', revision: '1' };
  return { sources: new MemorySources(ctx as never, new Map([['s', binding]])), leases: () => leases, flushes: () => count };
}
const streams = { s: { baseline: -1, cursor: -1 } };
describe('certified bounded memory sources', () => {
  it('freezes before the second flush and never exports later appended events', async () => {
    const events = [human(0, 'First'), event(1, 'step/end')];
    const f = fixture(events, { onFlush: count => { if (count === 2) events.push(human(2, 'After the cut'), event(3, 'step/end')); } });
    const batch = await f.sources.freeze('a', streams, { maxInputTokens: 2000 });
    expect(batch.units).toHaveLength(1); expect(batch.ranges[0]?.through).toBe(1);
    expect(JSON.stringify(batch)).not.toContain('After the cut'); expect(f.flushes()).toBe(2); expect(f.leases()).toBe(0);
  });
  it('does not return an uncertified live cut or mutate its cursor', async () => {
    const f = fixture([human(0, 'Unsaved'), event(1, 'step/end')], { onFlush: count => { if (count === 2) throw new Error('Disk failed'); } });
    const batch = await f.sources.freeze('a', streams, { maxInputTokens: 2000 });
    expect(batch.units).toEqual([]); expect(batch.ranges).toEqual([]); expect(batch.blocked[0]?.reason).toContain('Disk failed');
    expect(streams.s.cursor).toBe(-1); expect(f.leases()).toBe(0);
  });
  it('keeps failed results with their calls but leaves incomplete tools and inherited history out', async () => {
    const events = [human(0, 'Inherited'), event(1, 'step/end'), human(2, 'Own'), event(3, 'tool/call', { callId: 'fail', name: 'bash', arguments: '{"command":"false"}' }), event(4, 'tool/result', { message: { toolCallId: 'fail', isError: true, content: [{ type: 'text', text: 'exit 1' }] } }), event(5, 'step/end'), event(6, 'tool/call', { callId: 'pending', name: 'bash', arguments: '{}' }), event(7, 'step/end')];
    const f = fixture(events, { inherited: 2 });
    const batch = await f.sources.freeze('a', streams, { maxInputTokens: 2000 });
    expect(batch.ranges[0]?.through).toBe(5); expect(JSON.stringify(batch.units)).toContain('exit 1'); expect(JSON.stringify(batch.units)).not.toContain('Inherited');
    expect(JSON.stringify(batch.units)).not.toContain('pending'); expect(batch.blocked).toHaveLength(1);
  });
  it('does not learn replaced output a second time or treat a memory read as experience', async () => {
    const events = [human(0, 'Work'), event(1, 'tool/call', { callId: 'read', name: 'read', arguments: '{"file_path":"/owner/.nanoassistant/memory/MEMORY.md"}' }), event(2, 'tool/result', { message: { toolCallId: 'read', content: [{ type: 'text', text: 'OLD MEMORY' }] } }), event(3, 'step/end'), event(4, 'tool/result', { surfaceOp: { op: 'replace' }, message: { toolCallId: 'read', content: [{ type: 'text', text: 'REPLACED MEMORY' }] } }), event(5, 'step/end')];
    const batch = await fixture(events).sources.freeze('a', streams, { maxInputTokens: 2000 });
    expect(JSON.stringify(batch.units)).not.toContain('MEMORY'); expect(batch.ranges[0]?.through).toBe(5);
  });
  it('deduplicates an observed IM revision, preserves revisions, and filters revoked source messages', async () => {
    const result = (seq: number, id: string, content: string) => [event(seq, 'tool/call', { callId: id, name: 'inbox', arguments: '{}' }), event(seq + 1, 'tool/result', { message: { toolCallId: id, content: [{ type: 'text', text: JSON.stringify({ target: 'room', messages: [{ id: 'message', sender: { type: 'user' }, content }] }) }] } }), event(seq + 2, 'step/end')];
    const batch = await fixture([...result(0, 'one', 'First'), ...result(3, 'dup', 'First'), ...result(6, 'new', 'Corrected')], { cold: true }).sources.freeze('a', streams, { maxInputTokens: 3000 });
    expect(batch.units.flatMap(unit => unit.fingerprints)).toHaveLength(2);
    const revoked = await fixture(result(0, 'one', 'Do not read')).sources.freeze('a', streams, { maxInputTokens: 3000, sources: { revision: 'r', allowed: [], excluded: ['room'] } });
    expect(JSON.stringify(revoked.units)).not.toContain('Do not read');
  });
});

it('waits for every Inbox fragment, then deduplicates the full message against a historical read', async () => {
  const page = (seq: number, id: string, message: any, name = 'inbox') => [event(seq, 'tool/call', {callId:id,name,arguments:'{}'}),event(seq+1,'tool/result',{message:{toolCallId:id,content:[{type:'text',text:JSON.stringify({target:'room',messages:[message]})}]}}),event(seq+2,'step/end')];
  const base={id:'m',sender:{id:'u',type:'user',name:'User',is_owner:true}};
  const first=page(0,'part1',{...base,partial:true,part:1,parts:2,content:[{type:'text',text:'Private '}]});
  const blocked=await fixture(first).sources.freeze('a',streams,{maxInputTokens:4000});
  expect(blocked.units).toEqual([]);expect(blocked.ranges[0]?.through).toBe(-1);
  const second=page(3,'part2',{...base,partial:true,part:2,parts:2,content:[{type:'text',text:'only.'}]});
  const history=page(6,'history',{...base,sender:{id:'u',type:'user',name:'Different presentation'},content:[{type:'text',text:'Private only.'}]},'conversations');
  const batch=await fixture([...first,...second,...history]).sources.freeze('a',streams,{maxInputTokens:4000});
  expect(batch.units.flatMap(unit=>unit.fingerprints)).toHaveLength(1);
  expect(batch.ranges[0]?.through).toBe(8);
  expect(JSON.stringify(batch.units)).toContain('Private only.');
});

it('continues an oversized source across persisted bounded pages before advancing its complete-step cursor', async () => {
  const { commitSourceRange } = await import('../src/knowledge/memory-sources.js');
  const f = fixture([human(0, 'Long evidence: ' + 'conditions matter. '.repeat(300)), event(1, 'step/end'), human(2, 'Later useful correction'), event(3, 'step/end')], {cold:true});
  let progress = structuredClone(streams); const pages: string[] = [];
  for (let i = 0; i < 30 && progress.s.cursor < 1; i++) {
    const batch = await f.sources.freeze('a', progress, {maxInputTokens:500});
    expect(batch.units).toHaveLength(1); expect(batch.inputTokens).toBeLessThanOrEqual(500);
    const unit = batch.units[0]!;
    pages.push((unit.events[0] as {text:string}).text);
    commitSourceRange(progress.s, batch.ranges[0]!);
    if (unit.page!.end < unit.page!.total) expect(progress.s.cursor).toBe(-1);
    progress = JSON.parse(JSON.stringify(progress));
  }
  expect(progress.s.cursor).toBe(1); expect(progress.s.continuation).toBeUndefined();
  expect(pages.join('')).toContain('Long evidence: ' + 'conditions matter. '.repeat(300));
  expect(pages.join('')).not.toContain('source_json_page');
  const later = await f.sources.freeze('a', progress, {maxInputTokens:500});
  expect(JSON.stringify(later.units)).toContain('Later useful correction');
  expect(later.ranges[0]?.through).toBe(3);
});

function taskFixture() {
  const at = (e: any, time: number) => ({...e,time});
  const root: any[] = [at(human(0,'Must be refundable; budget 5000'),110),at(event(1,'step/end'),120),at(event(2,'subagent/catalog',{mode:'continuable',childId:'child',childCreatedAt:125}),125),at(event(3,'step/end'),130)];
  const child: any[] = [...root.slice(0,2),at(human(2,'Compare using those conditions'),140),at(event(3,'assistant/message',{message:{content:[{type:'text',text:'Compared two hotels; not booked.'}]}}),150),at(event(4,'step/end'),160)];
  const ctx={sessions:{get:()=>undefined},sessionQuery:{observeSession:async(id:string)=>{
    const events=structuredClone(id==='s'?root:child);
    return {source:'prepared',revision:'disk',header:id==='s'?{cwd:'/owner',origin:'root'}:{cwd:'/task',origin:'subagent',parentSession:'s'},inheritedEventCount:id==='s'?0:2,events,cursor:events.at(-1).seq,[Symbol.dispose]:()=>{}};
  }}};
  return {root,child,sources:new MemorySources(ctx as never,new Map([['s',{sessionId:'s',agentId:'a',ownerId:'owner',cwd:'/owner',revision:'1'}]]))};
}

it('discovers unreported direct tasks, retains inherited conditions and excludes future arrivals from a frozen cycle',async()=>{
  const f=taskFixture();
  const target=await f.sources.freezeTarget('a',streams,100,{generation:2});
  expect(Object.keys(target.children)).toEqual(['child']);
  f.root.push({...human(4,'Future root correction'),time:200},{...event(5,'step/end'),time:210});
  f.child.push({...human(5,'Future child correction'),time:200},{...event(6,'step/end'),time:210});
  const batch=await f.sources.freeze('a',streams,{maxInputTokens:2000,target});
  expect(batch.text).not.toContain('Future root');
  expect(await f.sources.children('a',target,batch,{maxInputTokens:2000})).toEqual([]);
  const consumed = {s:{baseline:-1,cursor:3}};
  const childOnly = await f.sources.freeze('a',consumed,{maxInputTokens:2000,target});
  const tasks=await f.sources.children('a',target,childOnly,{maxInputTokens:2000});
  expect(tasks).toHaveLength(1);
  expect(tasks[0]?.text).toContain('Must be refundable');
  expect(tasks[0]?.text).toContain('not booked');
  expect(tasks[0]?.text).not.toContain('Future child');
  expect(tasks[0]?.text).toContain('session_id=s; item_id=0');
  expect(tasks[0]?.through).toBe(4);
});

it('cuts child results at an earlier root batch and re-extracts the full activation range on later batches',async()=>{
  const f=taskFixture();
  f.root.push({...human(4,'Check the result'),time:170},{...event(5,'step/end'),time:180});
  const target=await f.sources.freezeTarget('a',streams,100);
  const early={id:'early',units:[],ranges:[{sessionId:'s',start:-1,through:3,observed:5}],cutoffs:{s:130},filtered:0,blocked:[],inputTokens:0};
  expect(await f.sources.children('a',target,early,{maxInputTokens:2000})).toEqual([]);
  const late=await f.sources.freeze('a',streams,{target,maxInputTokens:2000});
  const material=await f.sources.children('a',target,late,{maxInputTokens:2000});
  expect(material[0]?.text).toContain('Compare using those conditions');
  expect(material[0]?.text).toContain('not booked');
  const again=await f.sources.children('a',target,late,{maxInputTokens:2000});
  expect(again[0]?.sourceVersion).toBe(material[0]?.sourceVersion);
  expect(await f.sources.children('a',{...target,activationAt:135},late,{maxInputTokens:2000})).not.toEqual(material);
});

it('keeps original IDs while removing revoked messages before source queries',async()=>{
  const {qualifiedEvents}=await import('../src/knowledge/memory-source-view.js');
  const events:any[]=[{...event(10,'tool/call',{callId:'read',name:'conversations',arguments:'{}'}),time:100},{...event(11,'tool/result',{message:{toolCallId:'read',content:[{type:'text',text:JSON.stringify({messages:[{id:'good',conversation_id:'allowed',content:'visible'},{id:'bad',conversation_id:'revoked',content:'secret'}]})}]}}),time:101}];
  const view=qualifiedEvents(events,{sources:{revision:'r',allowed:['allowed'],excluded:['revoked']}});
  expect(view.map(item=>item.seq)).toEqual([10,11]);
  expect(JSON.stringify(view)).toContain('visible');
  expect(JSON.stringify(view)).not.toContain('secret');
});

it('continues each original Unicode Inbox message with its own identity and body offset',async()=>{
  const {commitSourceRange}=await import('../src/knowledge/memory-sources.js');
  const first='父母同行，免费取消。🌈'.repeat(180);const second='后续更正：改为周日。🌤'.repeat(180);
  const messages=[{id:'first',sender:{id:'u',type:'user'},content:first},{id:'second',sender:{id:'u',type:'user'},content:second}];
  const f=fixture([event(0,'tool/call',{callId:'inbox',name:'inbox',arguments:'{}'}),event(1,'tool/result',{message:{toolCallId:'inbox',content:[{type:'text',text:JSON.stringify({target:'room',name:'Family trip',delivery:'observer',conversation_type:'group',channel:'web',messages})}]}}),event(2,'step/end')],{cold:true});
  const progress=structuredClone(streams);const bodies=new Map<string,string>();
  for(let n=0;n<40&&progress.s.cursor<2;n++){
    const batch=await f.sources.freeze('a',progress,{maxInputTokens:500});
    expect(batch.units).toHaveLength(1);
    const part=batch.units[0]!.events[0] as {messageId:string;text:string;offset:number;end:number;total:number};
    bodies.set(part.messageId,(bodies.get(part.messageId)??'')+part.text);
    if(part.messageId==='first'||part.messageId==='second'){
      expect(Array.from(part.text).length).toBe(part.end-part.offset);
      expect(batch.text).toContain('Family trip');expect(batch.text).toContain('observer');
      expect(batch.text).toContain('room');expect(batch.text).toContain('group');expect(batch.text).toContain('web');
    }
    commitSourceRange(progress.s,batch.ranges[0]!);
    if(progress.s.continuation)expect(progress.s.cursor).toBe(-1);
  }
  expect(progress.s.cursor).toBe(2);expect(bodies.get('first')).toBe(first);expect(bodies.get('second')).toBe(second);
});

it('preserves the outer Inbox conversation and observation identity in direct material',()=>{
  const text=renderMaterial([{type:'tool/result',content:{target:'room',name:'Family trip',delivery:'observer',conversation_type:'group',channel:'web',messages:[{id:'m1',sender:{id:'u'},content:'Conditional preference'}]}}]);
  for(const value of ['room','Family trip','observer','group','web','m1','Conditional preference'])expect(text).toContain(value);
});
