import { PropsWithChildren } from "react";
import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { listConversations } from "../../features/chat/v2/chat-api";
import { useAuthStore } from "../../features/auth/auth-store";
import { UserMenu } from "./user-menu";

/**
 * Top-level app chrome: 48px dark top banner with brand + internal badge +
 * Chat/Agents tabs + UserMenu on desktop; collapses to a status spacer with
 * a bottom 3-tab nav (💬🤖👤 + unread badge on Chat) on mobile.
 *
 * Children are rendered inside the content area; routing is the caller's concern.
 */
export function AppShell({ children }: PropsWithChildren) {
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  const authed = useAuthStore((s) => Boolean(s.user));

  const { data: conversations } = useQuery({
    queryKey: ["chat-v2", "conversations"],
    queryFn: listConversations,
    enabled: authed && isMobile,
    staleTime: 10_000
  });
  const totalUnread = (conversations ?? []).reduce((sum, c) => sum + (c.unread_count ?? 0), 0);

  return (
    <div className="im-shell">
      {!isMobile && (
        <header role="banner" className="im-shell-topbar">
          <div className="im-shell-brand">
            <span>{t("shell.appName")}</span>
            <span
              data-testid="shell-internal-badge"
              className="im-shell-internal-badge"
            >
              internal
            </span>
          </div>
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
      {isMobile && (
        <nav aria-label="mobile" className="im-shell-bottombar">
          <NavLink to="/chat" className="im-shell-bottomtab">
            <span aria-hidden className="im-shell-bottomtab-icon">💬</span>
            <span>{t("shell.tabs.chat")}</span>
            {totalUnread > 0 && (
              <span data-testid="shell-chat-unread" className="im-shell-unread-badge">
                {totalUnread}
              </span>
            )}
          </NavLink>
          <NavLink to="/settings/agents" className="im-shell-bottomtab">
            <span aria-hidden className="im-shell-bottomtab-icon">🤖</span>
            <span>{t("shell.tabs.agents")}</span>
          </NavLink>
          <NavLink to="/me" className="im-shell-bottomtab">
            <span aria-hidden className="im-shell-bottomtab-icon">👤</span>
            <span>{t("shell.tabs.me")}</span>
          </NavLink>
        </nav>
      )}
    </div>
  );
}
