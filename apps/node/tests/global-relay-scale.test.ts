import { mkdir, mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { expect, it } from 'vitest';
import { WebSocketServer, type WebSocket } from 'ws';
import { WebRelayConnection, type ProtocolFrame } from '@nano/channels';
import { prepareProfile, RuntimeClient } from '@nano/dsh-integration/client';
import { GlobalAgent, InboxStore, NodeStore, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, AgentLifecycleSnapshot, RelayInput } from '@nano/product-contracts';

it('keeps a second Global available through Relay while an old child blocks recovery of its own root', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-global-relay-scale-'));
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  const server = new WebSocketServer({host:'127.0.0.1',port:0});
  const agents: AgentConfiguration[] = Array.from({length:50}, (_,i) => ({
    agentId:'agent-'+i, revision:'1', mode:'global', workspace:join(home, 'workspace-'+i), provider:'deepseek-official', model:'deepseek-flash',
    toolAllowlist:['subagent'], knowledge:{enabled:false},
  }));
  const bindings=agents.map(agent=>store.bind({
    sessionId:'root-'+agent.agentId,conversationId:'global:'+agent.agentId,agentId:agent.agentId,
    cwd:agent.workspace,revision:'1',ownerId:'owner',
  }));
  const root=bindings[0]!, other=bindings[1]!;
  let native:RuntimeClient|undefined, relay:WebRelayConnection|undefined, product:GlobalAgent|undefined;
  let socket:WebSocket|undefined, logs='', stage='listen';
  const errors:unknown[]=[], traffic:ProtocolFrame[]=[], rpcTrace:unknown[]=[];
  const step=(name:string)=>{stage=name;if(process.env.NANO_SCALE_TRACE) console.info(name);};
  const deadline=async<T>(task:Promise<T>):Promise<T>=>{
    let timer:ReturnType<typeof setTimeout>|undefined;
    try{return await Promise.race([task,new Promise<never>((_resolve,reject)=>{timer=setTimeout(()=>reject(Error('stage timed out')),45_000);})]);}
    finally{clearTimeout(timer);}
  };
  const lines=async(name:string)=>(await readFile(join(home,name),'utf8').catch(error=>{
    if (error.code!=='ENOENT') throw error;
    return '';
  })).trim().split('\n').filter(Boolean).map(line=>JSON.parse(line));
  const send=(binding:typeof root,id:string)=>{
    const input:RelayInput={agent_id:binding.agentId,conversation_id:'chat-'+binding.agentId,relay_task_id:id,idempotency_key:id,
      metadata:{conversation_type:'direct'},message:{id,content:id,sender_type:'user',sender_user_id:'owner',attachments:[]}};
    socket!.send(JSON.stringify({type:'relay.message',payload:input}));
  };
  const stopRuntime=async()=>{
    if (!native) return;
    native.process.kill('SIGKILL');
    await native.exited;
    native=undefined;
  };
  try {
    await new Promise<void>(resolve=>server.once('listening',resolve));
    server.on('connection',connection=>{
      socket=connection;
      connection.on('message',data=>{
        const frame=JSON.parse(String(data)) as ProtocolFrame;
        traffic.push(frame);
        const targets=(frame.payload.targets ?? []) as string[];
        const result={conversations:targets.map(target=>({target,name:target,conversation_type:'direct'}))};
        connection.send(JSON.stringify({type:frame.type==='conversation.query'?'conversation.query.result':'ack',payload:{message_type:frame.type,request_id:frame.payload.request_id,
          relay_request_ids:1,ok:true,result}}));
      });
    });
    const fixture=join(home,'fixture.mjs');
    await writeFile(fixture,`import {appendFile,readFile} from 'node:fs/promises';
      import {setTimeout} from 'node:timers/promises';
      export const name='relay-scale';export const inject=['llm','sessionQuery','sessionPersistence'];
      export function apply(ctx){
        const file=process.env.DSH_HOME;
        if(process.env.NANO_TEST_COLD){
          const observe=ctx.sessionQuery.observeSession.bind(ctx.sessionQuery);
          ctx.sessionQuery.observeSession=async(id,opts)=>{
            const blocked=await readFile(file+'/hold-child','utf8').catch(()=>null);
            if(id===blocked){
              await appendFile(file+'/blocked.jsonl',JSON.stringify({id})+'\\n');
              while(await readFile(file+'/hold-child','utf8').catch(()=>null))await setTimeout(10);
            }
            return observe(id,opts);
          };
          const open=ctx.sessionPersistence.open.bind(ctx.sessionPersistence);
          ctx.sessionPersistence.open=async(id,...args)=>{
            const handle=await open(id,...args);
            if(!handle)return handle;
            const read=handle.read.bind(handle);
            handle.read=async(...range)=>{
              const result=await read(...range);
              const stat=await ctx.sessionPersistence.stat(id);
              await appendFile(file+'/reads.jsonl',JSON.stringify({id,events:result.events.length,logBytes:stat?.sizeBytes})+'\\n');
              return result;
            };
            return handle;
          };
        }
        let launched=false;
        ctx.on('llm/stream',async function*(options){
          await appendFile(file+'/model.jsonl',JSON.stringify({id:options.sessionId,messages:options.messages})+'\\n');
          const text=options.messages.findLast(m=>m.role==='user'&&m.source?.kind!=='runtime-context')?.content.find(b=>b.type==='text')?.text;
          if(!options.sessionId.startsWith('root-agent-')){
            await appendFile(file+'/held-model.jsonl',JSON.stringify({id:options.sessionId})+'\\n');
            await new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true}));
          }
          if(text==='launch native child'&&!launched){
            launched=true;
            yield {type:'block-end',index:0,block:{type:'tool-call',name:'subagent',id:'start-child',
              arguments:JSON.stringify({prompt:'hold native child',description:'hold recovery',run_in_background:true,backgroundMode:'continuable'})}};
            yield {type:'finish',reason:{kind:'tool-calls'}};return;
          }
          yield {type:'block-end',index:0,block:{type:'text',text:'done'}};
          yield {type:'finish',reason:{kind:'stop'}};
        });
      }`);
    await Promise.all(agents.map(agent=>mkdir(agent.workspace)));
    await prepareProfile(home,[{insert:[{id:'relay-scale',name:fixture}]}]);
    const start=async(cold=false)=>{
      native=new RuntimeClient({home,cwd:home,env:cold?{NANO_TEST_COLD:'1'}:{},onLog:text=>{logs+=text;}});
      native.rpc.handle('product.task_context.prepare',()=>({messages:[],revoked:[]}));
      native.rpc.handle('product.task_context.commit',()=>null);
      await native.rpc.request('initialize',{protocol:1,recoveryMarkers:true,agents:cold?agents:agents.slice(0,1),bindings:cold?bindings:bindings.slice(0,1)});
    };
    step('seed DSH');await deadline(start());
    await native!.rpc.request('session.ensure',root);
    await native!.rpc.request('session.submit',{sessionId:root.sessionId,inputId:'seed',mode:'followup',
      content:[{type:'text',text:'launch native child'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'seed'}});
    await expect.poll(async()=>(await lines('held-model.jsonl')).length,{timeout:10000}).toBe(1);
    const child=(await lines('held-model.jsonl'))[0].id;
    await expect.poll(async()=>(await native!.rpc.request('session.lookup',{sessionId:root.sessionId,inputId:'seed'}) as {terminal?:string}).terminal,
      {timeout:10000}).toBeTruthy();
    await expect.poll(async()=>{
      const observed=await native!.rpc.request('session.observe',{sessionId:root.sessionId}) as {events:{type:string;data:{childId?:string}}[]};
      return observed.events.some(event=>event.type==='subagent/catalog' && event.data.childId===child);
    },{timeout:10000}).toBe(true);
    const durableChild=await native!.rpc.request('session.work.child',{sessionId:root.sessionId,childId:child}) as {events:{type:string}[]};
    expect(durableChild.events.some(event=>event.type==='turn/start')).toBe(true);
    await stopRuntime();
    await writeFile(join(home,'hold-child'),child);
    step('cold initialize');await deadline(start(true));
    expect(await lines('reads.jsonl')).toEqual([]);
    expect(await lines('blocked.jsonl')).toEqual([]);

    relay=new WebRelayConnection({url:`http://127.0.0.1:${(server.address() as {port:number}).port}`,
      credentials:()=>({accessToken:'fixture',registration:{node_id:'scale-node',agents:agents.map(agent=>agent.agentId)}}),
      onFrame:frame=>frame.type==='relay.message' ? product!.receive(frame.payload as unknown as RelayInput) : undefined,
      onError:error=>errors.push(error)});
    product=new GlobalAgent({nodeId:'scale-node',ownerId:'owner',agents,store,inbox,runtime:{
        request: async (method, value) => {
          const input=value as {sessionId?:string};
          rpcTrace.push([method,input.sessionId,'start']);
          const result=await native!.rpc.request(method,value);
          rpcTrace.push([method,input.sessionId,'done',method==='session.submit'?result:undefined]);
          return result;
        },
        onNotification: listener => native!.rpc.onNotification(listener),
      },relay,
      image:async()=>'',onError:error=>errors.push(error)});
    native!.rpc.handle('product.call',value=>product!.call(value as ProductCall));
    native!.rpc.handle('model.check',()=>({published:false}));
    step('relay register');await deadline(relay.start());
    step('held A recovery');send(root,'resume-a');
    await expect.poll(async()=>(await lines('blocked.jsonl')).some(row=>row.id===child),{timeout:10000}).toBe(true);
    step('B delivery while A is held');send(other,'accept-b');
    await expect.poll(async()=>(await lines('model.jsonl')).some(row=>row.id===other.sessionId),{timeout:30000}).toBe(true);
    expect(traffic.some(frame=>frame.type==='node.delivery_receipt' && frame.payload.relay_task_id==='accept-b')).toBe(true);
    expect((await lines('reads.jsonl')).every(row=>row.id!==child)).toBe(true);
    expect(traffic.find(frame=>frame.type==='node.register')?.payload.agents).toHaveLength(50);

    step('resume A');await unlink(join(home,'hold-child'));
    await expect.poll(async()=>(await lines('model.jsonl')).some(row=>row.id===root.sessionId &&
      row.messages.some((message:{source?:{channel?:string}})=>message.source?.channel==='subagent-recovery')),{timeout:30000}).toBe(true);
    const reads = await lines('reads.jsonl');
    expect(reads.filter(row => row.id === root.sessionId && row.events > 1)).toHaveLength(1);
    expect(reads.filter(row => row.id === child).length).toBeGreaterThan(0);
    expect(errors).toEqual([]);
  } catch (error) {
    const model=(await lines('model.jsonl')).map(row=>({id:row.id,sources:row.messages.map((message:{source?:{kind?:string;channel?:string}})=>[message.source?.kind,message.source?.channel]).filter((source:unknown[])=>source[0])}));
    const notices=await readFile(join(home,'storages/nano_subagent_recovery/sessions',root.sessionId+'.json'),'utf8').catch(()=>undefined);
    const evidence=stage==='B delivery while A is held' ? await native?.rpc.request('session.lookup',{sessionId:other.sessionId,inputId:'inbox-wake:'+other.agentId+':2'}).catch(String) : undefined;
    throw new Error(`${stage}: ${String(error)}\n${logs}\nmodel=${JSON.stringify(model)}\nnotices=${notices}\nB evidence=${JSON.stringify(evidence)}\nrpc=${JSON.stringify(rpcTrace)}\nerrors=${errors.join('\n')}`,{cause:error});
  }
  finally {
    await unlink(join(home,'hold-child')).catch(()=>{});
    await stopRuntime();
    await relay?.stop();
    await product?.stop().catch(()=>{});
    for (const connection of server.clients) connection.terminate();
    await new Promise<void>(resolve=>server.close(()=>resolve()));
    inbox.close();store.close();await rm(home,{recursive:true,force:true});
  }
},150000);

it('delivers a Relay frame through the production Node assembly before another target completes registration', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-node-registration-cut-'));
  const server=new WebSocketServer({host:'127.0.0.1',port:0});
  const ids=['a','b'];
  const lifecycles:AgentLifecycleSnapshot[]=ids.map(agent_id=>({agent_id,desired:'enabled',revision:1,
    disabled_through_revision:0,request_id:null,actor_user_id:null,requested_at:'2026-11-10',applied_revision:0,
    observed:'enabling',process_instance_id:null,confirmed_at:null,error_code:null,error_detail:null}));
  let node:ReturnType<typeof spawn>|undefined, exited:Promise<unknown>|undefined;
  let socket:WebSocket|undefined, held:(()=>void)|undefined, queries=0, log='';
  const frames:ProtocolFrame[]=[];
  try {
    await new Promise<void>(resolve=>server.once('listening',resolve));
    server.on('connection',connection=>{
      socket=connection;
      connection.on('message',bytes=>{
        const frame=JSON.parse(String(bytes)) as ProtocolFrame;
        frames.push(frame);
        const targets=(frame.payload.targets ?? []) as string[];
        const ack=()=>connection.send(JSON.stringify({type:frame.type==='conversation.query'?'conversation.query.result':'ack',payload:{
          ok:true,message_type:frame.type,request_id:frame.payload.request_id,relay_request_ids:1,
          work_sync_http:1,agent_lifecycle_v1:1,node_epoch:1,agent_lifecycles:lifecycles,
          schedule_ids:[],result:{conversations:targets.map(target=>({target,name:target,conversation_type:'direct'}))},
        }}));
        if(frame.type==='task.execution.frozen_schedules'&&frame.payload.agent_id==='a'&&++queries===2)held=ack;
        else ack();
      });
    });
    const config=join(home,'config.yaml');
    await Promise.all(ids.map(id=>mkdir(join(home,id))));
    await writeFile(config,JSON.stringify({
      node:{node_id:'registration-cut',user_id:'owner'},
      im_service:{url:`http://127.0.0.1:${(server.address() as {port:number}).port}`,token:'fixture'},
      agents:ids.map(id=>({agent_id:id,workspace_root:join(home,id),work_mode:'global',tool_allowlist:[],
        features:{task_graph:false,intelligent_ui:false,memory_curation:false,skill_creation:false,dreaming:false}})),
      llm:{default_model:'fixture',providers:[{name:'test',base_url:'http://127.0.0.1:9',api_key:'fixture',models:[{name:'fixture'}]}]},
    }));
    node=spawn(process.execPath,[resolve('apps/node/lib/main.js'),'--config',config],{
      env:{...process.env,NANO_OWNER_CONFIG_ROOT:home},stdio:['ignore','ignore','pipe'],
    });
    node.stderr?.on('data',data=>{log+=String(data);});
    exited=new Promise((resolve,reject)=>{node!.once('exit',resolve);node!.once('error',reject);});
    await expect.poll(()=>Boolean(held),{timeout:40000}).toBe(true);
    const input:RelayInput={agent_id:'b',conversation_id:'chat-b',relay_task_id:'accept-b',idempotency_key:'accept-b',
      metadata:{conversation_type:'direct'},message:{id:'accept-b',content:'New task for B',sender_type:'user',sender_user_id:'owner',attachments:[]}};
    socket!.send(JSON.stringify({type:'relay.message',payload:input}));
    await expect.poll(()=>frames.some(frame=>frame.type==='node.delivery_receipt'&&frame.payload.relay_task_id==='accept-b'),{timeout:12000}).toBe(true);
    expect(frames.some(frame=>frame.type==='agent.lifecycle.report'&&frame.payload.agent_id==='a'&&frame.payload.observed==='enabled')).toBe(true);
    expect(queries).toBe(2);
    held!();held=undefined;
  } catch(error) {
    throw new Error(`${String(error)}\n${log}\n${JSON.stringify(frames.map(frame=>[frame.type,frame.payload.agent_id,frame.payload.observed]))}`,{cause:error});
  } finally {
    held?.();
    if(node?.exitCode===null&&node.signalCode===null)node.kill('SIGTERM');
    for(const connection of server.clients)connection.terminate();
    await new Promise<void>(resolve=>server.close(()=>resolve()));
    if(exited)await exited;
    await rm(home,{recursive:true,force:true});
  }
},90000);
