import { spawn } from 'node:child_process';
import { open, readFile, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { nodeUpdateTerminal, type NodeUpdateReport, type NodeUpdateState } from '@nano/product-contracts';
import type { NodeConfiguration } from './configuration.js';
import { atomicPrivate, processBirth } from './lifecycle.js';

export interface UpdateLease {
  operation_id: string; worker_pid: number; worker_birth: string; heartbeat: number;
  state: NodeUpdateState; command?: 'prepare' | 'resume'; sequence: number;
}
export interface UpdateHandoff {
  operation_id: string; worker_pid: number; worker_birth: string; sequence: number;
  node_pid: number; node_birth: string; ready: boolean;
}
export const updatePath = (config: string, name = '.node-update.json') => join(dirname(config), name);
export async function readUpdateFile<T>(path: string): Promise<T | undefined> {
  try { return JSON.parse(await readFile(path, 'utf8')) as T; }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return; throw error; }
}
export async function validLease(lease: UpdateLease): Promise<boolean> {
  return Date.now() - lease.heartbeat < 15000 && await processBirth(lease.worker_pid) === lease.worker_birth;
}
/** Send only the authenticated operation protocol, never a caller-supplied package URL. */
export async function reportUpdate(config: NodeConfiguration, operation: string, action: string,
  extra: {state?: NodeUpdateState; error_code?: string; resumed?: boolean} = {}): Promise<NodeUpdateReport> {
  const response = await fetch(new URL('/im/v1/node-update/report', config.value.im_service.url), {
    method: 'POST', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${config.value.im_service.token}`},
    body: JSON.stringify({node_id: config.value.node.node_id, operation_id: operation, action, ...extra}),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`Update report rejected (${response.status})`);
  return await response.json() as NodeUpdateReport;
}

/** Own the local admission barrier; a detached worker exclusively owns the update journal. */
export class NodeUpdater {
  private timer?: NodeJS.Timeout;
  private busy = false;
  private held?: string;
  private handled = '';
  private closed = false;
  constructor(private readonly config: NodeConfiguration, private readonly hooks: {
    prepare(operationId: string): Promise<boolean>; resume(operationId: string): Promise<void>; onError?(error: unknown): void;
  }) {}
  /** Start recovery and barrier lease monitoring without authorizing new work. */
  async start(): Promise<void> {
    await this.tick();
    this.timer = setInterval(() => { void this.tick().catch(error => this.hooks.onError?.(error)); }, 500);
    this.timer.unref();
  }
  /** Launch one independent worker for an operation received on the authenticated relay. */
  async request(operationId: string): Promise<void> {
    if (!operationId || this.closed) throw new Error('Invalid update request');
    const fd = await open(updatePath(this.config.path, 'node-update.log'), 'a', 0o600);
    try {
      const child = spawn(process.execPath, [fileURLToPath(new URL('./update-worker.js', import.meta.url)), this.config.path, operationId],
        {detached: true, stdio: ['ignore', fd.fd, fd.fd], env: process.env});
      await new Promise<void>((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
      child.unref();
    } finally { await fd.close(); }
  }
  private async release(operation: string): Promise<void> {
    await this.hooks.resume(operation);
    this.held = undefined;
    const handoff = await readUpdateFile<UpdateHandoff>(updatePath(this.config.path, '.node-update-handoff.json'));
    if (handoff?.operation_id === operation) await rm(updatePath(this.config.path, '.node-update-handoff.json'), {force: true});
  }
  private async tick(): Promise<void> {
    if (this.busy || this.closed) return;
    this.busy = true;
    try {
      const lease = await readUpdateFile<UpdateLease>(updatePath(this.config.path));
      if (!lease) return;
      if (!await validLease(lease)) {
        const marker = `dead:${lease.operation_id}`;
        if (this.handled === marker) return;
        await this.release(lease.operation_id);
        if (!nodeUpdateTerminal(lease.state)) await reportUpdate(this.config, lease.operation_id, 'terminal',
          {state: ['switching', 'verifying', 'rolling_back'].includes(lease.state) ? 'recovery_required' : 'interrupted', resumed: true, error_code: 'worker_lost'});
        this.handled = marker;
        return;
      }
      const marker = `${lease.operation_id}:${lease.sequence}`;
      if (this.handled === marker || !lease.command) return;
      if (lease.command === 'resume') {
        await this.release(lease.operation_id);
        await this.writeHandoff(lease, false);
      } else {
        let ready = false;
        try { ready = await this.hooks.prepare(lease.operation_id); }
        catch (error) { this.hooks.onError?.(error); }
        if (ready) this.held = lease.operation_id;
        // Preparation may take time; a dead worker must never acquire a fresh handoff.
        const current = await readUpdateFile<UpdateLease>(updatePath(this.config.path));
        if (!current || current.sequence !== lease.sequence || !await validLease(current)) {
          await this.release(lease.operation_id); return;
        }
        if (!ready) await this.release(lease.operation_id);
        await this.writeHandoff(lease, ready);
      }
      this.handled = marker;
    } finally { this.busy = false; }
  }
  private async writeHandoff(lease: UpdateLease, ready: boolean): Promise<void> {
    const node_birth = await processBirth(process.pid);
    if (!node_birth) throw new Error('Cannot establish update controller identity');
    await atomicPrivate(updatePath(this.config.path, '.node-update-handoff.json'), {
      operation_id: lease.operation_id, worker_pid: lease.worker_pid, worker_birth: lease.worker_birth,
      sequence: lease.sequence, node_pid: process.pid, node_birth, ready,
    } satisfies UpdateHandoff);
  }
  /** Release local gates when the owning Node shuts down. */
  async close(): Promise<void> {
    this.closed = true;
    clearInterval(this.timer);
    if (this.held) await this.release(this.held);
  }
}
