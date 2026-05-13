import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getCurrentLanguage, setLanguage, useTranslation, type Locale } from "../../i18n";
import { useAuthStore } from "../../features/auth/auth-store";
import { listNodes } from "../../features/settings/im-settings-api";

/**
 * Desktop user menu — avatar dropdown with quick actions.
 *
 * Kept intentionally lightweight (no Radix dropdown primitive) because we only need
 * keyboard-accessible click toggling here; Radix is reserved for richer composer/dialog
 * surfaces in chat. Close-on-outside-click is wired via document-level listener.
 */
export function UserMenu() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lang = getCurrentLanguage();

  const nodesQuery = useQuery({ queryKey: ["settings", "nodes"], queryFn: listNodes, staleTime: 30_000 });
  const ownedNodes = (nodesQuery.data ?? []).filter((n) => user?.owned_node_ids?.includes(n.node_id));
  const onlineCount = ownedNodes.filter((n) => n.status === "online").length;
  const offlineCount = ownedNodes.length - onlineCount;

  useEffect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  if (!user) return null;

  const initials = (user.display_name || user.username).slice(0, 2).toUpperCase();

  const handleSignOut = () => {
    useAuthStore.getState().clear();
    navigate("/login", { replace: true });
  };

  const handleLanguage = (next: Locale) => {
    setLanguage(next);
    setOpen(false);
  };

  const nodesSubtitle = `${ownedNodes.length} ${t("common.owned")} · ${onlineCount} ${t("common.online")}${offlineCount > 0 ? ` · ${offlineCount} ${t("common.offline")}` : ""}`;

  return (
    <div ref={containerRef} className="im-user-menu">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className="im-user-menu-trigger"
      >
        <span aria-hidden className="im-user-menu-avatar">
          {initials}
        </span>
        <span>{user.display_name || user.username}</span>
        <span aria-hidden className="im-user-menu-chevron">▾</span>
      </button>
      {open && (
        <div role="menu" className="im-user-menu-popover">
          {/* Identity Strip */}
          <div
            role="none"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "12px 14px",
              borderBottom: "1px solid var(--im-border)",
              marginBottom: 4
            }}
          >
            <span
              aria-hidden
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                background: "oklch(0.52 0.14 270)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                fontWeight: 700,
                flexShrink: 0
              }}
            >
              {initials}
            </span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <p
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 700,
                  color: "var(--im-text)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap"
                }}
              >
                {user.display_name || user.username}
              </p>
              <p
                style={{
                  margin: "2px 0 0",
                  fontSize: 11,
                  color: "var(--im-text-muted)",
                  fontFamily: "var(--im-font-mono)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap"
                }}
              >
                {user.id}
              </p>
            </div>
          </div>

          <Link role="menuitem" to="/settings/account" onClick={() => setOpen(false)} className="im-user-menu-item">
            <span className="im-user-menu-icon">👤</span>
            <div className="im-user-menu-item-body">
              <div style={{ fontSize: 14, fontWeight: 500 }}>{t("shell.userMenu.account")}</div>
              <div style={{ fontSize: 12, color: "var(--im-text-muted)", marginTop: 1 }}>
                {t("me.sections.accountSubtitle")}
              </div>
            </div>
          </Link>
          <Link role="menuitem" to="/settings/nodes" onClick={() => setOpen(false)} className="im-user-menu-item">
            <span className="im-user-menu-icon">🖥</span>
            <div className="im-user-menu-item-body">
              <div style={{ fontSize: 14, fontWeight: 500 }}>{t("shell.userMenu.nodes")}</div>
              <div style={{ fontSize: 12, color: "var(--im-text-muted)", marginTop: 1 }}>
                {nodesSubtitle}
              </div>
            </div>
            <span className="im-user-menu-chevron-right" aria-hidden>›</span>
          </Link>
          <div role="group" className="im-user-menu-language">
            <span className="im-user-menu-icon">文</span>
            <span style={{ fontSize: 14, fontWeight: 500, flex: 1 }}>{t("shell.userMenu.language")}</span>
            <span className="im-user-menu-lang-options">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={lang === "en"}
                onClick={() => handleLanguage("en")}
                style={{ fontWeight: lang === "en" ? 700 : 500 }}
              >
                EN
              </button>
              <span className="im-user-menu-language-divider">|</span>
              <button
                type="button"
                role="menuitemradio"
                aria-checked={lang === "zh"}
                onClick={() => handleLanguage("zh")}
                style={{ fontWeight: lang === "zh" ? 700 : 500 }}
              >
                中
              </button>
            </span>
          </div>
          <button role="menuitem" type="button" onClick={handleSignOut} className="im-user-menu-signout">
            <span className="im-user-menu-icon">↗</span>
            <span style={{ flex: 1, textAlign: "left" }}>{t("shell.userMenu.signOut")}</span>
            <span className="im-user-menu-chevron-right" aria-hidden>›</span>
          </button>
        </div>
      )}
    </div>
  );
}
