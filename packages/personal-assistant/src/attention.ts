import { classifyChatDelivery, type AgentConfiguration, type RelayInput } from '@nano/product-contracts';

/** Determine direct addressing from trusted source facts, including IM mentions and replies. */
export function needsAttention(input: RelayInput, config: Pick<AgentConfiguration, 'agentId'>): boolean {
  const meta = input.metadata;
  if (meta.context_only || meta.personal_delivery === 'observer') return false;
  if (typeof meta.addressed_to_agent === 'boolean') return meta.addressed_to_agent;
  return meta.conversation_type !== 'group' || (Array.isArray(meta.mentioned_agent_ids) && meta.mentioned_agent_ids.includes(config.agentId))
    || meta.reply_to_agent_id === config.agentId;
}

/** Select a chat's admission and timing independently from command or publication authority. */
export function chatDelivery(input: RelayInput, config: AgentConfiguration, ownerId: string) {
  const meta = input.metadata;
  const direct = meta.conversation_type === 'direct' && meta.personal_delivery !== 'observer' && !meta.pa_observation;
  const ownerDirect = typeof meta.owner_direct === 'boolean' ? meta.owner_direct
    : direct && input.message.sender_type === 'user' && !input.message.pa_agent_id
      && (meta.channel==='feishu' ? meta.owner_user_id===ownerId : input.message.sender_user_id===ownerId);
  return classifyChatDelivery(config.collaborationScope, {
    ownerDirect, directToAgent: direct, addressedToAgent: needsAttention(input, config),
    addressedToOwner: !!config.personal && meta.addressed_to_owner === true, contextOnly: !!meta.context_only,
  });
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
