import { createHash, randomUUID } from 'node:crypto';
import { rm } from 'node:fs/promises';
import { join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { Storage } from '@deepseek-ai/dsh-storage';
import * as StorageJson from '@deepseek-ai/dsh-storage-json';
import * as StorageDomain from '@deepseek-ai/dsh-storage-domain';
import { createUserMessage, type UserMessage } from '@deepseek-ai/dsh-llm';
import {
  ScheduleService,
  scheduleDomain,
  isRecurringScheduleRecord,
  resolveRecurringOccurrence,
  renderReminderFraming,
  renderRecurringReminderBatchFraming,
  ScheduleId,
  ScheduleInputError,
  MIN_EVERY_INTERVAL_SECONDS,
  MAX_TITLE_LENGTH,
  REQUIRED_TITLE_MESSAGE,
  scheduleTitle,
  scheduleView,
  createAfterScheduleRecord,
  createAtScheduleRecord,
  createEveryScheduleRecord,
  createDailyScheduleRecord,
  createWeeklyScheduleRecord,
  createCronScheduleRecord,
  type AtInput,
  type DailyInput,
  type WeeklyInput,
  type CronInput,
  type ScheduleRecord,
  type ScheduleTask,
  type ScheduleView,
} from '@deepseek-ai/dsh-schedule';
import type { ScheduleOutput } from '@nano/product-contracts/runtime-rpc';
import { SessionId } from '@deepseek-ai/dsh-session';
import { scheduleRealm } from './features/cron.js';

type Fiber = ReturnType<Context['plugin']>;
interface Owner { ctx: Context; domain: StorageDomain.DomainFacility; fiber?: Fiber; schedule?: ScheduleService; chain: Promise<unknown>; storageFibers: Fiber[] }

const RETENTION_DAYS = 30;
const RETENTION_RECORDS = 200;
const DAY_MS = 86_400_000;

function appendScheduleDelivery(
  task: ScheduleTask,
  receipt: { scheduledAt: string; deliveredAt: string; messageId: UserMessage['id'] },
) {
  const history: NonNullable<ScheduleTask['deliveryHistory']> = task.deliveryHistory ?? {
    records: task.lastDelivery === undefined ? [] : [task.lastDelivery],
    earlierRecordsUnavailable: true,
  };
  const appended = [...history.records, { ...receipt, prompt: task.record.prompt }];
  const floor = Date.parse(receipt.deliveredAt) - RETENTION_DAYS * DAY_MS;
  const retained = appended.filter(record => Date.parse(record.deliveredAt) >= floor).slice(-RETENTION_RECORDS);
  return {
    lastDelivery: receipt,
    deliveryHistory: {
      records: retained,
      earlierRecordsUnavailable: history.earlierRecordsUnavailable || retained.length !== appended.length,
      ...(history.earlierRecordsPruned === true || retained.length !== appended.length ? { earlierRecordsPruned: true } : {}),
    },
  };
}

/** Native storage realms keep each Agent's schedule table and timer independent. */
export class CronOwners {
  private readonly owners = new Map<string, Promise<Owner>>();
  private paused?: string[];
  private stopped = false;
  private readonly disabled = new Set<string>();
  private now = () => Date.now();
  private logicalClock = false;

  /** Close timer admission synchronously, before asynchronous owner teardown. */
  block(agentId: string, disabled: boolean): void { if (disabled) this.disabled.add(agentId); else this.disabled.delete(agentId); }
  constructor(private readonly ctx: Context, private readonly home: string, private readonly held: (agentId: string, action: string) => boolean = () => false) {}

  /** Enable isolated E2E logical clock mode before driving future schedules deterministically. */
  useClock(now: () => number): void {
    this.now = now;
    this.logicalClock = true;
  }

  get isLogicalClock(): boolean {
    return this.logicalClock;
  }

  private async mountService(owner: Owner): Promise<void> {
    if (owner.fiber) return;
    owner.fiber = owner.ctx.plugin(ScheduleService, {});
    await owner.fiber.await();
    owner.schedule = await new Promise<ScheduleService>(resolve => {
      owner.fiber!.ctx.inject(['schedule'], child => { resolve(child.schedule); });
    });
    await owner.schedule.catalog();
  }

  private async unmountService(owner: Owner): Promise<void> {
    if (!owner.fiber) return;
    await owner.fiber.dispose();
    owner.fiber = undefined;
    owner.schedule = undefined;
  }

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
      if (enabled) await this.mountService(owner);
      else await this.unmountService(owner);
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

  /** Align a newly created/updated recurring schedule whose wall-clock target precedes logicalNow. */
  async alignToLogicalClock(agentId: string, scheduleId: string, nowMs = this.now()): Promise<void> {
    if (!this.logicalClock) return;
    await this.command(agentId, 'update', async owner => {
      const wasMounted = Boolean(owner.fiber);
      await this.unmountService(owner);
      const domain = await owner.domain.open(scheduleDomain);
      try {
        const tasks = domain.table('tasks');
        const id = ScheduleId(scheduleId);
        const task = tasks.get(id);
        if (task && task.status === 'active' && isRecurringScheduleRecord(task.record) && Date.parse(task.record.scheduledAt) <= nowMs) {
          const next = resolveRecurringOccurrence(task.record, nowMs).nextScheduledAt;
          await tasks.put(id, next ? { ...task, record: { ...task.record, scheduledAt: next } } : { ...task, status: 'inactive' });
        }
      } finally {
        await domain.close();
        if (wasMounted && !this.stopped && !this.disabled.has(agentId)) await this.mountService(owner);
      }
    });
  }

  /** Create a schedule anchored to the isolated E2E logical clock without mutating ToolExecution. */
  async createAtLogicalClock(
    agentId: string,
    sessionId: string,
    args: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<ScheduleView | { code: string; message: string }> {
    const allowedKeys = new Set(['prompt', 'title', 'after_seconds', 'at', 'every_seconds', 'daily', 'weekly', 'cron']);
    const selectors = [args.after_seconds, args.at, args.every_seconds, args.daily, args.weekly, args.cron].filter(v => v !== undefined).length;
    if (Object.keys(args).some(k => !allowedKeys.has(k)) || selectors !== 1) {
      return { code: 'invalid_selector', message: 'schedule_create accepts exactly one of after_seconds, at, every_seconds, daily, weekly, or cron.' };
    }
    if (typeof args.prompt !== 'string' || args.prompt.trim().length === 0) {
      return { code: 'invalid_prompt', message: 'prompt must be non-empty after trimming.' };
    }
    if (typeof args.title !== 'string' || args.title.trim().length === 0) {
      return { code: 'invalid_prompt', message: REQUIRED_TITLE_MESSAGE };
    }
    if (args.title.trim().length > MAX_TITLE_LENGTH) {
      return { code: 'invalid_prompt', message: `title must be at most ${MAX_TITLE_LENGTH} characters.` };
    }
    if (args.every_seconds !== undefined) {
      if (typeof args.every_seconds !== 'number' || !Number.isSafeInteger(args.every_seconds)) {
        return { code: 'invalid_rule', message: 'every_seconds must be a safe integer.' };
      }
      if (args.every_seconds < MIN_EVERY_INTERVAL_SECONDS) {
        return { code: 'frequency_too_high', message: `every_seconds must be at least ${MIN_EVERY_INTERVAL_SECONDS}.` };
      }
    }
    if (signal?.aborted) return { code: 'internal_error', message: 'The schedule operation failed.' };
    const nowMs = this.now();
    let record: ScheduleRecord;
    const id = ScheduleId(`schedule-${randomUUID()}`);
    try {
      const title = scheduleTitle(args.title);
      if (args.at !== undefined) record = createAtScheduleRecord(id, args.prompt, args.at as AtInput, nowMs, title);
      else if (args.after_seconds !== undefined) record = createAfterScheduleRecord(id, args.prompt, args.after_seconds as number, nowMs, title);
      else if (args.every_seconds !== undefined) record = createEveryScheduleRecord(id, args.prompt, args.every_seconds as number, nowMs, title);
      else if (args.daily !== undefined) record = createDailyScheduleRecord(id, args.prompt, args.daily as DailyInput, nowMs, title);
      else if (args.weekly !== undefined) record = createWeeklyScheduleRecord(id, args.prompt, args.weekly as WeeklyInput, nowMs, title);
      else record = createCronScheduleRecord(id, args.prompt, args.cron as CronInput, nowMs, title);
    } catch (error) {
      return error instanceof ScheduleInputError
        ? { code: error.code, message: error.message }
        : { code: 'internal_error', message: 'The schedule operation failed.' };
    }
    return this.command(agentId, 'create', async owner => {
      const wasMounted = Boolean(owner.fiber);
      await this.unmountService(owner);
      const domain = await owner.domain.open(scheduleDomain);
      try {
        signal?.throwIfAborted();
        await domain.table('tasks').put(id, {
          sessionId: SessionId(sessionId),
          record,
          status: 'active',
          deliveryHistory: { records: [], earlierRecordsUnavailable: false },
        });
      } finally {
        await domain.close();
        if (wasMounted && !this.stopped && !this.disabled.has(agentId) && Date.parse(record.scheduledAt) > Date.now()) {
          await this.mountService(owner);
        }
      }
      return scheduleView(record, nowMs);
    });
  }

  /** List active session schedules with state projected against the isolated E2E logical clock. */
  async listAtLogicalClock(agentId: string, sessionId: string): Promise<ScheduleView[]> {
    const nowMs = this.now();
    return this.command(agentId, 'list', async owner => {
      if (owner.fiber) {
        const list = await owner.schedule!.list({ sessionId: SessionId(sessionId) });
        return list.map(record => scheduleView(record, nowMs));
      }
      const domain = await owner.domain.open(scheduleDomain);
      try {
        return [...domain.table('tasks').entries()]
          .filter(([, task]) => task.sessionId === sessionId && task.status === 'active')
          .map(([, task]) => scheduleView(task.record, nowMs));
      } finally {
        await domain.close();
      }
    });
  }

  /** Drive due schedules up to nowMs using public @deepseek-ai/dsh-schedule framing and strict receipt invariants. */
  async advanceClock(
    agentIds: readonly string[],
    nowMs: number,
    deliver: (agentId: string, sessionId: string, message: UserMessage) => Promise<void>,
  ): Promise<number> {
    if (!this.logicalClock) throw new Error('Logical clock schedule advance is unavailable');
    let deliveredCount = 0;
    for (const agentId of agentIds) {
      if (this.stopped || this.disabled.has(agentId)) continue;
      const owner = await this.owner(agentId);
      const step = owner.chain.then(async () => {
        if (this.stopped || this.disabled.has(agentId)) return;
        const wasMounted = Boolean(owner.fiber);
        await this.unmountService(owner);
        const domain = await owner.domain.open(scheduleDomain);
        try {
          const tasks = domain.table('tasks');
          const due = [...tasks.entries()]
            .map(([, task]) => task)
            .filter(task => task.status === 'active' && Date.parse(task.record.scheduledAt) <= nowMs)
            .sort((a, b) => Date.parse(a.record.scheduledAt) - Date.parse(b.record.scheduledAt) || a.record.id.localeCompare(b.record.id));
          const handled = new Set<string>();
          const deliveredAt = new Date(nowMs).toISOString();
          for (const task of due) {
            if (handled.has(task.record.id)) continue;
            if (!isRecurringScheduleRecord(task.record)) {
              handled.add(task.record.id);
              const message = createUserMessage({
                content: [{ type: 'text', text: renderReminderFraming(task.record) }],
                source: { kind: 'schedule' },
              });
              await deliver(agentId, task.sessionId, message);
              deliveredCount++;
              await tasks.put(ScheduleId(task.record.id), {
                ...task,
                status: 'inactive',
                ...appendScheduleDelivery(task, {
                  scheduledAt: task.record.scheduledAt,
                  deliveredAt,
                  messageId: message.id,
                }),
              });
            } else {
              const group = due.filter(
                (candidate): candidate is ScheduleTask & { record: Extract<ScheduleTask['record'], { kind: 'every' | 'daily' | 'weekly' | 'cron' }> } =>
                  candidate.sessionId === task.sessionId && isRecurringScheduleRecord(candidate.record),
              );
              for (const member of group) handled.add(member.record.id);
              const occurrences = group.map(member => ({
                task: member,
                occurrence: resolveRecurringOccurrence(member.record, nowMs),
              }));
              const message = createUserMessage({
                content: [{
                  type: 'text',
                  text: renderRecurringReminderBatchFraming(occurrences.map(({ task: member, occurrence }) => ({
                    record: member.record,
                    occurrenceAt: occurrence.occurrenceAt,
                  }))),
                }],
                source: { kind: 'schedule' },
              });
              await deliver(agentId, task.sessionId, message);
              deliveredCount++;
              for (const { task: member, occurrence } of occurrences) {
                await tasks.put(ScheduleId(member.record.id), {
                  ...member,
                  record: {
                    ...member.record,
                    scheduledAt: occurrence.nextScheduledAt ?? occurrence.occurrenceAt,
                  },
                  status: occurrence.nextScheduledAt === undefined ? 'inactive' : 'active',
                  ...appendScheduleDelivery(member, {
                    scheduledAt: occurrence.occurrenceAt,
                    deliveredAt,
                    messageId: message.id,
                  }),
                });
              }
            }
          }
        } finally {
          await domain.close();
          if (wasMounted && !this.stopped && !this.disabled.has(agentId)) await this.mountService(owner);
        }
      });
      owner.chain = step.catch(() => {});
      await step;
    }
    return deliveredCount;
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
  async skipMissed(agentId: string, blockedSchedules: Set<string>, now = this.now()): Promise<void> {
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
