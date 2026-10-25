import type { AgentLifecycleAuthority } from './agent-lifecycle.js';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import type { AgentConfiguration, RuntimePort, SessionBinding } from '@nano/product-contracts';
import { heartbeatDue, heartbeatTasks, withinActiveHours, type HeartbeatSettings } from './heartbeat-policy.js';
import { formatLocalTime } from '@nano/product-contracts';

interface Options {
  agents: AgentConfiguration[]; runtime: RuntimePort; lifecycle?:AgentLifecycleAuthority;
  settings(agentId: string): HeartbeatSettings;
  binding(agent: AgentConfiguration): Promise<SessionBinding>;
  available(agentId: string): boolean; onError(error: unknown): void;
}
interface Intent { generation?:number; lifecycle_revision?:number; agentId: string; task: string; due: number; sessionId: string; inputId: string; content: { type: 'text'; text: string }[]; source: { kind: 'system'; actorId: string; channel: 'heartbeat'; messageId: string }; mode: 'followup'; onlyIfIdle: true }

/** Node-owned heartbeat policy. Cron's native timer and storage never enter this loop. */
export class Heartbeat {
  private readonly db: DatabaseSync;
  private readonly holds = new Map<string, string>();
  private readonly admitting = new Set<string>();
  private readonly subscriptions = new Set<string>();
  private timer?: ReturnType<typeof setTimeout>;
  private active?: Promise<void>;
  private running = false;
  constructor(path: string, private readonly options: Options) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS due(agent TEXT, task TEXT, time INTEGER, PRIMARY KEY(agent,task)); CREATE TABLE IF NOT EXISTS pending(agent TEXT PRIMARY KEY, intent TEXT NOT NULL); CREATE TABLE IF NOT EXISTS resets(agent TEXT PRIMARY KEY,generation INTEGER NOT NULL,time INTEGER NOT NULL)');
  }
  /** Cancel pending ticks and start the next cadence after this lifecycle boundary. */
  resetAgent(agentId:string,now=Date.now()):void {
    this.db.prepare('INSERT INTO resets VALUES(?,1,?) ON CONFLICT(agent) DO UPDATE SET generation=generation+1,time=excluded.time').run(agentId,now);
    this.db.prepare('DELETE FROM pending WHERE agent=?').run(agentId);
    this.db.prepare('DELETE FROM due WHERE agent=?').run(agentId);
  }
  private reset(agentId:string):{generation:number;time?:number} {
    return this.db.prepare('SELECT generation,time FROM resets WHERE agent=?').get(agentId) as {generation:number;time:number}|undefined ?? {generation:0};
  }
  private valid(agentId:string,generation:number,revision?:number):boolean {
    return this.reset(agentId).generation===generation && this.options.available(agentId) && (!this.options.lifecycle || this.options.lifecycle.allowed(agentId,revision));
  }
  /** Includes uncertain persisted admissions awaiting reconciliation. */
  get busy(): boolean { return !!this.active || !!this.db.prepare('SELECT 1 FROM pending LIMIT 1').get(); }
  /** Reserve only this Agent's future heartbeat admissions during configuration. */
  hold(agentId: string, operationId: string): boolean {
    const existing = this.holds.get(agentId);
    if (existing && existing !== operationId) return false;
    this.holds.set(agentId, operationId);
    return !this.busyFor(agentId);
  }
  release(agentId: string, operationId: string): void { if (this.holds.get(agentId) === operationId) this.holds.delete(agentId); }
  busyFor(agentId: string): boolean { return this.admitting.has(agentId) || !!this.db.prepare('SELECT 1 FROM pending WHERE agent=?').get(agentId); }
  subscription(agentId: string, enabled: boolean): void { if (enabled) this.subscriptions.add(agentId); else this.subscriptions.delete(agentId); }
  start(interval = 1000): void {
    if (this.running) return; this.running = true;
    const next = () => { if (this.running) this.timer = setTimeout(() => { void this.tick().catch(this.options.onError).finally(next); }, interval); };
    next();
  }
  tick(agentId?: string, manual = false, now = Date.now()): Promise<void> {
    if (this.active) return this.active;
    const task = this.evaluate(agentId, manual, now).finally(() => { this.active = undefined; }); this.active = task; return task;
  }
  private async evaluate(agentId: string | undefined, manual: boolean, now: number) {
    for (const agent of this.options.agents) {
      if (agentId && agent.agentId !== agentId) continue;
      if (!this.options.available(agent.agentId) || this.holds.has(agent.agentId)) continue;
      if (!agent.features?.heartbeat || !this.subscriptions.has(agent.agentId)) { if (manual) throw new Error('Heartbeat Feature is disabled'); continue; }
      const reset=this.reset(agent.agentId),revision=this.options.lifecycle?.assert(agent.agentId);
      const settings = this.options.settings(agent.agentId);
      const timezone = settings.timezone ?? settings.active_hours?.timezone;
      if (!withinActiveHours(now, settings)) continue;
      const pending = this.db.prepare('SELECT intent FROM pending WHERE agent=?').get(agent.agentId) as { intent: string } | undefined;
      if (pending) { await this.admit(JSON.parse(pending.intent) as Intent); continue; }
      let content: string;
      try { content = await readFile(join(agent.workspace, '.nanoassistant', 'HEARTBEAT.md'), 'utf8'); }
      catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') continue; throw error; }
      if(!this.valid(agent.agentId,reset.generation,revision))continue;
      const tasks = heartbeatTasks(content, settings);
      if (!tasks.length) continue;
      const binding = await this.options.binding(agent);
      if(!this.valid(agent.agentId,reset.generation,revision))continue;
      for (const task of tasks) {
        const previous = this.db.prepare('SELECT time FROM due WHERE agent=? AND task=?').get(agent.agentId, task.name) as { time: number } | undefined;
        const due = manual ? now : heartbeatDue(task, previous?.time??reset.time, now, timezone);
        if (due === undefined || !manual && reset.time!==undefined && due<=reset.time) continue;
        const hash = createHash('sha256').update(task.name + '\0' + task.prompt).digest('hex').slice(0, 16);
        const inputId = `heartbeat:${agent.agentId}:${due}:${hash}`;
        const intent: Intent = { generation:reset.generation,lifecycle_revision:revision,agentId: agent.agentId, task: task.name, due, sessionId: binding.sessionId, inputId, mode: 'followup', onlyIfIdle: true,
          content: [{ type: 'text', text: `Current time: ${formatLocalTime(now, timezone)}${timezone ? ` (${timezone})` : ' (user timezone unknown)'}.\nRead .nanoassistant/HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.\n\n${task.prompt}` }],
          source: { kind: 'system', actorId: agent.agentId, channel: 'heartbeat', messageId: inputId } };
        if (this.holds.has(agent.agentId)) break;
        this.db.prepare('INSERT INTO pending VALUES(?,?)').run(agent.agentId, JSON.stringify(intent));
        await this.admit(intent);
      }
    }
  }
  private async admit(intent: Intent) {
    if(!this.valid(intent.agentId,intent.generation??0,intent.lifecycle_revision))return;
    this.admitting.add(intent.agentId);
    try {
    const evidence = await this.options.runtime.request('session.lookup', { sessionId: intent.sessionId, inputId: intent.inputId }) as { accepted: boolean };
    if(!this.valid(intent.agentId,intent.generation??0,intent.lifecycle_revision))return;
    if (!evidence.accepted) await this.options.runtime.request('session.submit', intent);
    if(!this.valid(intent.agentId,intent.generation??0,intent.lifecycle_revision))return;
    // Busy is a skipped boundary, never a delayed low-priority wake behind human work.
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('INSERT INTO due VALUES(?,?,?) ON CONFLICT(agent,task) DO UPDATE SET time=excluded.time').run(intent.agentId, intent.task, intent.due);
      this.db.prepare('DELETE FROM pending WHERE agent=?').run(intent.agentId); this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
    } finally { this.admitting.delete(intent.agentId); }
  }
  async stop(): Promise<void> { this.running = false; clearTimeout(this.timer); await this.active; this.db.close(); }
}
