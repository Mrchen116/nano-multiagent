import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { createServer, type ServerResponse } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '@nano/dsh-integration/client';
import { NodeStore, SingleThread } from '@nano/personal-assistant';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';

it('delivers one same-chat carrier to an idle or busy native model and preserves the current speaker', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-single-chat-'));
  const store = new NodeStore(':memory:', 'owner');
  const requests: {messages:any[]; response:ServerResponse}[] = [];
  const provider = createServer(async (request,response) => {
    let body='';
    for await (const chunk of request) body += chunk;
    requests.push({messages:JSON.parse(body),response});
  });
  let client:RuntimeClient | undefined, product:SingleThread | undefined;
  const errors:unknown[] = [];
  let logs='';
  try {
    await new Promise<void>(resolve=>provider.listen(0,'127.0.0.1',resolve));
    const {port} = provider.address() as {port:number};
    const plugin = join(home,'model.mjs');
    await writeFile(plugin,`export const name='chat-fixture';export const inject=['llm'];
      export function apply(ctx){ctx.on('llm/stream',async function*(request){
        const reply=await fetch('http://127.0.0.1:${port}',{method:'POST',body:JSON.stringify(request.messages),signal:request.signal});
        for(const chunk of await reply.json())yield chunk;
      });}`);
    await writeFile(join(home,'fixture.txt'),'fixture tool output');
    await prepareProfile(home,[{insert:[{id:'chat-fixture',name:plugin}]}]);
    client = new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    client.rpc.handle('product.task_context.prepare',()=>({messages:[],revoked:[]}));
    client.rpc.handle('product.task_context.commit',()=>null);
    client.rpc.handle('model.check',()=>({published:false}));
    const config:AgentConfiguration = {agentId:'a',revision:'1',workspace:home,mode:'single_thread',collaborationScope:'team',
      provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['read'],approval:{dangerouslySkipPermissions:true}};
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    product = new SingleThread({nodeId:'node',ownerId:'owner',agents:[config],store,runtime:client.rpc,
      image:async()=> 'iVBORw0KGgoAAAANSUhEUgAAAKAAAABaCAIAAACwpMoFAAABNklEQVR4nO3ZwQmAMBQFwVRjY5ZtB9qD2ILkILgZ+PdJ2OMb235N33He08f9xh2rfXg1V+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrvjj4/mvj+B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx37cFxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx117cNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBx1x4cdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNy1B8ddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdx+RTJHLcoVInQAAAABJRU5ErkJggg==',
      relay:{request:async(_type,payload)=>({type:'ack',payload:{message_id:payload.idempotency_key ?? 'bubble'}})},onError:error=>errors.push(error)});
    const chat=(id:string,chatId:string,high=false):RelayInput=>({agent_id:'a',conversation_id:chatId,relay_task_id:id,idempotency_key:id,
      metadata:{conversation_type:'group',mentioned_agent_ids:high?['a']:[]},
      message:{id,content:`BODY_${id}`,sender_user_id:high?'alice':'bob',sender_type:'user',attachments:[]}});
    const reply=(index:number,tool=false)=>requests[index]!.response.end(JSON.stringify(tool ? [
      {type:'block-end',index:0,block:{type:'tool-call',id:'hold',name:'read',arguments:JSON.stringify({file_path:join(home,'fixture.txt')})}},
      {type:'finish',reason:{kind:'tool-calls'}},
    ] : [{type:'block-end',index:0,block:{type:'text',text:'NO_REPLY'}},{type:'finish',reason:{kind:'stop'}}]));
    await product.receive(chat('unrelated','other'));
    const photo=chat('image','group');
    photo.message.attachments.push({url:'/photo',content_type:'image/png',file_name:'photo.png'});
    await product.receive(photo);
    expect(requests).toHaveLength(0);
    await product.receive(chat('high','group',true));
    await expect.poll(()=>requests.length).toBe(1);
    const initial=requests[0]!.messages.filter(message=>message.id==='a:high');
    expect(initial).toHaveLength(1);
    expect(initial[0].source).toMatchObject({kind:'user',actorId:'alice',directHumanText:'BODY_high',nanoTeamChat:true});
    expect(initial[0].content.some((part:any)=>part.type==='image')).toBe(true);
    expect(JSON.stringify(initial[0].content)).toContain('BODY_image');
    expect(JSON.stringify(requests[0]!.messages)).not.toContain('BODY_unrelated');

    await product.receive(chat('later','group'));
    await product.receive(chat('correction','group',true));
    expect(requests).toHaveLength(1);
    reply(0,true);
    await expect.poll(()=>requests.length).toBe(2);
    const correction=requests[1]!.messages.filter(message=>message.id==='a:correction');
    expect(correction).toHaveLength(1);
    expect(JSON.stringify(correction[0].content)).toContain('BODY_later');
    expect(correction[0].source.directHumanText).toBe('BODY_correction');
    expect(requests[1]!.messages.some(message=>message.id==='a:later')).toBe(false);
    reply(1);
    const sessionId=store.bindingFor('a','group')!.sessionId;
    const observe=async(id:string)=>await client!.rpc.request('session.observe',{sessionId:id}) as {status:string;events:{type:string}[]};
    await expect.poll(async()=>(await observe(sessionId)).status).toBe('idle');
    expect((await observe(sessionId)).events.filter(event=>event.type==='turn/start')).toHaveLength(1);

    // Use the expired durable clock of an offline chat without advancing the native process clock.
    store.bufferGroup(chat('expired','clock'),Date.now()-1);
    await product.recover();
    await expect.poll(()=>requests.length).toBe(3);
    const expired=requests[2]!.messages.find(message=>message.id==='a:expired');
    expect(expired.source).toMatchObject({kind:'nano-system',channel:'chat-background'});
    expect(JSON.stringify(expired.content)).toContain('BODY_expired');
    expect(JSON.stringify(requests[2]!.messages)).not.toContain('BODY_correction');
    reply(2);
    await expect.poll(async()=>(await observe(store.bindingFor('a','clock')!.sessionId)).status).toBe('idle');
    expect(errors).toEqual([]);
  } catch(error) {throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally {
    provider.closeAllConnections();
    await product?.stop();
    if(client){client.process.kill('SIGKILL');await client.exited;}
    await new Promise<void>(resolve=>provider.close(()=>resolve()));
    store.close();
    await rm(home,{recursive:true,force:true});
  }
},30_000);
