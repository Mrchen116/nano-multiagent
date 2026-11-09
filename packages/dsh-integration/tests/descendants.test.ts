import { expect, it } from 'vitest';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId } from '@deepseek-ai/dsh-session';
import { DescendantReader } from '../src/descendants.js';
import { workPage } from '../src/work-page.js';

it('restores cold catalog cuts and only reads changed child bodies for their trusted root', async () => {
  const root=SessionId('root'), child=SessionId('child'), grandchild=SessionId('grandchild');
  const entry=(id:string)=>({id,createdAt:1,mode:'one-shot'});
  const event=(seq:number)=>({seq,time:seq,type:'step/start',data:{turn:1}});
  const stored=new Map<string, unknown>();
  const records=new Map<string, any>([
    [root,{revision:'r1',sizeBytes:100,cursor:0,children:[entry(child)],events:[event(0)]}],
    [child,{revision:'c1',sizeBytes:200,cursor:99,children:[],events:Array.from({length:100},(_,i)=>event(i))}],
  ]);
  const reads:string[]=[];
  const context=()=>({
    effect:()=>{},
    storageDomain:{open:async()=>({table:()=>({entries:()=>stored.entries(),put:async(id:string,row:unknown)=>stored.set(id,row)}),close:async()=>{}})},
    sessions:{get:()=>undefined},
    sessionPersistence:{identity:Symbol(),stat:async(id:string)=>records.has(id)?{...records.get(id),header:{id,createdAt:1,version:1,isSeeded:false}}:undefined},
    sessionQuery:{observeSession:async(id:string)=>{
      reads.push(id);const row=records.get(id);
      if(!row)throw new Error('missing');
      return {...row,source:'prepared',inheritedEventCount:1,projections:{values:{subagentCatalog:row.children,inbox:{'next-turn':[],'next-step':[]}}},[Symbol.dispose](){}};
    }},
  } as unknown as Context);
  async function catalog(reader:DescendantReader) {
    const result=[];
    for await(const row of reader.catalog(root))result.push(row);
    return result;
  }
  const first=new DescendantReader(context());
  expect(await catalog(first)).toMatchObject([{id:child,throughSeq:99}]);
  reads.length=0;
  const restarted=new DescendantReader(context());
  expect(await catalog(restarted)).toMatchObject([{id:child,throughSeq:99}]);
  expect(reads).toEqual([]);
  await expect(restarted.page(SessionId('other-root'),child,98,()=>false,()=>{throw Error('unauthorized read');})).rejects.toThrow('trusted Work lineage');
  const project=(afterSeq:number)=>restarted.page(root,child,afterSeq,()=>false,cut=>workPage({
    afterSeq,firstOwn:cut.inheritedEventCount,head:cut.cursor,eventAt:seq=>cut.events[seq],
    present:async event=>event,model:()=>undefined,modelVersion:'none',
  }));
  const tail=await project(98);
  expect(tail).toMatchObject({throughSeq:99,more:false,events:[event(99)]});
  expect(reads).toEqual([child]);
  expect(await project(99)).toBeUndefined();
  records.set(child,{...records.get(child),revision:'c2',sizeBytes:201,cursor:100,children:[entry(grandchild)],events:[...records.get(child).events,event(100)]});
  expect(await catalog(restarted)).toMatchObject([{id:child,throughSeq:100},{id:grandchild,kind:'diagnostic',reason:'unavailable'}]);
  expect(await project(99)).toMatchObject({throughSeq:100,events:[event(100)]});
});
