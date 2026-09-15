import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useTranslation } from "../../i18n";
import { AuthApiError, login } from "./auth-api";
import { AuthPasswordField, AuthTextField } from "./auth-form-fields";
import { AuthFeedbackCode, FieldErrors, validateLogin } from "./auth-form-feedback";
import { AuthAlert, AuthPageFrame, SubmitArrow } from "./auth-page-frame";
import { useAuthStore } from "./auth-store";

type LoginField = "username" | "password";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);
  const signOut = Boolean((location.state as { signOut?: boolean } | null)?.signOut);
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<LoginField>>({});
  const [formError, setFormError] = useState<AuthFeedbackCode | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (signOut) useAuthStore.getState().clear();
  }, [signOut]);

  function feedback(code?: AuthFeedbackCode) {
    return code ? t(`auth.feedback.${code}`) : undefined;
  }

  function updateField(field: LoginField, value: string) {
    if (field === "username") setUsername(value);
    else setPassword(value);
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setFormError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const errors = validateLogin({ username, password });
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      (errors.username ? usernameRef : passwordRef).current?.focus();
      return;
    }

    setFieldErrors({});
    setFormError(null);
    setSubmitting(true);
    try {
      const pair = await login({ username: username.trim(), password });
      setSession(pair);
      navigate(from, { replace: true });
    } catch (error) {
      setFormError(error instanceof AuthApiError && error.status === 401 ? "invalidCredentials" : "serviceUnavailable");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPageFrame
      kicker={t("auth.login.kicker")}
      title={t("auth.login.title")}
      subtitle={t("auth.login.subtitle")}
      footer={
        <>
          <span>{t("auth.login.noAccount")}</span>
          <Link
            className="im-auth-link"
            aria-disabled={submitting}
            tabIndex={submitting ? -1 : undefined}
            onClick={(event) => submitting && event.preventDefault()}
            to="/register"
          >
            {t("auth.login.registerLink")}
          </Link>
        </>
      }
    >
      <form className="im-auth-form" onSubmit={handleSubmit} noValidate>
        <AuthTextField
          id="username"
          label={t("auth.login.username")}
          value={username}
          onValueChange={(value) => updateField("username", value)}
          autoComplete="username"
          error={feedback(fieldErrors.username)}
          inputRef={usernameRef}
          disabled={submitting}
          maxLength={64}
        />
        <AuthPasswordField
          id="password"
          label={t("auth.login.password")}
          value={password}
          onValueChange={(value) => updateField("password", value)}
          autoComplete="current-password"
          error={feedback(fieldErrors.password)}
          inputRef={passwordRef}
          disabled={submitting}
          maxLength={256}
          showLabel={t("auth.common.showPassword")}
          hideLabel={t("auth.common.hidePassword")}
        />
        {formError && <AuthAlert>{feedback(formError)}</AuthAlert>}
        <button type="submit" className="im-auth-submit" disabled={submitting}>
          <span>{submitting ? t("auth.login.submitting") : t("auth.login.submit")}</span>
          {!submitting && <SubmitArrow />}
        </button>
      </form>
    </AuthPageFrame>
  );
}
