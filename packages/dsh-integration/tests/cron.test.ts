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
