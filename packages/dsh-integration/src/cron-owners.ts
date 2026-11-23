import { createHash } from 'node:crypto';
import { rm } from 'node:fs/promises';
import { join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { Storage } from '@deepseek-ai/dsh-storage';
import * as StorageJson from '@deepseek-ai/dsh-storage-json';
import * as StorageDomain from '@deepseek-ai/dsh-storage-domain';
import { ScheduleService, scheduleDomain, isRecurringScheduleRecord, resolveRecurringOccurrence, ScheduleId } from '@deepseek-ai/dsh-schedule';
import type { ScheduleOutput } from '@nano/product-contracts/runtime-rpc';
import { SessionId } from '@deepseek-ai/dsh-session';
import { scheduleRealm } from './features/cron.js';

type Fiber = ReturnType<Context['plugin']>;
interface Owner { ctx: Context; domain: StorageDomain.DomainFacility; fiber?: Fiber; schedule?: ScheduleService; chain: Promise<unknown>; storageFibers: Fiber[] }

/** Native storage realms keep each Agent's schedule table and timer independent. */
export class CronOwners {
  private readonly owners = new Map<string, Promise<Owner>>();
  private paused?: string[];
  private stopped = false;
  private readonly disabled = new Set<string>();
  /** Close timer admission synchronously, before asynchronous owner teardown. */
  block(agentId: string, disabled: boolean): void { if (disabled) this.disabled.add(agentId); else this.disabled.delete(agentId); }
  constructor(private readonly ctx: Context, private readonly home: string, private readonly held: (agentId: string, action: string) => boolean = () => false) {}
  private owner(agentId: string): Promise<Owner> {
    let owner = this.owners.get(agentId);
    if (!owner) {
      owner = (async () => {
        const label = scheduleRealm(agentId);
        const ctx = this.ctx.isolate('schedule', label)
          .isolate('storage', Symbol.for(`nano-storage:${agentId}`))
          .isolate('storageDomain', Symbol.for(`nano-storage-domain:${agentId}`))
          .isolate('storage.backend.json', Symbol.for(`nano-storage-json:${agentId}`));
        const storage = ctx.plugin(Storage); await storage.await();
        const json = ctx.plugin(StorageJson, { root: join(this.home, 'schedules', createHash('sha256').update(agentId).digest('hex')) }); await json.await();
        let domain!: StorageDomain.DomainFacility;
        // Keep both native dependencies in one fiber: alpha.1's nested domain
        // injection loses the isolated storage dependency through its shadow ctx.
        const domainFiber = ctx.inject(['storage', 'storage.backend.json'], child => {
          domain = new StorageDomain.DomainFacility(child, { backend: 'json' });
          const unmount = child.storage.mount('domain', domain);
          child.effect(() => async () => { await domain.closeAll(); unmount(); });
          child.provide('storageDomain', domain);
        });
        await domainFiber.await();
        return { ctx, domain, chain: Promise.resolve(), storageFibers: [domainFiber, json, storage] };
      })();
      this.owners.set(agentId, owner);
    }
    return owner;
  }
  async setEnabled(agentId: string, enabled: boolean): Promise<void> {
    if (enabled && (this.stopped || this.disabled.has(agentId))) throw new Error('agent_disabled');
    const owner = await this.owner(agentId);
    const change = owner.chain.then(async () => {
      if (enabled && (this.stopped || this.disabled.has(agentId))) throw new Error('agent_disabled');
      if (enabled && !owner.fiber) {
        owner.fiber = owner.ctx.plugin(ScheduleService, {}); await owner.fiber.await();
        owner.schedule = await new Promise<ScheduleService>(resolve => { owner.fiber!.ctx.inject(['schedule'], child => { resolve(child.schedule); }); });
        await owner.schedule.catalog();
      }
      else if (!enabled && owner.fiber) { await owner.fiber.dispose(); owner.fiber = undefined; owner.schedule = undefined; }
    });
    owner.chain = change.catch(() => {}); return change;
  }
  private async command<T>(agentId: string, action: string, run: (owner: Owner) => Promise<T>): Promise<T> {
    const owner = await this.owner(agentId);
    const result = owner.chain.then(() => {
      if (this.stopped || this.disabled.has(agentId) && !['catalog', 'history'].includes(action)) throw new Error('agent_disabled');
      if (this.held(agentId, action)) throw new Error('Capability is reserved by configuration');
      return run(owner);
    });
    owner.chain = result.catch(() => {});
    return result;
  }

  catalog(agentId: string) {
    return this.command(agentId, 'catalog', async owner => {
      if (owner.fiber) return owner.schedule!.catalog();
      const domain = await owner.domain.open(scheduleDomain);
      try {
        return [...domain.table('tasks').entries()].map(([, task]) => ({
          ...task.record, sessionId: task.sessionId, status: task.status,
          ...(task.lastDelivery ? {lastDelivery: task.lastDelivery} : {}),
        }));
      } finally { await domain.close(); }
    });
  }

  history(agentId: string, sessionId: string, id: string, limit = 20): Promise<ScheduleOutput<'history'>> {
    return this.command(agentId, 'history', async owner => {
      if (owner.fiber) return owner.schedule!.history({sessionId: SessionId(sessionId), id: ScheduleId(id), limit});
      const domain = await owner.domain.open(scheduleDomain);
      try {
        const task = domain.table('tasks').get(ScheduleId(id));
        if (!task || task.sessionId !== sessionId) throw new Error('Unknown schedule');
        return {id, records: [...(task.deliveryHistory?.records ?? (task.lastDelivery ? [task.lastDelivery] : []))].reverse().slice(0, limit),
          earlierRecordsUnavailable: task.deliveryHistory?.earlierRecordsUnavailable ?? true};
      } finally { await domain.close(); }
    });
  }

  withSchedule<T>(agentId: string, action: string, run: (schedule: ScheduleService) => Promise<T>): Promise<T> {
    return this.command(agentId, action, async owner => {
      if (!owner.fiber) throw new Error('Schedule service is unavailable');
      return run(owner.schedule!);
    });
  }

  /** Advance saved independent schedules before mounting timers; never replay missed occurrences. */
  async skipMissed(agentId: string, blockedSchedules: Set<string>, now = Date.now()): Promise<void> {
    const owner = await this.owner(agentId);
    const domain = await owner.domain.open(scheduleDomain);
    try {
      const tasks = domain.table('tasks');
      for (const [id, task] of tasks.entries()) {
        if (task.status !== 'active') continue;
        if (blockedSchedules.has(id)) { await tasks.put(id, {...task, status: 'inactive'}); continue; }
        if (Date.parse(task.record.scheduledAt) > now) continue;
        const next = isRecurringScheduleRecord(task.record) ? resolveRecurringOccurrence(task.record, now).nextScheduledAt : undefined;
        await tasks.put(id, next ? {...task, record: {...task.record, scheduledAt: next}} : {...task, status: 'inactive'});
      }
    } finally { await domain.close(); }
  }
  /** Suspend timers without changing saved jobs or the user's Feature setting. */
  async pause(): Promise<void> {
    if (this.paused) return;
    this.paused = [];
    for (const [agentId, pending] of this.owners) {
      const owner = await pending;
      await owner.chain;
      if (owner.fiber) { this.paused.push(agentId); await this.setEnabled(agentId, false); }
    }
  }
  /** Restore only timer owners that were enabled when the update acquired them. */
  async resume(): Promise<void> {
    const paused = this.paused;
    if (!paused) return;
    for (const agentId of paused) if (!this.disabled.has(agentId)) await this.setEnabled(agentId, true);
    this.paused = undefined;
  }
  /** Release a temporary catalog owner, or close a durable owner at shutdown. */
  async disposeAgent(agentId: string, removeData = false): Promise<void> {
    const pending = this.owners.get(agentId);
    if (pending) {
      const owner = await pending; await owner.chain; await owner.fiber?.dispose();
      for (const fiber of owner.storageFibers) await fiber.dispose();
      this.owners.delete(agentId);
    }
    if (removeData) await rm(join(this.home, 'schedules', createHash('sha256').update(agentId).digest('hex')), { recursive: true, force: true });
  }
  async dispose(): Promise<void> {
    this.stopped = true;
    for (const agentId of this.owners.keys()) await this.disposeAgent(agentId);
  }
}
