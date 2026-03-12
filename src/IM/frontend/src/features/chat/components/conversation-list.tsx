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
        <p className="mt-1 text-sm text-slate-500">
          Discover direct agent chats, shared group threads, and agent-to-agent coordination from one list.
        </p>
      </div>
      <div className="border-b border-[var(--im-border)] bg-slate-50 px-4 py-3 text-xs text-slate-600">
        <ul className="grid gap-1">
          <li>Direct agent chat: one available agent you can message yourself.</li>
          <li>Agent-to-agent chat: a read-only coordination thread between agents.</li>
          <li>Group chat: a shared thread with multiple people or agents.</li>
        </ul>
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
              <div className="min-w-0">
                {item.kind_label && (
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{item.kind_label}</p>
                )}
                <p className="font-semibold text-slate-900">{item.title}</p>
              </div>
              <p className="text-xs text-slate-500">{formatTime(item.last_message_at)}</p>
            </div>
            {item.target_label && <p className="mt-1 text-xs text-slate-600">Target: {item.target_label}</p>}
            {!props.compact && (
              <p className="mt-1 line-clamp-1 text-xs text-slate-500">{item.last_message_preview}</p>
            )}
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
              <span>{item.participants.slice(0, 3).join(" · ")}</span>
              {item.unread_count > 0 && (
                <span className="rounded-full bg-emerald-700 px-2 py-0.5 font-bold text-white">
                  {item.unread_count}
                </span>
              )}
            </div>
            {item.discoverability_hint && <p className="mt-2 text-[11px] text-slate-500">{item.discoverability_hint}</p>}
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
