import { createContext, useContext, type ReactNode } from "react";
import { Link } from "react-router-dom";

export const WorkNavigationContext = createContext<{ returnUrl: string; beforeLeave(): void } | null>(null);

/** A real Chat route; source IDs are supplied by persisted business records. */
export function WorkThreadLink({ conversationId, messageId, children }: { conversationId?: string | null; messageId?: string | null; children: ReactNode }) {
  const work = useContext(WorkNavigationContext);
  if (!conversationId || conversationId.startsWith("local:")) return <span>{children} · 暂不可定位</span>;
  return <Link className="im-work-source" to={`/chat/${encodeURIComponent(conversationId)}${messageId ? `?message_id=${encodeURIComponent(messageId)}` : ""}`}
    state={work ? { workReturnUrl: work.returnUrl } : undefined} onClick={() => work?.beforeLeave()}>{children}</Link>;
}
