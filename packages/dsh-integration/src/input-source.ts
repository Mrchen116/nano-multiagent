import type { MessageSource, MessageSourceMap } from '@deepseek-ai/dsh-llm';

interface NanoInputIdentity {
  actorId: string;
  roleAccountId?: string;
  channel: string;
  messageId: string;
  contextEnvelope?: string;
  directHumanText?: string;
  nanoTeamChat?: boolean;
  sender?: Record<string, unknown>;
  pa_agent_id?: string;
  background_returns?: Record<string, unknown>[];
}

declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    'nano-user': { kind: 'user' } & NanoInputIdentity;
    // Read existing logs and pending inputs without rewriting their provenance.
    'nano-human': { kind: 'nano-human' } & NanoInputIdentity;
  }
}

/** Identify host-attested humans; native child task prompts also use `user`. */
export function isHumanSource(source: MessageSource): source is MessageSourceMap['nano-user' | 'nano-human'] {
  return source.kind === 'nano-human' || source.kind === 'user'
    && 'actorId' in source && 'channel' in source && 'messageId' in source;
}

/** Preserve original turn positions while applying chat withdrawals to historical human evidence. */
export function scopedChatEvents(events: readonly import('@deepseek-ai/dsh-session').SessionEvent[]) {
  const replacements = new Map<number, (typeof events)[number]>();
  for (const event of events) {
    if (typeof event.surfaceOp !== 'object' || event.surfaceOp.startSeq !== event.surfaceOp.endSeq ||
        (event.type !== 'user/message' && event.type !== 'tool/result')) continue;
    replacements.set(event.surfaceOp.startSeq,event);
  }
  if (!replacements.size) return events;
  return events.flatMap(original => {
    if (typeof original.surfaceOp === 'object' && replacements.get(original.surfaceOp.startSeq)===original) return [];
    let projected=original;
    while (replacements.has(projected.seq)) projected=replacements.get(projected.seq)!;
    return [{...projected,seq:original.seq}];
  });
}
