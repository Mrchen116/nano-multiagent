import {mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect, it} from 'vitest';
import {prepareProfile, RuntimeClient} from '@nano/dsh-integration/client';
import {NodeStore, SingleThread} from '@nano/personal-assistant';
import type {AgentConfiguration, RuntimeEvent, SessionBinding, TaskExecutionSnapshot} from '@nano/product-contracts';

it.each(['schedule', 'task'] as const)('discovers a durable native %s admission after SIGKILL before Node observes it', async (source) => {
  const home = await mkdtemp(join(tmpdir(), 'nano-single-recovery-'));
  const store = new NodeStore(join(home, 'node.sqlite3'), 'owner');
  const agent: AgentConfiguration = {agentId: 'a', mode: 'single_thread', revision: '1', workspace: home,
    provider: 'deepseek-official', model: 'deepseek-flash', features: {cron_scheduling: source === 'schedule', task_graph: source === 'task'}};
  const bind = (id: string) => store.bind({sessionId: id, agentId: 'a', ownerId: 'owner', conversationId: id, cwd: home, revision: '1'});
  const root = bind('native-root'), idle = bind('idle-root'), absent = bind('missing-root');
  const forRuntime = ({conversationId: _, ...binding}: SessionBinding) => binding;
  const fault = join(home, 'fixture.mjs');
  const match = source === 'schedule' ? "message.source?.kind==='schedule'" : "message.source?.channel==='task-execution'";
  const taskSnapshot: TaskExecutionSnapshot = {kind: 'continue', tasks: [{graph_id: 'g', node_id: 't', title: 'Native Task fixture',
    status: 'doing', revision: 1, updated_at: '2026-10-23T15:00:00Z', conversation: {id: root.conversationId}, relative_url: '/tasks/g'}], repair_task_ids: []};
  const calls: Array<{method: string; sessionId?: string}> = [];
  const marks: Array<{sessionId: string; boot: string}> = [];
  const errors: unknown[] = [];
  let client: RuntimeClient | undefined, product: SingleThread | undefined, logs = '';
  let taskActive = false;
  const start = async (crash: boolean) => {
    await writeFile(fault, `import {appendFileSync,writeFileSync} from 'node:fs'; export const name='recovery-fixture'; export const inject=['llm','agents','sessions','sessionPersistence'];
      export function apply(ctx) {
        if (${crash}) {
          const open = ctx.sessionPersistence.open.bind(ctx.sessionPersistence);
          ctx.sessionPersistence.open = async (id, ...options) => {
            const handle = await open(id, ...options);
            if (id !== 'native-root') return handle;
            const read = handle.read.bind(handle);
            handle.read = async (...range) => {
              const result = await read(...range);
              if (result.events.length > 1) appendFileSync(process.env.DSH_HOME+'/root-reads', 'read\\n');
              return result;
            };
            return handle;
          };
        }
        let faulting = false;
        if (${crash}) ctx.on('session/flush', session => {
          const original = session.snapshotEvents().filter(event => event.type==='agent/inbox/spliced')
            .flatMap(event => event.data.inserted).find(message => ${match});
          if (!original) return;
          if (!faulting) {
            faulting = true;
            writeFileSync(process.env.DSH_HOME+'/original-admission', original.id);
            // Hold the timer's receipt commit. The persistence participant
            // runs independently and the cold replay proves the exact ID survived.
            setTimeout(() => process.kill(process.pid, 'SIGKILL'), 120);
          }
          return new Promise(() => {});
        });
        ctx.on('llm/stream', async function*() {
          if (${crash}) await ctx.sessions.flush(ctx.agents.currentInitiator().session);
          yield {type:'block-end',index:0,block:{type:'text',text:'Recovered output'}};
          yield {type:'finish',reason:{kind:'stop'}};
        });
      }`);
    await prepareProfile(home, [{insert: [{id: 'recovery-fixture', name: fault}]}]);
    client = new RuntimeClient({home, cwd: home, onLog: chunk => {logs += chunk;}});
    const boot = client.processInstanceId;
    client.rpc.handle('session.recovery.mark', value => {
      const {sessionId} = value as {sessionId: string};
      marks.push({sessionId, boot});
      store.markSessionWritable(sessionId, boot);
      return {marked: true};
    });
    client.rpc.handle('product.task_context.prepare', () => ({messages: [], revoked: []}));
    client.rpc.handle('product.task_context.commit', () => null);
    client.rpc.handle('product.task_execution.snapshot', () => taskActive ? taskSnapshot : {kind: 'quiescent', tasks: [], repair_task_ids: []});
    client.rpc.handle('model.check', () => ({published: false}));
    await client.rpc.request('initialize', {protocol: 1, recoveryMarkers: true, agents: [agent],
      bindings: [root, idle, absent].map(forRuntime)});
    return boot;
  };
  const request = async <T = unknown>(method: string, params: {sessionId?: string; [key: string]: unknown}): Promise<T> =>
    await client!.rpc.request(method, params) as T;
  try {
    await start(false);
    for (const binding of [root, idle]) {
      await request('session.ensure', forRuntime(binding));
      await request('session.submit', {sessionId: binding.sessionId, inputId: `seed-${binding.sessionId}`, mode: 'followup',
        content: [{type: 'text', text: 'Seed durable history'}], source: {kind: 'human', actorId: 'owner', channel: 'test', messageId: 'seed'}});
      await expect.poll(async () => (await request<{status: string}>('session.observe', {sessionId: binding.sessionId})).status).toBe('idle');
      store.recordEvents(binding.sessionId, (await request<{events: RuntimeEvent[]}>('session.observe', {sessionId: binding.sessionId})).events);
    }
    await client!.shutdown();
    const crashBoot = await start(true);
    expect(await request('session.recovery.probe', {sessionId: root.sessionId, afterSeq: store.cursor(root.sessionId), localWork: false}))
      .toEqual({live: false, unseen: false});
    if (source === 'schedule') {
      await request('schedule.command', {agentId: 'a', sessionId: root.sessionId,
        action: 'create', args: {title: 'Crash window', prompt: 'Run the saved instruction', after_seconds: 1}});
    } else {
      await request('session.ensure', forRuntime(root));
      taskActive = true;
      await request('task.execution.changed', {agentId: 'a'});
    }
    expect((await client!.exited).signal).toBe('SIGKILL');
    client = undefined;
    expect(await readFile(join(home, 'root-reads'), 'utf8')).toBe('read\n');
    taskActive = false;
    const original = await readFile(join(home, 'original-admission'), 'utf8');
    expect(marks).toContainEqual({sessionId: root.sessionId, boot: crashBoot});
    expect(store.inputs(root.sessionId)).toEqual([]);
    const boot = await start(false);
    product = new SingleThread({nodeId: 'node', ownerId: 'owner', agents: [agent], store,
      runtime: {onNotification: listener => client!.rpc.onNotification(listener), async request(method, params) {
        calls.push({method, sessionId: (params as {sessionId?: string})?.sessionId});
        return client!.rpc.request(method, params);
      }},
      relay: {async request(_type, payload) { return {type: 'ack', payload: {message_id: payload.idempotency_key ?? 'message'}}; }},
      recoveryGeneration: () => boot, image: async () => '', onError: error => errors.push(error),
    });
    await Promise.all([product.recover(), product.recover()]);
    const ensures = calls.filter(call => call.method === 'session.ensure');
    if (source === 'task' || ensures.length) expect(ensures).toEqual([{method: 'session.ensure', sessionId: root.sessionId}]);
    expect(marks.filter(mark => mark.boot === boot)).toEqual([{sessionId: root.sessionId, boot}]);
    expect(calls.filter(call => call.method === 'session.submit')).toEqual([]);
    // An unacknowledged native timer can fire a new occurrence after process loss.
    // Node must recover the original identity exactly once and never resubmit it.
    await expect.poll(() => store.inputs(root.sessionId).filter(input => input.id === original)).toHaveLength(1);
    expect(store.recoveryCandidates(['a']).map(item => item.binding.sessionId)).toEqual([root.sessionId]);
    expect(await request('session.recovery.probe', {sessionId: idle.sessionId, afterSeq: store.cursor(idle.sessionId), localWork: false}))
      .toEqual({live: false, unseen: false});
    expect(errors).toEqual([]);
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, {cause: error}); }
  finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    await product?.stop();
    store.close();
    await rm(home, {recursive: true, force: true});
  }
}, 30_000);
