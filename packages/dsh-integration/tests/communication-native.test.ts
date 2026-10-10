import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('routes single-thread public send fields through the product bridge', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-communication-'));
  let client: RuntimeClient | undefined;
  try {
    await writeFile(join(home, 'fixture.mjs'), `export const name='send-fixture';export const inject=['llm'];export function apply(ctx){let sent=false;ctx.on('llm/stream',async function*(){if(!sent){sent=true;yield {type:'block-end',index:0,block:{type:'tool-call',id:'public-send',name:'send_message',arguments:JSON.stringify({target:'current',text:'public reply'})}};yield {type:'finish',reason:{kind:'tool-calls'}};}else{yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};}});}`);
    await prepareProfile(home, [{insert:[{id:'send-fixture',name:join(home,'fixture.mjs')}]}]);
    client = new RuntimeClient({home,cwd:home});
    const calls: any[] = [];
    client.rpc.handle('product.call', value => {calls.push(value);return {status:'sent',message_id:'public-message'};});
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',mode:'single_thread',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['send_message'],approval:{dangerouslySkipPermissions:true}}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'chat',agentId:'a',revision:'1',ownerId:'owner',cwd:home});
    await client.rpc.request('session.submit',{sessionId:'chat',inputId:'human',mode:'followup',content:[{type:'text',text:'send the public reply'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'human'}});
    await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'chat',inputId:'human'}) as any).terminal).toBeTruthy();
    expect(calls).toContainEqual(expect.objectContaining({method:'send_message',args:{target:'current',text:'public reply'},rootSessionId:'chat',agentId:'a'}));
    await client.shutdown();client=undefined;
  }finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},15000);

it('finishes global turns silently after delivery or no-op, while preserving other failures and single-thread errors', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-silent-completion-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), `export const name='empty-fixture';export const inject=['llm'];export function apply(ctx){
      const sent=new Set();ctx.on('llm/stream',async function*(o){
        if(o.sessionId==='sent'&&!sent.has(o.sessionId)){sent.add(o.sessionId);yield{type:'block-end',index:0,block:{type:'tool-call',id:'public-send',name:'send_message',arguments:JSON.stringify({target:'chat',text:'Delivered once'})}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
        yield{type:'usage',usage:{inputTokens:10,outputTokens:0,totalTokens:10}};
        yield{type:'finish',reason:{kind:'error',failure:{code:o.sessionId==='failure'?'AUTH':'EMPTY_RESPONSE',message:'fixture terminal response'}}};
      });}`);
    await prepareProfile(home, [{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'fixture',contextWindow:100000}],retryPolicy:{mode:'normal',maxRetries:0}}}}},{insert:[{id:'empty-fixture',name:join(home,'fixture.mjs')}]}]);
    client = new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    const calls: any[] = [];
    client.rpc.handle('product.call', value => {calls.push(value);return {status:'sent',message_id:'delivered'};});
    client.rpc.handle('model.check', () => ({published:false}));
    await client.rpc.request('initialize',{protocol:1,agents:['global','single_thread'].map(mode=>({agentId:mode,revision:'1',mode,provider:'fixture',model:'fixture',toolAllowlist:['send_message'],approval:{dangerouslySkipPermissions:true}})),bindings:[]});
    for(const [sessionId,mode,expected] of [['sent','global','completed'],['noop','global','completed'],['failure','global','error'],['single','single_thread','error']]){
      await client.rpc.request('session.ensure',{sessionId,agentId:mode,revision:'1',ownerId:'owner',cwd:home});
      await client.rpc.request('session.submit',{sessionId,inputId:sessionId,mode:'followup',content:[{type:'text',text:'Handle this turn'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:sessionId}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId,inputId:sessionId}) as any).terminal).toMatchObject({kind:expected});
      const events=(await client.rpc.request('session.observe',{sessionId}) as any).events;
      expect(events.filter((e:any)=>e.type==='llm/retry')).toHaveLength(0);
      if(expected==='completed') {
        expect(events.filter((e:any)=>e.type==='assistant/message').flatMap((e:any)=>e.data.message.content).filter((b:any)=>b.type==='text')).toEqual([]);
      }
    }
    expect(calls.filter(call=>call.method==='send_message')).toHaveLength(1);
    await client.shutdown();client=undefined;
  }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},15000);
