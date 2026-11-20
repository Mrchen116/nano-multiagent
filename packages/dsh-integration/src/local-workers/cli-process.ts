/// <reference lib="es2024.promise" />
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { nativeCliEnvironment } from './cli-environment.js';
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

/** The two CLIs use independent protocols over newline-delimited JSON. */
export class CliProcess {
  private readonly child;
  private readonly pending = new Map<string | number, PromiseWithResolvers<unknown>>();
  private readonly closed = Promise.withResolvers<void>();
  private stderr = '';
  private failure?: Error;
  private closing = false;
  onMessage: (value: any) => void = () => {};
  onExit: (error: Error) => void = () => {};

  constructor(runtime: string, args: string[], cwd: string) {
    this.child = spawn(runtime, args, {
      cwd,
      env: nativeCliEnvironment(),
      stdio: 'pipe',
      detached: process.platform !== 'win32',
    });
    this.child.stderr.setEncoding('utf8').on('data', (chunk: string) => {
      this.stderr = (this.stderr + chunk).slice(-2048);
    });
    const lines = createInterface({ input: this.child.stdout, crlfDelay: Infinity });
    lines.on('line', (line) => {
      try {
        this.onMessage(JSON.parse(line));
      } catch (error) {
        this.fail(new Error(`${runtime} protocol error: ${String(error)}`));
        void this.close().catch(console.error);
      }
    });
    this.child.once('error', (error) => this.fail(error));
    this.child.stdin.on('error', () => {}); // Write callbacks and close carry the concrete failure to pending callers.
    this.child.once('close', (code, signal) => {
      this.fail(
        new Error(
          `${runtime} exited (${signal ?? code})${this.stderr.trim() ? `: ${this.stderr.trim()}` : ''}`,
        ),
      );
      this.closed.resolve();
    });
  }

  get ended() {
    return this.closing || !!this.failure;
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

  resolve(id: string | number, result: unknown, error?: string) {
    const pending = this.pending.get(id);
    if (error !== undefined) pending?.reject(new Error(error));
    else pending?.resolve(result);
  }

  async close() {
    if (!this.closing) {
      this.closing = true;
      const pid = this.child.pid;
      if (pid && this.child.exitCode === null && this.child.signalCode === null)
        await terminateRuntimeTree(pid);
    }
    await this.closed.promise;
  }
}
