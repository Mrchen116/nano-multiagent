import { Link, useNavigate } from "react-router-dom";

import { getCurrentLanguage, setLanguage, useTranslation, type Locale } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { ensureNotificationPermission } from "../notifications/notification-api";
import { useNotificationPreference } from "../notifications/notification-preference";

/**
 * Mobile-only aggregated entry page that bundles Account / Nodes / Language / Sign out.
 * Layout mirrors the WeChat-style "我的" tab from the design prototype
 * (`docs/changes/feat-340-agent-native-im/attachments/prototype/project/im-mypage.jsx`):
 * full-width identity card, then grouped action cards each carrying a leading
 * icon glyph and a chevron, plus a pill toggle for the language picker.
 */
export function MePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const lang = getCurrentLanguage();
  const [notificationsEnabled, setNotificationsEnabled] = useNotificationPreference();

  const handleSignOut = () => {
    useAuthStore.getState().clear();
    navigate("/login", { replace: true });
  };

  const handleLanguageChange = (next: Locale) => {
    setLanguage(next);
  };

  const initials = (user?.display_name || user?.username || "U").slice(0, 2).toUpperCase();

  return (
    <section className="im-me-page" data-testid="me-page">
      <header>
        <h1>{t("me.title")}</h1>
      </header>

      <Link
        to="/settings/account"
        className="im-me-identity-card"
        data-testid="me-identity-card"
      >
        <span className="im-me-identity-avatar" aria-hidden="true">{initials}</span>
        <div className="im-me-identity-body">
          <p className="im-me-identity-name">{user?.display_name ?? user?.username ?? ""}</p>
          <p
            className="im-me-identity-id font-mono"
            data-testid="me-identity-user-id"
          >
            {user?.id ?? ""}
          </p>
        </div>
        <span className="im-me-row-chevron" aria-hidden="true">›</span>
      </Link>

      <div className="im-me-card">
        <Link to="/settings/nodes" className="im-me-row" data-testid="me-row-nodes">
          <span className="im-me-row-icon" aria-hidden="true">🖥</span>
          <span className="im-me-row-label">{t("me.sections.nodes")}</span>
          <span className="im-me-row-chevron" aria-hidden="true">›</span>
        </Link>
      </div>

      <div className="im-me-card">
        <Link to="/settings/account" className="im-me-row" data-testid="me-row-account">
          <span className="im-me-row-icon" aria-hidden="true">👤</span>
          <span className="im-me-row-label">{t("me.sections.account")}</span>
          <span className="im-me-row-chevron" aria-hidden="true">›</span>
        </Link>
      </div>

      <div className="im-me-card">
        <div className="im-me-row" data-testid="me-row-language">
          <span className="im-me-row-icon" aria-hidden="true">文</span>
          <span className="im-me-row-label">{t("me.sections.language")}</span>
          <div className="im-me-lang-pill" role="group" aria-label={t("me.sections.language")}>
            <button
              type="button"
              className={lang === "en" ? "im-me-lang-pill-btn active" : "im-me-lang-pill-btn"}
              aria-pressed={lang === "en"}
              onClick={() => handleLanguageChange("en")}
            >
              EN
            </button>
            <button
              type="button"
              className={lang === "zh" ? "im-me-lang-pill-btn active" : "im-me-lang-pill-btn"}
              aria-pressed={lang === "zh"}
              onClick={() => handleLanguageChange("zh")}
            >
              中
            </button>
          </div>
        </div>
      </div>

      <div className="im-me-card">
        <label className="im-me-row" data-testid="me-row-notifications">
          <span className="im-me-row-icon" aria-hidden="true">🔔</span>
          <span className="im-me-row-label">{t("me.notifications.toggle")}</span>
          <input
            type="checkbox"
            checked={notificationsEnabled}
            onChange={(event) => {
              const next = event.target.checked;
              setNotificationsEnabled(next);
              if (next) {
                void ensureNotificationPermission();
              }
            }}
          />
        </label>
      </div>

      <div className="im-me-card">
        <button
          type="button"
          onClick={handleSignOut}
          className="im-me-row im-me-row--danger"
          data-testid="me-row-signout"
        >
          <span className="im-me-row-icon" aria-hidden="true">↗</span>
          <span className="im-me-row-label">{t("me.sections.signOut")}</span>
        </button>
      </div>
    </section>
  );
}
