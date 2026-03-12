import clsx from "clsx";
import { Link } from "react-router-dom";

import { ConversationSummary } from "../types";

function formatTime(input?: string) {
  if (!input) {
    return "";
  }
  const d = new Date(input);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function ConversationList(props: {
  items: ConversationSummary[];
  activeId?: string;
  compact?: boolean;
}) {
  return (
    <div className="im-card flex h-full min-h-[420px] flex-col overflow-hidden">
      <div className="border-b border-[var(--im-border)] px-4 py-3">
        <h1 className="im-title text-xl font-bold">Conversations</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {props.items.map((item) => (
          <Link
            key={item.conversation_id}
            to={`/chat/${item.conversation_id}`}
            className={clsx(
              "mb-2 block rounded-xl border border-transparent px-3 py-2 transition",
              item.conversation_id === props.activeId
                ? "bg-[#dceef0] border-[#9bd2d6]"
                : "bg-white hover:border-[var(--im-border)]"
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold text-slate-900">{item.title}</p>
              <p className="text-xs text-slate-500">{formatTime(item.last_message_at)}</p>
            </div>
            {!props.compact && (
              <p className="mt-1 line-clamp-1 text-xs text-slate-500">{item.last_message_preview}</p>
            )}
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
              <span>{item.participants.slice(0, 2).join(" · ")}</span>
              {item.unread_count > 0 && (
                <span className="rounded-full bg-emerald-700 px-2 py-0.5 font-bold text-white">
                  {item.unread_count}
                </span>
              )}
            </div>
            {(item.ownership_label || item.agent_label) && (
              <p className="mt-1 line-clamp-1 text-[11px] text-slate-500">
                {item.ownership_label ?? item.agent_label}
              </p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
