import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getCurrentLanguage, setLanguage, useTranslation, type Locale } from "../../i18n";
import { useAuthStore } from "../../features/auth/auth-store";

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

  useEffect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  if (!user) return null;

  const initials = (user.display_name || user.username).slice(0, 1).toUpperCase();

  const handleSignOut = () => {
    useAuthStore.getState().clear();
    navigate("/login", { replace: true });
  };

  const handleLanguage = (next: Locale) => {
    setLanguage(next);
    setOpen(false);
  };

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
      </button>
      {open && (
        <div role="menu" className="im-user-menu-popover">
          <Link role="menuitem" to="/settings/agents" onClick={() => setOpen(false)}>
            {t("shell.userMenu.newAgent")}
          </Link>
          <Link role="menuitem" to="/settings/account" onClick={() => setOpen(false)}>
            {t("shell.userMenu.account")}
          </Link>
          <div role="group" className="im-user-menu-language">
            <span>{t("shell.userMenu.language")}</span>
            <button
              type="button"
              role="menuitemradio"
              aria-checked={lang === "en"}
              onClick={() => handleLanguage("en")}
            >
              EN
            </button>
            <button
              type="button"
              role="menuitemradio"
              aria-checked={lang === "zh"}
              onClick={() => handleLanguage("zh")}
            >
              中
            </button>
          </div>
          <button role="menuitem" type="button" onClick={handleSignOut} className="im-user-menu-signout">
            {t("shell.userMenu.signOut")}
          </button>
        </div>
      )}
    </div>
  );
}
