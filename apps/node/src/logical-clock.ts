import { createServer, type Server, type Socket } from 'node:net';
import { createInterface } from 'node:readline';
import { chmod, mkdir, rm } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

export interface LogicalClockTarget {
  advancePartitions(nowMs: number, settle: boolean): Promise<void>;
  tickNode(nowMs: number): Promise<void>;
  isNodeBusy(): boolean;
}

/** Isolated E2E-only monotonic logical clock Unix socket; zero HTTP surface and refused in public mode. */
export class LogicalClockController {
  private server?: Server;
  private readonly sockets = new Set<Socket>();
  private currentMs: number;
  private chain: Promise<unknown> = Promise.resolve();
  readonly socketPath: string;

  private constructor(socketPath: string, initialNowMs: number, private readonly target: LogicalClockTarget) {
    this.socketPath = resolve(socketPath);
    this.currentMs = initialNowMs;
  }

  /** Create a logical clock controller strictly when NANO_E2E_LOGICAL_CLOCK_SOCKET is set outside public mode. */
  static fromEnvironment(target: LogicalClockTarget): LogicalClockController | undefined {
    const rawPath = process.env.NANO_E2E_LOGICAL_CLOCK_SOCKET?.trim();
    if (!rawPath) return undefined;
    if (process.env.IM_PUBLIC_MODE === '1') {
      throw new Error('NANO_E2E_LOGICAL_CLOCK_SOCKET is forbidden when IM_PUBLIC_MODE=1');
    }
    const rawInitial = process.env.NANO_E2E_INITIAL_LOGICAL_CLOCK_MS?.trim();
    const parsedInitial = rawInitial ? Number(rawInitial) : Date.now();
    if (!Number.isSafeInteger(parsedInitial) || parsedInitial < Date.now() - 60_000) {
      throw new Error('NANO_E2E_INITIAL_LOGICAL_CLOCK_MS must be a safe integer >= current wall clock');
    }
    return new LogicalClockController(rawPath, Math.max(Date.now(), parsedInitial), target);
  }

  now(): number {
    return this.currentMs;
  }

  async start(): Promise<void> {
    await mkdir(dirname(this.socketPath), { recursive: true, mode: 0o700 });
    await rm(this.socketPath, { force: true });
    this.server = createServer(socket => this.attachSocket(socket));
    await new Promise<void>((resolveListen, rejectListen) => {
      this.server!.once('error', rejectListen);
      this.server!.listen(this.socketPath, () => {
        this.server!.off('error', rejectListen);
        resolveListen();
      });
    });
    await chmod(this.socketPath, 0o600);
  }

  async close(): Promise<void> {
    for (const socket of this.sockets) socket.destroy();
    this.sockets.clear();
    if (this.server) {
      const active = this.server;
      this.server = undefined;
      await new Promise<void>(resolveClose => active.close(() => resolveClose()));
    }
    await rm(this.socketPath, { force: true });
  }

  async advance(input: { targetIso?: string; targetMs?: number; settle?: boolean }): Promise<{ nowMs: number; nowIso: string }> {
    const run = this.chain.catch(() => {}).then(async () => {
      const nextMs = typeof input.targetMs === 'number'
        ? input.targetMs
        : typeof input.targetIso === 'string'
          ? Date.parse(input.targetIso)
          : NaN;
      if (!Number.isSafeInteger(nextMs)) throw new Error('clock.advance requires a valid targetIso or targetMs');
      if (nextMs < this.currentMs) throw new Error(`Logical clock is monotonic: target ${nextMs} < current ${this.currentMs}`);
      const settle = input.settle !== false;
      this.currentMs = nextMs;
      await this.target.advancePartitions(nextMs, settle);
      await this.target.tickNode(nextMs);
      if (settle) {
        const deadline = Date.now() + 180_000;
        for (;;) {
          await this.target.advancePartitions(nextMs, true);
          if (!this.target.isNodeBusy()) break;
          if (Date.now() > deadline) throw new Error('Logical clock settle timed out while node work remained active');
          await new Promise<void>(r => setTimeout(r, 100));
        }
      }
      return { nowMs: this.currentMs, nowIso: new Date(this.currentMs).toISOString() };
    });
    this.chain = run;
    return run;
  }

  private attachSocket(socket: Socket): void {
    this.sockets.add(socket);
    socket.once('close', () => this.sockets.delete(socket));
    const lines = createInterface({ input: socket, crlfDelay: Infinity });
    lines.on('line', line => {
      if (!line.trim()) return;
      void (async () => {
        let id: unknown = null;
        try {
          const req = JSON.parse(line) as { id?: unknown; method?: string; params?: Record<string, unknown> };
          id = req.id ?? null;
          let result: unknown;
          if (req.method === 'clock.status') {
            result = { nowMs: this.currentMs, nowIso: new Date(this.currentMs).toISOString() };
          } else if (req.method === 'clock.advance') {
            result = await this.advance((req.params ?? {}) as { targetIso?: string; targetMs?: number; settle?: boolean });
          } else {
            throw new Error(`Unsupported logical clock method: ${String(req.method)}`);
          }
          socket.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
        } catch (error) {
          socket.write(JSON.stringify({
            jsonrpc: '2.0',
            id,
            error: { code: -32000, message: error instanceof Error ? error.message : String(error) },
          }) + '\n');
        }
      })();
    });
  }
}
