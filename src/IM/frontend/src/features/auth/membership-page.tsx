import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "../../i18n";
import { AuthAlert, AuthPageFrame } from "./auth-page-frame";
import { authFetchJson } from "./auth-fetch";
import { AuthUser, useAuthStore } from "./auth-store";

export function safeReturnPath(value: unknown): string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") && !/^\/(login|register|membership)([/?#]|$)/.test(value) ? value : "/chat";
}

export function MembershipPage() {
  const { t } = useTranslation();
  const user = useAuthStore(s => s.user);
  const hydrated = useAuthStore(s => s.hydrated);
  useEffect(() => { if (!hydrated) useAuthStore.getState().hydrate(); }, [hydrated]);
  const location = useLocation();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  if (!hydrated) return null;
  if (!user) return <Navigate to="/login" replace />;
  const from = safeReturnPath((location.state as { from?: string } | null)?.from);
  const suspended = user.membership_status === "suspended";
  async function refresh() {
    setBusy(true); setError(false);
    try {
      const snapshot = await authFetchJson<AuthUser>("/im/v1/auth/me");
      useAuthStore.getState().replaceUser(snapshot);
      if (snapshot.membership_status === "active") navigate(from, { replace: true });
    } catch { setError(true); } finally { setBusy(false); }
  }
  return <AuthPageFrame kicker={t("company.title")} title={t(suspended ? "company.suspended" : "company.pending")} subtitle={t(suspended ? "company.suspendedHint" : "company.pendingHint")} footer={<button className="im-auth-link" onClick={() => navigate("/login", { replace: true, state: { signOut: true } })}>{t("shell.userMenu.signOut")}</button>}>
    <p>{user.display_name || user.username}</p>
    {error && <AuthAlert>{t("auth.feedback.serviceUnavailable")}</AuthAlert>}
    <button className="im-auth-submit" disabled={busy} onClick={() => void refresh()}>{t("company.refresh")}</button>
  </AuthPageFrame>;
}
