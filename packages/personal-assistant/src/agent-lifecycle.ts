import { AsyncLocalStorage } from 'node:async_hooks';
import type { DatabaseSync } from 'node:sqlite';
import type { AgentLifecycleSnapshot } from '@nano/product-contracts';

/** Stores lifecycle intent and carries one admitted execution's epoch across awaits. */
export class AgentLifecycleAuthority {
  private readonly execution = new AsyncLocalStorage<{agentId:string;revision:number}>();
  constructor(private readonly db: DatabaseSync) {
    db.exec('CREATE TABLE IF NOT EXISTS agent_lifecycle(agent_id TEXT PRIMARY KEY,state TEXT NOT NULL)');
  }
  /** Identity captured at admission, retained across asynchronous product calls. */
  current(): {agentId:string;revision:number} | undefined { return this.execution.getStore(); }
  snapshot(agentId: string): AgentLifecycleSnapshot | undefined {
    const row=this.db.prepare('SELECT state FROM agent_lifecycle WHERE agent_id=?').get(agentId) as {state:string}|undefined;
    return row ? JSON.parse(row.state) as AgentLifecycleSnapshot : undefined;
  }
  /** Keep newer intent when a delayed command or registration snapshot arrives. */
  save(value: AgentLifecycleSnapshot): void {
    if ((this.snapshot(value.agent_id)?.revision ?? 0) > value.revision) return;
    this.db.prepare('INSERT INTO agent_lifecycle VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET state=excluded.state').run(value.agent_id,JSON.stringify(value));
  }
  assert(agentId: string, revision?: number): number {
    const state=this.snapshot(agentId);
    if (state?.desired === 'disabled') throw Object.assign(new Error('agent_disabled'),{code:'agent_disabled'});
    const admitted=this.execution.getStore();
    if(admitted?.agentId===agentId && admitted.revision !== (state?.revision??1))throw Object.assign(new Error('stale_lifecycle'),{code:'stale_lifecycle'});
    const expected=revision ?? (admitted?.agentId===agentId ? admitted.revision : state?.revision ?? 1);
    if (expected !== (state?.revision ?? 1)) throw Object.assign(new Error('stale_lifecycle'),{code:'stale_lifecycle'});
    return expected;
  }
  allowed(agentId: string, revision?: number): boolean {
    try { this.assert(agentId,revision); return true; } catch { return false; }
  }
  run<T>(agentId: string, revision: number | undefined, action: () => T): T {
    return this.execution.run({agentId,revision:this.assert(agentId,revision)},action);
  }
}
