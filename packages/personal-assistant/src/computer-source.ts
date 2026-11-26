import type { RelayInput } from '@nano/product-contracts';

/** Return the sender's own instruction only on an owner-to-Agent delivery. */
export function computerOwnerText(input: RelayInput, owner: string, personal: boolean): string | undefined {
  const { message, metadata } = input;
  if (
    message.sender_type !== 'user' ||
    message.sender_user_id !== owner ||
    message.pa_agent_id ||
    metadata.context_only ||
    metadata.pa_observation ||
    metadata.personal_delivery === 'observer' ||
    (personal && metadata.personal_delivery !== 'participant')
  )
    return;
  const mentions = metadata.explicit_mentioned_agent_ids ?? metadata.mentioned_agent_ids;
  if (
    metadata.conversation_type === 'direct' ||
    (metadata.conversation_type === 'group' && Array.isArray(mentions) && mentions.includes(input.agent_id))
  )
    return message.content;
}
