import { createHash } from 'node:crypto';
import { rm } from 'node:fs/promises';
import { join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { Storage } from '@deepseek-ai/dsh-storage';
import * as StorageJson from '@deepseek-ai/dsh-storage-json';
import * as StorageDomain from '@deepseek-ai/dsh-storage-domain';
import {
  ScheduleService,
  scheduleDomain,
  isRecurringScheduleRecord,
  resolveRecurringOccurrence,
  ScheduleId,
  ScheduleInputError,
  type AtInput,
  type CronInput,
  type DailyInput,
  type ScheduleCatalogEntry,
  type SchedulePatch,
  type ScheduleRecord,
  type ScheduleTarget,
  type ScheduleTiming,
  type WeeklyInput,
} from '@deepseek-ai/dsh-schedule';
import type { ScheduleInput, ScheduleOutput } from '@nano/product-contracts/runtime-rpc';
import { SessionId } from '@deepseek-ai/dsh-session';
import { scheduleRealm } from './features/cron.js';

type Fiber = ReturnType<Context['plugin']>;
interface Owner { ctx: Context; domain: StorageDomain.DomainFacility; fiber?: Fiber; schedule?: ScheduleService; chain: Promise<unknown>; storageFibers: Fiber[] }

export function targetSessionId(target: ScheduleTarget): string | undefined {
  return target.kind === 'session' || target.kind === 'new_once' ? target.sessionId : undefined;
}

export function toScheduleRecord(entry: ScheduleCatalogEntry | ScheduleRecord): ScheduleOutput<'list'>[number] {
  const { id, kind, title, prompt, scheduledAt } = entry;
  switch (kind) {
    case 'after': return { id, kind, title, prompt, afterSeconds: entry.afterSeconds, scheduledAt };
    case 'at': return { id, kind, title, prompt, scheduledAt };
    case 'every': return { id, kind, title, prompt, everySeconds: entry.everySeconds, scheduledAt };
    case 'daily': return { id, kind, title, prompt, time: entry.time, timeZone: entry.timeZone, scheduledAt };
    case 'weekly': return { id, kind, title, prompt, time: entry.time, timeZone: entry.timeZone, weekdays: [...entry.weekdays], scheduledAt };
    case 'cron': return { id, kind, title, prompt, expression: entry.expression, timeZone: entry.timeZone, scheduledAt };
    case 'rrule': return { id, kind, title, prompt, rrule: entry.rrule, scheduledAt };
  }
}

export interface ScheduleSelectorInput {
  after_seconds?: number;
  every_seconds?: number;
  at?: AtInput;
  daily?: DailyInput;
  weekly?: WeeklyInput;
  cron?: CronInput;
  rrule?: string;
}

export function toScheduleTiming(args: ScheduleSelectorInput): ScheduleTiming {
  const selectors = [args.after_seconds, args.every_seconds, args.at, args.daily, args.weekly, args.cron, args.rrule]
    .filter(value => value !== undefined);
  if (selectors.length !== 1) throw new ScheduleInputError('invalid_selector', 'Provide exactly one scheduling rule.');
  if (args.after_seconds !== undefined) return { kind: 'after', after_seconds: args.after_seconds };
  if (args.at !== undefined) return { kind: 'at', at: args.at };
  if (args.every_seconds !== undefined) return { kind: 'every', every_seconds: args.every_seconds };
  if (args.daily !== undefined) return { kind: 'daily', daily: args.daily };
  if (args.weekly !== undefined) return { kind: 'weekly', weekly: args.weekly };
  if (args.cron !== undefined) return { kind: 'cron', cron: args.cron };
  return { kind: 'rrule', rrule: args.rrule! };
}

function sameScheduleRecord(left: ScheduleOutput<'list'>[number], right: ScheduleOutput<'list'>[number]): boolean {
  return JSON.stringify(left) === JSON.stringify(toScheduleRecord(right as ScheduleRecord));
}

export async function createSessionSchedule(
  service: ScheduleService,
  sessionId: string,
  args: { title: string; prompt: string } & ScheduleSelectorInput,
  signal?: AbortSignal,
): Promise<ScheduleOutput<'create'>> {
  const created = await service.create({
    title: args.title,
    prompt: args.prompt,
    timing: toScheduleTiming(args),
    target: { kind: 'session', sessionId: SessionId(sessionId) },
  }, SessionId(sessionId), signal);
  return toScheduleRecord(created);
}

export async function listSessionSchedules(service: ScheduleService, sessionId: string): Promise<ScheduleOutput<'list'>> {
  const entries = await service.catalog();
  return entries
    .filter(entry => entry.status === 'active' && targetSessionId(entry.target) === sessionId)
    .map(toScheduleRecord);
}

export async function updateSessionSchedule(
  service: ScheduleService,
  sessionId: string,
  args: ScheduleInput<'update'>['args'],
  signal?: AbortSignal,
): Promise<ScheduleOutput<'update'>> {
  const id = ScheduleId(args.id);
  const current = await service.view({ id });
  if ('code' in current || targetSessionId(current.target) !== sessionId) {
    return { id: args.id, updated: false, code: 'schedule_not_found' };
  }
  if (current.status !== 'active' && args.change === undefined) {
    return { id: args.id, updated: false, code: 'schedule_ended' };
  }
  const currentRecord = toScheduleRecord(current);
  if (!sameScheduleRecord(currentRecord, args.expected)) {
    return { id: args.id, updated: false, code: 'schedule_conflict' };
  }
  const patch: SchedulePatch = {
    ...(args.title !== undefined ? { title: args.title } : {}),
    ...(args.prompt !== undefined ? { prompt: args.prompt } : {}),
    ...(args.change !== undefined ? { timing: args.change, ...(current.status !== 'active' ? { active: true } : {}) } : {}),
  };
  if (Object.keys(patch).length === 0) {
    return { id: args.id, updated: false, record: currentRecord };
  }
  try {
    const edited = await service.edit({
      id,
      action: 'update',
      patch,
      ...(current.updatedAt !== undefined ? { expectedUpdatedAt: current.updatedAt } : {}),
    }, SessionId(sessionId), signal);
    if ('code' in edited) return { id: args.id, updated: false, code: edited.code };
    if ('deleted' in edited) return { id: args.id, updated: false, code: 'schedule_not_found' };
    const nextRecord = toScheduleRecord(edited);
    const changed = !sameScheduleRecord(currentRecord, nextRecord) || current.status !== edited.status;
    return { id: args.id, updated: changed, record: nextRecord };
  } catch (error) {
    if (error instanceof ScheduleInputError) return { code: error.code, message: error.message };
    return { code: 'internal_error', message: 'The schedule operation failed.' };
  }
}

export async function deleteSessionSchedule(
  service: ScheduleService,
  sessionId: string,
  rawId: string,
  signal?: AbortSignal,
): Promise<ScheduleOutput<'delete'>> {
  const id = ScheduleId(rawId);
  const current = await service.view({ id });
  if ('code' in current || targetSessionId(current.target) !== sessionId) {
    return { id: rawId, deleted: false, code: 'schedule_not_found' };
  }
  const edited = await service.edit({ id, action: 'delete' }, SessionId(sessionId), signal);
  if ('deleted' in edited && edited.deleted) return { id: rawId, deleted: true };
  return { id: rawId, deleted: false, code: 'schedule_not_found' };
}

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
        // Keep both native dependencies in one fiber so isolated storage stays bound.
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

  catalog(agentId: string): Promise<ScheduleOutput<'catalog'>> {
    return this.command(agentId, 'catalog', async owner => {
      if (owner.fiber) {
        const entries = await owner.schedule!.catalog();
        return entries.flatMap(entry => {
          const sessionId = targetSessionId(entry.target);
          if (!sessionId) return [];
          return [{
            ...toScheduleRecord(entry),
            sessionId,
            status: entry.status === 'active' ? 'active' as const : 'inactive' as const,
            ...(entry.lastDelivery ? { lastDelivery: {
              scheduledAt: entry.lastDelivery.scheduledAt,
              deliveredAt: entry.lastDelivery.deliveredAt,
              messageId: entry.lastDelivery.messageId,
            } } : {}),
          }];
        });
      }
      const domain = await owner.domain.open(scheduleDomain);
      try {
        return [...domain.table('tasks').entries()].flatMap(([, task]) => {
          const sessionId = targetSessionId(task.target);
          if (!sessionId) return [];
          return [{
            ...toScheduleRecord(task.record),
            sessionId,
            status: task.status === 'active' ? 'active' as const : 'inactive' as const,
            ...(task.lastDelivery ? { lastDelivery: {
              scheduledAt: task.lastDelivery.scheduledAt,
              deliveredAt: task.lastDelivery.deliveredAt,
              messageId: task.lastDelivery.messageId,
            } } : {}),
          }];
        });
      } finally { await domain.close(); }
    });
  }

  history(agentId: string, sessionId: string, id: string, limit = 20): Promise<ScheduleOutput<'history'>> {
    return this.command(agentId, 'history', async owner => {
      if (owner.fiber) {
        const current = await owner.schedule!.view({ id: ScheduleId(id) });
        if ('code' in current || targetSessionId(current.target) !== sessionId) return { id, code: 'schedule_not_found' };
        const res = await owner.schedule!.history({ id: ScheduleId(id), limit });
        if ('code' in res) return res;
        return {
          id: res.id,
          records: res.records.map(r => ({
            scheduledAt: r.scheduledAt,
            deliveredAt: r.deliveredAt,
            messageId: r.messageId,
            ...(r.prompt !== undefined ? { prompt: r.prompt } : {}),
          })),
          earlierRecordsUnavailable: res.earlierRecordsUnavailable,
          earlierRecordsPruned: res.earlierRecordsPruned,
          retention: res.retention,
          ...(res.nextBefore !== undefined ? { nextBefore: res.nextBefore } : {}),
        };
      }
      const domain = await owner.domain.open(scheduleDomain);
      try {
        const task = domain.table('tasks').get(ScheduleId(id));
        if (!task || targetSessionId(task.target) !== sessionId) throw new Error('Unknown schedule');
        return {
          id,
          records: [...(task.deliveryHistory?.records ?? (task.lastDelivery ? [task.lastDelivery] : []))]
            .reverse()
            .slice(0, limit)
            .map(r => ({
              scheduledAt: r.scheduledAt,
              deliveredAt: r.deliveredAt,
              messageId: r.messageId,
              ...('prompt' in r && r.prompt !== undefined ? { prompt: r.prompt } : {}),
            })),
          earlierRecordsUnavailable: task.deliveryHistory?.earlierRecordsUnavailable ?? true,
        };
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
        if (blockedSchedules.has(id)) { await tasks.put(id, {...task, status: 'ended'}); continue; }
        if (Date.parse(task.record.scheduledAt) > now) continue;
        const next = isRecurringScheduleRecord(task.record) ? resolveRecurringOccurrence(task.record, now).nextScheduledAt : undefined;
        await tasks.put(id, next ? {...task, record: {...task.record, scheduledAt: next}} : {...task, status: 'ended'});
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
