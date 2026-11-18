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

/** Apply Nano chat withdrawals to original turn evidence while preserving native display projections. */
export function scopedChatEvents(events: readonly import('@deepseek-ai/dsh-session').SessionEvent[]) {
  type Event = (typeof events)[number];
  const identity = (event:Event) => event.type==='user/message' ? 'input:'+event.data.id :
    event.type==='tool/result' ? 'tool:'+event.data.message.toolCallId : undefined;
  const changes = new Map<string,Event>();
  for (const event of events) {
    if (typeof event.surfaceOp !== 'object') continue;
    const source = event.type==='user/message' ? event.data.source : event.type==='tool/result' ? event.data.message.source : undefined;
    if (source && 'nanoScopeReplacement' in source && source.nanoScopeReplacement===true) changes.set(identity(event)!,event);
  }
  if (!changes.size) return events;
  return events.flatMap(original => {
    const id=identity(original);
    const projected=id && changes.get(id);
    if (!projected) return [original];
    if (typeof original.surfaceOp==='object') return [];
    return [{...projected,seq:original.seq}];
  });
}
