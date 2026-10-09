import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('isolates native schedule owners, preserves disabled jobs across restart, and catches up once when enabled', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-cron-'));
  let client: RuntimeClient | undefined; let logs = '';
  const agents = ['a', 'b'].map(agentId => ({ agentId, revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', features: { cron_scheduling: true, task_graph: true } }));
  const bindings = agents.map(agent => ({ sessionId: `session-${agent.agentId}`, agentId: agent.agentId, revision: '1', ownerId: 'owner', cwd: join(home, agent.agentId) }));
  const start = async () => {
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings });
    for (const binding of bindings) await client.rpc.request('session.ensure', binding);
  };
  try {
    await prepareProfile(home); await start();
    const tools = async (sessionId: string) => (await client!.rpc.request('session.capabilities', { sessionId }) as { tools: string[] }).tools;
    expect(await tools('session-a')).toContain('schedule_create');
    const capabilities = () => client!.rpc.request('session.capabilities', { sessionId: 'session-a' });
    expect(JSON.stringify(await capabilities())).toContain('Task graphs are durable');
    await client!.rpc.request('configuration.features', { agentId: 'a', features: { task_graph: false, cron_scheduling: true } });
    expect(await tools('session-a')).not.toContain('task_graph');
    expect(await tools('session-b')).toContain('task_graph');
    expect(JSON.stringify(await capabilities())).not.toContain('Task graphs are durable');
    await client!.rpc.request('configuration.features', { agentId: 'a', features: { task_graph: true, cron_scheduling: true } });
    expect((await tools('session-a')).filter(name => name === 'task_graph')).toHaveLength(1);
    const a = await client!.rpc.request('schedule.command', { agentId: 'a', sessionId: 'session-a', action: 'create', args: { title: 'A reminder', prompt: 'A reminder', after_seconds: 1 } }) as { id: string };
    const received = new Promise<void>(resolve => client!.rpc.onNotification((method, value) => {
      const message = value as { sessionId: string; event?: { type: string; data: { source?: { kind: string } } } };
      if (method === 'session.event' && message.sessionId === 'session-b' && message.event?.type === 'user/message' && message.event.data.source?.kind === 'schedule') resolve();
    }));
    await client!.rpc.request('schedule.command', { agentId: 'b', sessionId: 'session-b', action: 'create', args: { title: 'B reminder', prompt: 'B reminder', after_seconds: 1 } });
    await client!.rpc.request('schedule.enabled', { agentId: 'a', enabled: false });
    expect(await tools('session-a')).not.toContain('schedule_create');
    expect(await tools('session-b')).toContain('schedule_create');
    await received;
    expect(await client!.rpc.request('schedule.command', { agentId: 'a', action: 'catalog' })).toMatchObject([{ id: a.id, status: 'active' }]);
    await client!.shutdown(); client = undefined;
    agents[0]!.features.cron_scheduling = false;
    await start();
    const disabled = await client!.rpc.request('schedule.command', { agentId: 'a', action: 'catalog' }) as { lastDelivery?: unknown }[];
    expect(disabled[0]!.lastDelivery).toBeUndefined();
    await client!.rpc.request('schedule.enabled', { agentId: 'a', enabled: true });
    expect(await tools('session-a')).toContain('schedule_create');
    let catalog: { lastDelivery?: { messageId: string } }[] = [];
    for (let tries = 0; tries < 30; tries++) {
      catalog = await client!.rpc.request('schedule.command', { agentId: 'a', action: 'catalog' }) as typeof catalog;
      if (catalog[0]?.lastDelivery) break;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    expect(catalog[0]?.lastDelivery?.messageId).toBeTruthy();
    const history = await client!.rpc.request('schedule.command', { agentId: 'a', sessionId: 'session-a', action: 'history', args: { id: a.id, limit: 10 } }) as { records: unknown[] };
    expect(history.records).toHaveLength(1);
    const manual = await client!.rpc.request('schedule.command', { agentId: 'a', sessionId: 'session-a', action: 'create', args: { title: 'Manual', prompt: 'Manual task', after_seconds: 3600 } }) as { id: string };
    const run = { agentId: 'a', sessionId: 'session-a', action: 'run', args: { id: manual.id, inputId: 'manual-schedule:test' } };
    await client!.rpc.request('schedule.command', run); await client!.rpc.request('schedule.command', run);
    const admissions = await client!.rpc.request('schedule.evidence', { sessionId: 'session-a' }) as { messageId: string; trigger: string; accepted: boolean }[];
    expect(admissions.filter(entry => entry.messageId === 'manual-schedule:test')).toMatchObject([{ trigger: 'manual', accepted: true }]);
    await client!.rpc.request('configuration.apply', { ...agents[0], revision: '2', systemPrompt: 'UPDATED_PERSONA_MARKER', features: { task_graph: false, cron_scheduling: false } });
    expect(await tools('session-a')).not.toContain('task_graph');
    expect(await tools('session-a')).not.toContain('schedule_create');
    expect(JSON.stringify(await capabilities())).toContain('UPDATED_PERSONA_MARKER');
    // Existing native Session identity still accepts its original product binding.
    expect(await client!.rpc.request('session.ensure', bindings[0])).toMatchObject({ sessionId: 'session-a' });
    await client!.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 20_000);

it('recovers admitted schedule identity when the process dies before the timer receipt commits', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-cron-gap-'));
  let client: RuntimeClient | undefined;
  const agent = { agentId: 'gap', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', features: { cron_scheduling: true } };
  const binding = { sessionId: 'gap-session', agentId: 'gap', revision: '1', ownerId: 'owner', cwd: home };
  try {
    const { writeFile } = await import('node:fs/promises');
    const fault = join(home, 'flush-fault.mjs');
    // Hold one public flush participant so the native timer cannot commit its
    // receipt. The real persistence listener runs independently; cold recovery
    // below proves that the actual schedule input reached its durable log.
    await writeFile(fault, `export const name='flush-fault'; export function apply(ctx) {
      ctx.on('session/flush', session => {
        if (!session.snapshotEvents().some(event => event.type==='agent/inbox/spliced' && event.data.inserted.some(message => message.source?.kind==='schedule'))) return;
        return new Promise(() => setTimeout(() => process.kill(process.pid, 'SIGKILL'), 100));
      });
    }`);
    await prepareProfile(home, [{ insert: [{ id: 'flush-fault', name: fault }] }]);
    client = new RuntimeClient({ home, cwd: home });
    await client.rpc.request('initialize', { protocol: 1, agents: [agent], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const task = await client.rpc.request('schedule.command', { agentId: 'gap', sessionId: binding.sessionId, action: 'create', args: { title: 'gap', prompt: 'gap', after_seconds: 1 } }) as { id: string };
    expect((await client.exited).signal).toBe('SIGKILL'); client = undefined;
    await prepareProfile(home); agent.features.cron_scheduling = false;
    client = new RuntimeClient({ home, cwd: home });
    await client.rpc.request('initialize', { protocol: 1, agents: [agent], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const catalog = await client.rpc.request('schedule.command', { agentId: 'gap', action: 'catalog' });
    expect(catalog).toMatchObject([{ id: task.id, status: 'active' }]);
    expect((catalog as { lastDelivery?: unknown }[])[0]!.lastDelivery).toBeUndefined();
    const evidence = await client.rpc.request('schedule.evidence', { sessionId: binding.sessionId });
    expect(evidence).toMatchObject([{ scheduleId: task.id, trigger: 'timed', accepted: true }]);
    expect((evidence as { messageId: string }[])[0]!.messageId).toBeTruthy();
    await client.shutdown(); client = undefined;
  } finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 20_000);
