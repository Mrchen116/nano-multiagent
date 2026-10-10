import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';
import { Heartbeat } from '../src/heartbeat.js';
import { heartbeatDue, heartbeatTasks, withinActiveHours } from '../src/heartbeat-policy.js';

it('keeps config cadence authoritative, evaluates task rhythms once, and respects active hours', () => {
  const [task] = heartbeatTasks('# Tasks\nevery: 1s\nCheck the inbox', { every: '10m' });
  expect(task?.interval).toBe(600000);
  expect(heartbeatTasks('# Nothing\n- [ ]\n```\n```', {})).toEqual([]);
  const tasks = heartbeatTasks('tasks:\n  - name: inbox\n    interval: 30m\n    prompt: "Check inbox"\n  - name: calendar\n    interval: 2h\n    prompt: Review calendar', {});
  expect(tasks.map(task => task.interval)).toEqual([1800000, 7200000]);
  expect(heartbeatDue(task!, 0, 1850000)).toBe(1800000);
  expect(heartbeatDue(task!, 1800000, 1850000)).toBeUndefined();
  expect(withinActiveHours(Date.parse('2026-10-09T02:00:00Z'), { active_hours: { start: '09:00', end: '18:00', timezone: 'Asia/Shanghai' } })).toBe(true);
  expect(withinActiveHours(Date.parse('2026-10-09T12:00:00Z'), { active_hours: { start: '09:00', end: '18:00', timezone: 'Asia/Shanghai' } })).toBe(false);
});

it('recovers an uncertain heartbeat admission by its original identity and does not refill missed ticks', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-heartbeat-'));
  await mkdir(join(directory, '.nanoassistant'));
  await writeFile(join(directory, '.nanoassistant/HEARTBEAT.md'), 'Check inbox');
  const agent = { agentId: 'a', revision: '1', workspace: directory, mode: 'single_thread' as const, provider: 'p', model: 'm', features: { heartbeat: true } };
  const accepted = new Set<string>(); let fail = true; let submissions = 0;
  const options = { agents: [agent], settings: () => ({ every: '10m' }), available: () => true, onError: () => {},
    binding: async () => ({ sessionId: 's', conversationId: 'c', ownerId: 'o', agentId: 'a', cwd: directory, revision: '1' }),
    runtime: { onNotification: () => () => {}, request: async (method: string, params: unknown) => {
      const value = params as { inputId: string; onlyIfIdle?: boolean; source?: { channel: string } };
      if (method === 'session.lookup') return { accepted: accepted.has(value.inputId) };
      expect(value.onlyIfIdle).toBe(true); expect(value.source?.channel).toBe('heartbeat');
      accepted.add(value.inputId); submissions++;
      if (fail) throw new Error('lost acceptance response'); return { accepted: true };
    } },
  };
  let heartbeat = new Heartbeat(join(directory, 'hb.sqlite3'), options);
  try {
    heartbeat.subscription('a', true);
    await expect(heartbeat.tick(undefined, false, 1200000)).rejects.toThrow('lost acceptance');
    await heartbeat.stop(); fail = false;
    heartbeat = new Heartbeat(join(directory, 'hb.sqlite3'), options); heartbeat.subscription('a', true);
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(1);
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(2);
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(2);
    heartbeat.subscription('a', false);
    await heartbeat.tick(undefined, false, 12000000); expect(submissions).toBe(2);
    await expect(heartbeat.tick('a', true, 12000000)).rejects.toThrow('disabled');
  } finally { await heartbeat.stop(); await rm(directory, { recursive: true, force: true }); }
});
