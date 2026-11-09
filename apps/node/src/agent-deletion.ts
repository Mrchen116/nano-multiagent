import { DatabaseSync } from 'node:sqlite';
import type { AgentDeletionIntent, AgentDeletionState } from '@nano/product-contracts';

interface DeletionPlan extends Record<string, unknown> {
  sessionIds: string[];
}
interface Receipt {
  intent: AgentDeletionIntent;
  plan?: DeletionPlan;
  runtimePurged?: true;
  complete?: true;
}

interface Dependencies {
  assertStopped(intent: AgentDeletionIntent): void;
  plan(intent: AgentDeletionIntent): Promise<DeletionPlan>;
  purge(intent: AgentDeletionIntent, plan: DeletionPlan): Promise<void>;
  finalize(intent: AgentDeletionIntent, plan: DeletionPlan): Promise<void>;
  report(intent: AgentDeletionIntent, state: AgentDeletionState, detail?: string): Promise<void>;
}

/** Persist the irreversible scope and runtime checkpoint independently of the relay connection. */
export class AgentDeletionLedger {
  private readonly db: DatabaseSync;

  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS deletions(agent_id TEXT PRIMARY KEY, receipt TEXT NOT NULL)');
  }

  read(agentId: string): Receipt | undefined {
    const row = this.db.prepare('SELECT receipt FROM deletions WHERE agent_id=?').get(agentId);
    return row ? JSON.parse(String(row.receipt)) as Receipt : undefined;
  }

  save(receipt: Receipt): void {
    this.db.prepare('INSERT INTO deletions VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET receipt=excluded.receipt')
      .run(receipt.intent.agent_id,JSON.stringify(receipt));
  }

  states(): Map<string, boolean> {
    return new Map(this.db.prepare('SELECT agent_id,receipt FROM deletions').all().map(row=>
      [String(row.agent_id),!!(JSON.parse(String(row.receipt)) as Receipt).complete]));
  }

  close(): void { this.db.close(); }
}

/** Run independent target deletions without putting work for peers on this promise. */
export class NodeAgentDeletions {
  private readonly active = new Map<string, Promise<void>>();

  constructor(private readonly ledger: AgentDeletionLedger, private readonly dependencies: Dependencies) {}

  apply(intent: AgentDeletionIntent): Promise<void> {
    const current = this.active.get(intent.agent_id);
    if (current) return current;
    const task = this.run(intent).finally(()=>this.active.delete(intent.agent_id));
    this.active.set(intent.agent_id,task);
    return task;
  }

  private async run(intent: AgentDeletionIntent): Promise<void> {
    const d = this.dependencies;
    const saved = this.ledger.read(intent.agent_id);
    if (saved && (saved.intent.operation_id!==intent.operation_id || saved.intent.revision!==intent.revision ||
      !saved.complete && JSON.stringify(saved.intent.workspace)!==JSON.stringify(intent.workspace)))
      throw new Error('Agent deletion scope changed');
    const receipt = saved ?? {intent};
    if (receipt.complete) { await d.report(intent,'deleted'); return; }
    try {
      if (!receipt.runtimePurged) d.assertStopped(intent);
      this.ledger.save(receipt);
      await d.report(intent,'deleting');
      if (!receipt.plan) {
        receipt.plan = await d.plan(intent);
        this.ledger.save(receipt);
      }
      if (!receipt.runtimePurged) {
        await d.purge(intent,receipt.plan);
        receipt.runtimePurged = true;
        this.ledger.save(receipt);
      }
      await d.finalize(intent,receipt.plan);
      const {agent_id,operation_id,revision} = intent;
      this.ledger.save({intent:{agent_id,operation_id,revision},complete:true});
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      await d.report(intent,'failed',detail);
      return;
    }
    await d.report(intent,'deleted');
  }

  async close(): Promise<void> {
    await Promise.allSettled(this.active.values());
    this.ledger.close();
  }
}
