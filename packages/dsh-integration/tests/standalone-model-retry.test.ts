import { Context } from '@deepseek-ai/cordis';
import { BlockAssembler, LlmAdapter, LlmRuntime, markAgentLoopRequest, resolveRetryPolicy, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm';
import { expect, it } from 'vitest';
import { installStandaloneModelRetry, withStandaloneRetry } from '../src/standalone-model-retry.js';

const policy = resolveRetryPolicy({mode:'normal',maxRetries:2,backoff:{initialDelayMs:1,maxDelayMs:1,jitterRatio:0}},'test');
const request = (): GenerateOptions => ({provider:'fixture',model:'test',system:'frozen instructions',messages:[{role:'user',content:[{type:'text',text:'frozen input'}]}]});
const text = (value:string): StreamChunk => ({type:'block-end',index:0,block:{type:'text',text:value}});
const fail: StreamChunk = {type:'finish',reason:{kind:'error',failure:{code:'SERVER',message:'transient',status:503}}};
const stop: StreamChunk = {type:'finish',reason:{kind:'stop'}};
function fixture(stream:(options:GenerateOptions, attempt:number)=>AsyncIterable<StreamChunk>, retryPolicy=policy, contextWindow=()=>100000) {
  const ctx=new Context(); new LlmRuntime(ctx); const seen:GenerateOptions[]=[];
  class Adapter extends LlmAdapter {
    providerRetryPolicy(){return retryPolicy;}
    async resolveModel(provider:string, model:string){return {...await super.resolveModel(provider,model),context:{contextWindow:contextWindow()}};}
    async *stream(options:GenerateOptions){seen.push(options);yield* stream(options,seen.length);}
  }
  ctx.llm.registerAdapter(['fixture'],new Adapter());
  installStandaloneModelRetry(ctx);
  return {ctx,seen,async run(options=request()){
    const assembly=new BlockAssembler();
    for await(const chunk of ctx.llm.stream(options))assembly.push(chunk);
    return {value:assembly.blocks().filter(b=>b.type==='text').map(b=>b.text).join(''),finish:assembly.finish};
  }};
}

it('retries a failed partial direct request with a fresh attempt and preserves the full request',async()=>{
  const f=fixture(async function*(_options,n){yield text(n===1?'discard partial':'complete');yield n===1?fail:stop;});
  expect(await f.run()).toEqual({value:'complete',finish:{kind:'stop'}});
  expect(f.seen).toHaveLength(2);
  expect(f.seen.map(o=>[o.system,o.messages])).toEqual(Array(2).fill(['frozen instructions',request().messages]));
});

it('leaves marked Loop requests untouched, including streamed partial output',async()=>{
  const f=fixture(async function*(){yield text('partial');yield fail;});
  const options=Object.freeze(markAgentLoopRequest(request()));
  expect(await f.run(options)).toMatchObject({value:'partial',finish:{kind:'error'}});
  expect(f.seen).toHaveLength(1);
});

it('honors provider no-retry and permanent failures',async()=>{
  const noRetry=fixture(async function*(){yield fail;},resolveRetryPolicy({mode:'normal',maxRetries:0},'test'));
  expect((await noRetry.run()).finish.kind).toBe('error');expect(noRetry.seen).toHaveLength(1);
  const permanent=fixture(async function*(){yield {type:'finish',reason:{kind:'error',failure:{code:'AUTH',message:'invalid',status:401}}};});
  expect((await permanent.run()).finish.kind).toBe('error');expect(permanent.seen).toHaveLength(1);
});

it('shares technical and format recovery budget across two review stages without retrying valid deny',async()=>{
  const f=fixture(async function*(_options,n){if(n===1){yield fail;return;}yield text(n===3?'invalid':JSON.stringify({behavior:'deny'}));yield stop;});
  const budget={remaining:2,formatRemaining:1};
  const decode=(value:string)=>{try{return JSON.parse(value);}catch{return undefined;}};
  await withStandaloneRetry({reviewBudget:budget,decodeReview:decode},()=>f.run());
  await withStandaloneRetry({reviewBudget:budget,decodeReview:decode},()=>f.run());
  expect(f.seen).toHaveLength(4);expect(budget).toEqual({remaining:0,formatRemaining:0});
});

it('refreshes each attempt deadline and drains cancellation before another request',async()=>{
  let active=0,maxActive=0;
  const f=fixture(async function*(options,n){active++;maxActive=Math.max(active,maxActive);try{
    if(n===1)await new Promise<void>(resolve=>options.signal!.addEventListener('abort',()=>resolve(),{once:true}));
    else yield text('after timeout');
    yield n===1?{type:'finish',reason:{kind:'aborted',failure:{code:'ABORTED',message:'cancelled'}}}:stop;
  }finally{active--;}});
  expect(await withStandaloneRetry({timeoutMs:10},()=>f.run())).toMatchObject({value:'after timeout'});
  expect(maxActive).toBe(1);expect(f.seen).toHaveLength(2);
  expect(f.seen[1]!.signal!.aborted).toBe(false);
  const parent=new AbortController();
  const cancelled=fixture(async function*(options){await new Promise<void>(resolve=>options.signal!.addEventListener('abort',()=>resolve(),{once:true}));yield {type:'finish',reason:{kind:'aborted',failure:{code:'ABORTED',message:'cancelled'}}};});
  const pending=withStandaloneRetry({timeoutMs:1000},()=>cancelled.run({...request(),signal:parent.signal}));
  setTimeout(()=>parent.abort(new Error('parent cancelled')),5);
  await expect(pending).rejects.toThrow('parent cancelled');expect(cancelled.seen).toHaveLength(1);
});


it('checks the exact retry capability before sending complete review evidence again',async()=>{
  let window=100000;
  const f=fixture(async function*(){window=100;yield fail;},policy,()=>window);
  await expect(withStandaloneRetry({reviewBudget:{remaining:2,formatRemaining:1},decodeReview:JSON.parse},()=>f.run())).rejects.toThrow('Complete review request exceeds current model context window');
  expect(f.seen).toHaveLength(1);
});

it('does not turn a thrown middleware error into a provider retry',async()=>{
  const f=fixture(async function*(){yield stop;});
  f.ctx.on('llm/stream',async function*(){throw new Error('plugin failure');});
  await expect(f.run()).rejects.toThrow('plugin failure');
  expect(f.seen).toHaveLength(0);
});
