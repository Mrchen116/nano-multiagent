import { PropsWithChildren } from "react";
import { NavLink } from "react-router-dom";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { UserMenu } from "./user-menu";

/**
 * Top-level app chrome: 48px dark top banner with brand + Chat/Agents tabs +
 * UserMenu on desktop; collapses to a status spacer with a bottom 3-tab nav on mobile.
 *
 * Children are rendered inside the content area; routing is the caller's concern.
 */
export function AppShell({ children }: PropsWithChildren) {
  const isMobile = useIsMobile();
  const { t } = useTranslation();

  return (
    <div className="im-shell">
      {!isMobile && (
        <header role="banner" className="im-shell-topbar">
          <div className="im-shell-brand">{t("shell.appName")}</div>
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
          <NavLink to="/chat">{t("shell.tabs.chat")}</NavLink>
          <NavLink to="/settings/agents">{t("shell.tabs.agents")}</NavLink>
          <NavLink to="/me">{t("shell.tabs.me")}</NavLink>
        </nav>
      )}
    </div>
  );
}
