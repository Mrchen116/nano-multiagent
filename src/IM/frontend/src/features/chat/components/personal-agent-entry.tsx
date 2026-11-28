import { Pin } from 'lucide-react';
import { useTranslation } from '../../../i18n';
import type { Conversation } from '../chat-types';
import { AssistantIllustration, Avatar, agentAvatarId } from './avatar';
import { conversationPreview, formatConversationDate } from './conversation-preview';

/** Keep the owner's assistant pinned while showing the same live summary as other chats. */
export function PersonalAgentEntry({ name, agentId, pending = false, conversation, active, onSelect }: {
  name?: string;
  agentId?: string;
  pending?: boolean;
  conversation?: Conversation;
  active: boolean;
  onSelect(): void;
}) {
  const { t } = useTranslation();
  const title = (!pending ? conversation?.title : undefined) || name || t('pa.create');
  const preview = !pending && conversation ? conversationPreview(conversation, t) : '';
  const time = !pending ? formatConversationDate(conversation?.last_message_at ?? null) : null;
  return <div className="pa-entry">
    <button type="button" className={`chat-sidebar-row${active ? ' chat-sidebar-row--active' : ''}`} aria-current={active ? 'true' : undefined} onClick={onSelect}>
      {agentId && !pending ? <Avatar id={agentAvatarId(agentId)} size={36} /> : <AssistantIllustration size={36} />}
      <span className="chat-sidebar-row-body">
        <span className="chat-sidebar-row-title-line">
          <span className="chat-sidebar-row-title">{title}</span>
          <Pin className="pa-entry-pin" aria-hidden="true" />
          {time && <span className="chat-sidebar-row-time">{time}</span>}
        </span>
        <span className="chat-sidebar-row-preview-line">
          <span className="chat-sidebar-row-preview">{preview || t(name && !pending ? 'pa.role' : 'firstUse.continue')}</span>
          {!pending && (conversation?.unread_count ?? 0) > 0 && <span className="chat-sidebar-row-unread" aria-label={`${conversation!.unread_count} unread`}>{conversation!.unread_count}</span>}
        </span>
      </span>
    </button>
  </div>;
}
