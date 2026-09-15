import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getCurrentLanguage, useTranslation } from "../../i18n";
import { register } from "./auth-api";
import { AuthPasswordField, AuthTextField } from "./auth-form-fields";
import { AuthFeedbackCode, FieldErrors, registrationFeedbackForApiError, validateRegistration } from "./auth-form-feedback";
import { AuthAlert, AuthPageFrame, SubmitArrow } from "./auth-page-frame";
import { useAuthStore } from "./auth-store";

type RegistrationField = "username" | "displayName" | "password";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<RegistrationField>>({});
  const [formError, setFormError] = useState<AuthFeedbackCode | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [responseErrorField, setResponseErrorField] = useState<RegistrationField | null>(null);
  const usernameRef = useRef<HTMLInputElement>(null);
  const displayNameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  function feedback(code?: AuthFeedbackCode) {
    return code ? t(`auth.feedback.${code}`) : undefined;
  }

  function updateField(field: RegistrationField, value: string) {
    if (field === "username") setUsername(value);
    else if (field === "displayName") setDisplayName(value);
    else setPassword(value);
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setFormError(null);
  }

  function focusField(field: RegistrationField) {
    ({ username: usernameRef, displayName: displayNameRef, password: passwordRef })[field].current?.focus();
  }

  useEffect(() => {
    if (!submitting && responseErrorField) {
      focusField(responseErrorField);
      setResponseErrorField(null);
    }
  }, [responseErrorField, submitting]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const errors = validateRegistration({ username, displayName, password });
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      const first = (["username", "displayName", "password"] as RegistrationField[]).find(
        (field) => errors[field]
      );
      if (first) focusField(first);
      return;
    }

    setFieldErrors({});
    setFormError(null);
    setSubmitting(true);
    try {
      const normalizedUsername = username.trim();
      const pair = await register({
        username: normalizedUsername,
        password,
        display_name: displayName.trim() || normalizedUsername,
        locale: getCurrentLanguage()
      });
      setSession(pair);
      navigate("/", { replace: true });
    } catch (error) {
      const fieldFeedback = registrationFeedbackForApiError(error);
      if (fieldFeedback) {
        setFieldErrors({ [fieldFeedback.field]: fieldFeedback.code });
        setResponseErrorField(fieldFeedback.field);
      } else {
        setFormError("serviceUnavailable");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPageFrame
      kicker={t("auth.register.kicker")}
      title={t("auth.register.title")}
      subtitle={t("auth.register.subtitle")}
      footer={
        <>
          <span>{t("auth.register.haveAccount")}</span>
          <Link
            className="im-auth-link"
            aria-disabled={submitting}
            tabIndex={submitting ? -1 : undefined}
            onClick={(event) => submitting && event.preventDefault()}
            to="/login"
          >
            {t("auth.register.loginLink")}
          </Link>
        </>
      }
    >
      <form className="im-auth-form" onSubmit={handleSubmit} noValidate>
        <AuthTextField
          id="username"
          label={t("auth.register.username")}
          value={username}
          onValueChange={(value) => updateField("username", value)}
          autoComplete="username"
          error={feedback(fieldErrors.username)}
          inputRef={usernameRef}
          disabled={submitting}
          maxLength={64}
        />
        <AuthTextField
          id="displayName"
          label={t("auth.register.displayName")}
          optionalLabel={t("auth.common.optional")}
          value={displayName}
          onValueChange={(value) => updateField("displayName", value)}
          autoComplete="name"
          hint={t("auth.register.displayHint")}
          error={feedback(fieldErrors.displayName)}
          inputRef={displayNameRef}
          disabled={submitting}
          maxLength={128}
          required={false}
        />
        <AuthPasswordField
          id="password"
          label={t("auth.register.password")}
          value={password}
          onValueChange={(value) => updateField("password", value)}
          autoComplete="new-password"
          hint={t("auth.register.passwordHint")}
          error={feedback(fieldErrors.password)}
          inputRef={passwordRef}
          disabled={submitting}
          maxLength={256}
          showLabel={t("auth.common.showPassword")}
          hideLabel={t("auth.common.hidePassword")}
        />
        {formError && <AuthAlert>{feedback(formError)}</AuthAlert>}
        <button type="submit" className="im-auth-submit" disabled={submitting}>
          <span>{submitting ? t("auth.register.submitting") : t("auth.register.submit")}</span>
          {!submitting && <SubmitArrow />}
        </button>
      </form>
    </AuthPageFrame>
  );
}
