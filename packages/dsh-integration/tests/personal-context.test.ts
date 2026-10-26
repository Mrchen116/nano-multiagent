import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { RuntimeClient, prepareProfile } from '../lib/client.js';

it('keeps selected private tools independent of proactivity and creates an actual snooze Schedule', async () => {
  const home=await mkdtemp(join(tmpdir(),'personal-context-'));let client:RuntimeClient|undefined,logs='';
  const until=new Date(Date.now()+3600000).toISOString();const completions:any[]=[];
  try {
    await writeFile(join(home,'fixture.mjs'),`import{appendFile}from'node:fs/promises';
export const name='private-context-fixture';export const inject=['llm','tools','agents'];
export function apply(ctx){ctx.on('llm/stream',async function*(o){const agent=ctx.agents.get(o.sessionId);
 const run=(name,args)=>ctx.tools.execute({name,arguments:args,callId:name+Date.now(),agent,signal:o.signal});
 const schemas=ctx.tools.schemas(agent).map(t=>t.name);
 const results={context:await run('personal_context',{query:'meeting'}),snooze:await run('personal_attention',{action:'snooze',id:'item',expected_revision:1,owner_instruction_id:'owner',snoozed_until:${JSON.stringify(until)}})};
 await appendFile(process.env.DSH_HOME+'/results.jsonl',JSON.stringify({schemas,results,system:o.system,messages:o.messages})+'\\n');
 yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home,[{insert:[{id:'private-context-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});
    client.rpc.handle('product.call',value=>{
      const call=value as {method:string;args:any};
      if(call.method==='personal_context')return {messages:[],tasks:[],attention:[],source_coverage:{complete:true},receipt_id:'query'};
      if(call.method==='personal_attention'){expect(call.args.exploration_batch_id).toMatch(/^root:/);return {id:'item',revision:2,snoozed_until:until,schedule_status:'pending'};}
      if(call.method==='pa.attention.snooze.complete'){completions.push(call.args);return {...call.args,schedule_status:'scheduled'};}
      throw new Error(call.method);
    });
    const config={agentId:'pa',revision:'1',workspace:home,provider:'deepseek-official',model:'deepseek-flash',mode:'global',personal:{bindingId:'b',ownerId:'owner',conversationId:'dm',epoch:1},features:{intelligent_ui:false,memory_curation:false,skill_creation:false,task_graph:false,personal_proactivity:false,cron_scheduling:false},toolAllowlist:['personal_context','personal_attention'],approval:{dangerouslySkipPermissions:true}};
    const binding={agentId:'pa',sessionId:'root',ownerId:'owner',revision:'1',cwd:home};
    await client.rpc.request('initialize',{protocol:1,agents:[],bindings:[]});
    const catalog=await client.rpc.request('configuration.catalog',{config,cwd:home}) as {tools:{name:string}[]};
    expect(catalog.tools.map(tool=>tool.name)).toEqual(expect.arrayContaining(['personal_sources','personal_context','personal_attention','publish_artifact']));
    await client.rpc.request('configuration.apply',config);await client.rpc.request('session.ensure',binding);
    const submit=async(id:string)=>{await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal).toMatchObject({kind:'completed'});};
    const rows=async()=>(await readFile(join(home,'results.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    await submit('no-cron');
    const first=(await rows())[0];expect(first.schemas).toContain('personal_context');expect(first.schemas).toContain('personal_attention');
    expect(first.schemas).not.toContain('publish_artifact');
    expect(first.results.context.isError,JSON.stringify(first.results.context)).not.toBe(true);
    expect(first.results.snooze.isError).toBe(true);expect(completions).toEqual([]);
    const changed=await client.rpc.request('configuration.apply',{...config,revision:'2',features:{...config.features,cron_scheduling:true},toolAllowlist:[...config.toolAllowlist,'schedule_create','schedule_list','schedule_update','schedule_delete','schedule_run','schedule_history']});expect(changed,JSON.stringify(changed)).toMatchObject({effective:true});
    await submit('with-cron');
    expect((await rows())[1].results.snooze.isError,JSON.stringify((await rows())[1].results.snooze)).not.toBe(true);
    expect(completions).toHaveLength(1);
    const schedules=await client.rpc.request('schedule.command',{agentId:'pa',action:'catalog'}) as any[];
    expect(schedules).toEqual(expect.arrayContaining([expect.objectContaining({id:completions[0].schedule_id})]));
  }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
  finally{await client?.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
},25000);
