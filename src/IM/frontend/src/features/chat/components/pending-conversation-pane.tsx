import { type ReactNode } from "react";

import { useTranslation } from "../../../i18n";
import type { Conversation } from "../chat-types";
import { Avatar, GroupAvatar, directAvatarId } from "./avatar";

/** Keep the selected conversation identifiable while its access check completes. */
export function PendingConversationPane({ conversation, selfUserId, children }: {
  conversation?: Conversation;
  selfUserId: string | null;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <section className="chat-pane" aria-label={conversation?.title}>
      <header className="chat-pane-header chat-pane-pending-header">
        {conversation && (conversation.type === "group"
          ? <GroupAvatar groupId={conversation.id} size={34} label={t("chat.list.filters.group")} />
          : <Avatar id={directAvatarId(conversation, selfUserId)} size={34} />)}
        <div className="chat-pane-header-body">
          <h2 className="chat-pane-title">{conversation?.title}</h2>
          {conversation?.type === "group" && <div className="chat-pane-header-meta">
            <span className="chat-pane-member-count">{t("chat.groupSettings.memberCount", { count: conversation.participants.length })}</span>
          </div>}
        </div>
      </header>
      <div className="chat-pane-messages"><div className="chat-pane-message-list">{children}</div></div>
      {conversation?.can_write !== false && <div aria-hidden="true" className="chat-pane-composer chat-pane-pending-composer" />}
    </section>
  );
}
