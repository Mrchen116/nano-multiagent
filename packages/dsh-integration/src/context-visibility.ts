import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-agent';
import { createSystemMessage } from '@deepseek-ai/dsh-llm';

export const name = 'nano-context-visibility';
const rootPrivateChannels = new Set(['task-execution', 'task-reminder', 'task-context-limitation', 'task-wait-repair']);

/** Hide inherited root-only Task packages through native, replayable surface decisions.
 *
 * Args:
 *   ctx: The internal child's agent-scoped context.
 */
export function apply(ctx: Context): void {
  // pre-step precedes step/start; system/message is replayable only inside the open step.
  ctx.on('agent/request', async ({ agent, turn, step }, next) => {
    const session = agent.session;
    if (session.header.origin === 'subagent') {
      // The durable fork cut, not firstLiveSeq, also distinguishes inherited history on resume.
      for (const seq of [...session.surface.nodes]) {
        if (session.isOwnSeq(seq)) continue;
        const event = session.eventAt(seq);
        if (event?.type !== 'user/message') continue;
        const source = event.data.source;
        if (source.kind !== 'nano-system' || !rootPrivateChannels.has(source.channel)) continue;
        // Empty later system nodes are native dormant surface nodes, not a new system head.
        // Replacing only this node preserves all original log events and neighboring evidence.
        session.append('system/message', { turn, step, message: createSystemMessage('') }, {
          surfaceOp: { op: 'replace', startSeq: seq, endSeq: seq }, sourceEventSeqs: [seq],
        });
      }
    }
    return next();
  }, { prepend: true });
}
