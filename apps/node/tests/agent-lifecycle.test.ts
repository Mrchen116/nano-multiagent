import {expect,it} from 'vitest';
import type {AgentLifecycleSnapshot,AgentLifecycleReport} from '@nano/product-contracts';
import {NodeAgentLifecycle} from '../src/agent-lifecycle.js';
const initial=(agent_id='a'):AgentLifecycleSnapshot=>({agent_id,desired:'enabled',revision:1,disabled_through_revision:0,request_id:null,actor_user_id:null,requested_at:'2026-10-25',applied_revision:0,observed:'enabling',process_instance_id:null,confirmed_at:null,error_code:null,error_detail:null});
function fixture() {
  const states=new Map<string,AgentLifecycleSnapshot>(),proofs=new Map<string,{boot:string;processInstanceId:string|null;stopped:boolean}>(),reports:AgentLifecycleReport[]=[],started:string[]=[],cancelled:string[]=[];
  let stopped:{confirmed:boolean;processInstanceId?:string}={confirmed:true};
  const lifecycle=new NodeAgentLifecycle({nodeId:'node',boot:'boot-one',snapshot:id=>states.get(id),save:s=>states.set(s.agent_id,s),proof:id=>proofs.get(id),saveProof:(id,p)=>proofs.set(id,p),
    host:()=>({available:false,disable:async()=>stopped}),start:async id=>{started.push(id);},cancel:id=>{cancelled.push(id);},resetHeartbeat:()=>{},report:async r=>{reports.push(r);}});
  return {lifecycle,states,proofs,reports,started,cancelled,setStop:(result:typeof stopped)=>{stopped=result;}};
}
it('waits for the authoritative snapshot and closes admission synchronously on disable',async()=>{
  const f=fixture();f.states.set('a',initial());expect(f.lifecycle.allowed('a')).toBe(false);
  await f.lifecycle.synchronize([initial(),{...initial('b'),desired:'disabled',revision:2,observed:'stopping'}]);
  expect(f.started).toEqual(['a']);expect(f.lifecycle.allowed('a')).toBe(true);expect(f.lifecycle.allowed('b')).toBe(false);
  f.setStop({confirmed:true,processInstanceId:'a-process'});
  const stop=f.lifecycle.apply({...initial(),desired:'disabled',revision:2,disabled_through_revision:2,observed:'stopping',process_instance_id:'a-process'});
  expect(f.lifecycle.allowed('a')).toBe(false);expect(f.cancelled).toContain('a');await stop;
  expect(f.reports.at(-1)).toMatchObject({revision:2,observed:'disabled',process_instance_id:'a-process'});
});
it('retains unknown cleanup across Node restart and retry until machine reboot supplies proof',async()=>{
  const f=fixture(),disabled={...initial(),desired:'disabled' as const,revision:2,disabled_through_revision:2,observed:'stop_unconfirmed' as const,process_instance_id:'lost'};
  f.proofs.set('a',{boot:'boot-one',processInstanceId:'lost',stopped:false});
  await f.lifecycle.synchronize([disabled]);expect(f.reports.at(-1)?.observed).toBe('stop_unconfirmed');
  f.lifecycle.recordStopped('a');expect(f.proofs.get('a')?.stopped).toBe(false);
  await f.lifecycle.apply(disabled);expect(f.reports.at(-1)?.observed).toBe('stop_unconfirmed');
  f.proofs.set('a',{boot:'previous-boot',processInstanceId:'lost',stopped:false});
  await f.lifecycle.apply(disabled);expect(f.reports.at(-1)?.observed).toBe('disabled');
});
it('never lets delayed disabled intent override a newer enabled generation',async()=>{
  const f=fixture();f.states.set('a',{...initial(),revision:3,disabled_through_revision:2});await f.lifecycle.synchronize([{...initial(),revision:3,disabled_through_revision:2}]);
  await f.lifecycle.apply({...initial(),desired:'disabled',revision:2});expect(f.cancelled).toEqual([]);expect(f.lifecycle.allowed('a')).toBe(true);
});

it.each([true,false])('reports the prior execution identity after a host restart (prior cleanup confirmed=%s)',async priorStopped=>{
  const f=fixture();
  const disabled={...initial(),desired:'disabled' as const,revision:2,disabled_through_revision:2,observed:'stopping' as const,process_instance_id:'prior-host'};
  f.proofs.set('a',{boot:'boot-one',processInstanceId:'prior-host',stopped:priorStopped});
  f.setStop({confirmed:true,processInstanceId:'new-shared-host'});
  await f.lifecycle.synchronize([disabled]);
  expect(f.reports.at(-1)).toMatchObject({process_instance_id:'prior-host',observed:priorStopped?'disabled':'stop_unconfirmed'});
  expect(f.lifecycle.allowed('a')).toBe(false);
});

it('resumes cleanup after a durable native purge without rebuilding the plan', async()=>{
  const {AgentDeletionLedger,NodeAgentDeletions}=await import('../src/agent-deletion.js');
  const {mkdtemp,rm}=await import('node:fs/promises');
  const {tmpdir}=await import('node:os');
  const {join}=await import('node:path');
  const dir=await mkdtemp(join(tmpdir(),'nano-node-delete-'));
  const path=join(dir,'deletions.sqlite3'),intent={agent_id:'a',operation_id:'a-operation',revision:2};
  const stages:string[]=[];
  let failFinalize=true;
  const dependencies={
    assertStopped:()=>{stages.push('stop');},
    plan:async()=>{stages.push('plan');return {sessionIds:['session-a']};},
    purge:async()=>{stages.push('purge');},
    finalize:async(_intent:typeof intent,plan:{sessionIds:string[]})=>{
      expect(plan.sessionIds).toEqual(['session-a']);
      if (failFinalize) throw new Error('temporary filesystem failure');
      stages.push('finalize');
    },
    report:async(_intent:typeof intent,state:string)=>{stages.push(state);},
  };
  let agent=new NodeAgentDeletions(new AgentDeletionLedger(path),dependencies);
  try {
    await agent.apply(intent);
    expect(stages).toEqual(['stop','deleting','plan','purge','failed']);
    await agent.close();
    failFinalize=false;
    agent=new NodeAgentDeletions(new AgentDeletionLedger(path),dependencies);
    await agent.apply(intent);
    await agent.apply(intent);
    expect(stages).toEqual(['stop','deleting','plan','purge','failed','deleting','finalize','deleted','deleted']);
  } finally { await agent.close(); await rm(dir,{recursive:true,force:true}); }
});
