import { describe, expect, it } from 'vitest';
import { MemorySources } from '../src/knowledge/memory-sources.js';

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

it('compares a child report with certified original tool results without importing its inherited context', async()=>{
  const root=[event(0,'user/message',{source:{kind:'agent-message',senderSessionId:'child'},content:[{type:'text',text:'The test passed.'}]}),event(1,'step/end')];
  const child=[human(0,'Inherited secret'),event(1,'step/end'),event(2,'tool/call',{callId:'check',name:'bash',arguments:'{"command":"test"}'}),event(3,'tool/result',{message:{toolCallId:'check',isError:true,content:[{type:'text',text:'Test actually failed.'}]}}),event(4,'step/end')];
  const ctx={sessions:{get:()=>undefined},sessionQuery:{observeSession:async(id:string)=>({source:'prepared',revision:'disk',header:id==='s'?{cwd:'/owner',origin:'root'}:{cwd:'/child',origin:'subagent',parentSession:'s'},inheritedEventCount:id==='s'?0:2,events:id==='s'?root:child,cursor:4,[Symbol.dispose]:()=>{}})}};
  const sources=new MemorySources(ctx as never,new Map([['s',{sessionId:'s',agentId:'a',ownerId:'owner',cwd:'/owner',revision:'1'}]]));
  const batch=await sources.freeze('a',streams,{maxInputTokens:3000});
  expect(JSON.stringify(batch.units)).toContain('The test passed.');
  expect(JSON.stringify(batch.units)).toContain('Test actually failed.');
  expect(JSON.stringify(batch.units)).not.toContain('Inherited secret');
  expect(batch.units[0]?.fingerprints).toEqual(['child:child:4']);
});
