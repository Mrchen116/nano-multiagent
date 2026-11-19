import { type ReactNode } from "react";

import { useTranslation } from "../../../i18n";
import type { Conversation } from "../chat-types";
import { Avatar, GroupAvatar, colorForAgentSeed, directPersonAvatarName } from "./avatar";

/** Keep the selected conversation identifiable while its access check completes. */
export function PendingConversationPane({ conversation, personal, selfUserId, children }: {
  conversation?: Conversation;
  personal: boolean;
  selfUserId: string | null;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const agent = conversation?.participants.find(person => person.type === "agent");
  const name = conversation && !agent ? directPersonAvatarName(conversation, selfUserId) : conversation?.title ?? "";
  return (
    <section className="chat-pane" aria-label={conversation?.title}>
      <header className="chat-pane-header chat-pane-pending-header">
        {conversation && (conversation.type === "group"
          ? <GroupAvatar size={34} label={t("chat.list.filters.group")} />
          : <Avatar size={34} personal={personal || agent?.role === "personal"} agentId={agent?.id}
              avatarVariant={agent?.avatar_variant} initials={name} color={colorForAgentSeed(name)} />)}
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
