import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';

/** Mention and reply targeting are transport metadata, never inferred from message text. */
export function needsAttention(input: RelayInput, config: AgentConfiguration): boolean {
  if (input.metadata.context_only) return false;
  const mentions = input.metadata.mentioned_agent_ids;
  return input.metadata.conversation_type !== 'group' || config.groupReplyPolicy === 'always'
    || (Array.isArray(mentions) && mentions.includes(config.agentId)) || input.metadata.reply_to_agent_id === config.agentId;
}

/** Read a command after the host-resolved mention of this input's target Agent. */
export function controlText(input:RelayInput):string {
  // A represented message is conversation input, never a fresh human control command.
  if(input.message.pa_agent_id)return '';
  const text=input.message.content.trim();
  const self=input.participants?.find(member=>member.type==='agent'&&member.id===input.agent_id);
  const mention=/^<mention type="user" target_id="([^"<>]+)"\s*\/>\s*/.exec(text);
  return self&&mention?.[1]===self.user_id?text.slice(mention[0].length).trim():text;
}
