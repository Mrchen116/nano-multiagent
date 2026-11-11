import { describe, expect, it } from 'vitest';
import { createHistoryView } from 'dsh-agent-context';
import { qualifiedEvents } from '../src/knowledge/memory-source-view.js';
import { MemorySources, renderMaterial, selectChildMaterial } from '../src/knowledge/memory-sources.js';

const event = (seq: number, type: string, data: any = {}) => ({ seq, time: 1700000000000 + seq, type, data: data.message ? {...data,message:{source:{kind:type === 'tool/result' ? 'tool' : 'model'},...data.message}} : data });
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
  it('keeps memory reads as recorded experience without replaying native display replacements', async () => {
    const events = [human(0, 'Work'), event(1, 'tool/call', { callId: 'read', name: 'read', arguments: '{"file_path":"/owner/.nanoassistant/memory/MEMORY.md"}' }), event(2, 'tool/result', { message: { toolCallId: 'read', content: [{ type: 'text', text: 'OLD MEMORY' }] } }), event(3, 'step/end'), {...event(4, 'tool/result', { message: { toolCallId: 'read', content: [{ type: 'text', text: 'REPLACED MEMORY' }] } }),surfaceOp:{op:'replace'}}, event(5, 'step/end')];
    const batch = await fixture(events).sources.freeze('a', streams, { maxInputTokens: 2000 });
    expect(batch.text).toContain('OLD MEMORY'); expect(batch.text).not.toContain('REPLACED MEMORY'); expect(batch.ranges[0]?.through).toBe(5);
  });
  it('preserves repeated IM reads and revisions exactly as the Agent observed them', async () => {
    const result = (seq: number, id: string, content: string) => [event(seq, 'tool/call', { callId: id, name: 'inbox', arguments: '{}' }), event(seq + 1, 'tool/result', { message: { toolCallId: id, content: [{ type: 'text', text: JSON.stringify({ target: 'room', messages: [{ id: 'message', sender: { type: 'user' }, content }] }) }] } }), event(seq + 2, 'step/end')];
    const batch = await fixture([...result(0, 'one', 'First'), ...result(3, 'dup', 'First'), ...result(6, 'new', 'Corrected')], { cold: true }).sources.freeze('a', streams, { maxInputTokens: 3000 });
    expect(batch.text!.match(/First/g)).toHaveLength(2); expect(batch.text).toContain('Corrected');
    const revoked = await fixture(result(0, 'one', 'Do not read')).sources.freeze('a', streams, { maxInputTokens: 3000 });
    expect(revoked.text).toContain('Do not read');
  });
});

it('preserves separate Inbox fragment returns and a subsequent full historical read', async () => {
  const page = (seq: number, id: string, message: any, name = 'inbox') => [event(seq, 'tool/call', {callId:id,name,arguments:'{}'}),event(seq+1,'tool/result',{message:{toolCallId:id,content:[{type:'text',text:JSON.stringify({target:'room',messages:[message]})}]}}),event(seq+2,'step/end')];
  const base={id:'m',sender:{id:'u',type:'user',name:'User',is_owner:true}};
  const first=page(0,'part1',{...base,partial:true,part:1,parts:2,content:[{type:'text',text:'Private '}]});
  const blocked=await fixture(first).sources.freeze('a',streams,{maxInputTokens:4000});
  expect(blocked.units).toHaveLength(1);expect(blocked.ranges[0]?.through).toBe(2);
  const second=page(3,'part2',{...base,partial:true,part:2,parts:2,content:[{type:'text',text:'only.'}]});
  const history=page(6,'history',{...base,sender:{id:'u',type:'user',name:'Different presentation'},content:[{type:'text',text:'Private only.'}]},'conversations');
  const batch=await fixture([...first,...second,...history]).sources.freeze('a',streams,{maxInputTokens:4000});
  expect(batch.units).toHaveLength(3); expect(batch.text).toContain('"partial":true'); expect(batch.text).toContain('"part":2');
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
  expect(tasks[0]?.text).toContain('session_id=s\n');
  expect(tasks[0]?.text).toContain('window_id=s:initial');
  expect(tasks[0]?.text).toContain('item_id=0');
  expect(tasks[0]?.through).toBe(4); expect(tasks[0]?.omitted).toBe(0); expect(tasks[0]?.text).not.toContain('Additional records omitted');
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

it('keeps original IDs and unmodified mixed-conversation tool returns',async()=>{
  const {qualifiedEvents}=await import('../src/knowledge/memory-source-view.js');
  const events:any[]=[{...event(10,'tool/call',{callId:'read',name:'conversations',arguments:'{}'}),time:100},{...event(11,'tool/result',{message:{toolCallId:'read',content:[{type:'text',text:JSON.stringify({messages:[{id:'good',conversation_id:'allowed',content:'visible'},{id:'bad',conversation_id:'revoked',content:'secret'}]})}]}}),time:101}];
  const view=qualifiedEvents(events);
  expect(view.map(item=>item.seq)).toEqual([10,11]);
  expect(JSON.stringify(view)).toContain('visible');
  expect(view).toEqual(events);
});

it('pages an oversized Unicode tool return without changing its original JSON body',async()=>{
  const {commitSourceRange}=await import('../src/knowledge/memory-sources.js');
  const original=JSON.stringify({target:'room',messages:[{id:'first',content:'父母同行，免费取消。🌈'.repeat(180)},{id:'second',content:'后续更正：改为周日。🌤'.repeat(180)}]});
  const f=fixture([event(0,'tool/call',{callId:'inbox',name:'inbox',arguments:'{}'}),event(1,'tool/result',{message:{toolCallId:'inbox',content:[{type:'text',text:original}]}}),event(2,'step/end')],{cold:true});
  const progress=structuredClone(streams);let body='';
  for(let n=0;n<60&&progress.s.cursor<2;n++){
    const batch=await f.sources.freeze('a',progress,{maxInputTokens:500});
    expect(batch.units).toHaveLength(1);expect(batch.inputTokens).toBeLessThanOrEqual(500);
    const part=batch.units[0]!.events[0] as {source:{type:string};text:string;offset:number;end:number};
    if(part.source.type==='tool/result')body+=part.text;
    expect(Array.from(part.text).length).toBe(part.end-part.offset);
    commitSourceRange(progress.s,batch.ranges[0]!);
    if(progress.s.continuation)expect(progress.s.cursor).toBe(-1);
  }
  expect(progress.s.cursor).toBe(2);expect(body).toBe(original);
});

it('preserves the outer Inbox conversation and observation identity in direct material',()=>{
  const text=renderMaterial([{type:'tool/result',content:{target:'room',name:'Family trip',delivery:'observer',conversation_type:'group',channel:'web',messages:[{id:'m1',sender:{id:'u'},content:'Conditional preference'}]}}]);
  for(const value of ['room','Family trip','observer','group','web','m1','Conditional preference'])expect(text).toContain(value);
});


it('renders native windows once and uses only readable History items for messages and calls', async () => {
  const events = [human(0, 'Before window'), event(1, 'step/end'),
    event(2, 'compaction/start', {compactionId:'c'}), event(3, 'compaction/summary', {compactionId:'c',summary:[]}), event(4, 'compaction/end', {compactionId:'c'}),
    human(5, 'Read the inbox'),
    event(6, 'assistant/message', {message:{content:[{type:'text',text:'Reading messages.'},{type:'tool-call',id:'in',name:'inbox',arguments:'{"action":"read","target":"room"}'}]}}),
    event(7, 'tool/call', {callId:'in',name:'inbox',arguments:'{"action":"read","target":"room"}'}),
    event(8, 'tool/result', {message:{toolCallId:'in',content:[{type:'text',text:JSON.stringify({target:'room',delivery:'observer',messages:[{id:'im1',sender:{id:'owner',type:'user'},content:'Only refundable'}]})}]}}),
    event(9, 'tool/call', {callId:'send',name:'send_message',arguments:'{"target":"agent:other","text":"Ask first"}'}),
    event(10, 'tool/result', {message:{toolCallId:'send',isError:true,content:[{type:'text',text:'Permission denied'}]}}),event(11,'step/end')];
  const batch = await fixture(events).sources.freeze('a', streams, {maxInputTokens:4000});
  const text = batch.text!;
  expect(text.match(/session_id=s(?:\n|;)/g)).toHaveLength(1);
  expect(text.match(/window_id=s:2/g)).toHaveLength(1);
  expect(text).toContain('2023-11-14T22:13:20.005Z');
  expect(text).toContain('item_id=6');
  expect(text).not.toContain('item_id=7');
  expect(text).not.toContain('item_id=9');
  expect(text).not.toMatch(/events \d|"sessionId"|"seq"/);
  for (const value of ['inbox','callId','in','send_message','agent:other','Permission denied','observer','owner','im1','Only refundable']) expect(text).toContain(value);
  const child = selectChildMaterial({sessionId:'s',rootSessionId:'parent',events:events as never,inheritedEvents:[]},4000).text;
  expect(child).toContain('window_id=s:2');
  expect(child).not.toContain('item_id=7');
  expect(child).not.toContain('item_id=9');
  expect(child).toContain('Own experience');
  expect(child).toContain('send_message');
  expect(child).toContain('agent:other');
  const view = createHistoryView('s', qualifiedEvents(events as never));
  let windowId = '';
  for (const line of text.split('\n')) {
    if (line.startsWith('## window_id=')) windowId = line.slice('## window_id='.length);
    const itemId = /item_id=(\S+)/.exec(line)?.[1];
    if (itemId) expect(() => view.read(windowId, itemId)).not.toThrow();
  }
  const later = [...events,human(12,'Later same window'),event(13,'step/end')];
  const increment = await fixture(later).sources.freeze('a',{s:{baseline:1,cursor:11}},{maxInputTokens:4000});
  expect(increment.text).toContain('window_id=s:2');
  expect(increment.text).toContain('item_id=12');
  expect(increment.text).not.toContain('Before window');
});


it('keeps child references in the original parent and child windows despite activation and inheritance cuts', async () => {
  const events = [human(0,'Old input'),event(1,'step/end'),event(2,'compaction/start',{compactionId:'c'}),
    event(3,'compaction/summary',{compactionId:'c',summary:[]}),event(4,'compaction/end',{compactionId:'c'}),
    human(5,'Inherited condition'),event(6,'step/end'),event(7,'subagent/catalog',{mode:'continuable',childId:'child',childCreatedAt:1700000000007}),event(8,'step/end')];
  const own = [human(7,'Own task'),event(8,'step/end')];
  const ctx = {sessions:{get:()=>undefined},sessionQuery:{observeSession:async(id:string)=>({
    source:'prepared',revision:'disk',header:id==='s'?{cwd:'/owner',origin:'root'}:{cwd:'/task',origin:'subagent',parentSession:'s'},
    events:id==='s'?events:[...events.slice(0,7),...own],inheritedEventCount:id==='s'?0:7,cursor:8,[Symbol.dispose]:()=>{},
  })}};
  const sources = new MemorySources(ctx as never,new Map([['s',{sessionId:'s',agentId:'a',ownerId:'owner',cwd:'/owner',revision:'1'}]]));
  const progress = {s:{baseline:4,cursor:8}};
  const target = await sources.freezeTarget('a',progress,1700000000005);
  const batch = await sources.freeze('a',progress,{target,maxInputTokens:4000});
  const [material] = await sources.children('a',target,batch,{maxInputTokens:4000});
  expect(material?.text).toContain('window_id=s:2');
  expect(material?.text).toContain('window_id=child:2');
  expect(material?.text).toContain('item_id=5');
  expect(material?.text).toContain('item_id=7');
  expect(material?.text).not.toContain('Old input');
  expect(selectChildMaterial(material!,4000).text).toBe(material!.text);
});


it('preserves the original IM timestamp separately from the tool execution time',()=>{
  const text=renderMaterial([{type:'tool/result',time:Date.parse('2026-11-11T07:00:00Z'),callId:'read-inbox',content:{target:'group:release',messages:[{id:'m1',time:'2026-11-11T02:00:00Z',sender:{id:'owner'},content:'Do not restart.'}]}}]);
  expect(text).toContain('2026-11-11T07:00:00.000Z');
  expect(text).toContain('2026-11-11T02:00:00Z');
  expect(text).toContain('group:release');
});


it('does not leak assistant tool blocks when their paired result cannot fit',()=>{
  const events=[event(0,'assistant/message',{message:{content:[{type:'tool-call',id:'send',name:'send_message',arguments:'{"target":"agent:other"}'}]}}),
    event(1,'tool/call',{callId:'send',name:'send_message',arguments:{target:'agent:other'}}),
    event(2,'tool/result',{message:{toolCallId:'send',isError:true,content:[{type:'text',text:'Permission denied. '.repeat(500)}]}})];
  const small=selectChildMaterial({sessionId:'child',rootSessionId:'root',events:events as never,inheritedEvents:[]},200);
  expect(small.text).not.toContain('agent:other');
  const full=selectChildMaterial({sessionId:'child',rootSessionId:'root',events:events as never,inheritedEvents:[]},10000);
  expect(full.text).toContain('agent:other');expect(full.text).toContain('Permission denied.');
});


it('labels main-Agent delegation and messages without relabelling humans or peers',()=>{
  const input=event(0,'user/message',{id:'task',source:{kind:'user'},content:[{type:'text',text:'Delegated requirement'}]});
  const message=(seq:number,senderSessionId:string)=>event(seq,'user/message',{id:`m${seq}`,source:{kind:'agent-message',form:'relay',senderSessionId},content:[{type:'text',text:`Message from ${senderSessionId}`}]});
  const events=[input,message(1,'root'),message(2,'peer'),human(3,'Direct human correction')];
  const material=selectChildMaterial({sessionId:'child',rootSessionId:'root',events:events as never,inheritedEvents:[]},10000);
  expect(material.text.match(/\[main agent\]/g)).toHaveLength(2);
  expect(material.text.match(/\[other agent\]/g)).toHaveLength(1);
  expect(material.text.match(/\[human user\]/g)).toHaveLength(1);
  expect(material.text).not.toContain('evidence:');expect(material.text).not.toContain('Additional records omitted');
});

it('retains every tool name, directory read and non-JSON result unchanged in both consumers',async()=>{
  const names=['skill','notes','history','memory_maintenance','read'];
  const events=names.flatMap((name,i)=>[event(i*3,'tool/call',{callId:name,name,arguments:'{ "file_path": "/owner/.nanoassistant/memory/MEMORY.md" }'}),event(i*3+1,'tool/result',{message:{toolCallId:name,content:[{type:'text',text:`  original ${name} result\n  untouched`}]}}),event(i*3+2,'step/end')]);
  const batch=await fixture(events).sources.freeze('a',streams,{maxInputTokens:10000});
  const child=selectChildMaterial({sessionId:'s',rootSessionId:'root',events:qualifiedEvents(events as never),inheritedEvents:[]},10000);
  for(const text of [batch.text!,child.text])for(const name of names)expect(text).toContain(`  original ${name} result\n  untouched`);
  expect(child.text.replace(/^Own experience\n\n/, '')).toBe(batch.text);
});

it('prefers recent input over assistant text and keeps tool pairs together under budget',()=>{
  const events=[event(0,'user/message',{id:'task',source:{kind:'user'},content:[{type:'text',text:'EARLY_REQUIREMENT '+ 'x'.repeat(300)}]}),event(1,'assistant/message',{message:{content:[{type:'text',text:'ASSISTANT_REPORT '+ 'x'.repeat(300)}]}}),event(2,'user/message',{id:'correction',source:{kind:'user'},content:[{type:'text',text:'LATEST_CORRECTION '+ 'x'.repeat(300)}]})];
  const result=selectChildMaterial({sessionId:'child',rootSessionId:'root',events:events as never,inheritedEvents:[]},180);
  expect(result.text).toContain('LATEST_CORRECTION');expect(result.text).not.toContain('EARLY_REQUIREMENT');expect(result.text).not.toContain('ASSISTANT_REPORT');expect(result.omitted).toBe(2);
});


it('pages long tool arguments within budget and resumes their offset when the next budget grows',async()=>{
  const {commitSourceRange}=await import('../src/knowledge/memory-sources.js');
  const args=JSON.stringify({file_path:'/owner/.nanoassistant/memory/detail.md',content:'x'.repeat(5000)});
  const f=fixture([event(0,'tool/call',{callId:'write',name:'write',arguments:args}),event(1,'tool/result',{message:{toolCallId:'write',content:[{type:'text',text:'saved'}]}}),event(2,'step/end')]);
  const progress=structuredClone(streams);let reconstructed='';let priorEnd=0;
  for(let i=0;i<5&&progress.s.cursor<2;i++){
    const budget=i===0?500:10000;
    const batch=await f.sources.freeze('a',progress,{maxInputTokens:budget});
    expect(batch.units).toHaveLength(1);expect(batch.inputTokens).toBeLessThanOrEqual(budget);
    const page=batch.units[0]!.events[0] as {source:{type:string};offset:number;end:number;text:string};
    if(page.source.type==='tool/call'){expect(page.offset).toBe(priorEnd);reconstructed+=page.text;priorEnd=page.end;}
    commitSourceRange(progress.s,batch.ranges[0]!);
  }
  expect(progress.s.cursor).toBe(2);expect(reconstructed).toBe(args);
});

it('indexes IM sources only from actual IM calls while retaining lookalike tool bodies',async()=>{
  const body=(target:string)=>JSON.stringify({target,messages:[{id:'m',content:'Observed body'}]});
  const events=['read','inbox','conversations'].flatMap((name,i)=>[event(i*3,'tool/call',{callId:name,name,arguments:'{}'}),event(i*3+1,'tool/result',{message:{toolCallId:name,content:[{type:'text',text:body(name+'-room')}]}}),event(i*3+2,'step/end')]);
  const {sourceConversations}=await import('../src/knowledge/memory-source-view.js');
  const batch=await fixture(events).sources.freeze('a',streams,{maxInputTokens:4000});
  expect(batch.conversations).toEqual(['inbox-room','conversations-room']);
  expect(sourceConversations(qualifiedEvents(events as never))).toEqual(batch.conversations);
  expect(batch.text).toContain(body('read-room'));
});
