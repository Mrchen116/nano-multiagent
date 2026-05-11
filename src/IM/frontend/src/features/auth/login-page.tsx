import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useTranslation } from "../../i18n";
import { AuthApiError, login } from "./auth-api";
import { useAuthStore } from "./auth-store";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const pair = await login({ username: username.trim(), password });
      setSession(pair);
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof AuthApiError && err.status === 401) {
        setError(t("auth.login.errorInvalid"));
      } else {
        setError(t("auth.login.errorGeneric"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="im-auth-screen">
      <form className="im-auth-card" onSubmit={handleSubmit} noValidate>
        <header className="im-auth-header">
          <h1>{t("auth.login.title")}</h1>
          <p>{t("auth.login.subtitle")}</p>
        </header>
        <label className="im-auth-field">
          <span>{t("auth.login.username")}</span>
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
          <span>{t("auth.login.password")}</span>
          <input
            type="password"
            autoComplete="current-password"
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
          {submitting ? t("auth.login.submitting") : t("auth.login.submit")}
        </button>
        <footer className="im-auth-footer">
          <span>{t("auth.login.noAccount")}</span>
          <Link to="/register">{t("auth.login.registerLink")}</Link>
        </footer>
      </form>
    </div>
  );
}
