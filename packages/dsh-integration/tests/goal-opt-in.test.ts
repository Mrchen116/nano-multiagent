import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

const goalTools = ['create_goal', 'get_goal', 'update_goal'];
it('defaults Goal tools off and honors each ordinary tool selection', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-goal-'));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    await writeFile(join(home, 'probe.mjs'), `import {writeFile} from 'node:fs/promises';
export const name='goal-probe';export const inject=['tools','llm','agents','subagents'];
export function apply(ctx){
ctx.on('agent/pre-step',async({agent,messages,signal},next)=>{
if(agent.id==='default' && messages.some(m=>m.content.some(b=>b.type==='text'&&b.text==='probe'))){
  const child=await ctx.subagents.start('fork',{parent:agent,signal,label:'goal-child',prompt:[{type:'text',text:'child probe'}]});
  try{await child.result;}finally{await child.dispose();}
}
const result=await ctx.tools.execute({name:'get_goal',callId:'probe',arguments:{},agent,signal:new AbortController().signal});
await writeFile(process.env.DSH_HOME+'/'+(agent.session.header.origin==='subagent'?'child':agent.id)+'.json',JSON.stringify(result));return next();});
ctx.on('llm/stream',async function*(o){const agent=ctx.agents.currentInitiator();await writeFile(process.env.DSH_HOME+'/'+agent.id+'.request.json',JSON.stringify(o.messages));if(o.messages.findLast(m=>m.role==='user')?.id==='hold'){await new Promise(resolve=>o.signal.addEventListener('abort',resolve,{once:true}));return;}yield{type:'block-end',index:0,block:{type:'text',text:'ordinary reply'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home, [{insert: [{id: 'goal-probe', name: join(home, 'probe.mjs')}]}]);
    client = new RuntimeClient({home, cwd: home, onLog: text => {logs += text;}});
    registerNoopTaskHosts(client);
    const base = {knowledge:{memoryMode:'legacy'},features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false},revision:'1',provider:'deepseek-official',model:'deepseek-flash'};
    const agents = [
      {...base,agentId:'default'},
      {...base,agentId:'empty',toolAllowlist:[]},
      {...base,agentId:'read-goal',toolAllowlist:['get_goal','read']},
      {...base,agentId:'create-only',toolAllowlist:['create_goal']},
      {...base,agentId:'update-only',toolAllowlist:['update_goal']},
      {...base,agentId:'all',toolAllowlist:goalTools},
      {...base,agentId:'global',mode:'global'},
    ];
    await client.rpc.request('initialize',{protocol:1,agents,bindings:[]});
    for(const config of agents){
      await client.rpc.request('session.ensure',{sessionId:config.agentId,agentId:config.agentId,revision:'1',ownerId:'owner',cwd:home});
      const caps=await client.rpc.request('session.capabilities',{sessionId:config.agentId}) as {tools:string[];prompt:unknown};
      const expected=(config.toolAllowlist ?? []).filter(name=>goalTools.includes(name));
      expect(caps.tools.filter(name=>goalTools.includes(name)).sort()).toEqual([...expected].sort());
      expect(JSON.stringify(caps.prompt).includes('create_goal may infer goal intent')).toBe(expected.length>0);
      await client.rpc.request('session.submit',{sessionId:config.agentId,inputId:'probe-'+config.agentId,mode:'followup',content:[{type:'text',text:'probe'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'probe-'+config.agentId}});
      await expect.poll(()=>readFile(join(home,config.agentId+'.json'),'utf8').catch(()=>'' )).not.toBe('');
      const probe=JSON.parse(await readFile(join(home,config.agentId+'.json'),'utf8'));
      if(expected.includes('get_goal')) expect(probe.isError, JSON.stringify(probe)).not.toBe(true);
      else expect(JSON.stringify(probe)).toContain('UNKNOWN_TOOL');
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:config.agentId,inputId:'probe-'+config.agentId}) as {terminal?:unknown}).terminal).toBeTruthy();
    }
    expect(await readFile(join(home,'child.json'),'utf8')).toContain('UNKNOWN_TOOL');
    await client.rpc.request('session.submit',{sessionId:'read-goal',inputId:'hold',mode:'followup',content:[{type:'text',text:'hold'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'hold'}});
    await expect.poll(()=>readFile(join(home,'read-goal.request.json'),'utf8')).toContain('hold');
    let applied = false;
    const applying = client.rpc.request('configuration.apply',{...agents[2],revision:'2',toolAllowlist:['update_goal']}).then(()=>{applied=true;});
    void applying.catch(()=>{});
    await expect.poll(async()=>(await client!.rpc.request('session.capabilities',{sessionId:'read-goal'}) as {tools:string[]}).tools).not.toContain('get_goal');
    const busy=await client.rpc.request('session.capabilities',{sessionId:'read-goal'}) as {tools:string[]};
    expect(busy.tools).not.toContain('read');
    expect(busy.tools).not.toContain('update_goal');
    expect(applied).toBe(false);
    await client.rpc.request('session.cancel',{sessionId:'read-goal'});
    await applying;
    const updated=await client.rpc.request('session.capabilities',{sessionId:'read-goal'}) as {tools:string[]};
    expect(updated.tools.filter(name=>goalTools.includes(name))).toEqual(['update_goal']);
    await client.rpc.request('session.submit',{sessionId:'default',inputId:'hold',mode:'followup',content:[{type:'text',text:'hold'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'hold'}});
    await expect.poll(()=>readFile(join(home,'default.request.json'),'utf8')).toContain('hold');
    const defaultApply=client.rpc.request('configuration.apply',{...agents[0],revision:'2',toolAllowlist:['get_goal']});
    void defaultApply.catch(()=>{});
    await expect.poll(async()=>(await client!.rpc.request('session.capabilities',{sessionId:'default'}) as {tools:string[]}).tools).not.toContain('read');
    const defaultBusy=await client.rpc.request('session.capabilities',{sessionId:'default'}) as {tools:string[]};
    expect(defaultBusy.tools).not.toContain('get_goal');
    await client.rpc.request('session.cancel',{sessionId:'default'});
    await defaultApply;
    const defaultUpdated=await client.rpc.request('session.capabilities',{sessionId:'default'}) as {tools:string[]};
    expect(defaultUpdated.tools.filter(name=>goalTools.includes(name))).toEqual(['get_goal']);
  } catch(error){throw new Error((error instanceof Error ? error.stack : String(error))+'\n'+logs);} finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},60_000);
