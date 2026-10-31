import {registerNoopTaskContext} from './helpers/noop-task-context.js';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it.each([false, true])('keeps Global product tools on the root across spawn, fork and cold resume (PA=%s)', async personal => {
  const home = await mkdtemp(join(tmpdir(), 'global-child-tools-'));
  let client: RuntimeClient | undefined, logs = '';
  const calls: { method: string; sessionId: string }[] = [];
  const config = { agentId: 'a', revision: '1', mode: 'global', workspace: home,
    provider: 'deepseek-official', model: 'deepseek-flash',
    toolAllowlist: ['subagent', 'subagent_fork', 'send_message', 'inbox', 'conversations', 'task_graph'],
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
 await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({id:agent.id,parent:agent.session.header.parentSession,tools:o.tools,schemas:ctx.tools.schemas(agent),system:o.messages.filter(m=>m.role==='system'||m.role==='developer')})+'\\n');
 const user=o.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&'actorId'in m.source);
 const key=agent.id+':'+(user?.id??'child');const fresh=!seen.has(key);seen.add(key);
 const text=user?.content.filter(b=>b.type==='text').map(b=>b.text).join('')??'';
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
    expect(root.schemas.map((tool: any) => tool.name)).toEqual(expect.arrayContaining(['inbox', 'conversations', 'send_message', ...(personal ? ['send_user_message'] : [])]));
    for (const row of before.filter(row => row.id !== 'root')) {
      const names = row.schemas.map((tool: any) => tool.name);
      expect(JSON.stringify(row.system)).toContain('You are an internal execution agent');
      expect(JSON.stringify(row.system)).not.toContain('In Global mode this requires send_message; private prose is not delivery.');
      expect(names).not.toContain('inbox'); expect(names).not.toContain('conversations'); expect(names).not.toContain('send_user_message');
      const send = row.schemas.find((tool: any) => tool.name === 'send_message');
      expect(send.parameters.properties).toHaveProperty('agent_id'); expect(send.parameters.properties).not.toHaveProperty('target');
      expect(JSON.stringify(row.tools)).not.toContain('"name":"inbox"');
      expect(JSON.stringify(row.tools)).not.toContain('"name":"conversations"');
    }
    expect(calls).toEqual([]);
    const descendants = await client!.rpc.request('session.descendants', { sessionId: 'root' }) as any[];
    for (const child of descendants) {
      const results = child.events.filter((event: any) => event.type === 'tool/result');
      const continuable = child.events.find((event: any) => event.type === 'subagent/descriptor').data.mode === 'continuable';
      expect(results).toHaveLength(continuable ? (before.find(row => row.id === child.id)?.parent === 'root' ? 2 : 1) : 0);
      if (continuable) expect(results[0].data.message.isError, JSON.stringify(results[0].data.message)).not.toBe(true);
    }
    await client!.rpc.request('trajectory.prepare', { observerId: 'root', rootAgentId: 'a', rootSessionId: 'root', sessionId: 'root', ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 });
    const runs = (await client!.rpc.request('trajectory.call', { observerId: 'root', method: 'trajectory/runs' }) as any).value;
    expect(runs).toHaveLength(2);
    // The ordinary child remains continuable after the runtime process is recreated.
    const firstChild = runs.find((run: any) => run.provider === 'spawn').sessionId;
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
