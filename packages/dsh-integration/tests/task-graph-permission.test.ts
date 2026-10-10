import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('sends task deletion through the actual native tool only after ordinary approval, and never on denial', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-task-permission-'));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    await writeFile(join(home,'fixture.mjs'), `export const name='task-permission-fixture';export const inject=['llm'];
export function apply(ctx){const seen=new Set();ctx.on('llm/stream',async function*(o){
 const human=o.messages.findLast(m=>m.role==='user'&&m.source.kind==='nano-human');
 const text=human.content.filter(b=>b.type==='text').map(b=>b.text).join('');
 if(['对','直接删！'].includes(text)&&!seen.has(human.id)){
  seen.add(human.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:human.id+'-delete',name:'task_graph',arguments:JSON.stringify({action:'delete',graph_id:'graph',node_id:'n2',base_revision:2,request_key:human.id})}};yield{type:'finish',reason:{kind:'tool-calls'}};
 }else{yield{type:'block-end',index:0,block:{type:'text',text:'Scope is the selected subtree.'}};yield{type:'finish',reason:{kind:'stop'}};}
});}`);
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}},{insert:[{id:'task-permission-fixture',name:join(home,'fixture.mjs')}]}]);
    const agents = ['allow','deny'].map(agentId=>({agentId,revision:'1',provider:'fixture',model:'test',mode:'single_thread',toolAllowlist:['task_graph'],features:{task_graph:true,memory_curation:false,skill_creation:false},approval:{...approvalDefaults,enabled:false,globalRoot:home}}));
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    const sent: any[] = []; const approvals: string[] = [];
    client.rpc.handle('product.call',value=>{sent.push(value);return{ok:true,result:{deleted_ids:['n2']}};});
    client.rpc.onNotification((method,value)=>{if(method==='approval.request'){
      const request=value as {requestId:string;sessionId:string};approvals.push(request.sessionId);
      void client!.rpc.request('approval.answer',{requestId:request.requestId,decision:request.sessionId==='allow'?'allowed-once':'rejected'});
    }});
    await client.rpc.request('initialize',{protocol:1,agents,bindings:[]});
    for (const config of agents) {
      await client.rpc.request('session.ensure',{sessionId:config.agentId,agentId:config.agentId,revision:'1',ownerId:'owner',cwd:home});
      for (const [index,text] of ['删除已讨论的 n2 子树',config.agentId==='allow'?'对':'直接删！'].entries()) {
        const inputId=config.agentId+'-'+index;
        await client.rpc.request('session.submit',{sessionId:config.agentId,inputId,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
        await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:config.agentId,inputId})as{terminal?:unknown}).terminal).toBeTruthy();
      }
    }
    expect(approvals).toEqual(['allow','deny']);
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({method:'task_graph',agentId:'allow',args:{action:'delete',node_id:'n2',base_revision:2}});
    const denied=await client.rpc.request('session.observe',{sessionId:'deny'}) as {events:{type:string;data:any}[]};
    expect(denied.events.some(event=>event.type==='tool/result'&&event.data.message.isError)).toBe(true);
    await client.shutdown();client=undefined;
  } catch(error) {throw new Error(`${error}\n${logs}`,{cause:error});}
  finally {if(client){client.process.kill('SIGKILL');await client.exited;}await rm(home,{recursive:true,force:true});}
},20000);
