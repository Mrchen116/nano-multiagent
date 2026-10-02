import { PropsWithChildren, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { authFetchJson } from "./auth-fetch";
import { AuthUser, useAuthStore } from "./auth-store";
import { useTranslation } from "../../i18n";

/** Verify this tab against the server before mounting any company cache or transport. */
export function RequireAuth({ children }: PropsWithChildren) {
  const { t } = useTranslation();
  const accessToken = useAuthStore(s => s.accessToken);
  const user = useAuthStore(s => s.user);
  const hydrated = useAuthStore(s => s.hydrated);
  const [verified, setVerified] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const location = useLocation();
  const userId = user?.id;
  useEffect(() => { if (!hydrated) useAuthStore.getState().hydrate(); }, [hydrated]);
  useEffect(() => {
    if (!hydrated || !userId) return;
    let disposed = false;
    setFailed(false);
    void authFetchJson<AuthUser>("/im/v1/auth/me").then(snapshot => {
      if (!disposed && useAuthStore.getState().replaceUser(snapshot)) setVerified(userId);
    }).catch(() => { if (!disposed) setFailed(true); });
    return () => { disposed = true; };
  }, [hydrated, userId, attempt]);
  if (!hydrated) return null;
  if (!accessToken || !user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />;
  if (failed) return <div role="alert">{t("auth.feedback.serviceUnavailable")} <button onClick={() => setAttempt(x => x + 1)}>{t("company.refresh")}</button></div>;
  if (verified !== user.id) return null;
  if (user.membership_status !== "active") return <Navigate to="/membership" replace state={{ from: location.pathname + location.search + location.hash }} />;
  return <>{children}</>;
}
