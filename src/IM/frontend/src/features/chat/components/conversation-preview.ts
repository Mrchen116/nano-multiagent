import type { TFunction } from 'i18next';
import type { Conversation } from '../chat-types';
import { formatSystemNotice } from '../system-notice';
import { mentionNameMap, mentionPlainText } from './mention-parser';

/** Use the same message summary for pinned and ordinary conversations. */
export function conversationPreview(conversation: Conversation, t: TFunction): string {
  const notice = formatSystemNotice(t, conversation.last_message_system_notice, conversation.type === 'direct');
  if (notice) return notice;
  const content = conversation.last_message_card
    ? [t('chat.toast.card'), conversation.last_message_card.title].filter(Boolean).join(' · ')
    : mentionPlainText(conversation.last_message_preview ?? '', mentionNameMap(conversation.participants));
  return content && conversation.type === 'group' && conversation.last_message_sender_name
    ? `${conversation.last_message_sender_name}: ${content}` : content;
}

/** Format the latest message time consistently across conversation entries. */
export function formatConversationDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const isToday = d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
  if (isToday) {
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  }
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.getDate() === yesterday.getDate() && d.getMonth() === yesterday.getMonth() && d.getFullYear() === yesterday.getFullYear()) {
    return "Yesterday";
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

