import { expect, it } from 'vitest';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { safeBoundary } from '../src/knowledge/memory-source-view.js';

const record = (seq:number,type:string,data:unknown={},extra:unknown={}) => ({seq,time:seq+1,type,data,...extra as object});
const records = [
  record(0,'tool/call',{callId:'one'}),
  record(1,'tool/result',{message:{toolCallId:'one'}}),
  record(2,'step/end'),
  record(3,'tool/result',{message:{toolCallId:'one'}},{surfaceOp:{op:'replace',startSeq:1,endSeq:1},sourceEventSeqs:[1]}),
  record(4,'tool/call',{callId:'two'}),
  record(5,'tool/result',{message:{toolCallId:'two'}}),
  record(6,'step/end'),
] as unknown as SessionEvent[];

it('advances the completed evidence cut past native result replacements',()=>{
  expect(safeBoundary(records)).toEqual({through:6,time:7});
  expect(safeBoundary(records,4)).toEqual({through:2,time:3});
});
it('still stops at a genuinely unpaired appended result',()=>{
  const unpaired=[...records,record(7,'tool/result',{message:{toolCallId:'unknown'}}),record(8,'step/end')] as SessionEvent[];
  expect(safeBoundary(unpaired)).toEqual({through:6,time:7});
});
