import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';

/** Mention and reply targeting are transport metadata, never inferred from message text. */
export function needsAttention(input: RelayInput, config: AgentConfiguration): boolean {
  const mentions = input.metadata.mentioned_agent_ids;
  return input.metadata.conversation_type !== 'group' || config.groupReplyPolicy === 'always'
    || (Array.isArray(mentions) && mentions.includes(config.agentId)) || input.metadata.reply_to_agent_id === config.agentId;
}
