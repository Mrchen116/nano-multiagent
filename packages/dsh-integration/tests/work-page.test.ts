import { expect, it } from 'vitest';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { jsonBytes, workPage, workPageBytes, WorkCatalogPages } from '../src/work-page.js';

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

it('walks a catalog once, replays an acknowledged page, and restarts an interrupted scan without dropping rows', async () => {
  const pages=new WorkCatalogPages();
  let visits=0;
  async function* catalog(fail=false) {
    for (let i=0;i<1000;i++) {
      if (fail && i===300) throw Error('catalog failed during second page');
      visits++;
      yield {kind:'child' as const,id:String(i),parentId:'root'};
    }
  }
  const first=await pages.read('root',undefined,undefined,()=>catalog(true));
  await expect(pages.read('root',first.next,undefined,()=>catalog())).rejects.toThrow('second page');
  await expect(pages.read('root',first.next,undefined,()=>catalog())).rejects.toThrow('position changed');
  visits=0;
  const start=await pages.read('root',undefined,undefined,()=>catalog());
  await expect(pages.read('root',first.next,undefined,()=>catalog())).rejects.toThrow('position changed');
  await expect(pages.read('root',start.next,1,()=>catalog())).rejects.toThrow('position changed');
  const next=await pages.read('root',start.next,undefined,()=>catalog());
  const beforeReplay=visits;
  await expect(pages.read('root',start.next,undefined,()=>catalog())).resolves.toEqual(next);
  expect(visits).toBe(beforeReplay);
  const result=[...start.children,...next.children];
  let cursor=next.next;
  while (cursor) {
    const page=await pages.read('root',cursor,undefined,()=>catalog());
    result.push(...page.children);
    cursor=page.next;
  }
  expect(result.map(child=>child.id)).toEqual(Array.from({length:1000},(_,i)=>String(i)));
  expect(visits).toBe(1000);
});
