import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "../../i18n";
import { subscribeUserStream, type UserStreamConnectionStatus } from "./index";

/** Display transport-owned recovery timing without managing another connection. */
export function UserStreamConnectionNotice() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<UserStreamConnectionStatus>(null);
  const [now, setNow] = useState(Date.now);
  useEffect(() => subscribeUserStream({ onEvent: () => undefined, onConnectionStatus: setStatus }), []);
  useEffect(() => {
    if (!status) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [status]);
  if (!status) return null;
  const seconds = Math.max(0, Math.ceil((status.retryAt - now) / 1000));
  return <div className="im-stream-notice" role="status">
    <span>{t(seconds > 0 ? `realtime.${status.kind}` : "realtime.retrying", { seconds })}</span>
    <Link to="/login" state={{ signOut: true }}>{t("realtime.signInAgain")}</Link>
  </div>;
}
