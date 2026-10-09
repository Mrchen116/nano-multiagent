import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import type { AgentConfiguration, RuntimePort, SessionBinding } from '@nano/product-contracts';
import { heartbeatDue, heartbeatTasks, withinActiveHours, type HeartbeatSettings } from './heartbeat-policy.js';

interface Options {
  agents: AgentConfiguration[]; runtime: RuntimePort;
  settings(agentId: string): HeartbeatSettings;
  binding(agent: AgentConfiguration): Promise<SessionBinding>;
  available(agentId: string): boolean; onError(error: unknown): void;
}
interface Intent { agentId: string; task: string; due: number; sessionId: string; inputId: string; content: { type: 'text'; text: string }[]; source: { kind: 'system'; actorId: string; channel: 'heartbeat'; messageId: string }; mode: 'followup'; onlyIfIdle: true }

/** Node-owned heartbeat policy. Cron's native timer and storage never enter this loop. */
export class Heartbeat {
  private readonly db: DatabaseSync;
  private readonly subscriptions = new Set<string>();
  private timer?: ReturnType<typeof setTimeout>;
  private active?: Promise<void>;
  private running = false;
  constructor(path: string, private readonly options: Options) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS due(agent TEXT, task TEXT, time INTEGER, PRIMARY KEY(agent,task)); CREATE TABLE IF NOT EXISTS pending(agent TEXT PRIMARY KEY, intent TEXT NOT NULL)');
  }
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
      if (!this.options.available(agent.agentId)) continue;
      if (!agent.features?.heartbeat || !this.subscriptions.has(agent.agentId)) { if (manual) throw new Error('Heartbeat Feature is disabled'); continue; }
      const settings = this.options.settings(agent.agentId);
      if (!withinActiveHours(now, settings)) continue;
      const pending = this.db.prepare('SELECT intent FROM pending WHERE agent=?').get(agent.agentId) as { intent: string } | undefined;
      if (pending) { await this.admit(JSON.parse(pending.intent) as Intent); continue; }
      let content: string;
      try { content = await readFile(join(agent.workspace, '.nanoassistant', 'HEARTBEAT.md'), 'utf8'); }
      catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') continue; throw error; }
      const tasks = heartbeatTasks(content, settings);
      if (!tasks.length) continue;
      const binding = await this.options.binding(agent);
      for (const task of tasks) {
        const previous = this.db.prepare('SELECT time FROM due WHERE agent=? AND task=?').get(agent.agentId, task.name) as { time: number } | undefined;
        const due = manual ? now : heartbeatDue(task, previous?.time, now);
        if (due === undefined) continue;
        const hash = createHash('sha256').update(task.name + '\0' + task.prompt).digest('hex').slice(0, 16);
        const inputId = `heartbeat:${agent.agentId}:${due}:${hash}`;
        const intent: Intent = { agentId: agent.agentId, task: task.name, due, sessionId: binding.sessionId, inputId, mode: 'followup', onlyIfIdle: true,
          content: [{ type: 'text', text: `Read .nanoassistant/HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.\n\n${task.prompt}` }],
          source: { kind: 'system', actorId: agent.agentId, channel: 'heartbeat', messageId: inputId } };
        this.db.prepare('INSERT INTO pending VALUES(?,?)').run(agent.agentId, JSON.stringify(intent));
        await this.admit(intent);
      }
    }
  }
  private async admit(intent: Intent) {
    const evidence = await this.options.runtime.request('session.lookup', { sessionId: intent.sessionId, inputId: intent.inputId }) as { accepted: boolean };
    if (!evidence.accepted) await this.options.runtime.request('session.submit', intent);
    // Busy is a skipped boundary, never a delayed low-priority wake behind human work.
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare('INSERT INTO due VALUES(?,?,?) ON CONFLICT(agent,task) DO UPDATE SET time=excluded.time').run(intent.agentId, intent.task, intent.due);
      this.db.prepare('DELETE FROM pending WHERE agent=?').run(intent.agentId); this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  async stop(): Promise<void> { this.running = false; clearTimeout(this.timer); await this.active; this.db.close(); }
}
