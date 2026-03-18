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

function formatPreview(item: ConversationSummary) {
  const preview = item.last_message_preview?.trim();
  if (preview) {
    return preview;
  }
  if (item.kind_label === "Group chat") {
    return "No messages yet in this shared thread.";
  }
  if (item.kind_label === "Agent-to-agent chat") {
    return "No coordination updates yet.";
  }
  return "No messages yet.";
}

function formatParticipantSummary(participants: string[]) {
  if (participants.length === 0) {
    return "No participants listed";
  }
  if (participants.length <= 3) {
    return participants.join(" · ");
  }
  return `${participants.slice(0, 3).join(" · ")} +${participants.length - 3}`;
}

export function ConversationList(props: {
  items: ConversationSummary[];
  activeId?: string;
  compact?: boolean;
  onCreateGroupChat?: () => void;
}) {
  return (
    <div className="im-card flex h-full min-h-[420px] flex-col overflow-hidden">
      <div className="border-b border-[var(--im-border)] px-4 py-4">
        <div className="flex items-start justify-between gap-4 overflow-hidden">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="im-title text-xl font-bold">Conversations</h1>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                {props.items.length}
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            {props.onCreateGroupChat && (
              <button type="button" className="im-btn im-btn-muted" onClick={props.onCreateGroupChat}>
                Create group chat
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {props.items.length === 0 ? (
          <div className="flex h-full min-h-[260px] items-center justify-center px-6 py-8 text-center">
            <div className="max-w-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">No conversations yet</p>
              <h2 className="im-title mt-2 text-lg font-bold text-slate-900">Open an agent chat or create a shared thread</h2>
              <p className="mt-2 text-sm text-slate-500">
                Agent chats launched from Settings reopen each agent's stable direct thread here, and new group threads appear with participant context, latest activity, and unread updates.
              </p>
            </div>
          </div>
        ) : (
          props.items.map((item) => (
            <Link
              key={item.conversation_id}
              to={`/chat/${item.conversation_id}`}
              className={clsx(
                "mb-2 block rounded-2xl border px-3 py-3 transition shadow-sm",
                item.conversation_id === props.activeId
                  ? "border-[#9bd2d6] bg-[#eef8f8]"
                  : "border-slate-200 bg-white hover:border-[var(--im-border)] hover:bg-slate-50"
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  {item.kind_label && (
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{item.kind_label}</p>
                  )}
                  <p className="mt-1 font-semibold text-slate-900">{item.title}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-xs font-medium text-slate-500">{formatTime(item.last_message_at) || "New"}</p>
                  {item.unread_count > 0 && (
                    <span className="mt-2 inline-flex rounded-full bg-emerald-700 px-2 py-0.5 text-[11px] font-bold text-white">
                      {item.unread_count} new
                    </span>
                  )}
                </div>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-slate-600">{formatPreview(item)}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="rounded-full bg-slate-100 px-2 py-1">{formatParticipantSummary(item.participants)}</span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
