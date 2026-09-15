import { AuthApiError } from "./auth-api";

export type AuthFeedbackCode =
  | "usernameRequired"
  | "usernameTooLong"
  | "displayNameInvalid"
  | "displayNameTooLong"
  | "passwordRequired"
  | "passwordTooShort"
  | "passwordTooLong"
  | "reservedUsername"
  | "usernameTaken"
  | "invalidCredentials"
  | "serviceUnavailable";

export type FieldErrors<Field extends string> = Partial<Record<Field, AuthFeedbackCode>>;

type LoginValues = {
  username: string;
  password: string;
};

type RegistrationValues = LoginValues & {
  displayName: string;
};

export function validateLogin(values: LoginValues): FieldErrors<"username" | "password"> {
  const errors: FieldErrors<"username" | "password"> = {};
  const username = values.username.trim();
  if (!username) errors.username = "usernameRequired";
  else if (username.length > 64) errors.username = "usernameTooLong";
  if (!values.password) errors.password = "passwordRequired";
  else if (values.password.length > 256) errors.password = "passwordTooLong";
  return errors;
}

export function validateRegistration(
  values: RegistrationValues
): FieldErrors<"username" | "displayName" | "password"> {
  const errors: FieldErrors<"username" | "displayName" | "password"> = validateLogin(values);
  const username = values.username.trim();
  if (username === "system" || username.startsWith("agent:") || username.startsWith("shadow:")) {
    errors.username = "reservedUsername";
  }
  if (values.displayName.trim().length > 128) errors.displayName = "displayNameTooLong";
  if (values.password && values.password.length < 8) errors.password = "passwordTooShort";
  return errors;
}

export function registrationFeedbackForApiError(
  error: unknown
): { field: "username" | "displayName" | "password"; code: AuthFeedbackCode } | null {
  if (!(error instanceof AuthApiError)) return null;
  if (error.status === 409) return { field: "username", code: "usernameTaken" };
  if (error.status !== 422) return null;
  if (error.detail === "username must be non-empty") return { field: "username", code: "usernameRequired" };
  if (error.detail === "username uses a reserved runtime identity") {
    return { field: "username", code: "reservedUsername" };
  }
  if (error.detail === "display_name must be non-empty") {
    return { field: "displayName", code: "displayNameInvalid" };
  }
  if (error.detail.startsWith("password must be at least")) {
    return { field: "password", code: "passwordTooShort" };
  }
  return null;
}
