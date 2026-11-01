import {AsyncLocalStorage} from 'node:async_hooks';
import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import {freezeMessage} from '@deepseek-ai/dsh-llm';

const creatingFork = new AsyncLocalStorage<string>();
const forks = new WeakSet<Agent>();

/** Carry native tool creation intent until its durable descriptor exists. */
export function trackForkCreation(ctx: Context): void {
  ctx.on('tools/execute', (exec, next) => exec.name === 'subagent_fork' && exec.agent
    ? creatingFork.run(exec.agent.id, next) : next());
}

/** Capture the execution role before prompt and tool registration, including empty forks. */
export function attachChildRole(agent: Agent): void {
  if (agent.session.header.origin !== 'subagent') return;
  const descriptor = agent.session.snapshotEvents().findLast(event =>
    agent.session.isOwnSeq(event.seq) && event.type === 'subagent/descriptor');
  if (!agent.session.header.isSeeded && !(descriptor?.type === 'subagent/descriptor' && descriptor.data.provider === 'fork')
    && creatingFork.getStore() !== agent.session.header.parentSession) return;
  forks.add(agent);
  let first = !agent.session.snapshotEvents().some(event => agent.session.isOwnSeq(event.seq) && event.type === 'request/header');
  agent.ctx.on('agent/pre-step', async (_payload, next) => {
    const decision = await next();
    if (!first || decision.kind !== 'enter') return decision;
    const task = decision.messages.find(message => message.source.kind === 'user');
    if (!task) return decision;
    first = false;
    // Tail guidance leaves the inherited system, tool declarations and history intact.
    return {...decision, messages: decision.messages.map(message => message !== task ? message : freezeMessage({
      ...message, content: [...message.content, {type:'text',text:
        'For this delegated task you are an internal fork of the parent Agent. Inherited instructions describe its product role; only the root handles Inbox, product conversations, public delivery, source-policy changes and saved-task execution/history. Those tool definitions remain visible for shared context, but do not grant you the root permissions. Complete only the delegated work and return the result through the native completion path; do not send an extra public reply or treat inherited Tasks as new assignments.'}],
    }))};
  }, {prepend:true});
}

/** Whether Nano should supply a standalone internal worker prompt and tool view. */
export function isOrdinaryChild(agent?: Agent): boolean {
  return agent?.session.header.origin === 'subagent' && !forks.has(agent);
}
