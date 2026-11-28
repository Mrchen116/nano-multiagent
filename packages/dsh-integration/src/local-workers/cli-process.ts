/// <reference lib="es2024.promise" />
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { createInterface } from 'node:readline';
import { nativeCliEnvironment } from './cli-environment.js';
import { isWindowsBatch } from './worker-executable.js';
import { terminateRuntimeTree } from '../runtime-health.js';

/** A request deadline bounds protocol acknowledgments, never the worker's model turn. */
export async function acknowledged<T>(promise: Promise<T>, action: string, timeout = 60_000): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timed out waiting for ${action}`)), timeout);
    timer.unref();
  });
  try {
    return await Promise.race([promise, deadline]);
  } finally {
    clearTimeout(timer);
  }
}

export interface CliProcessOptions {
  env?: Record<string, string | undefined>;
  onStdoutLine?: (line: string) => Error | undefined;
  onCleanup?: () => Promise<void>;
}

/** Local CLIs use independent protocols over newline-delimited JSON. */
export class CliProcess {
  private readonly child;
  private readonly pending = new Map<string | number, PromiseWithResolvers<unknown>>();
  private readonly closed = Promise.withResolvers<void>();
  private cleanupPromise?: Promise<void>;
  private stderr = '';
  private failure?: Error;
  private closing = false;
  onMessage: (value: any) => void = () => {};
  onExit: (error: Error) => void = () => {};

  constructor(runtime: string, args: string[], cwd: string, private readonly options?: CliProcessOptions) {
    const env = nativeCliEnvironment();
    for (const [key, value] of Object.entries(options?.env ?? {})) {
      if (value === undefined) delete env[key];
      else env[key] = value;
    }
    let command = runtime;
    const batch = isWindowsBatch(runtime);
    if (batch) {
      command = join(process.env.SystemRoot!, 'System32', 'cmd.exe');
      // Values are expanded once, inside quotes. Only paths, fixed flags and the session ID
      // reach cmd; Claude's free-form prompt and MCP config are loaded from files.
      env.NANO_CLI_COMMAND = [runtime, ...args].map(value => {
        if (/["\r\n]/.test(value)) throw new Error('Invalid Windows batch worker argument');
        return `"${value}"`;
      }).join(' ');
      args = ['/d', '/v:off', '/s', '/c', '"%NANO_CLI_COMMAND%"'];
    }
    this.child = spawn(command, args, {
      cwd,
      env,
      stdio: 'pipe',
      windowsVerbatimArguments: batch,
      detached: process.platform !== 'win32',
    });
    this.child.stderr.setEncoding('utf8').on('data', (chunk: string) => {
      this.stderr = (this.stderr + chunk).slice(-2048);
    });
    const lines = createInterface({ input: this.child.stdout, crlfDelay: Infinity });
    lines.on('line', (line) => {
      const lineError = options?.onStdoutLine?.(line);
      if (lineError) {
        this.fail(lineError);
        void this.close().catch(console.error);
        return;
      }
      try {
        this.onMessage(JSON.parse(line));
      } catch (error) {
        this.fail(new Error(`${runtime} protocol error: ${String(error)}`));
        void this.close().catch(console.error);
      }
    });
    this.child.once('error', (error) => {
      this.fail(error);
      this.closed.resolve();
      void this.runCleanup();
    });
    this.child.stdin.on('error', () => {}); // Write callbacks and close carry the concrete failure to pending callers.
    this.child.once('close', (code, signal) => {
      this.fail(
        new Error(
          `${runtime} exited (${signal ?? code})${this.stderr.trim() ? `: ${this.stderr.trim()}` : ''}`,
        ),
      );
      this.closed.resolve();
      void this.runCleanup();
    });
  }

  get ended() {
    return this.closing || !!this.failure;
  }

  private runCleanup() {
    this.cleanupPromise ??= Promise.resolve()
      .then(() => this.options?.onCleanup?.())
      .catch(() => {});
    return this.cleanupPromise;
  }

  private fail(error: Error) {
    if (this.failure) return;
    this.failure = error;
    for (const pending of this.pending.values()) pending.reject(error);
    this.pending.clear();
    if (!this.closing) this.onExit(error);
  }

  async write(value: unknown) {
    if (this.ended) throw this.failure ?? new Error('Worker process is closing');
    await new Promise<void>((resolve, reject) =>
      this.child.stdin.write(JSON.stringify(value) + '\n', (error) => (error ? reject(error) : resolve())),
    );
  }

  async request<T>(id: string | number, frame: unknown, action: string) {
    const response = Promise.withResolvers<unknown>();
    this.pending.set(id, response);
    try {
      const [, result] = await acknowledged(Promise.all([this.write(frame), response.promise]), action);
      return result as T;
    } finally {
      this.pending.delete(id);
    }
  }

  /** Send a JSON-RPC request whose completion is bounded by the turn lifecycle rather than handshake ack. */
  async sendRequest<T>(id: string | number, frame: unknown): Promise<{ sent: void; response: Promise<T> }> {
    const response = Promise.withResolvers<unknown>();
    this.pending.set(id, response);
    const cleaned = response.promise.finally(() => {
      this.pending.delete(id);
    }) as Promise<T>;
    // Prevent unhandled rejection if the caller attaches its handler after write settles.
    void cleaned.catch(() => {});
    try {
      const sent = await this.write(frame);
      return { sent, response: cleaned };
    } catch (error) {
      this.pending.delete(id);
      throw error;
    }
  }

  resolve(id: string | number, result: unknown, error?: string | { code?: number; message?: string }) {
    const pending = this.pending.get(id);
    if (error !== undefined) {
      const err =
        typeof error === 'string'
          ? new Error(error)
          : Object.assign(
              new Error(error.message ?? 'RPC error'),
              error.code !== undefined ? { code: error.code } : {},
            );
      pending?.reject(err);
    } else pending?.resolve(result);
  }

  async close() {
    if (!this.closing) {
      this.closing = true;
      const pid = this.child.pid;
      if (pid && this.child.exitCode === null && this.child.signalCode === null)
        await terminateRuntimeTree(pid);
    }
    await this.closed.promise;
    await this.runCleanup();
  }
}
