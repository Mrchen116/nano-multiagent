import {createServer} from 'node:http';
import {registerNoopTaskContext} from './helpers/noop-task-context.js';
import { mkdir, mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it.each([{mode:'global',personal:false},{mode:'global',personal:true},{mode:'single_thread',personal:false}])('keeps forks equal and ordinary workers internal across cold resume ($mode, PA=$personal)', async ({mode,personal}) => {
  const home = await mkdtemp(join(tmpdir(), 'global-child-tools-'));
  let client: RuntimeClient | undefined, logs = '';
  const calls: { method: string; sessionId: string }[] = [];
  const config = { agentId: 'a', revision: '1', mode, workspace: home,
    provider: 'deepseek-official', model: 'deepseek-flash',
    toolAllowlist: ['subagent', 'subagent_fork', 'send_message', 'inbox', 'conversations', 'task_graph', ...(personal ? ['agent_creation'] : [])],
    features: { task_graph: true, intelligent_ui: true, memory_curation: false, skill_creation: false },
    approval: { dangerouslySkipPermissions: true },
    ...(personal ? { personal: { bindingId: 'binding', ownerId: 'owner', conversationId: 'dm', epoch: 1 } } : {}),
  };
  const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  const snapshots = async (): Promise<any[]> => (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
  try {
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile} from 'node:fs/promises';
export const name='global-child-tools-fixture';export const inject=['llm','agents','tools'];
export function apply(ctx){ctx.on('agent/created',({agent})=>{agent.ctx.tools.presentAs('native');});const seen=new Set();
ctx.on('llm/stream',async function*(o){
 const agent=ctx.agents.get(o.sessionId);if(!agent)throw Error('Expected actual Agent model request');
 await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({id:agent.id,parent:agent.session.header.parentSession,fork:agent.session.snapshotEvents().findLast(e=>agent.session.isOwnSeq(e.seq)&&e.type==='subagent/descriptor')?.data.provider==='fork',tools:o.tools,schemas:ctx.tools.schemas(agent),system:o.messages.filter(m=>m.role==='system'||m.role==='developer')})+'\\n');
 const user=o.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&'actorId'in m.source);
 const key=agent.id+':'+(user?.id??'child');const fresh=!seen.has(key);seen.add(key);
 const text=user?.content.find(b=>b.type==='text')?.text??'';
 let calls=[];
 if(fresh&&agent.id==='root')calls=text.startsWith('resume:')?[['send_message',{agent_id:text.slice(7),message:'Resume original work'}]]:[['subagent',{prompt:'Prepare findings',description:'Continuable work',run_in_background:true}],['subagent_fork',{prompt:'Check findings independently',description:'Fork work',run_in_background:false}]];
 if(fresh&&agent.id!=='root'&&agent.session.snapshotEvents().find(e=>e.type==='subagent/descriptor')?.data.mode==='continuable'){calls=[['send_message',{agent_id:agent.session.header.parentSession,message:'Findings ready for the parent to deliver'}]];if(agent.session.header.parentSession==='root')calls.push(['subagent',{prompt:'Verify one independent fact',description:'Second level',run_in_background:true}]);}
 if(calls.length){for(const[index,[name,args]]of calls.entries())yield{type:'block-end',index,block:{type:'tool-call',id:key+'-'+index,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
 yield{type:'block-end',index:0,block:{type:'text',text:'Finished internal work'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
    await prepareProfile(home, [{ insert: [{ id: 'global-child-tools-fixture', name: join(home, 'fixture.mjs') }] }]);
    const start = async () => {
      client = new RuntimeClient({ home, cwd: home, onLog: value => { logs += value; } });registerNoopTaskContext(client);
      client.rpc.handle('product.task_execution.snapshot', () => ({ kind: 'quiescent', tasks: [], repair_task_ids: [] }));
      client.rpc.handle('product.call', value => { calls.push(value as any); throw new Error('Internal coordination must not use product messaging'); });
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
      await client.rpc.request('session.ensure', binding);
    };
    const submit = async (id: string, text: string) => {
      await client!.rpc.request('session.submit', { sessionId: 'root', inputId: id, mode: 'followup',
        content: [{ type: 'text', text }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: id }) as any).terminal, { timeout: 15000 }).toBeTruthy();
    };
    await start(); await submit('work', 'Delegate independent work');
    await expect.poll(async () => { const rows = await client!.rpc.request('session.descendants', {sessionId:'root'}) as any[]; return rows.filter(row => row.events.some((event: any) => event.type === 'turn/end')).length; }).toBe(3);
    const before = await snapshots();
    const children = [...new Set(before.filter(row => row.id !== 'root').map(row => row.id))];
    expect(children).toHaveLength(3);
    const root = before.find(row => row.id === 'root');
    expect(root.schemas.map((tool: any) => tool.name)).toEqual(expect.arrayContaining([...(mode==='global'?['inbox']:[]), 'conversations', 'send_message', ...(personal ? ['send_user_message'] : [])]));
    const conversations = root.schemas.find((tool: any) => tool.name === 'conversations');
    expect(conversations.description).toContain('next_cursor');
    expect(conversations.description).toContain('partial');
    for (const name of ['keywords', 'query', 'sort', 'around_message_id', 'sender_source_id', 'cursor']) {
      expect(conversations.parameters.properties[name].description).toBeTruthy();
    }
    for (const row of before.filter(row => row.id !== 'root')) {
      if (row.fork) { expect(row.schemas).toEqual(root.schemas); expect(row.tools).toEqual(root.tools); continue; }
      const names = row.schemas.map((tool: any) => tool.name);
      if (mode === 'single_thread') expect(JSON.stringify(row.system)).toContain('You are an internal execution agent');
      expect(JSON.stringify(row.system)).not.toContain('Your final prose is delivered to the current conversation.');
      expect(JSON.stringify(row.system)).not.toContain('In Global mode this requires send_message; private prose is not delivery.');
      expect(names).not.toContain('inbox'); expect(names).not.toContain('conversations'); expect(names).not.toContain('send_user_message');expect(names).not.toContain('agent_creation');
      const send = row.schemas.find((tool: any) => tool.name === 'send_message');
      expect(send.parameters.properties).toHaveProperty('agent_id'); expect(send.parameters.properties).not.toHaveProperty('target');
      expect(JSON.stringify(row.tools)).not.toContain('"name":"inbox"');
      expect(JSON.stringify(row.tools)).not.toContain('"name":"conversations"');
    }
    expect(calls).toEqual([]);
    const descendants = await client!.rpc.request('session.descendants', { sessionId: 'root' }) as any[];
    for (const child of descendants) {
      expect(child.kind,JSON.stringify(child)).toBe('child');
      const results = child.events.filter((event: any) => event.type === 'tool/result' && typeof event.surfaceOp !== 'object');
      const continuable = child.events.find((event: any) => event.type === 'subagent/descriptor').data.mode === 'continuable';
      expect(results).toHaveLength(continuable ? (before.find(row => row.id === child.id)?.parent === 'root' ? 2 : 1) : 0);
      if (continuable) expect(results[0].data.message.isError, JSON.stringify(results[0].data.message)).not.toBe(true);
    }
    const firstChild = descendants.find(child => child.events.some((event:any) => event.type==='subagent/descriptor' && event.data.mode==='continuable')).id;
    if (mode === 'global') {
    await client!.rpc.request('trajectory.prepare', { observerId: 'root', rootAgentId: 'a', rootSessionId: 'root', sessionId: 'root', ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 });
    const runs = (await client!.rpc.request('trajectory.call', { observerId: 'root', method: 'trajectory/runs' }) as any).value;
    expect(runs).toHaveLength(2);
    // The ordinary child remains continuable after the runtime process is recreated.
    expect(runs.find((run: any) => run.provider === 'spawn').sessionId).toBe(firstChild);
    }
    await client!.shutdown(); client = undefined;
    await start(); await submit('resume', `resume:${firstChild}`);
    await expect.poll(async () => (await snapshots()).filter(row => row.id === firstChild).length).toBeGreaterThan(before.filter(row => row.id === firstChild).length);
    const after = await snapshots();
    expect(after.filter(row => row.id === firstChild).length).toBeGreaterThan(before.filter(row => row.id === firstChild).length);
    for (const row of after.filter(row => row.id === firstChild)) {
      expect(row.schemas.map((tool: any) => tool.name)).not.toContain('inbox');
      expect(row.schemas.find((tool: any) => tool.name === 'send_message').parameters.properties).not.toHaveProperty('target');
    }
    expect(calls).toEqual([]);
  } catch (error) { const observation = await client?.rpc.request('session.observe', {sessionId:'root'}).catch(() => undefined); throw new Error(`${error}\n${logs}\n${JSON.stringify((observation as any)?.events?.filter((event: any) => ['tool/result', 'turn/end'].includes(event.type)))}`, { cause: error }); }
  finally { if (client) await client.shutdown(); await rm(home, { recursive: true, force: true }); }
}, 40000);

it.each([false,true])('gives Global workers native work tools and native nested context on the provider wire (PA=%s)', async personal => {
  const home=await mkdtemp(join(tmpdir(),'global-work-defaults-'));
  let client:RuntimeClient|undefined,logs='';
  const wire:{id:string;depth:number;fork:boolean;model:string;tools:any[];system:any;messages:any[]}[]=[];
  const seen=new Set<string>();const resumed=new Set<string>();
  const metadata=async():Promise<any[]> => (await readFile(join(home,'agents.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
  const server=createServer(async(req,res)=>{
    let text='';for await(const chunk of req)text+=chunk;
    const body=JSON.parse(text),id=String(req.headers['x-agent-session-id']);
    const meta=(await metadata()).findLast(row=>row.id===id);
    if(!meta){res.writeHead(500);res.end('Missing native session identity');return;}
    wire.push({...meta,model:body.model,tools:body.tools.map((tool:any)=>({...tool,parameters:tool.input_schema})),system:body.system,messages:body.messages});
    const fresh=!seen.has(id);seen.add(id);
    let calls:any[]=[];
    const resume=body.messages.map((m:any)=>JSON.stringify(m)).findLast((m:string)=>m.includes('resume:'))?.match(/resume:([a-z0-9-]+):([a-z-]+)/);
    const continuation=body.messages.map((m:any)=>JSON.stringify(m)).findLast((m:string)=>m.includes('continue-worker:'))?.match(/continue-worker:([a-z-]+)/);
    if(id==='root'&&resume&&!resumed.has(resume[2]!)){resumed.add(resume[2]!);calls=[['send_message',{agent_id:resume[1],message:'continue-worker:'+resume[2]}]];}
    else if(fresh&&meta.depth===0)calls=[['subagent',{prompt:'WHOLE_ASSIGNMENT_SENTINEL: prepare a complete finding',description:'whole task',run_in_background:true}]];
    if(fresh&&meta.depth===1)calls=[['read',{file_path:join(home,'AGENTS.md')}],['subagent',{prompt:'CHILD_ASSIGNMENT_SENTINEL: check one fact',description:'one fact',run_in_background:true}],['subagent_fork',{prompt:'Check this delegated fact',description:'fork fact',run_in_background:false}]];
    // The second-level continuation is steered only by its original direct parent.
    if(meta.depth===1&&continuation&&!resumed.has('worker-'+continuation[1])){resumed.add('worker-'+continuation[1]);
      const nested=(await metadata()).find(row=>row.depth===2&&!row.fork);
      calls=[['send_message',{agent_id:nested.id,message:'Recheck the same delegated fact'}]];
    }
    const blocks=calls.length?calls.map(([name,input],index)=>({type:'tool_use',id:id+'-'+wire.length+'-'+index,name,input})):[{type:'text',text:'Done'}];
    res.writeHead(200,{'content-type':'text/event-stream'});
    const emit=(type:string,data:object)=>res.write(`event: ${type}\ndata: ${JSON.stringify({type,...data})}\n\n`);
    emit('message_start',{message:{id:'fixture',type:'message',role:'assistant',model:body.model,content:[],stop_reason:null,usage:{input_tokens:20,output_tokens:0}}});
    blocks.forEach((block:any,index:number)=>{
      emit('content_block_start',{index,content_block:block.type==='tool_use'?{...block,input:{}}:block});
      if(block.type==='tool_use')emit('content_block_delta',{index,delta:{type:'input_json_delta',partial_json:JSON.stringify(block.input)}});
      emit('content_block_stop',{index});
    });
    emit('message_delta',{delta:{stop_reason:calls.length?'tool_use':'end_turn',stop_sequence:null},usage:{output_tokens:5}});emit('message_stop',{});res.end();
  });
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  const config={agentId:'worker-owner',displayName:'ROOT_IDENTITY_SENTINEL',revision:'1',mode:'global',workspace:home,
    systemPrompt:'ROOT_PERSONA_SENTINEL',provider:'fixture',model:'fixture',toolAllowlist:['subagent','send_message','read','write','skill',...(personal?['agent_creation']:[])],
    skillRoots:[{path:join(home,'skills'),source:'workspace'}],skillSelection:{mode:'explicit_allowlist',names:['nano-interactive-ui','worker-old']},
    features:{task_graph:false,intelligent_ui:true,memory_curation:false,skill_creation:false,heartbeat:true,cron_scheduling:false},
    approval:{dangerouslySkipPermissions:true},...(personal?{personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}}:{})};
  const withoutCache=(value:unknown)=>JSON.parse(JSON.stringify(value,(key,item)=>key==='cache_control'?undefined:item));
  try {
    await writeFile(join(home,'AGENTS.md'),'WORKSPACE_INSTRUCTIONS_SENTINEL');
    for(const name of ['nano-interactive-ui','worker-old','worker-new']){
      const dir=join(home,'skills',name);
      await mkdir(dir,{recursive:true});
      await writeFile(join(dir,'SKILL.md'),'---\nname: '+name+'\ndescription: Fixture '+name+'\n---\nWorker instructions');
    }
    await writeFile(join(home,'fixture.mjs'),`import {appendFile} from 'node:fs/promises';
export const name='work-defaults';export const inject=['tools','agents','llm'];
export function apply(ctx){ctx.on('agent/created',({agent})=>{agent.ctx.tools.presentAs('native');});ctx.on('llm/stream',async function*(o,next){const agent=ctx.agents.get(o.sessionId);await appendFile(process.env.DSH_HOME+'/agents.jsonl',JSON.stringify({id:agent.id,depth:agent.session.header.delegationDepth??0,fork:agent.session.snapshotEvents().findLast(e=>agent.session.isOwnSeq(e.seq)&&e.type==='subagent/descriptor')?.data.provider==='fork'})+'\\n');yield*next();});}`);
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'anthropic-messages',baseURL:`http://127.0.0.1:${(server.address() as any).port}`,apiKeyEnv:'NANO_TEST_KEY',models:[{id:'fixture',contextWindow:200000},{id:'replacement',contextWindow:200000}],retryPolicy:{mode:'normal',maxRetries:0}}}}},{insert:[{id:'work-defaults',name:join(home,'fixture.mjs')}]}]);
    const start=async()=>{
      client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});registerNoopTaskContext(client);
      client.rpc.handle('product.task_execution.snapshot',()=>({kind:'quiescent',tasks:[],repair_task_ids:[]}));
      client.rpc.handle('product.call',()=>{throw Error('Internal coordination must not use product messaging');});
      await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
      await client.rpc.request('session.ensure',{sessionId:'root',agentId:config.agentId,revision:'1',ownerId:'owner',cwd:home});
    };
    await start();
    const caps=await client!.rpc.request('session.capabilities',{sessionId:'root'}) as any;
    expect(caps.tools).not.toContain('subagent_fork');expect(caps.tools).toContain('read');
    const submit=(inputId:string,text:string)=>client!.rpc.request('session.submit',{sessionId:'root',inputId,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
    await submit('delegate','Do one complete task');
    await expect.poll(()=>wire.some(row=>row.depth===1)).toBe(true);
    const root=wire.find(row=>row.depth===0)!;
    for(const row of [root,wire.find(row=>row.depth===1)!]){
      const system=JSON.stringify(row.system);
      expect(system.includes('sender.is_owner')).toBe(personal);
      expect(system.includes('delivery=observer')).toBe(personal);
    }
    const rootSystem = JSON.stringify(root.system);
    if (personal) {
      expect(rootSystem).toContain('load nano-interactive-ui and use send_message to give the owner an editable TextArea');
      expect(rootSystem).toContain('Deliver the draft card in your private Nano IM conversation with the owner');
      expect(rootSystem).toContain('continuing your own conversation after checking with the owner');
      expect(rootSystem).toContain('Use send_user_message when the owner delegates their reply');
      expect(rootSystem).toContain('Both tools use the same outbound review for messages to others');
    }
    expect(rootSystem).toContain('Follow task-specific delivery guidance');
    const inbox=root.tools.find(tool=>tool.name==='inbox');
    expect(inbox.parameters.properties.action.enum.includes('review')).toBe(personal);
    expect('message_id' in inbox.parameters.properties).toBe(personal);
    const first=wire.find(row=>row.depth===1)!;
    expect(JSON.stringify(first.system)).not.toContain('ComposeMessage adopts');
    expect(JSON.stringify(first.system)).toContain('nano-interactive-ui');
    expect(JSON.stringify(root.system)).toContain('HEARTBEAT_OK');
    expect(JSON.stringify(first.system)).not.toContain('HEARTBEAT_OK');
    expect(first.tools.map(tool=>tool.name)).toEqual(expect.arrayContaining(['read','write','bash','subagent','subagent_fork','send_message','list_agents','interrupt_agent']));
    await expect.poll(()=>wire.some(row=>row.depth===2&&!row.fork)).toBe(true);
    const second=wire.find(row=>row.depth===2&&!row.fork)!;
    const secondContext=JSON.stringify([second.system,second.messages]);
    for(const forbidden of ['ROOT_IDENTITY_SENTINEL','ROOT_PERSONA_SENTINEL','You are an internal execution agent','You execute an internal task for','main Agent owns public delivery','Heartbeat is a system wake','Role: personal assistant','Role: independent expert'])expect(secondContext).not.toContain(forbidden);
    expect(secondContext).toContain('WORKSPACE_INSTRUCTIONS_SENTINEL');expect(secondContext).toContain('Your parent agent id is');
    for(const row of [first,second]){
      const names=row.tools.map(tool=>tool.name);expect(names).not.toContain('inbox');expect(names).not.toContain('conversations');
      expect(names).not.toContain('send_user_message');expect(names).not.toContain('personal_sources');expect(names).not.toContain('agent_creation');
      expect(row.tools.find(tool=>tool.name==='send_message').parameters.properties).not.toHaveProperty('target');
    }
    await expect.poll(async()=>(await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[]).filter(row=>row.events.some((event:any)=>event.type==='turn/end')).length).toBe(3);
    const fork=wire.find(row=>row.fork)!;expect(fork.tools).toEqual(first.tools);expect(withoutCache(fork.system)).toEqual(withoutCache(first.system));
    const children=await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[];
    expect(children.find(row=>row.id===first.id).events.filter((event:any)=>event.type==='tool/result' && typeof event.surfaceOp !== 'object').every((event:any)=>!event.data.message.isError)).toBe(true);
    const beforeFirst=wire.filter(row=>row.id===first.id).length,beforeSecond=wire.filter(row=>row.id===second.id).length;
    await client!.shutdown();client=undefined;await start();
    await submit('resume-worker','resume:'+first.id+':restart');
    await expect.poll(()=>wire.filter(row=>row.id===first.id).length).toBeGreaterThan(beforeFirst);
    await expect.poll(()=>wire.filter(row=>row.id===second.id).length).toBeGreaterThan(beforeSecond);
    const restoredFirst=wire.findLast(row=>row.id===first.id)!,restoredSecond=wire.findLast(row=>row.id===second.id)!;
    expect(restoredFirst.tools.map(tool=>tool.name)).toContain('subagent_fork');
    expect(JSON.stringify(restoredSecond.system)).not.toContain('ROOT_IDENTITY_SENTINEL');
    expect(JSON.stringify(restoredSecond.messages)).toContain('Recheck the same delegated fact');
    expect(new Set(wire.map(row=>row.id)).size).toBe(4);

    const requests = (id: string) => wire.filter(row => row.id === id);
    const normalize = (messages: any[]) => messages.map(message => ({
      ...message,
      content: typeof message.content === 'string' ? [{type:'text',text:message.content}] : message.content,
    }));
    const equal = (a: unknown, b: unknown) => JSON.stringify(withoutCache(a)) === JSON.stringify(withoutCache(b));
    const fieldsChanged = (before: typeof first, after: typeof first) => {
      const prior = normalize(before.messages);
      return [
        ...(before.model === after.model ? [] : ['route']),
        ...(equal(before.system, after.system) ? [] : ['system']),
        ...(equal(before.tools, after.tools) ? [] : ['tools']),
        ...(equal(prior, normalize(after.messages).slice(0, prior.length)) ? [] : ['messages']),
      ];
    };
    const childrenUnderTest = [first, second];
    const settle = async () => {
      await expect.poll(async () => {
        const root = await client!.rpc.request('session.observe',{sessionId:'root'}) as any;
        const children = await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[];
        const cursors = Object.fromEntries([['root',root.throughSeq],...children.map(row=>[row.id,row.throughSeq])]);
        const modelVersions = Object.fromEntries([['root',root.modelVersion],...children.map(row=>[row.id,row.modelVersion])]);
        return (await client!.rpc.request('session.work.check',{sessionId:'root',cursors,modelVersions}) as any).settled;
      },{timeout:15_000}).toBe(true);
    };
    await settle();
    for (const child of childrenUnderTest) {
      const rows = requests(child.id);
      for (let i = 1; i < rows.length; i++) {
        expect(fieldsChanged(rows[i-1]!, rows[i]!), 'L'+child.depth+' continuation '+i).toEqual([]);
      }
    }

    let current = {...config};
    const apply = async (revision: string, change: Partial<typeof config>) => {
      current = {...current,...change,revision};
      const applied = await client!.rpc.request('configuration.apply',current);
      expect(applied,JSON.stringify(applied)).toMatchObject({effective:true});
    };
    const replay = async (label: string, change: () => Promise<unknown>, expected: string[][],
                          addedText?: string) => {
      const counts = childrenUnderTest.map(child => requests(child.id).length);
      await change();
      await submit('probe-'+label,'resume:'+first.id+':'+label);
      await expect.poll(() => childrenUnderTest.every((child,i) => requests(child.id).length > counts[i]!), {timeout:15_000}).toBe(true);
      await settle();
      for (const [i, child] of childrenUnderTest.entries()) {
        const rows = requests(child.id);
        const firstNew = counts[i]!;
        const previous = rows[firstNew-1]!;
        const next = rows[firstNew]!;
        // The strict TLC invariant reports these observed changes for policy review.
        expect(fieldsChanged(previous,next), label+' L'+child.depth).toEqual(expected[i]);
        if (addedText) expect(JSON.stringify(next.messages.slice(previous.messages.length))).toContain(addedText);
        for (let j = firstNew+1; j < rows.length; j++) {
          expect(fieldsChanged(rows[j-1]!,rows[j]!), label+' L'+child.depth+' continuation').toEqual([]);
        }
      }
    };
    await replay('root-settings', () => apply('root-settings', {
      systemPrompt:'ROOT_PERSONA_CHANGED',toolAllowlist:config.toolAllowlist.filter(name=>name!=='write'),
    }), [[],[]]);
    await replay('rename', () => apply('rename', {displayName:'ROOT_RENAMED_SENTINEL'}), [['system'],[]]);
    await replay('feature', () => apply('feature', {features:{...config.features,intelligent_ui:false}}), [['system'],[]]);
    await replay('skill', () => apply('skill', {
      skillSelection:{mode:'explicit_allowlist',names:['worker-new']},
    }), [[],[]], 'worker-new');
    await replay('workspace', () => writeFile(join(home,'AGENTS.md'),'UPDATED_WORKSPACE_SENTINEL'),
      [[],[]], 'UPDATED_WORKSPACE_SENTINEL');
    await replay('model', () => apply('model', {model:'replacement'}), [['route'],['route']]);
    await replay('context-plugin', async () => {
      await client!.rpc.request('plugins.manage',{agentId:config.agentId,action:'set_bundle',target:'dsh-agent-context',enabled:false});
      await expect.poll(async () => {
        const state = await client!.rpc.request('plugins.manage',{agentId:config.agentId,action:'list_bundles'}) as {
          pending?: unknown; entries: {name:string;enabled:boolean}[];
        };
        return !state.pending && state.entries.some(entry => entry.name === 'dsh-agent-context' && !entry.enabled);
      },{timeout:15_000}).toBe(true);
    }, [['system','tools'],['system','tools']]);

  } catch(error){throw new Error(String(error)+'\n'+logs,{cause:error});}
  finally {await client?.shutdown();server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));await rm(home,{recursive:true,force:true});}
},120_000);

it('withdraws a root tool while its worker keeps the native capability and the root handles new input', async()=>{
  const home=await mkdtemp(join(tmpdir(),'global-worker-selection-'));
  let client:RuntimeClient|undefined,logs='';
  const config={agentId:'a',revision:'1',mode:'global',workspace:home,provider:'deepseek-official',model:'deepseek-flash',
    toolAllowlist:['subagent','send_message','read'],features:{task_graph:false,intelligent_ui:false,memory_curation:false,skill_creation:false},approval:{dangerouslySkipPermissions:true}};
  try {
    await writeFile(join(home,'fixture.mjs'),`import {writeFile} from 'node:fs/promises';
export const name='worker-selection';export const inject=['llm','agents','tools'];
export function apply(ctx){let release;const gate=new Promise(resolve=>release=resolve);const seen=new Set();
ctx.on('tools/pre-execute',async(exec,next)=>{const decision=await next();if(exec.name==='read'&&exec.agent?.session.header.origin==='subagent'){exec.signal.addEventListener('abort',release,{once:true});await writeFile(process.env.DSH_HOME+'/child-reading','yes');await gate;}return decision;});
ctx.on('llm/stream',async function*(o){const agent=ctx.agents.get(o.sessionId);const user=o.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&'actorId'in m.source);const text=user?.content?.find(b=>b.type==='text')?.text??'';
if(agent.id==='root'&&text==='release'){release();await writeFile(process.env.DSH_HOME+'/root-received','yes');}
const fresh=!seen.has(agent.id);seen.add(agent.id);let calls=[];
if(fresh&&agent.id==='root')calls=[['subagent',{prompt:'Read the workspace instructions and return findings',description:'one complete task',run_in_background:true}]];
if(agent.id!=='root'){await writeFile(process.env.DSH_HOME+'/child-tools.json',JSON.stringify(ctx.tools.schemas(agent).map(tool=>tool.name)));if(fresh)calls=[['read',{file_path:process.env.DSH_HOME+'/fixture.mjs'}]];}
if(calls.length){for(const[index,[name,args]]of calls.entries())yield{type:'block-end',index,block:{type:'tool-call',id:agent.id+'-'+index,name,arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home,[{insert:[{id:'worker-selection',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text;}});registerNoopTaskContext(client);
    client.rpc.handle('product.task_execution.snapshot',()=>({kind:'quiescent',tasks:[],repair_task_ids:[]}));
    await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'root',agentId:'a',revision:'1',ownerId:'owner',cwd:home});
    const submit=(inputId:string,text:string)=>client!.rpc.request('session.submit',{sessionId:'root',inputId,mode:'followup',content:[{type:'text',text}],source:{kind:'human',actorId:'owner',channel:'test',messageId:inputId}});
    await submit('task','Read an independent item');
    await expect.poll(()=>readFile(join(home,'child-reading'),'utf8').catch(()=>'' )).toBe('yes');
    const usage=await client.rpc.request('configuration.usage',{agentId:'a'}) as any;
    expect(usage.busy).not.toContainEqual({kind:'tool',name:'read'});
    const applying=client.rpc.request('configuration.apply',{...config,revision:'2',toolAllowlist:['subagent','send_message']});void applying.catch(()=>{});
    await expect.poll(async()=>(await client!.rpc.request('session.capabilities',{sessionId:'root'}) as any).tools,{timeout:8000}).not.toContain('read');
    await submit('release','release');
    await expect.poll(()=>readFile(join(home,'root-received'),'utf8').catch(()=>'' )).toBe('yes');
    await applying;
    expect(JSON.parse(await readFile(join(home,'child-tools.json'),'utf8'))).toContain('read');
    const children=await client.rpc.request('session.descendants',{sessionId:'root'}) as any[];
    await expect.poll(async()=>{
      const rows=await client!.rpc.request('session.descendants',{sessionId:'root'}) as any[];
      return rows[0]?.events.some((e:any)=>e.type==='tool/result' && typeof e.surfaceOp !== 'object'&&!e.data.message.isError);
    }).toBe(true);
    expect(children).toHaveLength(1);
  } catch(error){throw new Error(String(error)+'\n'+logs,{cause:error});}
  finally {await client?.shutdown();await rm(home,{recursive:true,force:true});}
},30_000);
