/** Maximum wait for the oldest unnotified background chat. */
export const CHAT_BACKGROUND_DELAY_MS = 10 * 60_000;

/** Visibility and bidirectional communication scope for an ordinary or global Agent. */
export type CollaborationScope = 'team' | 'project' | 'owner_only';

/** Visibility and bidirectional communication scope supported by a Personal Assistant (PA). */
export type PersonalCollaborationScope = 'team' | 'owner_only';

/** Facts resolved from a trusted conversation source for one receiving Agent. */
export interface ChatAddress {
  ownerDirect: boolean;
  ownerInternal?: boolean;
  ownerObserved?: boolean;
  projectAllowed?: boolean;
  directToAgent: boolean;
  addressedToAgent: boolean;
  addressedToOwner: boolean;
  contextOnly?: boolean;
}

/** Check the public configuration value without coercing an unknown scope to team. */
export function isCollaborationScope(value: unknown): value is CollaborationScope {
  return value === 'team' || value === 'project' || value === 'owner_only';
}

/** Check whether a collaboration scope is valid for a Personal Assistant (PA). */
export function isPersonalCollaborationScope(value: unknown): value is PersonalCollaborationScope {
  return value === 'team' || value === 'owner_only';
}

/** Apply the receiving boundary before deciding when to notify the model.
 *
 * Args:
 *   scope: Current collaboration scope; an omitted setting defaults to team.
 *   facts: Recipient and source identity resolved by the authenticated channel.
 * Returns:
 *   Whether to skip the message, or the priority of its admitted content.
 */
export function classifyChatDelivery(scope: CollaborationScope | undefined, facts: ChatAddress): 'skip' | 'high' | 'background' {
  if (scope === 'owner_only' && !facts.ownerDirect && !facts.ownerInternal && !facts.ownerObserved) return 'skip';
  if (scope === 'project' && !facts.ownerDirect && !facts.ownerInternal && !facts.projectAllowed) return 'skip';
  if (facts.contextOnly) return 'background';
  return facts.ownerDirect || facts.directToAgent || facts.addressedToAgent || facts.addressedToOwner ? 'high' : 'background';
}
