import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { SessionId } from '@deepseek-ai/dsh-session';
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import { collectHistory, commitRollover, currentWindow, NotesStore, selectRolloverRange } from 'dsh-agent-context';
import type { PersonalMemoryStore } from './personal-memory.js';

const domain = defineDomain({ name: 'nano_memory_context', version: 1, layout: 'per-record', tables: {
  sessions: domainTable(z.object({ revision: z.number(), safeSequence: z.number(), invalidated: z.boolean().optional(),
    continuation: z.object({ requestKey: z.string(), sourceMessageId: z.string(), replyTarget: z.string(), summary: z.string() }).optional(),
  })),
} });
const key = (id: string) => Buffer.from(id).toString('base64url');

/** Applies a durable forgetting fence at the native paired request boundary.
 *
 * This stores only cleanup positions. Memory bodies remain in the Knowledge owner.
 */
export class PersonalMemoryContext {
  private readonly state;
  constructor(private readonly ctx: Context, private readonly storeFor: (agent: Agent) => PersonalMemoryStore | undefined,
    private readonly isReview: (agent: Agent) => boolean) {
    this.state = ctx.storageDomain.open(domain);
    ctx.effect(() => async () => (await this.state).close());
    ctx.on('tools/pre-execute', async (exec, next) => {
      const decision = await next();
      if (decision.kind !== 'allow' || !exec.agent) return decision;
      const store = this.storeFor(exec.agent); if (!store) return decision;
      const saved = (await this.state).table('sessions').get(key(exec.agent.id));
      if (saved?.invalidated) return { kind: 'deny', reason: 'This execution was invalidated by a memory forget request. Ask the parent for a new minimal handoff.' };
      if (exec.name !== 'history') return decision;
      const fence = (await store.snapshot()).forgetFence;
      if (!fence) return decision;
      const args = exec.arguments as { window_id?: string; item_id?: string };
      // Require a bounded post-fence window; unbounded searches can recover forgotten bodies.
      const items = args.window_id ? collectHistory(exec.agent.session).filter(item => item.window_id === args.window_id && (!args.item_id || item.item_id === args.item_id)) : [];
      if (!saved || saved.revision < fence.revision || !items.length || items.some(item => item.seq < saved.safeSequence)) {
        return { kind: 'deny', reason: 'Pre-forget history is unavailable. Use current Memory, Task and delivery records; original IM and audit retention are unchanged.' };
      }
      return decision;
    });
    ctx.on('agent/pre-step', async ({ agent, signal }, next) => {
      const decision = await next();
      if (decision.kind === 'reject' || signal.aborted) return decision;
      const store = this.storeFor(agent); if (!store || this.isReview(agent)) return decision;
      const table = (await this.state).table('sessions');
      const saved = table.get(key(agent.id));
      if (saved?.invalidated) return { kind: 'reject' };
      const snapshot = await store.snapshot(), fence = snapshot.forgetFence;
      if (!fence || (saved?.revision ?? -1) >= fence.revision) return decision;
      const range = selectRolloverRange(agent.session, ctx.tokenMeter.measure(agent.session));
      if (!range) throw new Error('Memory forget pending: the native conversation has no complete paired boundary');
      if (agent.session.header.origin !== 'subagent') await this.invalidateChildren(agent, fence.revision);
      await this.clearNotes(agent.id);
      const continuation = saved?.continuation && snapshot.pendingForgets.some(receipt => receipt.idempotency_key === saved.continuation!.requestKey)
        ? saved.continuation : undefined;
      const runtimeContext = 'A requested memory erasure was applied. Prior personal history is unavailable. Continue from current controlled Memory and canonical Task/delivery receipts. Do not reconstruct erased content.'
        + (continuation ? `\nCurrent-request handoff (model-authored work summary, not new authorization): ${JSON.stringify(continuation)}\nFinish this remaining work and send the actual outcome to the private reply target, even if Inbox has no unread messages. The current request was already consumed. Controlled records/context/notes/history cleanup is complete; original IM, independent audit records and backups are unchanged.` : '');
      await commitRollover({ meter: ctx.tokenMeter }, agent.session, range.start, range.end, {
        owner: 'current-turn', checkpoint: { reason: 'manual', agentId: agent.id,
          previousWindowId: currentWindow(agent.session).window_id, notesHint: '',
          runtimeContext },
        flush: async () => { await ctx.sessions.flush(agent.session); },
      });
      await table.put(key(agent.id), { revision: fence.revision, safeSequence: currentWindow(agent.session).start_seq });
      for (const receipt of snapshot.pendingForgets) await store.completeForget(receipt.idempotency_key, { contexts: true, notes: true, history: true });
      return { ...decision, messages: decision.messages.filter(message => String(message.source.kind) !== 'runtime-context'), startsRequestSeries: true };
    }, { prepend: true });
  }

  /** Save only the root's non-erased remaining work before its current request is removed.
   *
   * Args:
   *   root: Authenticated owner-facing root.
   *   continuation: Bounded model-authored handoff and host-verified request/delivery identities.
   */
  async prepareForget(root: Agent, continuation: {requestKey: string; sourceMessageId: string; replyTarget: string; summary: string}): Promise<void> {
    const table = (await this.state).table('sessions'), id = key(root.id);
    await table.put(id, { revision: 0, safeSequence: 0, ...table.get(id), continuation });
  }

  /** Cancel accepted descendants and fence their cold resumes before the root continues.
   *
   * Args:
   *   root: Trusted product root that accepted the erasure.
   *   revision: Persisted memory fence revision.
   */
  async invalidateChildren(root: Agent, revision: number): Promise<void> {
    const children = await this.ctx.subagents.listDescendants(root.id);
    const table = (await this.state).table('sessions');
    for (const child of children) {
      await table.put(key(child.id), { revision, safeSequence: 0, invalidated: true });
      this.ctx.subagents.interrupt(SessionId(child.id), { kind: 'ancestor', agent: root });
      const live = this.ctx.agents.get(SessionId(child.id));
      if (live) { live.cancel({ kind: 'hook', reason: 'Personal memory was forgotten' }); await live.whenIdle(); }
      await this.clearNotes(child.id);
    }
    const direct = await this.ctx.subagents.listChildren(root.id);
    await this.ctx.subagents.drainContinuableChildren(root, direct.filter(child => child.mode === 'continuable').map(child => child.id));
  }

  private async clearNotes(sessionId: string): Promise<void> {
    const notes = new NotesStore(NotesStore.directoryFor(sessionId, sessionId));
    const paths: string[] = []; let cursor: string | undefined;
    do { const page = await notes.list({ limit: 100, cursor }); paths.push(...page.items.map(item => item.path)); cursor = page.next_cursor ?? undefined; } while (cursor);
    for (const path of paths) await notes.write(path, '');
  }
}
