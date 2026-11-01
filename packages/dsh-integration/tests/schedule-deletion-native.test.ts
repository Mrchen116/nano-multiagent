import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {join} from 'node:path';
import {expect, it} from 'vitest';
import {prepareProfile, RuntimeClient} from '../lib/client.js';
import {registerNoopTaskHosts} from './helpers/noop-task-hosts.js';

type Event = {seq: number; type: string; data: any};
type Child = {id: string; kind: string; events: Event[]};
type Manifest = {parent: string; child: string; oneShot: string};
type Request = {sessionId: string; messages: any[]; tools?: {name: string}[]; model?: string; provider?: string; reasoningEffort?: string};

// Native Schedule refuses new delegated-child schedules. Seed legacy rows only
// through its exported authority; native deletion still supports those rows.
const fixture = String.raw`import {appendFile, writeFile} from 'node:fs/promises';
import {createAfterScheduleRecord, ScheduleId, scheduleDomain} from ${JSON.stringify(pathToFileURL(createRequire(import.meta.url).resolve('@deepseek-ai/dsh-schedule')).href)};
export const name='schedule-delete-fixture';
export const inject=['llm','subagents','agents','agentPresets','sessions'];
export function apply(ctx) {
  let seeded=false;
  ctx.on('agent/created',({agent,source})=>appendFile(process.env.DSH_HOME+'/created.jsonl',JSON.stringify({id:agent.id,source,parent:agent.session.header.parentSession,depth:agent.session.header.delegationDepth})+'\n'));
  ctx.on('agent/pre-step',async({agent,messages,signal},next)=>{
    if(agent.id==='root'&&!seeded&&messages.some(message=>message.id==='seed')) {
      seeded=true;
      try {
        const options={provider:'deepseek-official',model:'deepseek-flash'};
        const first=await ctx.subagents.startContinuable({provider:'spawn',label:'original-parent',request:{parent:agent,prompt:[{type:'text',text:'Parent original history'}],persona:'NATIVE PARENT PERSONA',toolFilter:{allow:['read']},agentOptions:options},signal});
        const parent=ctx.agents.get(first.childId);await parent.whenIdle();
        const second=await ctx.subagents.startContinuable({provider:'spawn',label:'original-child',request:{parent,prompt:[{type:'text',text:'Child original history'}],persona:'NATIVE CHILD PERSONA',toolFilter:{allow:['read']},agentOptions:options},signal});
        const child=ctx.agents.get(second.childId);await child.whenIdle();
        const once=await ctx.subagents.start('spawn',{parent:agent,prompt:[{type:'text',text:'One-shot original history'}],signal});
        await once.result;await once.dispose();
        const unrelated=await ctx.agents.create({sessionId:'unmanaged-native-root',meta:{cwd:agent.session.header.cwd,agentPreset:agent.session.header.agentPreset},setup:async child=>{await ctx.agentPresets.mount(child,agent.session.header.agentPreset);}});
        await ctx.sessions.flush(unrelated.agent.session);await unrelated.dispose();
        const facility=await new Promise(resolve=>ctx.isolate('storageDomain',Symbol.for('nano-storage-domain:a')).inject(['storageDomain'],child=>resolve(child.storageDomain)));
        const existing=facility.get(scheduleDomain.name),lease=existing??await facility.open(scheduleDomain);
        try {for(const [id,sessionId] of [['legacy-child',second.childId],['legacy-one-shot',once.id]]){
          const record=createAfterScheduleRecord(ScheduleId(id),'Legacy saved instructions',3600,Date.now(),'Legacy child schedule');
          await lease.table('tasks').put(ScheduleId(id),{sessionId,record,status:'inactive'});
        }} finally {if(!existing)await lease.close();}
        await writeFile(process.env.DSH_HOME+'/ready.json',JSON.stringify({parent:first.childId,child:second.childId,oneShot:once.id}));
      } catch(error) {await writeFile(process.env.DSH_HOME+'/fixture-error',String(error));throw error;}
    }
    return next();
  });
  ctx.on('llm/stream',async function*(options){
    await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(options)+'\n');
    yield {type:'block-end',index:0,block:{type:'text',text:'original native turn complete'}};
    yield {type:'finish',reason:{kind:'stop'}};
  });
}`;

async function harness() {
  const home = await mkdtemp(join(tmpdir(), 'nano-schedule-deletion-native-'));
  await Promise.all(['a','b'].map(agentId=>mkdir(join(home,agentId))));
  const agents = ['a', 'b'].map(agentId => ({agentId, workspace: join(home,agentId), revision: '1', provider: 'deepseek-official', model: 'deepseek-flash',
    features: {cron_scheduling: true, heartbeat: false, dreaming: false}, toolAllowlist: ['read', 'write', 'subagent', 'schedule_create']}));
  const bindings = agents.map(agent => ({sessionId: agent.agentId === 'a' ? 'root' : 'root-b', agentId: agent.agentId, ownerId: 'owner', revision: '1', cwd: agent.workspace}));
  let client: RuntimeClient | undefined;
  let logs = '';
  const requests = async (): Promise<Request[]> => (await readFile(join(home, 'requests.jsonl'), 'utf8').catch(() => '')).trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
  const start = async (stop?: 'paused' | 'interrupted') => {
    client = new RuntimeClient({home, cwd: home, onLog: text => {logs += text;}});
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', {protocol: 1, agents, bindings,
      ...(stop === 'paused' ? {taskStops: ['root']} : {}),
      ...(stop === 'interrupted' ? {taskStopFences: ['root']} : {})});
  };
  const call = async <T = any>(method: string, input: unknown): Promise<T> => await client!.rpc.request(method, input) as T;
  const descendants = () => call<Child[]>('session.descendants', {sessionId: 'root'});
  const history = async (id: string) => id === 'root' ? (await call<{events: Event[]}>('session.observe', {sessionId: id})).events : (await descendants()).find(child => child.id === id)!.events;
  const notify = (sessionId: string, inputId: string, agentId = 'a') => call('schedule.deleted.notify', {agentId, sessionId, inputId,
    content: [{type: 'text', text: 'Schedule deleted by the user. This notice changes no Task status or authority.'}]});
  const seed = async () => {
    await writeFile(join(home, 'fixture.mjs'), fixture);
    await prepareProfile(home, [{insert: [{id: 'schedule-delete-fixture', name: join(home, 'fixture.mjs')}]}]);
    await start();
    await call('session.ensure', bindings[0]);
    await call('session.submit', {sessionId: 'root', inputId: 'seed', mode: 'followup', content: [{type: 'text', text: 'Create original native children'}],
      source: {kind: 'human', actorId: 'owner', channel: 'test', messageId: 'seed'}});
    await expect.poll(async () => {
      const error = await readFile(join(home, 'fixture-error'), 'utf8').catch(() => '');
      if (error) throw new Error(error + '\n' + logs);
      return readFile(join(home, 'ready.json'), 'utf8').catch(() => '');
    }, {timeout: 12_000}).not.toBe('');
    await expect.poll(async () => (await call('session.lookup', {sessionId: 'root', inputId: 'seed'})).terminal).toBeTruthy();
    const manifest = JSON.parse(await readFile(join(home, 'ready.json'), 'utf8')) as Manifest;
    // Establish only the normal persisted ancestry read-model before cold start.
    await descendants();
    return manifest;
  };
  return {home, bindings, call, requests, start, seed, history, descendants, notify,
    restart: async (stop?: 'paused' | 'interrupted') => {await client!.shutdown(); client = undefined; await start(stop);},
    close: async () => {if (client) await client.shutdown(); await rm(home, {recursive: true, force: true});},
    logs: () => logs};
}

const admissions = (events: Event[], id: string) => events.flatMap(event => event.type === 'agent/inbox/spliced' ? event.data.inserted : []).filter(message => message.id === id);
const consumed = (events: Event[], id: string) => events.filter(event => event.type === 'user/message' && event.data.id === id);

it('deletes a legacy child Schedule and restores only its original native lineage, composition, and exactly-once input', async () => {
  const h = await harness();
  try {
    const ids = await h.seed();
    const originalRoot = await h.history('root');
    const originalParent = await h.history(ids.parent);
    const originalChild = await h.history(ids.child);
    const before = await h.requests();
    const initialRequest = before.find(request => request.sessionId === ids.child)!;
    await h.restart();
    const inputId = 'schedule-deleted:legacy-child:user-operation';
    await expect(h.notify(ids.child, inputId, 'b')).rejects.toThrow();
    await expect(h.notify('root-b', inputId)).rejects.toThrow();
    await expect(h.notify('unmanaged-native-root', inputId)).rejects.toThrow('trusted native child lineage');
    await expect(h.notify('arbitrary-unmanaged-session', inputId)).rejects.toThrow();
    expect(await h.requests()).toEqual(before);
    expect(await h.call('schedule.command', {agentId: 'a', action: 'catalog'})).toEqual(expect.arrayContaining([expect.objectContaining({id: 'legacy-child', sessionId: ids.child})]));
    expect(await h.call('schedule.command', {agentId: 'a', sessionId: ids.child, action: 'delete', args: {id: 'legacy-child'}})).toMatchObject({deleted: true});
    for (const receipt of await Promise.all([h.notify(ids.child, inputId), h.notify(ids.child, inputId)])) expect(receipt).toMatchObject({durable: true});
    await expect.poll(async () => consumed(await h.history(ids.child), inputId).length).toBe(1);
    expect(await h.notify(ids.child, inputId)).toMatchObject({durable: true});
    const child = await h.history(ids.child);
    expect(admissions(child, inputId)).toHaveLength(1);
    expect(consumed(child, inputId)).toHaveLength(1);
    expect(child.slice(0, originalChild.length)).toEqual(originalChild);
    const root = await h.history('root');
    const parent = await h.history(ids.parent);
    expect(root.slice(0, originalRoot.length)).toEqual(originalRoot);
    expect(parent.slice(0, originalParent.length)).toEqual(originalParent);
    expect(admissions(root, inputId)).toHaveLength(0);
    expect(admissions(parent, inputId)).toHaveLength(0);
    const notification = admissions(child, inputId)[0];
    expect(notification.source).toMatchObject({kind: 'nano-system', actorId: 'a', channel: 'schedule-change', messageId: inputId});
    const recovered = (await h.requests()).slice(before.length);
    expect(recovered.map(request => request.sessionId)).toEqual([ids.child]);
    expect(JSON.stringify(recovered[0].messages)).toContain('NATIVE CHILD PERSONA');
    for (const key of ['model', 'provider', 'reasoningEffort'] as const) expect(recovered[0][key]).toEqual(initialRequest[key]);
    expect(recovered[0].tools?.map(tool => tool.name)).toEqual(initialRequest.tools?.map(tool => tool.name));
    expect(recovered[0].tools?.map(tool => tool.name)).not.toContain('write');
    const created = (await readFile(join(h.home, 'created.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const resumed = created.filter(row => row.source === 'resume');
    expect(resumed).toEqual(expect.arrayContaining([
      expect.objectContaining({id: ids.parent, parent: 'root', depth: 1}),
      expect.objectContaining({id: ids.child, parent: ids.parent, depth: 2})]));
    await h.call('session.ensure', h.bindings[1]);
    const stopped = await h.call('agent.disable', {agentId: 'a', revision: 2});
    expect(stopped, h.logs()).toMatchObject({confirmed: true});
    expect(stopped.history.map((row: any) => row.sessionId)).toEqual(expect.arrayContaining(['root', ids.parent, ids.child]));
    await expect(h.notify(ids.child, 'schedule-deleted:disabled')).rejects.toThrow('agent_disabled');
    expect(await h.notify('root-b', 'schedule-deleted:b-still-enabled', 'b')).toMatchObject({durable: true});
  } catch (error) {throw new Error(String(error) + '\n' + h.logs(), {cause: error});}
  finally {await h.close();}
}, 40_000);

it.each(['paused', 'interrupted'] as const)('keeps cold native child and root D6 notices passive behind the %s root fence', async stop => {
  const h = await harness();
  try {
    const ids = await h.seed();
    const before = await h.requests();
    await h.restart(stop);
    const inputId = 'schedule-deleted:passive-' + stop;
    for (const sessionId of [ids.child, 'root']) {
      expect(await h.notify(sessionId, inputId)).toMatchObject({durable: true});
      expect(await h.notify(sessionId, inputId)).toMatchObject({durable: true});
      const events = await h.history(sessionId);
      expect(admissions(events, inputId)).toHaveLength(1);
      expect(consumed(events, inputId)).toHaveLength(0);
    }
    expect(await h.requests()).toEqual(before);
    // A second cold start proves the passive receipt is durable, not an in-memory promise.
    await h.restart(stop);
    expect(await h.notify(ids.child, inputId)).toMatchObject({durable: true});
    expect(admissions(await h.history(ids.child), inputId)).toHaveLength(1);
    expect(consumed(await h.history(ids.child), inputId)).toHaveLength(0);
    expect(await h.requests()).toEqual(before);
  } catch (error) {throw new Error(String(error) + '\n' + h.logs(), {cause: error});}
  finally {await h.close();}
}, 40_000);

it('leaves cold one-shot deletion notification pending instead of pretending delivery or starting an unsupported loop', async () => {
  const h = await harness();
  try {
    const ids = await h.seed();
    const original = await h.history(ids.oneShot);
    const before = await h.requests();
    await h.restart();
    expect(await h.call('schedule.command', {agentId: 'a', sessionId: ids.oneShot, action: 'delete', args: {id: 'legacy-one-shot'}})).toMatchObject({deleted: true});
    let durableReceipt: unknown;
    await expect(h.notify(ids.oneShot, 'schedule-deleted:one-shot').then(receipt => {durableReceipt = receipt;})).rejects.toThrow('resumable continuation descriptor');
    // A product pending receipt must not become notified without native durability.
    // This boundary test verifies no success receipt; PA owns the durable pending row.
    expect(durableReceipt).toBeUndefined();
    expect(await h.history(ids.oneShot)).toEqual(original);
    expect(await h.requests()).toEqual(before);
  } catch (error) {throw new Error(String(error) + '\n' + h.logs(), {cause: error});}
  finally {await h.close();}
}, 40_000);
