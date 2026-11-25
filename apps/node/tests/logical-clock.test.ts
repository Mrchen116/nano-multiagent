import { createConnection } from 'node:net';
import { createInterface } from 'node:readline';
import { stat, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { LogicalClockController } from '../src/logical-clock.js';

async function rpcCall(socketPath: string, method: string, params?: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const socket = createConnection(socketPath);
    const rl = createInterface({ input: socket, crlfDelay: Infinity });
    socket.once('error', reject);
    socket.once('connect', () => {
      socket.write(JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }) + '\n');
    });
    rl.once('line', line => {
      rl.close();
      socket.end();
      const parsed = JSON.parse(line) as { result?: unknown; error?: { message: string } };
      if (parsed.error) reject(new Error(parsed.error.message));
      else resolve(parsed.result);
    });
  });
}

describe('LogicalClockController', () => {
  const savedSocket = process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET;
  const savedInitial = process.env.NANO_E2E_INITIAL_LOGICAL_CLOCK_MS;
  const savedPublic = process.env.IM_PUBLIC_MODE;

  afterEach(() => {
    if (savedSocket === undefined) delete process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET;
    else process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET = savedSocket;
    if (savedInitial === undefined) delete process.env.NANO_E2E_INITIAL_LOGICAL_CLOCK_MS;
    else process.env.NANO_E2E_INITIAL_LOGICAL_CLOCK_MS = savedInitial;
    if (savedPublic === undefined) delete process.env.IM_PUBLIC_MODE;
    else process.env.IM_PUBLIC_MODE = savedPublic;
  });

  it('refuses activation when IM_PUBLIC_MODE=1 and stays inert when unset', () => {
    delete process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET;
    delete process.env.IM_PUBLIC_MODE;
    const noopTarget = { advancePartitions: async () => {}, tickNode: async () => {}, isNodeBusy: () => false };
    expect(LogicalClockController.fromEnvironment(noopTarget)).toBeUndefined();

    process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET = '/tmp/forbidden.sock';
    process.env.IM_PUBLIC_MODE = '1';
    expect(() => LogicalClockController.fromEnvironment(noopTarget)).toThrow('IM_PUBLIC_MODE=1');
  });

  it('serves 0600 Unix socket RPCs, enforces monotonicity, settles node work, and unlinks on close', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'nano-logical-clock-'));
    const sockPath = join(dir, 'clock.sock');
    const baseMs = Date.now() + 3_600_000;
    process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET = sockPath;
    process.env.NANO_E2E_INITIAL_LOGICAL_CLOCK_MS = String(baseMs);
    delete process.env.IM_PUBLIC_MODE;

    const events: string[] = [];
    let busyPolls = 0;
    const controller = LogicalClockController.fromEnvironment({
      advancePartitions: async (nowMs, settle) => {
        events.push(`partitions:${nowMs}:${settle}`);
      },
      tickNode: async nowMs => {
        events.push(`node:${nowMs}`);
        busyPolls = 1;
      },
      isNodeBusy: () => {
        if (busyPolls > 0) {
          busyPolls--;
          return true;
        }
        return false;
      },
    })!;

    try {
      await controller.start();
      const mode = (await stat(sockPath)).mode & 0o777;
      expect(mode).toBe(0o600);

      const status = await rpcCall(sockPath, 'clock.status') as { nowMs: number };
      expect(status.nowMs).toBeGreaterThanOrEqual(baseMs);

      const targetMs = baseMs + 1_800_000;
      const advanced = await rpcCall(sockPath, 'clock.advance', { targetMs, settle: true }) as { nowMs: number };
      expect(advanced.nowMs).toBe(targetMs);
      expect(events).toEqual([
        `partitions:${targetMs}:true`,
        `node:${targetMs}`,
        `partitions:${targetMs}:true`,
        `partitions:${targetMs}:true`,
      ]);

      await expect(rpcCall(sockPath, 'clock.advance', { targetMs: targetMs - 1000 })).rejects.toThrow('monotonic');
    } finally {
      await controller.close();
      await expect(stat(sockPath)).rejects.toThrow();
      await rm(dir, { recursive: true, force: true });
    }
  });
});
