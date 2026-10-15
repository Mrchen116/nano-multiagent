import { Context } from '@deepseek-ai/cordis';
import { expect, it, vi } from 'vitest';
import { CodexApproval } from '../src/policy/codex.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import type { ApprovalReviewRequest } from '../src/policy/types.js';

function deferred<T=void>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>resolve=done);return{promise,resolve};}
function harness(run:(turn:{events:any[];input:string;cancelled:Promise<void>})=>Promise<void>){
  const ctx=new Context();const disposed:string[]=[];const inputs:string[]=[];let rows:any[]=[{user:'original permission',origin:{kind:'human'}}];
  ctx.provide('llm',{resolveModelInfo:async()=>({context:{contextWindow:100000}})} as any);
  ctx.provide('tools',{schemas:()=>[{name:'edit',parameters:{type:'object'}}]} as any);
  ctx.provide('agents',{create:async(options:any)=>{
    const events:any[]=[...(options.seed??[])];const cancelled=deferred();let pending=Promise.resolve();
    const agent={id:options.sessionId,session:{snapshotEvents:()=>events,deriveMessages:()=>events.filter(e=>e.type==='user/message').map(e=>e.data)},
      followup(message:any){inputs.push(message.content[0].text);events.push({type:'user/message',seq:events.length,data:message});pending=run({events,input:message.content[0].text,cancelled:cancelled.promise});},
      whenIdle:()=>pending,cancel:()=>cancelled.resolve()};
    return{agent,dispose:async()=>{cancelled.resolve();await pending;await Promise.resolve();disposed.push(agent.id);}};
  }} as any);
  const plugin=new CodexApproval(ctx);
  const controller=new AbortController();
  const request={exec:{agent:{id:'parent',session:{header:{cwd:'/tmp'}}},callId:'pending',name:'edit',arguments:{path:'a',text:'complete'},signal:controller.signal},config:{agentId:'a',revision:'1',approval:{...approvalDefaults,rules:'codex'}},reviewer:{provider:'fixture',model:'fixture'},sources:{history:async()=>rows,restoreEntries:(r:any)=>r},inherited:[]} as unknown as ApprovalReviewRequest;
  return{plugin,request,controller,disposed,inputs,setRows:(next:any[])=>rows=next,close:()=>ctx.fiber.dispose()};
}
function verdict(events:any[]){events.push({type:'assistant/message',seq:events.length,data:{message:{content:[{type:'text',text:JSON.stringify({outcome:'allow',risk_level:'low',user_authorization:'high',rationale:'authorized'})}]}}});events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'completed'}}});}

it('rebuilds rewritten parent evidence and changed frozen configuration, without retaining old authorization',async()=>{
  const h=harness(async({events})=>verdict(events));
  try{
    const first=await h.plugin.review(h.request);expect(first.metadata?.contextMode).toBe('full');
    h.setRows([{user:'new instruction only',origin:{kind:'human'}}]);
    const changed=await h.plugin.review(h.request);expect(changed.metadata?.sessionId).not.toBe(first.metadata?.sessionId);expect(h.inputs.at(-1)).not.toContain('original permission');
    h.request.config={...h.request.config,revision:'2'};
    const configured=await h.plugin.review(h.request);expect(configured.metadata?.sessionId).not.toBe(changed.metadata?.sessionId);
    expect(h.disposed).toContain(first.metadata!.sessionId);expect(h.disposed).toContain(changed.metadata!.sessionId);
    await h.plugin.release('parent');expect(h.disposed).toContain(configured.metadata!.sessionId);
    expect((await h.plugin.review(h.request)).metadata?.contextMode).toBe('full');
  }finally{await h.close();}
});

it('replays full parent evidence after native overflow, and commits only the successful retry',async()=>{
  let calls=0;const h=harness(async({events})=>{if(++calls===2)events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'error',error:{code:'CONTEXT_WINDOW_EXCEEDED'}}}});else verdict(events);});
  try{
    await h.plugin.review(h.request);
    h.setRows([{user:'original permission',origin:{kind:'human'}},{tool_result:'new evidence'}]);
    const result=await h.plugin.review(h.request);expect(result.metadata?.contextMode).toBe('rebuild');
    expect(h.inputs[1]).not.toContain('original permission');expect(h.inputs[2]).toContain('original permission');expect(h.inputs[2]).toContain('new evidence');
    expect((await h.plugin.review(h.request)).metadata?.sessionId).toBe(result.metadata?.sessionId);
  }finally{await h.close();}
});

it.each(['parent','deadline'] as const)('suppresses late grants on %s cancellation and drains the retry under the original deadline',async(kind)=>{
  const deadline=new AbortController();const timeout=vi.spyOn(AbortSignal,'timeout').mockReturnValue(deadline.signal);
  const retry=deferred();let calls=0;
  const h=harness(async({events,cancelled})=>{if(++calls===1){events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'error',error:{code:'CONTEXT_WINDOW_EXCEEDED'}}}});return;}retry.resolve();await cancelled;verdict(events);});
  try{
    const review=h.plugin.review(h.request);const rejected=expect(review).rejects.toThrow();
    await retry.promise;
    if(kind==='parent')h.controller.abort(new Error('parent cancelled'));else deadline.abort(new Error('deadline exceeded'));
    await rejected;
    expect(timeout.mock.calls).toEqual([[90000]]);expect(h.disposed).toHaveLength(2);
  }finally{timeout.mockRestore();await h.close();}
});
