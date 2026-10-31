import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('holds true idle, fences admissions and preserves native Cron jobs through release', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-update-barrier-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await writeFile(join(home, 'model.mjs'), `export const name='update-model'; export const inject=['llm']; export function apply(ctx){ctx.on('llm/stream',async function*(){yield {type:'block-end',index:0,block:{type:'text',text:'Done'}};yield {type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home, [{ insert: [{ id: 'update-model', name: join(home, 'model.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    const scheduled: string[] = [];
    client.rpc.onNotification((method, value) => {
      const data = value as { event?: { type: string; data: { source?: { kind: string }; id?: string } } };
      if (method === 'session.event' && data.event?.type === 'user/message' && data.event.data.source?.kind === 'schedule') scheduled.push(data.event.data.id!);
    });
    const config = { agentId: 'a', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', features: { cron_scheduling: true } };
    const binding = { sessionId: 's', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    await client.rpc.request('session.ensure', binding);
    const schedule = await client.rpc.request('schedule.command', { agentId: 'a', sessionId: 's', action: 'create', args: { title: 'Due during hold', prompt: 'check', after_seconds: 1 } }) as { id: string };
    expect(await client.rpc.request('update.prepare', { operationId: 'one' })).toEqual({ ready: true });
    expect(await client.rpc.request('update.prepare', { operationId: 'one' })).toEqual({ ready: true });
    expect(await client.rpc.request('update.prepare', { operationId: 'other' })).toEqual({ ready: false });
    expect(await client.rpc.request('update.release', { operationId: 'other' })).toEqual({ released: false });
    await expect(client.rpc.request('session.ensure', binding)).rejects.toThrow('held for update');
    await expect(client.rpc.request('session.submit', { sessionId: 's', inputId: 'blocked' })).rejects.toThrow('held for update');
    await expect(client.rpc.request('session.command', { sessionId: 's', id: 'blocked', action: 'compact' })).rejects.toThrow('held for update');
    await expect(client.rpc.request('model.setup.stage', {})).rejects.toThrow('held for update');
    // Permission replies use an independent path, even while update holds idle.
    await expect(client.rpc.request('approval.answer', { requestId: 'none', decision: 'allowed-once' })).rejects.toThrow('no longer pending');
    await new Promise(resolve => setTimeout(resolve, 1200));
    expect(scheduled).toEqual([]);
    expect(await client.rpc.request('update.release', { operationId: 'one' })).toEqual({ released: true });
    await expect.poll(() => scheduled.length).toBe(1);
    const jobs = await client.rpc.request('schedule.command', { agentId: 'a', action: 'jobs' }) as { id: string }[];
    expect(jobs.some(job => job.id === schedule.id)).toBe(true);
    const capabilities = await client.rpc.request('session.capabilities', { sessionId: 's' }) as { tools: string[] };
    expect(capabilities.tools).toContain('schedule_create');
    await expect.poll(() => client!.rpc.request('update.prepare', { operationId: 'two' })).toEqual({ ready: true });
    expect(await client.rpc.request('update.release', { operationId: 'one' })).toEqual({ released: false });
    // shutdown must release maintenance before native whenIdle() can finish.
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30000);

it('refuses an idle-looking native queued input, including before cold PA recovery', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-update-inbox-'));
  let client: RuntimeClient | undefined;
  const binding = { sessionId: 's', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  const config = { protocol: 1, agents: [{ agentId: 'a', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash' }], bindings: [binding] };
  try {
    await prepareProfile(home);
    client = new RuntimeClient({ home, cwd: home });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', config);
    await client.rpc.request('session.ensure', binding);
    expect(await client.rpc.request('session.submit', { sessionId: 's', inputId: 'pending', mode: 'inject', content: [{ type: 'text', text: 'Retained input' }], source: { kind: 'system', actorId: 'owner', channel: 'test', messageId: 'pending' } })).toMatchObject({ pending: true, accepted: true });
    expect(await client.rpc.request('session.observe', { sessionId: 's' })).toMatchObject({ status: 'idle' });
    expect(await client.rpc.request('update.prepare', { operationId: 'one' })).toEqual({ ready: false });
    expect(await client.rpc.request('session.lookup', { sessionId: 's', inputId: 'pending' })).toMatchObject({ accepted: true, pending: true });
    client.process.kill('SIGKILL'); await client.exited;
    client = new RuntimeClient({ home, cwd: home });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', config);
    expect(await client.rpc.request('update.prepare', { operationId: 'cold' })).toEqual({ ready: false });
    expect(await client.rpc.request('session.lookup', { sessionId: 's', inputId: 'pending' })).toMatchObject({ accepted: true, pending: true });
    await client.shutdown(); client = undefined;
  } finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30000);
