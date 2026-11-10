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
    agents:{get:()=>undefined},
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
  const cold=()=>{throw Error('fixture only has cold sessions');};
  await expect(restarted.eventPage(SessionId('other-root'),child,98,false,cold,cold)).rejects.toThrow('trusted Work lineage');
  const project=(afterSeq:number)=>restarted.eventPage(root,child,afterSeq,false,cold,cut=>workPage({
    afterSeq,firstOwn:cut.inheritedEventCount,head:cut.cursor,eventAt:seq=>cut.events[seq],
    present:async event=>event,model:()=>undefined,modelVersion:'none',
  }));
  const tail=await project(98);
  expect(tail).toMatchObject({throughSeq:99,more:false,events:[event(99)]});
  expect(reads).toEqual([child]);
  expect(await project(99)).toBeUndefined();
  expect(reads).toEqual([child]);
  records.set(child,{...records.get(child),revision:'c2',sizeBytes:201,cursor:100,children:[entry(grandchild)],events:[...records.get(child).events,event(100)]});
  expect(await catalog(restarted)).toMatchObject([{id:child,throughSeq:100},{id:grandchild,kind:'diagnostic',reason:'unavailable'}]);
  expect(await project(99)).toMatchObject({throughSeq:100,events:[event(100)]});

  const current=records.get(child);
  records.set(child,{...current,revision:'c3',sizeBytes:202,events:[...current.events.slice(0,-1),
    {seq:100,type:'turn/end',data:{turn:1,reason:{kind:'interrupted'}}}]});
  expect(await restarted.interruptedChildren(root)).toEqual([{id:child,turnEnd:100}]);
  const saved=stored.get(Buffer.from(child).toString('base64url')) as {interruptedTurnEnd?:number};
  delete saved.interruptedTurnEnd; // An older catalog has a durable cut but no interruption witness.
  reads.length=0;
  const recovered=new DescendantReader(context());
  await recovered.ready;
  expect(await recovered.interruptedChildren(root)).toEqual([{id:child,turnEnd:100}]);
  expect(await recovered.interruptedChildren(root)).toEqual([{id:child,turnEnd:100}]);
  expect(reads).toEqual([child]);
});

it.each([1000,10_000])('reads only the hot child with %i old siblings and requires its parent catalog flush', async count => {
  const root=SessionId('root'), child=SessionId('changed');
  const histories=Array.from({length:count},(_,i)=>({id:SessionId(`old-${i}`),createdAt:1,mode:'one-shot'}));
  const storage=[
    [Buffer.from(root).toString('base64url'),{rootId:root,active:false,cursor:0,children:histories}],
    [Buffer.from(child).toString('base64url'),{rootId:root,active:false,cursor:0,
      children:histories.map(entry=>({...entry,id:SessionId('grand-'+entry.id)}))}],
  ];
  const parent={id:root,seq:4,isOwnSeq:()=>true};
  const target={id:child,seq:8};
  const lookups:string[]=[];
  const writes:string[]=[];
  let durable=false;
  const reader=new DescendantReader({
    effect:()=>{}, storageDomain:{open:async()=>({table:()=>({entries:()=>storage,put:async(id:string)=>writes.push(id)})})},
    sessions:{get:(id:string)=>{lookups.push(id);return id===root ? parent : id===child ? target : undefined;},
      flush:async(session:{id:string})=>session.id===root ? durable : true},
    sessionQuery:{observeSession:()=>{throw Error('hot read materialized history');}},
  } as unknown as Context);
  await reader.ready;
  reader.remember(parent as never,{type:'subagent/catalog',seq:3,time:1,data:{version:0,mode:'one-shot',childId:child,childCreatedAt:1}} as never,root);
  await expect(reader.targets(root,child)).rejects.toThrow('Parent catalog has no persistence barrier');
  durable=true;
  expect(await reader.targets(root,child)).toMatchObject([{id:child,parentId:root,throughSeq:7}]);
  const response={durable:true,events:[],modelRuns:[],modelVersion:'none',throughSeq:7,more:false} as const;
  await expect(reader.eventPage(root,child,4,false,async()=>({...response,events:[],modelRuns:[]}),async()=>{throw Error('cold read');})).resolves.toMatchObject({throughSeq:7});
  expect(lookups).toEqual([root,root,child,child]);
  expect(writes).toEqual([]);
});

it('does not accept an unflushed live cut acquired during a cold read', async () => {
  const root=SessionId('root'), child=SessionId('child'), reads: unknown[]=[];
  let attached=false, flushed=false;
  const reader=new DescendantReader({
    effect:()=>{},storageDomain:{open:async()=>({table:()=>({entries:()=>[[Buffer.from(root).toString('base64url'),
      {rootId:root,active:false,cursor:0,children:[{id:child,createdAt:1,mode:'one-shot'}]}]]})})},
    sessions:{get:()=>attached ? {seq:5} : undefined,flush:async()=>flushed},
    sessionQuery:{observeSession:async(_id:string, options:unknown)=>{
      reads.push(options);attached=true;return {source:'live',[Symbol.dispose](){}};
    }},
  } as unknown as Context);
  await reader.ready;
  const read=()=>reader.eventPage(root,child,0,false,async(_session,head)=>({
    durable:true,events:[],modelRuns:[],modelVersion:'none',throughSeq:head,more:false,
  }),async()=>{throw Error('unflushed live cut accepted');});
  await expect(read()).rejects.toThrow('Child Session has no persistence barrier');
  flushed=true;
  await expect(read()).resolves.toMatchObject({throughSeq:4});
  expect(reads).toEqual([{projectionMode:'none'}]);
});
