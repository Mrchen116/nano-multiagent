import { expect, it, vi } from 'vitest';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolRunContext } from '@deepseek-ai/dsh-tools';
import { LocalWorkers } from '../src/local-workers/manager.js';
import { openCliWorker } from '../src/local-workers/drivers.js';

vi.mock('../src/local-workers/drivers.js', () => ({ openCliWorker: vi.fn() }));

it('binds follow-ups to the original worker and replays an unacknowledged result with its stable id', async () => {
  const domain = new Map<string, Map<string, unknown>>();
  const storage = {
    table: (name: string) => {
      let rows = domain.get(name);
      if (!rows) domain.set(name, (rows = new Map()));
      return {
        get: rows.get.bind(rows),
        put: rows.set.bind(rows),
        delete: rows.delete.bind(rows),
        entries: () => rows.entries(),
      };
    },
    close: vi.fn(),
  };
  const session = { header: { cwd: process.cwd() }, append: vi.fn() };
  const ctx = {
    provide: vi.fn(),
    on: vi.fn(),
    effect: vi.fn(),
    logger: { error: vi.fn() },
    storageDomain: { open: async () => storage },
    sessions: { get: () => session, flush: async () => true },
  };
  const root = { id: 'router', session } as unknown as Agent;
  const other = { id: 'other', session } as unknown as Agent;
  const accepted: string[] = [];
  let online = false;
  const report = vi.fn(async (_root: string, _worker: string, id: string) => {
    if (!online) throw new Error('runtime busy');
    accepted.push(id);
  });
  const manager = new LocalWorkers(ctx as unknown as Context, report, () => true, vi.fn());
  const send = vi.fn(async () => {}),
    close = vi.fn(async () => {});
  vi.mocked(openCliWorker).mockImplementation(async (options) => ({
    sessionId: options.sessionId ?? 'original-session',
    send,
    close,
    stop: async () => {},
  }));
  const exec = { callId: 'dispatch', signal: new AbortController().signal } as ToolRunContext;
  const row = await manager.start(root, 'codex', 'review', 'inspect A', exec);
  expect(await manager.start(root, 'claude', 'review', 'inspect A', exec)).toMatchObject({
    workerId: row.workerId,
    runtime: 'codex',
  });
  expect(send.mock.calls).toHaveLength(1);
  await expect(manager.control(other, row.workerId, 'send', 'replace the task', exec.signal)).rejects.toThrow(
    /belong/,
  );
  const launch = vi.mocked(openCliWorker).mock.calls[0]![0];
  await launch.onTurnEnd('turn-1', 18);
  await launch.onTurnEnd('turn-1', 18);
  await expect(launch.onEnd('turn-1', 'completed', 'A exists')).rejects.toThrow('runtime busy');
  await expect.poll(() => close.mock.calls.length).toBe(1);
  online = true;
  const restored = new LocalWorkers(ctx as unknown as Context, report, () => true, vi.fn());
  const turns=(await restored.workPage(root.id)).filter(update=>update.turnUsage);
  expect(turns.map(update=>update.turnUsage)).toEqual([{id:'turn-1', totalTokens:18}]);
  await restored.confirmWork(root.id,turns);
  await restored.flushReports(root.id);
  await restored.flushReports(root.id);
  expect(accepted).toEqual(['end:turn-1']);
  await restored.control(root, row.workerId, 'send', 'inspect B', exec.signal);
  expect(vi.mocked(openCliWorker).mock.calls.at(-1)![0]).toMatchObject({
    runtime: 'codex',
    sessionId: 'original-session',
  });
  expect(send).toHaveBeenLastCalledWith('inspect B');
  await restored.stopRoot(root.id);
});
