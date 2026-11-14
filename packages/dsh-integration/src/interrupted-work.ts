import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { freezeMessage, MessageId } from '@deepseek-ai/dsh-llm';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { OwnedSessions } from './owned-sessions.js';
import type { DescendantReader } from './descendants.js';

/** The native resume closer distinguishes process loss from user cancellation. */
function interrupted(events: readonly SessionEvent[]): {seq:number;time:number} | undefined {
  const last = events.findLast(event => event.type === 'turn/start' || event.type === 'turn/end');
  if (last?.type !== 'turn/end' || last.data.reason.kind !== 'interrupted') return;
  const turn = last.data.turn;
  const start = events.findLast(event => event.type === 'turn/start' && event.data.turn === turn);
  return start ? {seq:last.seq,time:start.time} : undefined;
}

/** Resume interrupted conversations through their original native composition and history. */
export class InterruptedWork {
  private readonly stopped = new Map<string, number>();
  private readonly restored = new Set<string>();
  private readonly pending = new Map<string, Promise<void>>();
  constructor(private readonly ctx: Context, private readonly owned: OwnedSessions, private readonly descendants: DescendantReader) {}

  /** A persisted user stop takes precedence over automatic process recovery. */
  stop(rootId: string, stoppedAt?: string): void {this.stopped.set(rootId,stoppedAt ? Date.parse(stoppedAt) : Date.now());}

  /** Restore a tree once per process; repeated admission shares the same durable notifications. */
  recover(root: Agent, owner: {agentId: string; revision: number}): Promise<void> {
    if (this.restored.has(root.id)) return Promise.resolve();
    const prior = this.pending.get(root.id);
    if (prior) return prior;
    const task = this.restore(root, owner).then(() => {this.restored.add(root.id);})
      .finally(() => this.pending.delete(root.id));
    this.pending.set(root.id, task);
    return task;
  }
  private async restore(root: Agent, owner: {agentId: string; revision: number}): Promise<void> {
    const candidates: Agent[] = [];
    const orphaned: {id:string;seq:number;time:number}[] = [];
    for await (const child of this.descendants.catalog(root.id)) {
      if (child.kind !== 'child' || this.ctx.agents.get(child.id)) continue;
      using view = await this.ctx.sessionQuery.observeSession(child.id);
      const cut = interrupted(view.events.slice(view.inheritedEventCount));
      if (cut === undefined || cut.time <= (this.stopped.get(root.id) ?? -Infinity)) continue;
      if (child.mode !== 'continuable') {orphaned.push({id:child.id,...cut});continue;}
      candidates.push((await this.owned.resolveManaged(child.id, owner.agentId)).agent);
    }
    // Children keep their own assignments. Tell the parent which identities are
    // already being recovered so it does not recreate the same delegation.
    const rootChildren = candidates.filter(child => child.session.header.parentSession === root.id).map(child => child.id);
    const orphanMessages = orphaned.flatMap(child => {
      const id = MessageId(`runtime-fork-recovery:${child.id}:${child.seq}`);
      if (root.session.snapshotEvents().some(event => event.type === 'user/message' && event.data.id === id) ||
          [...root.inbox.nextStep,...root.inbox.nextTurn].some(message => message.id === id)) return [];
      return [freezeMessage({id,role:'user',content:[{type:'text',text:
        `The runtime recovered after interruption. Your one-shot delegated execution ${child.id} could not be resumed in place because it has no persisted continuation composition. Continue the original unfinished assignment from its existing history and inspect its tool results before replacing any work. Do not repeat completed actions or assume interrupted external actions had no effect. This system notice does not add human authorization.` +
        (rootChildren.length ? ` These existing subagents are already being resumed; retain their identities: ${rootChildren.join(', ')}.` : '')}],
        source:{kind:'nano-system',channel:'runtime-recovery',actorId:owner.agentId,messageId:id,lifecycle_revision:owner.revision}})];
    });
    const resumed = [...candidates];
    for (const agent of [...candidates.reverse(), ...(orphanMessages.length ? [] : [root])]) {
      const cut = interrupted(agent.session.snapshotEvents().filter(event => agent.session.isOwnSeq(event.seq)));
      if (cut === undefined || cut.time <= (this.stopped.get(root.id) ?? -Infinity)) continue;
      const children = resumed.filter(child => child.session.header.parentSession === agent.id).map(child => child.id);
      const id = MessageId(`runtime-recovery:${agent.id}:${cut.seq}`);
      if ([...agent.inbox.nextStep, ...agent.inbox.nextTurn].some(message => message.id === id)) continue;
      agent.steer(freezeMessage({id, role:'user', content:[{type:'text',text:
        'The execution runtime was interrupted and has recovered. Continue your unfinished original task using the existing conversation, original authorization, and persisted tool results. Do not repeat completed work. An interrupted tool result does not prove whether an external action happened; inspect its actual state before repeating any side effect. This is a system recovery notice, not new human permission.' +
        (children.length ? ` These existing subagents are also being resumed; use their original identities instead of creating replacements: ${children.join(', ')}.` : '')}],
        source:{kind:'nano-system',channel:'runtime-recovery',actorId:owner.agentId,messageId:id,lifecycle_revision:owner.revision}}));
      if (!await this.ctx.sessions.flush(agent.session)) throw new Error('Runtime recovery notification has no durable barrier');
    }
    for (const [index,message] of orphanMessages.entries()) {
      if (index === orphanMessages.length - 1) root.steer(message); else root.inject(message);
    }
    if (orphanMessages.length && !await this.ctx.sessions.flush(root.session)) throw new Error('Fork recovery notice has no durable barrier');

  }
}
