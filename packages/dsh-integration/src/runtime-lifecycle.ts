import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

export interface RuntimeLifecycle { revision: number; disabled?: boolean; disabledThroughRevision?: number }
const lifecycleDomain = defineDomain({ name: 'nano_lifecycle', version: 1, tables: { fences: domainTable(z.number()) } });

/** Persist each owner and cold Session barrier after its cancellation is durable. */
export class ColdLifecycleBarrier {
  private readonly state;
  private readonly owners = new Map<string, RuntimeLifecycle>();
  constructor(private readonly ctx: Context) { this.state = ctx.storageDomain.open(lifecycleDomain); }
  configure(agentId: string, lifecycle: RuntimeLifecycle): void { this.owners.set(agentId, lifecycle); }
  current(agentId: string): RuntimeLifecycle { return this.owners.get(agentId) ?? {revision: 1}; }
  assertEnabled(agentId: string): void { if (this.current(agentId).disabled) throw new Error('agent_disabled'); }
  async clean(agentId: string, agent: Agent, restored: boolean): Promise<void> {
    const through = this.current(agentId).disabledThroughRevision ?? 0;
    if (!through) return;
    const table = (await this.state).table('fences'), key = `session:${agent.id}`;
    if ((table.get(key) ?? 0) >= through) return;
    if (restored) agent.inbox.clear();
    if (!await this.ctx.sessions.flush(agent.session)) throw new Error('Lifecycle inbox cleanup has no persistence barrier');
    await table.put(key, through);
  }
  async prepare(agentId: string, clean: () => Promise<void>): Promise<void> {
    const through = this.current(agentId).disabledThroughRevision ?? 0;
    if (!through) return;
    const table = (await this.state).table('fences'), key = `owner:${agentId}`;
    if ((table.get(key) ?? 0) >= through) return;
    await clean();
    await table.put(key, through);
  }
}
