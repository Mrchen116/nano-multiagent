import { describe, expect, it } from 'vitest';
import type { TrajectoryRun } from '@nano/product-contracts';
import type { TrajectorySnapshot } from '../src/client/trajectory-contract';
import { withLaunches, executionFocus, verifiedRun } from '../src/client/navigation-model';

const run = { runId: 'epoch-old', sessionId: 'child', parentSessionId: 'parent', kind: 'tool', provider: 'fork', state: 'completed', startSeq: 40, endSeq: 60, startedAt: 1000 } as TrajectoryRun;
const node = (seq: number) => ({ kind: 'user', seq, time: seq, turn: seq, content: [{type:'text', text:String(seq)}] });
const request = (startSeq: number, turn: number) => ({purpose:'assistant', startSeq, turn, step:1, startedAt:startSeq, status:'running'});
const snapshot = { eventNodes: [node(1), node(40), node(60), node(80)], systemPrompts: [], eventLocations: new Map(), callSchemas: new Map(), requests: [request(42,1), request(82,2)], partial: {turn:2,step:1,blocks:[]}, runningCalls:[{turn:2,step:1,callId:'new'}] } as unknown as TrajectorySnapshot;

describe('native execution projection', () => {
  it('checks reread run identity and parent instead of trusting a navigation payload', () => {
    expect(verifiedRun([run], 'child', run.runId, 'wrong')).toBeUndefined();
    expect(verifiedRun([run], 'child', run.runId, 'parent')).toBe(run);
  });
  it('decorates the real tool row and inserts only resident standalone launches with stable identities', () => {
    const turns = [{turn:1,groups:[{title:'step',cells:[{index:1,kind:'tool' as const,callId:'c',sourceSeq:50,text:'tool',timeSeconds:1},{index:2,kind:'user' as const,sourceSeq:60,text:'input',timeSeconds:null}]}]}];
    const runs = [{...run,runId:'tool',parentSessionId:'parent',callId:'c',launchSeq:50},{...run,runId:'background',kind:'memory',launchSeq:55},{...run,runId:'earlier',launchSeq:2}] as TrajectoryRun[];
    const cells = withLaunches(turns,runs,'parent',40).flatMap(t=>t.groups.flatMap(g=>g.cells));
    expect(cells.map(c=>c.sourceSeq)).toEqual([50,55,60]);
    expect(cells[0]?.launchRuns?.[0]?.runId).toBe('tool');
    expect(cells[1]?.recordId).toBe('run:background');
    expect(cells[1]?.launchRuns?.[0]?.kind).toBe('memory');
    expect(cells.map(c=>c.index)).toEqual([1,2,3]);
    expect(turns[0]?.groups[0]?.cells).toHaveLength(2);
  });
  it('selects exact seq members even when native time spans overlap inherited records', () => {
    const turns=[{turn:1,groups:[{title:'step',cells:[1,40,60,80].map((seq,index)=>({index:index+1,sourceSeq:seq,kind:'user' as const,text:'input',timeSeconds:1,startedAt:1000}))}]}];
    for(const mode of ['sequence','duration','time','actual'] as const) {
      const focus=executionFocus(turns,run,mode);
      expect([...focus.indexes!]).toEqual([2,3]);
      expect(focus.range).not.toBeNull();
    }
  });
});

it('keeps native tool and live assistant coordinates tied to their request epoch', async () => {
  const { coordinateLayout } = await import('../src/client/navigation-model');
  const turns=[{turn:2,groups:[{title:'step',cells:[{index:1,recordId:'assistant\u00002\u00001',sourceSeq:Number.MAX_SAFE_INTEGER,kind:'message' as const,text:'live',timeSeconds:null},{index:2,callId:'new',kind:'tool' as const,text:'tool',timeSeconds:null}]}]}];
  const cells=coordinateLayout(turns,snapshot).flatMap(t=>t.groups.flatMap(g=>g.cells));
  expect(cells.map(c=>c.sourceSeq)).toEqual([82,82]);
});
