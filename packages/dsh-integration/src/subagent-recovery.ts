import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { freezeMessage, MessageId } from '@deepseek-ai/dsh-llm';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

const interruptedChild = z.object({id: z.string(), turnEnd: z.number()});
type InterruptedChild = z.infer<typeof interruptedChild>;
interface RecoveryQueue { pending: InterruptedChild[]; delivered: Record<string, number> }
interface RecoveryDomain extends DomainSpec { tables: { sessions: DomainTableSpec<string, RecoveryQueue> } }

export const subagentRecoveryDomain: RecoveryDomain = defineDomain({
  name: 'nano_subagent_recovery', version: 1, layout: 'per-record',
  tables: {sessions: domainTable(z.object({
    pending: z.array(interruptedChild),
    delivered: z.record(z.string(), z.number()),
  }))},
});
export const subagentRecoveryChannel = 'subagent-recovery';
const noticeId = ({id, turnEnd}: InterruptedChild) => `${subagentRecoveryChannel}:${id}:${turnEnd}`;

/** Keep recovery notices outside the native Inbox until a normal model step is admitted. */
export class SubagentRecovery {
  readonly ready;

  constructor(private readonly ctx: Context, ownerOf: (agent: Agent) => {agentId: string; revision: number} | undefined) {
    this.ready = ctx.storageDomain.open(subagentRecoveryDomain);
    ctx.effect(() => async () => { await (await this.ready).close(); });
    ctx.on('agent/pre-step', async ({agent, signal}, next) => {
      const decision = await next();
      if (decision.kind !== 'enter' || !decision.messages.length) return decision;
      const owner = ownerOf(agent);
      if (!owner) return decision;
      const pending = await this.pending(agent);
      signal.throwIfAborted();
      if (!pending.length) return decision;
      const notices = pending.map(child => {
        const id = noticeId(child);
        return freezeMessage({id: MessageId(id), role: 'user' as const,
          content: [{type: 'text', text: `System recovery notice: subagent ${child.id} was interrupted when the execution runtime stopped. Check any available results before deciding how to handle the delegation.`}],
          source: {kind: 'nano-system' as const, channel: subagentRecoveryChannel, actorId: owner.agentId,
            messageId: id, lifecycle_revision: owner.revision},
        });
      });
      return {...decision, messages: [...notices, ...decision.messages]};
    });
    ctx.on('agent/turn-stopping', async ({agent}) => { if (ownerOf(agent)) await this.pending(agent); });
  }

  /** Journal each interruption once without materializing or waking the parent. */
  async record(sessionId: string, children: InterruptedChild[]): Promise<void> {
    const table = (await this.ready).table('sessions');
    const queue = table.get(sessionId) ?? {pending: [], delivered: {}};
    const known = new Set(queue.pending.map(noticeId));
    const added = children.filter(child => (queue.delivered[child.id] ?? -1) < child.turnEnd && !known.has(noticeId(child)));
    if (added.length) await table.put(sessionId, {...queue, pending: [...queue.pending, ...added]});
  }

  private async pending(agent: Agent): Promise<InterruptedChild[]> {
    const table = (await this.ready).table('sessions');
    const queue = table.get(agent.id);
    if (!queue?.pending.length) return [];
    const received = new Set(agent.session.snapshotEvents().flatMap(event =>
      event.type === 'user/message' && event.data.source.kind === 'nano-system' &&
      event.data.source.channel === subagentRecoveryChannel && agent.session.isOwnSeq(event.seq) ? [event.data.id] : []));
    const pending = queue.pending.filter(child => !received.has(MessageId(noticeId(child))));
    // Only retire a notice after the native message that carries it survives a restart.
    if (pending.length !== queue.pending.length && await this.ctx.sessions.flush(agent.session)) {
      const delivered = {...queue.delivered};
      for (const child of queue.pending) if (received.has(MessageId(noticeId(child)))) {
        delivered[child.id] = Math.max(delivered[child.id] ?? -1, child.turnEnd);
      }
      await table.put(agent.id, {pending, delivered});
    }
    return pending;
  }
}
