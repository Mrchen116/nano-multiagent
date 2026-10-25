import type { MessageSource, MessageSourceMap } from '@deepseek-ai/dsh-llm';

interface NanoInputIdentity {
  actorId: string;
  channel: string;
  messageId: string;
  contextEnvelope?: string;
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
