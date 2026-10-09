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
