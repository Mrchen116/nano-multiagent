import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

export interface RuntimeLifecycle { revision: number; disabledThroughRevision?: number }
const lifecycleDomain = defineDomain({ name: 'nano_lifecycle', version: 1, tables: {
  fences: domainTable(z.number()),
} });

/** Persist each cold Session barrier only after the native inbox cancellation is durable. */
export class ColdLifecycleBarrier {
  private readonly state;
  private through = 0;
  constructor(private readonly ctx: Context) { this.state = ctx.storageDomain.open(lifecycleDomain); }
  configure(lifecycle?: RuntimeLifecycle): void { this.through = lifecycle?.disabledThroughRevision ?? 0; }
  async clean(agent: Agent, restored: boolean): Promise<void> {
    if (!this.through) return;
    const table = (await this.state).table('fences');
    const key = `session:${agent.id}`;
    if ((table.get(key) ?? 0) >= this.through) return;
    if (restored) agent.inbox.clear();
    if (!await this.ctx.sessions.flush(agent.session)) throw new Error('Lifecycle inbox cleanup has no persistence barrier');
    await table.put(key, this.through);
  }
  async prepare(clean: () => Promise<void>): Promise<void> {
    if (!this.through) return;
    const table = (await this.state).table('fences');
    if ((table.get('owners') ?? 0) >= this.through) return;
    await clean();
    await table.put('owners', this.through);
  }
}
