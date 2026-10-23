import { expect, it } from 'vitest';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId } from '@deepseek-ai/dsh-session';
import { DescendantReader } from '../src/descendants.js';

it('reads changed cold branches while preserving full own context and retrying unavailable branches', async () => {
  const root = SessionId('root'), child = SessionId('child'), grandchild = SessionId('grandchild');
  const entry = (id: string) => ({id,createdAt:1,mode:'one-shot'});
  const call = {seq:1,type:'tool/call',data:{callId:'call',name:'read'},time:1};
  const result = {seq:2,type:'tool/result',data:{message:{toolCallId:'call'}},time:2};
  const records = new Map<string, any>([
    [root,{revision:'r1',cursor:0,children:[entry(child)],events:[]}],
    [child,{revision:'c1',cursor:1,children:[],events:[{seq:0,type:'inherited'},call]}],
  ]);
  let unavailable = false;
  const bodyReads: string[] = [];
  const ctx = {
    sessions:{get:()=>undefined},
    sessionPersistence:{identity:Symbol(),stat:async(id:string)=>records.get(id)},
    sessionQuery:{observeSession:async(id:string)=>{
      bodyReads.push(id);
      if(id===grandchild && unavailable)throw new Error('temporary source failure');
      const row=records.get(id);
      return {...row,inheritedEventCount:1,projections:{values:{subagentCatalog:row.children}},[Symbol.dispose](){}};
    }},
  } as unknown as Context;
  const reader = new DescendantReader(ctx);
  const cursors: Record<string,number> = {};
  const first = await reader.read(root,cursors);
  expect(first).toMatchObject([{id:child,throughSeq:1,events:[call]}]);
  cursors[child] = 1;
  bodyReads.length = 0;
  expect(await reader.read(root,cursors)).toMatchObject([{id:child,events:[]}]);
  // A cold metadata check must not open unchanged bodies, regardless of native
  // prepared-cache capacity. Root discovery is outside the descendant budget.
  expect(bodyReads.filter(id=>id!==root)).toEqual([]);
  records.set(child,{revision:'c2',cursor:2,children:[entry(grandchild)],events:[{seq:0,type:'inherited'},call,result]});
  records.set(grandchild,{revision:'g1',cursor:0,children:[],events:[]});
  unavailable = true;
  expect(await reader.read(root,cursors)).toMatchObject([
    {id:child,throughSeq:2,events:[call,result]},
    {id:grandchild,kind:'diagnostic',reason:'unavailable'},
  ]);
  cursors[child] = 2;
  unavailable = false;
  expect(await reader.read(root,cursors)).toMatchObject([{id:child,events:[]},{id:grandchild,parentId:child,kind:'child'}]);
  expect(await reader.read(root,cursors,id=>id===child)).toMatchObject([{id:child,events:[call,result]},{id:grandchild}]);
  expect(await new DescendantReader(ctx).read(root)).toMatchObject([{id:child,events:[call,result]},{id:grandchild,parentId:child}]);
});

it('captures projection state after an awaited observation and re-captures on cold replay', async () => {
  let modelVersion = 'old', observedVersion = '', childReads = 0;
  const ctx = {
    sessions:{get:()=>undefined},
    sessionPersistence:{identity:Symbol(),stat:async()=>({revision:'same'})},
    sessionQuery:{observeSession:async(id:string)=>{
      if(id==='child'){
        childReads++;
        await Promise.resolve();
        modelVersion = childReads===1?'initial':'completed';
      }
      return {revision:'same',cursor:2,inheritedEventCount:0,events:[{seq:2,type:'turn/end'}],
        projections:{values:{subagentCatalog:id==='root'?[{id:'child',mode:'one-shot',createdAt:1}]:[]}},[Symbol.dispose](){}};
    }},
  } as unknown as Context;
  const reader = new DescendantReader(ctx);
  const refresh = () => { observedVersion = modelVersion; return modelVersion!=='initial'; };
  await reader.read(SessionId('root'),{},refresh);
  expect(observedVersion).toBe('initial');
  modelVersion = 'switching';
  const changed = await reader.read(SessionId('root'),{child:2},refresh);
  expect(observedVersion).toBe('completed');
  expect(changed).toMatchObject([{id:'child',throughSeq:2,events:[{type:'turn/end'}]}]);
});
