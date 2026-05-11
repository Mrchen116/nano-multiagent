import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getCurrentLanguage, useTranslation } from "../../i18n";
import { AuthApiError, register } from "./auth-api";
import { useAuthStore } from "./auth-store";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const pair = await register({
        username: username.trim(),
        password,
        display_name: displayName.trim() || username.trim(),
        locale: getCurrentLanguage()
      });
      setSession(pair);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof AuthApiError && err.status === 409) {
        setError(t("auth.register.errorUsernameTaken"));
      } else {
        setError(t("auth.register.errorGeneric"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="im-auth-screen">
      <form className="im-auth-card" onSubmit={handleSubmit} noValidate>
        <header className="im-auth-header">
          <h1>{t("auth.register.title")}</h1>
          <p>{t("auth.register.subtitle")}</p>
        </header>
        <label className="im-auth-field">
          <span>{t("auth.register.username")}</span>
          <input
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label className="im-auth-field">
          <span>{t("auth.register.displayName")}</span>
          <input
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            disabled={submitting}
          />
        </label>
        <label className="im-auth-field">
          <span>{t("auth.register.password")}</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        {error && (
          <div role="alert" className="im-auth-error">
            {error}
          </div>
        )}
        <button type="submit" className="im-auth-submit" disabled={submitting}>
          {submitting ? t("auth.register.submitting") : t("auth.register.submit")}
        </button>
        <footer className="im-auth-footer">
          <span>{t("auth.register.haveAccount")}</span>
          <Link to="/login">{t("auth.register.loginLink")}</Link>
        </footer>
      </form>
    </div>
  );
}
