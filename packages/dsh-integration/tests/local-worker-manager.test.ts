import { cliWorkerRuntimes } from '@nano/product-contracts';
import { expect, it, vi } from 'vitest';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolRunContext } from '@deepseek-ai/dsh-tools';
import { LocalWorkers } from '../src/local-workers/manager.js';
import { openCliWorker } from '../src/local-workers/drivers.js';

vi.mock('../src/local-workers/drivers.js', () => ({ openCliWorker: vi.fn() }));

it.each(cliWorkerRuntimes)('%s binds follow-ups to the original session and replays a result once', async (runtime) => {
  vi.mocked(openCliWorker).mockClear();
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
  const report = vi.fn(async (_root: string, _worker: string, id: string, _text: string) => {
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
  const row = await manager.start(root, runtime, 'review', 'inspect A', exec);
  expect(await manager.isWorker(row.workerId)).toBe(true);
  expect(await manager.start(root, 'dsh', 'review', 'inspect A', exec)).toMatchObject({
    workerId: row.workerId,
    runtime,
  });
  expect(send.mock.calls).toHaveLength(1);
  await expect(manager.control(other, row.workerId, 'send', 'replace the task', exec.signal)).rejects.toThrow(
    /belong/,
  );
  const launch = vi.mocked(openCliWorker).mock.calls[0]![0];
  const end = {turnId:'turn-1', fact:{type:'turn_end' as const, payload:{status:'completed', usage:{total_tokens:18}}}};
  await launch.onDetail('end', end);
  await launch.onDetail('end', end);
  await expect(launch.onEnd('turn-1', 'completed', 'Which file should I inspect?')).rejects.toThrow('runtime busy');
  await expect.poll(() => close.mock.calls.length).toBe(1);
  online = true;
  const restored = new LocalWorkers(ctx as unknown as Context, report, () => true, vi.fn());
  const turns=(await restored.workPage(root.id)).page.filter(update=>update.detail);
  expect(turns.map(update=>update.detail)).toEqual([end]);
  await restored.confirmWork(root.id,turns);
  await restored.flushReports(root.id);
  await restored.flushReports(root.id);
  expect(accepted).toEqual(['end:turn-1']);
  expect(report.mock.calls.at(-1)).toEqual([root.id, row.workerId, 'end:turn-1',
    expect.stringContaining('This turn ended. The worker will do no further work unless you send it more.\nWhich file should I inspect?')]);
  await restored.control(root, row.workerId, 'send', 'inspect B', exec.signal);
  expect(vi.mocked(openCliWorker).mock.calls.at(-1)![0]).toMatchObject({
    runtime,
    sessionId: 'original-session',
  });
  expect(send).toHaveBeenLastCalledWith('inspect B');
  await restored.stopRoot(root.id);
});
