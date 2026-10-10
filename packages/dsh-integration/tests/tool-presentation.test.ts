import {mkdtemp, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect, it} from 'vitest';
import {prepareProfile, RuntimeClient} from '../lib/client.js';

it('preserves native presenter output and actual child identity across configuration withdrawal and restart', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-tool-view-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const binding = {sessionId:'view', agentId:'a', revision:'1', ownerId:'owner', cwd:home};
  let config = {agentId:'a', revision:'1', provider:'deepseek-official', model:'deepseek-flash', toolAllowlist:['read','subagent']};
  try {
    await writeFile(join(home, 'sample.txt'), 'PERSISTED_CONTENT');
    await writeFile(join(home, 'fixture.mjs'), `export const name='presenter-fixture';export const inject=['llm'];export function apply(ctx){
      const seen=new Set();ctx.on('llm/stream',async function*(o){
        const user=o.messages.findLast(m=>m.role==='user'&&m.source?.kind!=='runtime-context');
        const text=user?.content.find(b=>b.type==='text')?.text;
        if(text==='launch'&&!seen.has(user.id)){seen.add(user.id);
          yield{type:'block-end',index:0,block:{type:'tool-call',id:'read-call',name:'read',arguments:JSON.stringify({file_path:${JSON.stringify(join(home,'sample.txt'))}})}};
          yield{type:'block-end',index:1,block:{type:'tool-call',id:'child-call',name:'subagent',arguments:JSON.stringify({prompt:'Return CHILD_VIEW',description:'View child',run_in_background:false})}};
          yield{type:'finish',reason:{kind:'tool-calls'}};return;}
        yield{type:'block-end',index:0,block:{type:'text',text:'CHILD_VIEW'}};yield{type:'finish',reason:{kind:'stop'}};
      });}`);
    await prepareProfile(home,[{insert:[{id:'presenter-fixture',name:join(home,'fixture.mjs')}]}]);
    const start=async()=>{
      client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});
      await client.rpc.request('session.ensure',binding);
    };
    await start();
    await client!.rpc.request('session.submit',{sessionId:'view',inputId:'launch',mode:'followup',content:[{type:'text',text:'launch'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'launch'}});
    await expect.poll(async()=> (await client!.rpc.request('session.lookup',{sessionId:'view',inputId:'launch'}) as any).terminal,{timeout:15000}).toMatchObject({kind:'completed'});
    const observe=async()=> (await client!.rpc.request('session.observe',{sessionId:'view'}) as any).events as any[];
    expect((await observe()).find(e=>e.type==='tool/call' && e.data.callId==='read-call')?.data.nanoToolView.call.title).toContain('sample.txt');
    const views=(await observe()).filter(e=>e.data.nanoToolView).map(e=>e.data.nanoToolView);
    expect(JSON.stringify(views),JSON.stringify(await observe())).toContain('PERSISTED_CONTENT');
    const child=views.find(e=>e.callId==='child-call')?.childSessionId;
    expect(child).toBeTruthy();
    const children=await client!.rpc.request('session.descendants',{sessionId:'view'}) as any[];
    const detail=children.find(item=>item.id===child);
    expect(detail).toBeTruthy();
    expect(JSON.stringify(detail)).toContain('CHILD_VIEW');
    config={...config,revision:'2',toolAllowlist:[]};
    await client!.rpc.request('configuration.apply',config);
    await client!.shutdown();client=undefined;
    await start();
    expect((await observe()).filter(e=>e.data.nanoToolView).map(e=>e.data.nanoToolView)).toEqual(views);
    await client!.shutdown();client=undefined;
  }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
  finally{if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},25000);
