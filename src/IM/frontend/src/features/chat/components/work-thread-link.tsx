import { createContext, useContext, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "../../../i18n";

export const WorkNavigationContext = createContext<{ returnUrl: string; names?: Record<string, string>; people?: Record<string, string>; beforeLeave(): void } | null>(null);

/** A real Chat route; source IDs are supplied by persisted business records. */
export function WorkThreadLink({ conversationId, messageId, children }: { conversationId?: string | null; messageId?: string | null; children: ReactNode }) {
  const work = useContext(WorkNavigationContext);
  const { t } = useTranslation();
  if (!conversationId || conversationId.startsWith("local:")) return <span>{children} · {t("agents.work.暂不可定位")}</span>;
  return <Link className="im-work-source" to={`/chat/${encodeURIComponent(conversationId)}${messageId ? `?message_id=${encodeURIComponent(messageId)}` : ""}`}
    state={work ? { workReturnUrl: work.returnUrl } : undefined} onClick={() => work?.beforeLeave()}>{typeof children === "string" && children === conversationId ? work?.names?.[conversationId] || children : children}</Link>;
}
