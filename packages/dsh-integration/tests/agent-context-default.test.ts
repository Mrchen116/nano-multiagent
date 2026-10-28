import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

const contextTools = ['get_context_remaining', 'history', 'new_context', 'notes'];

it('defaults new and existing Agents to context management and persists explicit workspace opt-out', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-context-default-'));
  const workspaces = Object.fromEntries(['fresh', 'old', 'disabled'].map(name => [name, join(home, name)]));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    for (const workspace of Object.values(workspaces)) await mkdir(workspace);
    for (const name of ['old', 'disabled']) {
      const dir = join(workspaces[name]!, '.nanoassistant', 'dsh-plugins'); await mkdir(dir, {recursive:true});
      await writeFile(join(dir, 'package.json'), JSON.stringify({name:`profile-${name}`,private:true,
        dependencies:name === 'disabled' ? {'dsh-agent-context':'0.3.0'} : {},
        dsh:{profile:{bundles:[]}},custom:{keep:'EXISTING_USER_FIELD'}}));
      await writeFile(join(dir, 'cordis.patch.yml'), '[]\n');
    }
    const base = {knowledge:{memoryMode:'legacy'},revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:[]};
    const agents = [
      ...Object.entries(workspaces).map(([agentId,workspace]) => ({...base,agentId,workspace})),
      {...base,agentId:'peer',workspace:workspaces.fresh},
      {...base,agentId:'sdk'},
      {...base,agentId:'global',mode:'global',workspace:workspaces.fresh},
    ];
    const bindings = agents.map(agent => ({sessionId:`context-${agent.agentId}`,agentId:agent.agentId,revision:'1',ownerId:'owner',cwd:home}));
    const start = async (restore = false) => {
      client = new RuntimeClient({home,cwd:home,onLog:text => {logs += text;}});
      await client.rpc.request('initialize',{protocol:1,agents,bindings:restore ? bindings : []});
      for (const binding of bindings) await client.rpc.request('session.ensure',binding);
    };
    const tools = async (id:string) => ((await client!.rpc.request('session.capabilities',{sessionId:`context-${id}`})) as {tools:string[]}).tools;
    type View = {pending?:unknown;error?:string;entries:{name:string;enabled:boolean;removable:boolean;state:string}[]};
    const view = (id:string) => client!.rpc.request('plugins.manage',{agentId:id,action:'list_bundles'}) as Promise<View>;
    const toggle = async (enabled:boolean) => {
      await client!.rpc.request('plugins.manage',{agentId:'fresh',action:'set_bundle',target:'dsh-agent-context',enabled});
      await expect.poll(async () => (await view('fresh')).pending).toBeUndefined();
      expect((await view('fresh')).error).toBeUndefined();
    };
    await prepareProfile(home); await start();
    for (const id of ['fresh','old','peer','sdk','global']) {
      expect(await tools(id),id).toEqual(expect.arrayContaining(contextTools));
      expect(await tools(id),id).not.toContain('bash');
      expect(await tools(id),id).not.toContain('plugin_manager');
    }
    expect(await tools('disabled')).toEqual([]);
    expect((await view('fresh')).entries.find(entry => entry.name === 'dsh-agent-context')).toMatchObject({enabled:true,removable:false,state:'enabled'});
    expect(JSON.parse(await readFile(join(workspaces.old!,'.nanoassistant','dsh-plugins','package.json'),'utf8')).custom).toEqual({keep:'EXISTING_USER_FIELD'});
    await client!.rpc.request('plugins.manage',{agentId:'fresh',action:'remove_bundle',target:'dsh-agent-context'});
    await expect.poll(async () => (await view('fresh')).pending).toBeUndefined();
    expect((await view('fresh')).error).toContain('cannot be removed');
    expect(await tools('fresh')).toEqual(expect.arrayContaining(contextTools));
    await toggle(false);
    expect(await tools('fresh')).toEqual([]); expect(await tools('peer')).toEqual([]);
    expect(await tools('old')).toEqual(expect.arrayContaining(contextTools));
    await client!.shutdown(); client = undefined; await start(true);
    expect(await tools('fresh')).toEqual([]); expect(await tools('peer')).toEqual([]);
    expect(await tools('disabled')).toEqual([]);
    expect(await tools('old')).toEqual(expect.arrayContaining(contextTools));
    await toggle(true);
    expect((await tools('fresh')).sort()).toEqual(contextTools);
    expect((await tools('peer')).sort()).toEqual(contextTools);
  } catch (error) { throw new Error(`${String(error)}\n${logs}`,{cause:error}); }
  finally { if (client) await client.shutdown().catch(() => {}); await rm(home,{recursive:true,force:true}); }
}, 30_000);


it('gives a private Personal Agent the same default context tools without business permissions', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-pa-context-default-'));
  let client: RuntimeClient | undefined;
  try {
    await prepareProfile(home); client = new RuntimeClient({home,cwd:home});
    const config = {agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:[],
      personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}};
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'pa-default',agentId:'pa',ownerId:'owner',revision:'1',cwd:home});
    const view = await client.rpc.request('session.capabilities',{sessionId:'pa-default'}) as {tools:string[]};
    expect(view.tools).toEqual(expect.arrayContaining(contextTools));
    expect(view.tools).not.toContain('bash'); expect(view.tools).not.toContain('plugin_manager');
  } finally { if (client) await client.shutdown().catch(() => {}); await rm(home,{recursive:true,force:true}); }
}, 15_000);

it.each(['nano','codex','dsh'] as const)('allows bounded internal context operations with %s Auto off while retaining child business denial', async (rules) => {
  const home = await mkdtemp(join(tmpdir(), 'nano-context-approval-'));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    await writeFile(join(home,'probe.mjs'), `import {writeFile} from 'node:fs/promises';
export const inject=['tools','llm','subagents'];
export function apply(ctx) {
  ctx.tools.register({name:'context_forbidden',description:'A business side effect',parameters:{type:'object',properties:{}},output:{schema:{type:'object'},render:(_a,r)=>[{type:'text',text:JSON.stringify(r)}]},execute:()=>{throw Error('BUSINESS_TOOL_EXECUTED');}});
  ctx.on('tools/pre-execute',(exec,next)=>exec.name==='notes'&&exec.arguments.path==='blocked'?{kind:'deny',reason:'EXPLICIT_CONTEXT_DENY'}:next());
  ctx.on('llm/stream',async function*(){yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};});
  ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{
    try {
      const run=await ctx.subagents.start('spawn',{parent:agent,prompt:[{type:'text',text:'context probe'}],signal:new AbortController().signal});
      await run.result; const child=run.localAgent;
      const probe=async(target)=>{const results=[];for(const [name,args] of [['notes',{action:'write',path:'checkpoint',text:'PRIVATE_PROGRESS'}],['history',{action:'list_windows'}],['get_context_remaining',{}],['new_context',{}],['notes',{action:'write',path:'blocked',text:'must not write'}],['context_forbidden',{}]]) results.push({name,blocked:args.path==='blocked',result:await ctx.tools.execute({name,callId:'probe-'+target.id+'-'+name,arguments:args,agent:target,signal:new AbortController().signal})});return results;};
      await writeFile(process.env.DSH_HOME+'/probe.json',JSON.stringify({root:await probe(agent),child:await probe(child)}));await run.dispose();
    } catch(error) {await writeFile(process.env.DSH_HOME+'/probe.json',JSON.stringify({error:String(error)}));}
  },0);});
}`);
    await prepareProfile(home,[{insert:[{id:'context-probe',name:join(home,'probe.mjs')}]}]);
    const {approvalDefaults} = await import('../../product-contracts/src/approval.js');
    client = new RuntimeClient({home,cwd:home,onLog:text => {logs+=text;}});
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'global',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:['context_forbidden'],approval:{...approvalDefaults,enabled:false,rules,globalRoot:home}}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'root',agentId:'global',ownerId:'owner',revision:'1',cwd:home});
    await expect.poll(async()=>readFile(join(home,'probe.json'),'utf8').catch(()=>''),{timeout:15000}).not.toBe('');
    const result = JSON.parse(await readFile(join(home,'probe.json'),'utf8'));
    expect(result.error,JSON.stringify(result)).toBeUndefined();
    for (const key of ['root','child']) {
      for (const entry of result[key]) {
        if (entry.name === 'get_context_remaining' && key === 'root') continue;
        expect(entry.result.isError,JSON.stringify({key,entry})).toBe(entry.name === 'context_forbidden' || entry.blocked);
        if (entry.blocked) expect(JSON.stringify(entry.result)).toContain('EXPLICIT_CONTEXT_DENY');
      }
      expect(JSON.stringify(result[key].find((entry:{name:string})=>entry.name==='context_forbidden'))).not.toContain('BUSINESS_TOOL_EXECUTED');
    }
  } catch(error){throw new Error(`${String(error)}\n${logs}`,{cause:error});}
  finally {if(client)await client.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
}, 25_000);
