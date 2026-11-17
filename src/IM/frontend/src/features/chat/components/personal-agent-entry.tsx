import { Pin } from 'lucide-react';
import { useTranslation } from '../../../i18n';
import type { Conversation } from '../chat-types';
import { Avatar, colorForAgentSeed } from './avatar';
import { conversationPreview, formatConversationDate } from './conversation-preview';

/** Keep the owner's assistant pinned while showing the same live summary as other chats. */
export function PersonalAgentEntry({ name, agentId, avatarVariant, conversation, active, onSelect }: {
  name?: string;
  agentId?: string;
  avatarVariant?: number | null;
  conversation?: Conversation;
  active: boolean;
  onSelect(): void;
}) {
  const { t } = useTranslation();
  const title = conversation?.title || name || t('pa.create');
  const preview = conversation ? conversationPreview(conversation, t) : '';
  const time = formatConversationDate(conversation?.last_message_at ?? null);
  return <div className="pa-entry">
    <button type="button" className={`chat-sidebar-row${active ? ' chat-sidebar-row--active' : ''}`} aria-current={active ? 'true' : undefined} onClick={onSelect}>
      <Avatar personal agentId={agentId} avatarVariant={avatarVariant} initials={title.slice(0, 2)} color={colorForAgentSeed(title)} size={36} />
      <span className="chat-sidebar-row-body">
        <span className="chat-sidebar-row-title-line">
          <span className="chat-sidebar-row-title">{title}</span>
          <Pin className="pa-entry-pin" aria-hidden="true" />
          {time && <span className="chat-sidebar-row-time">{time}</span>}
        </span>
        <span className="chat-sidebar-row-preview-line">
          <span className="chat-sidebar-row-preview">{preview || t(name ? 'pa.role' : 'firstUse.continue')}</span>
          {(conversation?.unread_count ?? 0) > 0 && <span className="chat-sidebar-row-unread" aria-label={`${conversation!.unread_count} unread`}>{conversation!.unread_count}</span>}
        </span>
      </span>
    </button>
  </div>;
}
