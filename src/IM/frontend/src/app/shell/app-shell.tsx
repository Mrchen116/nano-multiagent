import { PropsWithChildren } from "react";
import { NavLink, useMatch } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { listConversations } from "../../features/chat/chat-api";
import { useAuthStore } from "../../features/auth/auth-store";
import { useLocalUnreadFeedback } from "../../features/notifications/local-unread-feedback";
import { AgentsNavIcon, ChatNavIcon, MeNavIcon } from "./mobile-nav-icons";
import { NanoBrand } from "./nano-brand";
import { UserMenu } from "./user-menu";

/**
 * Top-level app chrome: 48px top banner with brand + internal badge +
 * Chat/Agents tabs + UserMenu on desktop; collapses to a status spacer with
 * a bottom 3-tab nav with product icons and unread feedback on mobile list pages.
 * Mobile conversations hide global navigation to give messages the full height.
 *
 * Children are rendered inside the content area; routing is the caller's concern.
 */
export function AppShell({ children }: PropsWithChildren) {
  const isMobile = useIsMobile();
  const conversationMatch = useMatch("/chat/:conversationId");
  const isMobileConversation = isMobile && Boolean(conversationMatch);
  const { t } = useTranslation();
  const authed = useAuthStore((s) => Boolean(s.user));

  const { data: conversations } = useQuery({
    queryKey: ["chat", "conversations"],
    queryFn: listConversations,
    enabled: authed && isMobile,
    staleTime: 10_000
  });
  const conversationsWithLocalUnread = useLocalUnreadFeedback(conversations ?? []);
  const totalUnread = conversationsWithLocalUnread.reduce((sum, c) => sum + (c.unread_count ?? 0), 0);

  return (
    <div className={`im-shell${isMobileConversation ? " im-shell--conversation" : ""}`}>
      {!isMobile && (
        <header role="banner" className="im-shell-topbar">
          <NanoBrand className="im-shell-brand" />
          <nav aria-label="primary" className="im-shell-tabs">
            <NavLink to="/chat" end={false}>
              {t("shell.tabs.chat")}
            </NavLink>
            <NavLink to="/settings/agents">{t("shell.tabs.agents")}</NavLink>
          </nav>
          <UserMenu />
        </header>
      )}
      <main className="im-shell-main">{children}</main>
      {isMobile && !isMobileConversation && (
        <nav aria-label="mobile" className="im-shell-bottombar">
          <NavLink to="/chat" className="im-shell-bottomtab">
            <span aria-hidden className="im-shell-bottomtab-icon">
              <ChatNavIcon />
            </span>
            <span>{t("shell.tabs.chat")}</span>
            {totalUnread > 0 && (
              <span data-testid="shell-chat-unread" className="im-shell-unread-badge">
                {totalUnread}
              </span>
            )}
          </NavLink>
          <NavLink to="/settings/agents" className="im-shell-bottomtab">
            <span aria-hidden className="im-shell-bottomtab-icon">
              <AgentsNavIcon />
            </span>
            <span>{t("shell.tabs.agents")}</span>
          </NavLink>
          <NavLink to="/me" className="im-shell-bottomtab">
            <span aria-hidden className="im-shell-bottomtab-icon">
              <MeNavIcon />
            </span>
            <span>{t("shell.tabs.me")}</span>
            {totalUnread > 0 && (
              <span data-testid="shell-me-unread" className="im-shell-unread-badge">
                {totalUnread}
              </span>
            )}
          </NavLink>
        </nav>
      )}
    </div>
  );
}
