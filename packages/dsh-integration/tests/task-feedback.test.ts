import {registerNoopTaskContext} from './helpers/noop-task-context.js';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';

it.each([['waiting',true],['in_review',true],['done',true],['done',false]] as const)('applies %s feedback only with Task Feature enabled=%s',async(status,enabled)=>{
  const home=await mkdtemp(join(tmpdir(),'nano-task-feedback-'));
  let client:RuntimeClient|undefined;
  try {
    await writeFile(join(home,'fixture.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='task-feedback-fixture';export const inject=['llm'];
export function apply(ctx){let step=0;ctx.on('llm/stream',async function*(o){
 step++;await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify(o.messages)+'\\n');
 const feedback=o.messages.findLast(m=>m.role==='user'&&m.source?.channel==='task-feedback');
 const data=feedback&&JSON.parse(feedback.content[0].text.split('\\n').find(line=>line.startsWith('{')));
 let block;
 if(step<3)block={type:'tool-call',id:'apply-'+step,name:'task_graph',arguments:JSON.stringify({action:'apply',graph_id:'graph',base_revision:1,request_key:'change',change_note:'Verified current facts',operations:[{op:'update_task',node_id:'child',patch:{status:${JSON.stringify(status)},result:'Verified result'}}]})};
 else if(step===3&&data)block={type:'tool-call',id:'deliver',name:'send_message',arguments:JSON.stringify({target:data.conversation_id,text:JSON.stringify(data.tasks)})};
 else block={type:'text',text:'The confirmed result was delivered to its original conversation.'};
 yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:block.type==='tool-call'?'tool-calls':'stop'}};
});}`);
    await prepareProfile(home,[{insert:[{id:'task-feedback-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home});registerNoopTaskContext(client);
    let applied=0,finished=false;
    const sent:unknown[]=[];
    const task={graph_id:'graph',node_id:'child',title:'Child',status:'doing',updated_at:'2026-10-23T15:00:00Z',revision:1,conversation:{id:'original-chat'},relative_url:'/tasks/graph'};
    client.rpc.handle('product.task_execution.snapshot',()=>finished?{kind:'quiescent',tasks:[],repair_task_ids:[]}:{kind:'continue',tasks:[task],repair_task_ids:[]});
    client.rpc.handle('product.call',value=>{
      const call=value as {method:string;args:Record<string,unknown>};
      if(call.method==='task_graph'){
        if(++applied===1)return {ok:false,error:{code:'write_outcome_unknown',message:'Confirm using the same request key'}};
        finished=true;
        return {ok:true,result:{graph_id:'graph',revision:2,changed_ids:['child'],feedback:{conversation_id:'original-chat',tasks:[{node_id:'child',title:'Child',status,result:'Verified result',...(status==='waiting'?{wait:{reason:'External prerequisite',schedule_id:'real-schedule',next_check_at:new Date(Date.now()+60_000).toISOString()}}:{})}]}}};
      }
      if(call.method==='send_message'){sent.push(call.args);return {status:'sent',message_id:'confirmed'};}
      throw new Error('Unexpected product call '+call.method);
    });
    await client.rpc.request('initialize',{protocol:1,agents:[{features:{task_graph:enabled,intelligent_ui:false,cron_scheduling:true},agentId:'a',mode:'global',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['task_graph','send_message'],approval:{dangerouslySkipPermissions:true}}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'s',agentId:'a',ownerId:'owner',revision:'1',cwd:home});
    if(!enabled)await client.rpc.request('session.submit',{sessionId:'s',inputId:'manual',mode:'followup',content:[{type:'text',text:'Use the selected task tool to save the verified result.'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'manual'}});
    await expect.poll(async()=>applied).toBe(2);
    if(enabled)await expect.poll(async()=>sent.length).toBe(1);
    await expect.poll(async()=>(await client!.rpc.request('session.observe',{sessionId:'s'}) as {status:string}).status).toBe('idle');
    if(enabled)expect(sent[0]).toMatchObject({target:'original-chat',text:expect.stringContaining('child')});
    else expect(sent).toHaveLength(0);
    const calls=(await readFile(join(home,'calls'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    expect(calls).toHaveLength(enabled?4:3);
    expect(calls[1].some((m:any)=>m.source?.channel==='task-feedback')).toBe(false);
    expect(calls[2].filter((m:any)=>m.source?.channel==='task-feedback')).toHaveLength(enabled?1:0);
    expect(applied).toBe(2);
  } finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},20_000);
