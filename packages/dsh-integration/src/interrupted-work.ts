import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { freezeMessage, MessageId } from '@deepseek-ai/dsh-llm';
import { SessionId, type SessionEvent } from '@deepseek-ai/dsh-session';
// Declared package export: the host adapter retains system provenance while
// restoring native continuation residency, including child-to-parent messaging.
import { steerHostSubagentPrompt } from '@deepseek-ai/dsh-subagent/internal';
import type { DescendantReader } from './descendants.js';

type Cut = {seq:number;time:number};
function interrupted(events: readonly SessionEvent[]): Cut | undefined {
  const last = events.findLast(event => event.type === 'turn/start' || event.type === 'turn/end');
  if (last?.type !== 'turn/end' || last.data.reason.kind !== 'interrupted') return;
  const turn = last.data.turn;
  const start = events.findLast(event => event.type === 'turn/start' && event.data.turn === turn);
  return start ? {seq:last.seq,time:start.time} : undefined;
}

/** Restore original task ownership through the native continuation service. */
export class InterruptedWork {
  private readonly stopped = new Map<string, number>();
  private readonly restored = new Set<string>();
  private readonly pending = new Map<string, Promise<void>>();
  private readonly aborts = new Map<string, AbortController>();
  constructor(private readonly ctx: Context, private readonly descendants: DescendantReader) {}

  /** A persisted user stop takes precedence over automatic process recovery. */
  stop(rootId: string, stoppedAt?: string): void {
    this.stopped.set(rootId,stoppedAt ? Date.parse(stoppedAt) : Date.now());
    this.aborts.get(rootId)?.abort(new Error('User stopped runtime recovery'));
  }

  /** Restore a tree once per process; repeated admission shares the same attempt. */
  recover(root: Agent, owner: {agentId: string; revision: number}): Promise<void> {
    if (this.restored.has(root.id)) return Promise.resolve();
    const prior = this.pending.get(root.id);
    if (prior) return prior;
    const abort = new AbortController();this.aborts.set(root.id,abort);
    const task = this.restore(root,owner,abort.signal).then(() => {this.restored.add(root.id);})
      .finally(() => {this.pending.delete(root.id);this.aborts.delete(root.id);});
    this.pending.set(root.id,task);return task;
  }
  private async restore(root: Agent, owner: {agentId:string;revision:number}, signal: AbortSignal): Promise<void> {
    const rows = new Map<string,{id:string;parentId:string;cut?:Cut;head:number}>();
    const nonresumable = new Set<string>(), wanted = new Set<string>();
    const orphaned: {id:string;seq:number}[] = [];
    for await (const child of this.descendants.catalog(root.id)) {
      signal.throwIfAborted();
      if (child.kind !== 'child') throw new Error(`Cannot inspect interrupted child ${child.id}: ${child.reason}`);
      if (child.mode !== 'continuable' || nonresumable.has(child.parentId)) nonresumable.add(child.id);
      using view = await this.ctx.sessionQuery.observeSession(child.id);
      const cut = interrupted(view.events.slice(view.inheritedEventCount));
      rows.set(child.id,{id:child.id,parentId:child.parentId,cut,head:view.cursor});
      if (!cut || cut.time <= (this.stopped.get(root.id) ?? -Infinity) || this.ctx.agents.get(child.id)) continue;
      if (nonresumable.has(child.id)) {orphaned.push({id:child.id,seq:cut.seq});continue;}
      // Native continuation admission needs resident ancestors, even when their
      // own last turn finished before the still-running delegated work.
      for(let id:string=child.id;id!==root.id;id=rows.get(id)!.parentId) wanted.add(id);
    }
    const source = (id:string) => ({kind:'nano-system' as const,channel:'runtime-recovery',actorId:owner.agentId,messageId:id,lifecycle_revision:owner.revision});
    const children = (id:string) => [...rows.values()].filter(row=>row.parentId===id&&wanted.has(row.id)).map(row=>row.id);
    const text = (id:string,unfinished:boolean) =>
      'The execution runtime was interrupted and has recovered. ' +
      (unfinished ? 'Continue your unfinished original task using the existing conversation, original authorization, and persisted tool results. ' : 'Resume supervision of the existing delegated work below; do not redo your completed task. ') +
      'Do not repeat completed work. An interrupted tool result does not prove whether an external action happened; inspect its actual state before repeating any side effect. This is a system recovery notice, not new human permission.' +
      (children(id).length ? ` These existing subagents are also being resumed; retain their identities instead of creating replacements: ${children(id).join(', ')}.` : '');
    // Catalog order is parent-first. Use native host delivery rather than bare
    // Agent resume, which would omit the child's authorized parent return route.
    for (const row of rows.values()) {
      if (!wanted.has(row.id) || this.ctx.agents.get(SessionId(row.id))) continue;
      signal.throwIfAborted();
      const parent = this.ctx.agents.get(SessionId(row.parentId));
      if (!parent) throw new Error(`Recovery parent is not resident: ${row.parentId}`);
      await steerHostSubagentPrompt(this.ctx.subagents,parent,SessionId(row.id),[{type:'text',text:text(row.id,!!row.cut)}],source(`runtime-recovery:${row.id}:${row.cut?.seq ?? row.head}`),signal);
      const agent = this.ctx.agents.get(SessionId(row.id));
      if (!agent || !await this.ctx.sessions.flush(agent.session)) throw new Error('Child recovery has no durable barrier');
    }
    const messages = orphaned.flatMap(child => {
      const id = MessageId(`runtime-fork-recovery:${child.id}:${child.seq}`);
      if (root.session.snapshotEvents().some(event=>event.type==='user/message'&&event.data.id===id) ||
          [...root.inbox.nextStep,...root.inbox.nextTurn].some(message=>message.id===id)) return [];
      return [freezeMessage({id,role:'user',source:source(id),content:[{type:'text',text:
        `The runtime recovered after interruption. Your delegated execution ${child.id} could not be resumed in place because its parent chain includes a one-shot execution without persisted continuation composition. Continue the original unfinished assignment from its existing history and inspect its tool results before replacing any work. Do not repeat completed actions or assume interrupted external actions had no effect. This system notice does not add human authorization.` +
        (children(root.id).length ? ` These existing subagents are being resumed; retain their identities: ${children(root.id).join(', ')}.` : '')}]} )];
    });
    const cut = interrupted(root.session.snapshotEvents().filter(event=>root.session.isOwnSeq(event.seq)));
    if (!messages.length && cut && cut.time > (this.stopped.get(root.id) ?? -Infinity)) {
      const id=MessageId(`runtime-recovery:${root.id}:${cut.seq}`);
      if (![...root.inbox.nextStep,...root.inbox.nextTurn].some(message=>message.id===id))
        messages.push(freezeMessage({id,role:'user',source:source(id),content:[{type:'text',text:text(root.id,true)}]}));
    }
    signal.throwIfAborted();
    for (const [index,message] of messages.entries()) {
      if(index===messages.length-1)root.steer(message);else root.inject(message);
    }
    if(messages.length&&!await this.ctx.sessions.flush(root.session))throw new Error('Root recovery has no durable barrier');
  }
}
