import {expect,it} from 'vitest';
import {TRAJECTORY_MAX_BYTES,encodeTrajectoryValue} from '@nano/product-contracts';
import {NativeTrajectory} from '../src/trajectory.js';

it.each([false,true])('keeps ready unfragmented and preserves large catalogs through normal reads, large=%s',async large=>{
  const padding='x'.repeat(large?TRAJECTORY_MAX_BYTES+4096:1024);
  const cut={header:{id:'root',createdAt:1,cwd:'/test'},cursor:1,projections:{values:{padding}},[Symbol.dispose](){}};
  const ctx={sessionQuery:{observeSession:async()=>cut},agents:{get:()=>undefined}};
  const native=new NativeTrajectory(ctx as never,{controller:Promise.resolve({}) as never,
    bindings:new Map([['root',{agentId:'agent',ownerId:'owner',revision:'1'} as never]]),
    configurations:new Map([['nano:agent:1',{mode:'global'} as never]])});
  try{
    const prepared=await native.prepare({observerId:'reader',rootAgentId:'agent',rootSessionId:'root',sessionId:'root',ownerId:'owner',nodeId:'node',nodeEpoch:1});
    expect(Boolean(prepared.initialCatalog)).toBe(!large);
    expect([...encodeTrajectoryValue({type:'ready',observerId:'reader',...prepared})]).toHaveLength(1);
    const fresh=await native.call({observerId:'reader',method:'session/list'}) as any;
    expect(fresh.value.items[0].projections.values.padding).toHaveLength(padding.length);
    if(!large)expect(prepared.initialCatalog!.result).toEqual(fresh);
  }finally{native.dispose();}
});
