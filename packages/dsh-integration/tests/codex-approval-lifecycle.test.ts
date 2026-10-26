import { Context } from '@deepseek-ai/cordis';
import { expect, it, vi } from 'vitest';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { ReviewRecovery } from '../src/policy/recovery.js';
import { CodexApproval } from '../src/policy/codex.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import type { ApprovalReviewRequest } from '../src/policy/types.js';

function deferred<T=void>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>resolve=done);return{promise,resolve};}
function harness(run:(turn:{events:any[];input:string;cancelled:Promise<void>})=>Promise<void>,reasoning?:any,lifecycle?:{created?:()=>Promise<void>;disposing?:()=>Promise<void>}){
  const ctx=new Context();const disposed:string[]=[];const inputs:string[]=[];const optionsSeen:any[]=[];let rows:any[]=[{user:'original permission',origin:{kind:'human'}}];
  ctx.provide('llm',{resolveModelInfo:async()=>({context:{contextWindow:100000},reasoning})} as any);
  ctx.provide('tools',{schemas:()=>[{name:'edit',parameters:{type:'object'}}]} as any);
  ctx.provide('agents',{create:async(options:any)=>{
    optionsSeen.push(options);const events:any[]=[...(options.seed??[])];const cancelled=deferred();let pending=Promise.resolve();
    const agent={id:options.sessionId,session:{snapshotEvents:()=>events,deriveMessages:()=>events.filter(e=>e.type==='user/message').map(e=>e.data)},
      followup(message:any){inputs.push(message.content[0].text);events.push({type:'user/message',seq:events.length,data:message});pending=run({events,input:message.content[0].text,cancelled:cancelled.promise});},
      whenIdle:()=>pending,cancel:()=>cancelled.resolve()};
    await lifecycle?.created?.();
    return{agent,dispose:async()=>{await lifecycle?.disposing?.();cancelled.resolve();await pending.catch(()=>undefined);await Promise.resolve();disposed.push(agent.id);}};
  }} as any);
  const plugin=new CodexApproval(ctx);
  const controller=new AbortController();
  const request={exec:{agent:{id:'parent',session:{header:{cwd:'/tmp'},requestHeader:()=>undefined}},callId:'pending',name:'edit',arguments:{path:'a',text:'complete'},signal:controller.signal},config:{agentId:'a',revision:'1',approval:{...approvalDefaults,rules:'codex'}},reviewer:{provider:'fixture',model:'fixture'},sources:{history:async()=>rows,restoreEntries:(r:any)=>r},inherited:[]} as unknown as ApprovalReviewRequest;
  return{plugin,request,controller,disposed,inputs,optionsSeen,setRows:(next:any[])=>rows=next,close:()=>ctx.fiber.dispose()};
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

it('keeps context rebuilding inside one full judgment budget and suppresses late grants after parent cancellation',async()=>{
  vi.useFakeTimers();
  const retry=deferred();let calls=0;
  const h=harness(async({events,cancelled})=>{if(++calls===1){events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'error',error:{code:'CONTEXT_WINDOW_EXCEEDED'}}}});return;}retry.resolve();await cancelled;verdict(events);});
  try{
    const review=h.plugin.review(h.request);const rejected=expect(review).rejects.toThrow();
    await retry.promise;
    await vi.advanceTimersByTimeAsync(89_999);
    expect(calls).toBe(2);
    h.controller.abort(new Error('parent cancelled'));
    await rejected;expect(h.disposed).toHaveLength(2);
  }finally{vi.useRealTimers();await h.close();}
});


it('keeps PA disclosure checkpoints separate, appends deltas and discards old context after rollover',async()=>{
  const h=harness(async({events,input})=>{
    if(!input.includes('"payload"'))return verdict(events);
    events.push({type:'assistant/message',seq:events.length,data:{message:{content:[{type:'text',text:'{"decision":"allow","reason":"Original owner authorized this exact public reply"}'}]}}});
    events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'completed'}}});
  });
  let evidence:any[]=[{user:'ORIGINAL_OWNER_AUTHORIZATION',origin:{kind:'human'}}];
  const request={agent:h.request.exec.agent!,config:h.request.config,action:{payload:{content:'Public reply'},recipient_ids:['peer']},evidence:async()=>evidence};
  try{
    const tool=await h.plugin.review(h.request);
    const first=await h.plugin.reviewDisclosure(request);
    expect(first.decision).toBe('allow');expect(first.metadata?.contextMode).toBe('full');
    expect(first.metadata?.sessionId).not.toBe(tool.metadata?.sessionId);
    evidence.push({tool_result:'ACTUAL_SENT_RECEIPT'});
    const delta=await h.plugin.reviewDisclosure(request);
    expect(delta.metadata?.sessionId).toBe(first.metadata?.sessionId);expect(delta.metadata?.contextMode).toBe('delta');
    expect(h.inputs.at(-1)).toContain('ACTUAL_SENT_RECEIPT');expect(h.inputs.at(-1)).not.toContain('ORIGINAL_OWNER_AUTHORIZATION');
    evidence=[{context:'New window summary: not authorization',origin:{kind:'runtime-context'}}];
    const reset=await h.plugin.reviewDisclosure(request);
    expect(reset.metadata?.sessionId).not.toBe(first.metadata?.sessionId);expect(h.inputs.at(-1)).not.toContain('ORIGINAL_OWNER_AUTHORIZATION');
    await h.plugin.release('parent');
    expect(h.disposed).toEqual(expect.arrayContaining([tool.metadata!.sessionId,first.metadata!.sessionId,reset.metadata!.sessionId]));
  }finally{await h.close();}
});

it.each([
  [{efforts:[{id:'high'},{id:'max'}],defaultEffort:'high'},'high'],
  [{efforts:[{id:'low'},{id:'high'}],defaultEffort:'high'},'low'],
  [undefined,undefined],
])('uses only supported effort for the unchanged configured reviewer: %j',async(reasoning,expected)=>{
  const h=harness(async({events})=>verdict(events),reasoning);
  try{
    const result=await h.plugin.review(h.request);
    expect(result.decision.behavior).toBe('allow');
    expect(h.optionsSeen[0].agentOptions).toMatchObject({provider:'fixture',model:'fixture'});
    if(expected)expect(h.optionsSeen[0].agentOptions.reasoningEffort).toBe(expected);
    else expect(h.optionsSeen[0].agentOptions).not.toHaveProperty('reasoningEffort');
    expect(h.inputs[0]).toContain('original permission');
  }finally{await h.close();}
});

it('quarantines late creation until the aborted handle is disposed without running a turn',async()=>{
  vi.useFakeTimers();const creation=deferred();let creates=0;
  const h=harness(async({events})=>verdict(events),undefined,{created:async()=>{if(++creates===1)await creation.promise;}});
  try{
    const first=h.plugin.review(h.request).catch(error=>error.category);
    await vi.advanceTimersByTimeAsync(95_000);
    expect(await first).toBe('cleanup_unavailable');expect(h.inputs).toHaveLength(0);
    await expect(h.plugin.review(h.request)).rejects.toMatchObject({category:'cleanup_unavailable'});
    expect(creates).toBe(1);
    creation.resolve();await vi.advanceTimersByTimeAsync(0);
    expect(h.disposed).toHaveLength(1);expect(h.inputs).toHaveLength(0);
    expect((await h.plugin.review(h.request)).decision.behavior).toBe('allow');
    expect(creates).toBe(2);expect(h.inputs).toHaveLength(1);
  }finally{creation.resolve();vi.useRealTimers();await h.close();}
});

it('blocks successor attempts and cache reuse while failed-review disposal remains quarantined',async()=>{
  vi.useFakeTimers();const disposal=deferred();let calls=0;
  const h=harness(async({events})=>{if(++calls===1){events.push({type:'assistant/message',seq:events.length,data:{message:{content:[{type:'text',text:'invalid verdict'}]}}});events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'completed'}}});}else verdict(events);},undefined,{disposing:()=>disposal.promise});
  try{
    const first=h.plugin.review(h.request).catch(error=>error.category);
    await vi.advanceTimersByTimeAsync(5000);
    expect(await first).toBe('cleanup_unavailable');expect(calls).toBe(1);
    await expect(h.plugin.review(h.request)).rejects.toMatchObject({category:'cleanup_unavailable'});
    expect(h.optionsSeen).toHaveLength(1);
    disposal.resolve();await vi.advanceTimersByTimeAsync(0);
    expect(h.disposed).toHaveLength(1);
    const next=await h.plugin.review(h.request);
    expect(next.decision.behavior).toBe('allow');expect(next.metadata?.contextMode).toBe('full');
  }finally{disposal.resolve();vi.useRealTimers();await h.close();}
});

it.each([false,true])('shares one context rebuild across technical retries, repeated overflow=%s',async(repeatedOverflow)=>{
  vi.useFakeTimers();let calls=0;
  const h=harness(async({events})=>{
    calls++;
    if(calls===1||repeatedOverflow&&calls===3){events.push({type:'turn/end',seq:events.length,data:{reason:{kind:'error',error:{code:'CONTEXT_WINDOW_EXCEEDED'}}}});return;}
    if(calls===2||calls===3)throw new LlmError('temporary service failure','SERVER',{status:503});
    verdict(events);
  });
  const recovery=new ReviewRecovery(h.controller.signal,'pending',()=>0.5);h.request.recovery=recovery;
  try{
    const result=h.plugin.review(h.request).then(value=>value,error=>error);
    await vi.advanceTimersByTimeAsync(1500);
    const actual=await result;
    if(repeatedOverflow){expect(actual).toBeInstanceOf(Error);expect(calls).toBe(3);}
    else{expect(actual.decision.behavior).toBe('allow');expect(calls).toBe(4);}
    const trace=recovery.finish(repeatedOverflow?'unavailable_unknown':'allow',repeatedOverflow?'return_to_agent':'allow');
    expect(trace.contextRebuilds).toBe(1);expect(trace.retriesUsed).toBe(repeatedOverflow?1:2);
    expect(trace.attempts).toHaveLength(repeatedOverflow?2:3);
    expect(trace.attempts.every(row=>row.budgetMs===90_000)).toBe(true);
    expect(h.optionsSeen).toHaveLength(calls);expect(new Set(h.optionsSeen.map(row=>row.sessionId)).size).toBe(calls);
    expect(h.inputs.every(input=>input.includes('original permission'))).toBe(true);
  }finally{recovery.finish('test_cleanup','internal');vi.useRealTimers();await h.close();}
});

it('freezes the exact action before asynchronous evidence preparation',async()=>{
  const evidence=deferred<any[]>();const h=harness(async({events})=>verdict(events));
  (h.request.sources as any).history=()=>evidence.promise;
  try{
    const pending=h.plugin.review(h.request);
    (h.request.exec.arguments as any).text='mutated after acceptance';
    evidence.resolve([{user:'original permission'}]);
    expect((await pending).decision.behavior).toBe('allow');
    expect(h.inputs[0]).toContain('complete');expect(h.inputs[0]).not.toContain('mutated after acceptance');
  }finally{evidence.resolve([]);await h.close();}
});
