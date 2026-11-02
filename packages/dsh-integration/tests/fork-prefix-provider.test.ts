import {createServer} from 'node:http';
import {mkdtemp, rm, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {expect, it} from 'vitest';
import {prepareProfile, RuntimeClient} from '../lib/client.js';
import {registerNoopTaskHosts} from './helpers/noop-task-hosts.js';

// The provider moves cache hints as the conversation grows and may collapse a
// single text block to a string. Neither changes the tokens of the prefix.
const messages = (body: any) => body.messages.map((m: any) => ({...m,
  content: typeof m.content === 'string' ? [{type:'text',text:m.content}]
    : m.content.map(({cache_control: _hint,...block}: any) => block),
}));
const system = (body: any) => body.system.map(({cache_control: _hint,...block}: any) => block);

it.each([{mode:'global',personal:false},{mode:'global',personal:true},{mode:'single_thread',personal:false}])('preserves parent system, tools and wire history in empty, seeded and restored forks ($mode, PA=$personal)', async ({mode,personal}) => {
  const home=await mkdtemp(join(tmpdir(),'nano-fork-prefix-'));
  const requests: Array<{session:string;body:any}>=[], issued=new Set<string>();
  let client: RuntimeClient|undefined, logs='';
  const server=createServer(async(req,res)=>{
    const chunks:Buffer[]=[];for await(const chunk of req)chunks.push(Buffer.from(chunk));
    const body=JSON.parse(Buffer.concat(chunks).toString('utf8')), session=String(req.headers['x-agent-session-id']);
    requests.push({session,body});
    const command=messages(body).findLast((m:any)=>m.role==='user'&&m.content.some((b:any)=>b.text?.startsWith('PREFIX_COMMAND_')))?.content.find((b:any)=>b.text?.startsWith('PREFIX_COMMAND_')).text;
    const fork=session==='root'&&command&&!issued.has(command);
    if(fork)issued.add(command);
    res.writeHead(200,{'content-type':'text/event-stream'});
    const emit=(type:string,data:object)=>res.write(`event: ${type}\ndata: ${JSON.stringify({type,...data})}\n\n`);
    emit('message_start',{message:{id:'fixture-'+requests.length,type:'message',role:'assistant',model:'fixture',content:[],stop_reason:null,usage:{input_tokens:20,output_tokens:0}}});
    emit('content_block_start',{index:0,content_block:fork
      ? {type:'tool_use',id:'fork-'+requests.length,name:'subagent_fork',input:{}}
      : {type:'text',text:'PREFIX_ANSWER_'+requests.length}});
    if(fork)emit('content_block_delta',{index:0,delta:{type:'input_json_delta',partial_json:JSON.stringify({prompt:'FORK_PREFIX_TASK: independently verify this conversation and return internally.',description:'Verify prefix',run_in_background:false})}});
    emit('content_block_stop',{index:0});
    emit('message_delta',{delta:{stop_reason:fork?'tool_use':'end_turn',stop_sequence:null},usage:{output_tokens:4}});
    emit('message_stop',{});res.end();
  });
  const binding={sessionId:'root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
  const config={agentId:'a',displayName:'Prefix Agent',revision:'1',workspace:home,mode,provider:'wire',model:'fixture',systemPrompt:'PARENT_PERSONA_PREFIX: respond to the source conversation.',
    toolAllowlist:['subagent_fork','send_message','inbox','conversations','task_graph','personal_sources','schedule_run','schedule_history'],
    features:{task_graph:true,intelligent_ui:true,dreaming:false,cron_scheduling:true},approval:{dangerouslySkipPermissions:true},
    ...(personal?{personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}}:{}),
  };
  const start=async()=>{
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture-only'},onLog:value=>{logs+=value;}});
    registerNoopTaskHosts(client);
    client.rpc.handle('product.call',()=>{throw Error('A fork must not perform public product actions');});
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    await client.rpc.request('session.ensure',binding);
  };
  const submit=async(id:string)=>{
    const offset=requests.length;
    await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text:'PREFIX_COMMAND_'+id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
    await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:15000}).toBeTruthy();
    const round=requests.slice(offset),parent=round.find(r=>r.session==='root')!,child=round.find(r=>r.session!=='root');
    expect(child,JSON.stringify({round,session:await client!.rpc.request('session.observe',{sessionId:'root'})})+logs).toBeDefined();
    expect(child!.body.tools).toEqual(parent.body.tools);
    expect(system(child!.body)).toEqual(system(parent.body));
    expect(JSON.stringify(child!.body)).toContain('FORK_PREFIX_TASK');
    return {parent:parent.body,child:child!.body};
  };
  try{
    await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
    await writeFile(join(home,'fixture.mjs'),"export const inject=['tools'];export function apply(ctx){ctx.on('agent/created',({agent})=>{agent.ctx.tools.presentAs('native');});}");
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{wire:{api:'anthropic-messages',baseURL:`http://127.0.0.1:${(server.address() as any).port}`,apiKeyEnv:'NANO_TEST_KEY',models:[{id:'fixture',contextWindow:200000}]}}}},{insert:[{id:'prefix-fixture',name:join(home,'fixture.mjs')}]}]);
    await start();
    const first=await submit('empty');
    expect(JSON.stringify(first.child.messages)).not.toContain('PREFIX_COMMAND_empty');
    const completedParent=requests.filter(r=>r.session==='root').at(-1)!.body;
    const seeded=await submit('seeded');
    expect(messages(seeded.child).slice(0,messages(completedParent).length)).toEqual(messages(completedParent));
    const beforeRestart=requests.filter(r=>r.session==='root').at(-1)!.body;
    await client!.shutdown();client=undefined;await start();
    const restored=await submit('restored');
    expect(messages(restored.child).slice(0,messages(beforeRestart).length)).toEqual(messages(beforeRestart));
  }catch(error){throw new Error(String(error)+'\n'+logs,{cause:error});}
  finally{if(client)await client.shutdown();await new Promise<void>(resolve=>{server.close(()=>resolve());server.closeAllConnections();});await rm(home,{recursive:true,force:true});}
},60000);
