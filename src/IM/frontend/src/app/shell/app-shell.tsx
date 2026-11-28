import { PropsWithChildren, useEffect } from "react";
import { Link, NavLink, useLocation, useMatch, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { computeUnreadBadgeTotal } from "@nano/product-contracts/client-parity";

import { reportDesktopAttention } from "../../desktop/desktop-api";
import { isDesktopClient } from "../../desktop/desktop-context";
import { DesktopNodeOnboardingBanner } from "../../desktop/desktop-node-onboarding-banner";
import {
  DesktopNarrowUpdateBanner,
  DesktopRailUpdatePill,
} from "../../desktop/desktop-update-pill";
import { useHasDesktopUnsavedForm } from "../../desktop/use-desktop-unsaved-form";
import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { listConversations } from "../../features/chat/chat-api";
import { useAuthStore } from "../../features/auth/auth-store";
import { useLocalUnreadFeedback } from "../../features/notifications/local-unread-feedback";
import { AgentsNavIcon, ChatNavIcon, MeNavIcon, PeopleNavIcon, TasksNavIcon } from "./mobile-nav-icons";
import { NanoBrand } from "./nano-brand";
import "./app-shell.css";
import { UserMenu } from "./user-menu";

/**
 * Top-level app chrome: persistent desktop navigation with
 * Chat/Tasks/Agents destinations and an account menu; collapses to
 * a bottom 4-tab nav with product icons and unread feedback on mobile list pages.
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
  const navigate = useNavigate();
  const location = useLocation();
  const hasUnsavedForm = useHasDesktopUnsavedForm();

  useEffect(() => {
    if (!isDesktopClient()) return;
    (window as unknown as { __CREWDEN_SHELL_READY__?: boolean }).__CREWDEN_SHELL_READY__ = true;
    const onNavigate = (event: Event) => {
      const target = (event as CustomEvent<string>).detail;
      if (typeof target === "string" && target.startsWith("/")) {
        navigate(target);
      }
    };
    window.addEventListener("crewden:navigate", onNavigate);
    return () => {
      (window as unknown as { __CREWDEN_SHELL_READY__?: boolean }).__CREWDEN_SHELL_READY__ = false;
      window.removeEventListener("crewden:navigate", onNavigate);
    };
  }, [navigate]);

  useEffect(() => {
    if (!isDesktopClient()) return;
    const current_route = `${location.pathname}${location.search}`;
    void reportDesktopAttention({
      current_route,
      has_unsaved_form: hasUnsavedForm,
    })
      .then((data) => {
        if (data?.navigate_to && data.navigate_to !== current_route) {
          navigate(data.navigate_to);
        }
      })
      .catch(() => {});
  }, [hasUnsavedForm, location.pathname, location.search, navigate]);

  const { data: conversations } = useQuery({
    queryKey: ["chat", "conversations"],
    queryFn: listConversations,
    enabled: authed,
    staleTime: 10_000
  });
  const conversationsWithLocalUnread = useLocalUnreadFeedback(conversations ?? []);
  const totalUnread = computeUnreadBadgeTotal(conversationsWithLocalUnread);

  return (
    <div className={`im-shell${isMobileConversation ? " im-shell--conversation" : ""}`}>
      {!isMobile && (
        <header role="banner" className="im-shell-rail">
          <Link to="/chat" className="im-shell-brand-link" aria-label={t("shell.home")}><NanoBrand className="im-shell-brand" /></Link>
          <nav aria-label="primary" className="im-shell-tabs">
            <NavLink to="/chat" end={false}>
              <span className="im-shell-rail-icon-wrap">
                <ChatNavIcon />
                {totalUnread > 0 && (
                  <span data-testid="shell-chat-unread" className="im-shell-unread-badge">
                    {totalUnread}
                  </span>
                )}
              </span>
              <span>{t("shell.tabs.chat")}</span>
            </NavLink>
            <NavLink to="/people"><PeopleNavIcon /><span>{t("shell.tabs.people")}</span></NavLink>
            <NavLink to="/tasks"><TasksNavIcon /><span>{t("shell.tabs.tasks")}</span></NavLink>
            <NavLink to="/settings/agents"><AgentsNavIcon /><span>{t("shell.tabs.agents")}</span></NavLink>
          </nav>
          <DesktopRailUpdatePill />
          <UserMenu />
        </header>
      )}
      <main className="im-shell-main">
        {isMobile && <DesktopNarrowUpdateBanner />}
        {children}
        <DesktopNodeOnboardingBanner />
      </main>
      {isMobile && !isMobileConversation && (
        <nav aria-label="mobile" className="im-shell-bottombar">
          <NavLink to="/chat" className="im-shell-bottomtab">
            <span className="im-shell-bottomtab-icon-wrap">
              <span aria-hidden className="im-shell-bottomtab-icon">
                <ChatNavIcon />
              </span>
              {totalUnread > 0 && (
                <span data-testid="shell-chat-unread" className="im-shell-unread-badge">
                  {totalUnread}
                </span>
              )}
            </span>
            <span>{t("shell.tabs.chat")}</span>
          </NavLink>
          <NavLink to="/people" className="im-shell-bottomtab">
            <span className="im-shell-bottomtab-icon-wrap">
              <span aria-hidden className="im-shell-bottomtab-icon"><PeopleNavIcon /></span>
            </span>
            <span>{t("shell.tabs.people")}</span>
          </NavLink>
          <NavLink to="/tasks" className="im-shell-bottomtab">
            <span className="im-shell-bottomtab-icon-wrap">
              <span aria-hidden className="im-shell-bottomtab-icon"><TasksNavIcon /></span>
            </span>
            <span>{t("shell.tabs.tasks")}</span>
          </NavLink>
          <NavLink to="/settings/agents" className="im-shell-bottomtab">
            <span className="im-shell-bottomtab-icon-wrap">
              <span aria-hidden className="im-shell-bottomtab-icon">
                <AgentsNavIcon />
              </span>
            </span>
            <span>{t("shell.tabs.agents")}</span>
          </NavLink>
          <NavLink to="/me" className="im-shell-bottomtab">
            <span className="im-shell-bottomtab-icon-wrap">
              <span aria-hidden className="im-shell-bottomtab-icon">
                <MeNavIcon />
              </span>
            </span>
            <span>{t("shell.tabs.me")}</span>
          </NavLink>
        </nav>
      )}
    </div>
  );
}
