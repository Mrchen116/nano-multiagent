import {afterEach, expect, it, vi} from 'vitest';
import {CatalogReads} from '../src/catalog-reads.js';

afterEach(() => vi.useRealTimers());
const scope = {owner_id:'owner',node_id:'node',agent_id:'agent',node_epoch:1,workspace_root:'/workspace',profile_version:1,connection:{}};
function deferred<T>() { let resolve!: (value:T)=>void; const promise=new Promise<T>(r=>{resolve=r;}); return {promise,resolve}; }

it('shares refreshes, preserves capture time on hits and refreshes expired data', async()=>{
  vi.useFakeTimers();
  const reads=new CatalogReads(), pending=deferred<any>();
  const load=vi.fn(()=>pending.promise);
  const first=reads.read(scope,load), second=reads.read(scope,load);
  pending.resolve({models:[],skills:[],tools:[]});
  const [a,b]=await Promise.all([first,second]); expect(a).toBe(b); expect(load).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(299999);
  expect((await reads.read(scope,load)).captured_at).toBe(a.captured_at);
  await vi.advanceTimersByTimeAsync(1);
  expect((await reads.read(scope,load)).captured_at).not.toBe(a.captured_at); expect(load).toHaveBeenCalledTimes(2);
});

it('invalidation rejects old waiters and fences previously delivered results even if a loader ignores abort',async()=>{
  const reads=new CatalogReads(), pending=deferred<any>(); let signal!:AbortSignal;
  const old=reads.read(scope,s=>{signal=s;return pending.promise;});
  const rejected=expect(old).rejects.toMatchObject({statusCode:503});
  reads.invalidateNode('node'); expect(signal.aborted).toBe(true); await rejected;
  const fresh=await reads.read(scope,async()=>({models:[],tools:[],skills:[]}));
  pending.resolve({models:[{name:'obsolete'}],tools:[],skills:[]});
  expect((await reads.read(scope,async()=>{throw new Error('unexpected');})).capabilities).toEqual(fresh.capabilities);
  reads.invalidateNode('node'); expect(fresh.current()).toBe(false);
});

it('bounds hung loaders, applies failure cooldown and recovers after it',async()=>{
  vi.useFakeTimers(); const reads=new CatalogReads();
  const load=vi.fn(()=>new Promise<any>(()=>{}));
  const failed=expect(reads.read(scope,load)).rejects.toMatchObject({statusCode:504});
  await vi.advanceTimersByTimeAsync(9000); await failed;
  await expect(reads.read(scope,load)).rejects.toMatchObject({statusCode:504}); expect(load).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1000);
  expect((await reads.read(scope,async()=>({models:[],skills:[],tools:[]}))).current()).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});

it('fences identity changes and bounds completed slots without evicting active refreshes',async()=>{
  const reads=new CatalogReads(); const load=async()=>({models:[],skills:[],tools:[]});
  const old=await reads.read(scope,load);
  await reads.read({...scope,connection:{}},load); expect(old.current()).toBe(false);
  const initial=await reads.read(scope,load);
  for(let i=0;i<256;i++)await reads.read({...scope,agent_id:`other-${i}`},load);
  expect(initial.current()).toBe(false);
});

it('rejects excess active scopes and releases every invalidated refresh without waiting for loaders',async()=>{
  const reads=new CatalogReads(),load=()=>new Promise<any>(()=>{});
  const waits=Array.from({length:256},(_,i)=>reads.read({...scope,agent_id:`agent-${i}`},load));
  const done=Promise.allSettled(waits);
  await expect(reads.read({...scope,agent_id:'excess'},load)).rejects.toMatchObject({statusCode:503});
  reads.invalidateNode('node');
  expect((await done).every(result=>result.status==='rejected')).toBe(true);
  expect((await reads.read(scope,async()=>({models:[]}))).current()).toBe(true);
});

it.each(['owner_id','node_id','agent_id','node_epoch','workspace_root','profile_version','connection'] as const)('does not reuse candidates after %s changes',async field=>{
  const reads=new CatalogReads(),load=vi.fn(async()=>({models:[]}));
  await reads.read(scope,load);
  await reads.read({...scope,[field]:field==='connection'?{}:typeof scope[field]==='number'?2:'other'},load);
  expect(load).toHaveBeenCalledTimes(2);
});
