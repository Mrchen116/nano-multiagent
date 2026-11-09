import { expect, it } from 'vitest';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { jsonBytes, workPage, workPageBytes } from '../src/work-page.js';

it('starts after the durable cursor, removes request snapshots and lets one large fact make progress', async () => {
  const body='中'.repeat(workPageBytes / 2);
  const events=[
    {seq:50,time:1,type:'request/header',data:{header:{config:{model:'backup'},system:body}}},
    {seq:51,time:2,type:'tool/call',data:{callId:'x',turn:4,arguments:JSON.stringify({body})}},
    {seq:52,time:3,type:'turn/end',data:{turn:4,reason:{kind:'completed'}}},
  ] as unknown as SessionEvent[];
  const lookedUp:number[]=[];
  const read=(afterSeq:number)=>workPage({afterSeq,firstOwn:20,head:52,eventAt:seq=>{
    lookedUp.push(seq);return events[seq-50];
  },present:async event=>event,model:()=>undefined,modelVersion:'version'});
  const header=await read(49);
  expect(header).toMatchObject({throughSeq:50,more:true,events:[{data:{header:{config:{model:'backup'}}}}]});
  expect(jsonBytes(header)).toBeLessThan(1024);
  expect(lookedUp).toEqual([50,51,52]);
  const large=await read(50);
  expect(large).toMatchObject({throughSeq:51,more:true,events:[events[1]]});
  expect(jsonBytes(large)).toBeGreaterThan(workPageBytes);
  expect(await read(51)).toMatchObject({throughSeq:52,more:false,events:[events[2]]});
});
