import type { Context } from '@deepseek-ai/cordis';
import { SessionId } from '@deepseek-ai/dsh-session';
import { deriveTurnTokenUsage } from '@deepseek-ai/dsh-token-meter/client';
import type { UsageReport } from '@nano/product-contracts';

/** Read native persisted accounting without loading cold children as active agents. */
export async function readUsage(ctx: Context, rootId: string): Promise<UsageReport[]> {
  const children = await ctx.subagents.listDescendants(SessionId(rootId));
  const ids = [SessionId(rootId), ...children.filter(child => child.kind === 'child').map(child => child.id)];
  const reports: UsageReport[] = [];
  for (const id of ids) {
    const live = ctx.sessions.get(id);
    if (live && !await ctx.sessions.flush(live)) throw new Error('Usage read has no persistence barrier');
    using observation = await ctx.sessionQuery.observeSession(id);
    const events = observation.events.slice(observation.inheritedEventCount);
    let start = -1;
    for (let i = 0; i < events.length; i++) {
      const event = events[i]!;
      if (event.type === 'turn/start') start = i;
      if (event.type !== 'turn/end' || start < 0) continue;
      const usage = deriveTurnTokenUsage(events.slice(start, i + 1));
      if (usage) reports.push({sessionId: id, turn: event.data.turn, time: event.time,
        usage: {prompt_tokens: usage.totalTokens - usage.outputTokens, completion_tokens: usage.outputTokens, total_tokens: usage.totalTokens}});
      start = -1;
    }
  }
  return reports;
}
