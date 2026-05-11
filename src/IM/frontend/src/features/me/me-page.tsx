import { Link, useNavigate } from "react-router-dom";

import { getCurrentLanguage, setLanguage, useTranslation, type Locale } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";

/**
 * Mobile-only aggregated entry page that bundles Account / Nodes / Language / Sign out.
 * Desktop renders the same links inline within the user menu instead.
 */
export function MePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const lang = getCurrentLanguage();

  const handleSignOut = () => {
    useAuthStore.getState().clear();
    navigate("/login", { replace: true });
  };

  const handleLanguageChange = (next: Locale) => {
    setLanguage(next);
  };

  return (
    <section className="im-me-page" data-testid="me-page">
      <header>
        <h1>{t("me.title")}</h1>
        {user && <p>{user.display_name}</p>}
      </header>
      <nav aria-label="me-sections">
        <ul>
          <li>
            <Link to="/settings/account">{t("me.sections.account")}</Link>
          </li>
          <li>
            <Link to="/settings/nodes">{t("me.sections.nodes")}</Link>
          </li>
        </ul>
      </nav>
      <fieldset>
        <legend>{t("me.sections.language")}</legend>
        <label>
          <input
            type="radio"
            name="lang"
            value="en"
            checked={lang === "en"}
            onChange={() => handleLanguageChange("en")}
          />
          {t("me.language.en")}
        </label>
        <label>
          <input
            type="radio"
            name="lang"
            value="zh"
            checked={lang === "zh"}
            onChange={() => handleLanguageChange("zh")}
          />
          {t("me.language.zh")}
        </label>
      </fieldset>
      <button type="button" onClick={handleSignOut} className="im-me-signout">
        {t("me.sections.signOut")}
      </button>
    </section>
  );
}
