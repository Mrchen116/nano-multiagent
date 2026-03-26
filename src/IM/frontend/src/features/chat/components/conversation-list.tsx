import clsx from "clsx";
import { UIEvent, useLayoutEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { getConversationPreviewSnapshot } from "../im-chat-api";
import { ConversationSummary } from "../types";

type ConversationSectionKey = "agent-network" | "group" | "direct" | "other";

let conversationListScrollTop = 0;

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
  if (item.kind_label?.startsWith("Agent-to-agent")) {
    return "No agent coordination updates yet.";
  }
  return "No messages yet.";
}

function withLatestPreviewSnapshot(item: ConversationSummary): ConversationSummary {
  const snapshot = getConversationPreviewSnapshot(item.conversation_id);
  if (!snapshot) {
    return item;
  }
  return {
    ...item,
    last_message_preview: snapshot.preview,
    last_message_at: snapshot.lastMessageAt ?? item.last_message_at
  };
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

function resolveSectionKey(item: ConversationSummary): ConversationSectionKey {
  if (item.kind === "agent-network") {
    return "agent-network";
  }
  if (item.kind === "group") {
    return "group";
  }
  if (item.kind === "direct-agent" || item.kind === "direct-user") {
    return "direct";
  }
  if (item.kind_label?.toLowerCase().includes("agent-to-agent")) {
    return "agent-network";
  }
  if (item.kind_label === "Group chat") {
    return "group";
  }
  return "other";
}

function toSectionTitle(section: ConversationSectionKey): string {
  if (section === "agent-network") {
    return "Agent-to-agent direct";
  }
  if (section === "group") {
    return "Group chats";
  }
  if (section === "direct") {
    return "Direct chats";
  }
  return "Other";
}

export function ConversationList(props: {
  items: ConversationSummary[];
  activeId?: string;
  compact?: boolean;
  onCreateGroupChat?: () => void;
}) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    if (!scrollContainerRef.current) {
      return;
    }
    scrollContainerRef.current.scrollTop = conversationListScrollTop;
  }, [props.activeId, props.items.length]);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    conversationListScrollTop = event.currentTarget.scrollTop;
  };

  const rememberScrollPosition = () => {
    conversationListScrollTop = scrollContainerRef.current?.scrollTop ?? 0;
  };

  const sectionOrder: ConversationSectionKey[] = ["agent-network", "group", "direct", "other"];
  const sectionItems = new Map<ConversationSectionKey, ConversationSummary[]>(
    sectionOrder.map((section) => [section, [] as ConversationSummary[]])
  );
  for (const item of props.items) {
    const section = resolveSectionKey(item);
    sectionItems.get(section)?.push(item);
  }

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
      <div
        ref={scrollContainerRef}
        data-testid="conversation-list-scroll-container"
        className="flex-1 overflow-y-auto p-2"
        onScroll={handleScroll}
      >
        {props.items.length === 0 ? (
          <div className="flex h-full min-h-[260px] items-center justify-center px-6 py-8 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">No conversations yet</p>
          </div>
        ) : (
          sectionOrder.map((section) => {
            const items = sectionItems.get(section) ?? [];
            if (items.length === 0) {
              return null;
            }
            return (
              <section key={section} className="mb-4">
                <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {toSectionTitle(section)}
                </p>
                {items.map((item) => {
                  const hydratedItem = withLatestPreviewSnapshot(item);
                  return (
                  <Link
                    key={hydratedItem.conversation_id}
                    to={`/chat/${hydratedItem.conversation_id}`}
                    onClick={rememberScrollPosition}
                    className={clsx(
                      "mb-2 block rounded-2xl border px-3 py-3 transition shadow-sm",
                      hydratedItem.conversation_id === props.activeId
                        ? "border-[#9bd2d6] bg-[#eef8f8]"
                        : "border-slate-200 bg-white hover:border-[var(--im-border)] hover:bg-slate-50"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        {hydratedItem.kind_label && (
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{hydratedItem.kind_label}</p>
                        )}
                        <p className="mt-1 font-semibold text-slate-900">{hydratedItem.title}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-xs font-medium text-slate-500">{formatTime(hydratedItem.last_message_at) || "New"}</p>
                        {hydratedItem.unread_count > 0 && (
                          <span className="mt-2 inline-flex rounded-full bg-emerald-700 px-2 py-0.5 text-[11px] font-bold text-white">
                            {hydratedItem.unread_count} new
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm text-slate-600">{formatPreview(hydratedItem)}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="rounded-full bg-slate-100 px-2 py-1">{formatParticipantSummary(hydratedItem.participants)}</span>
                    </div>
                  </Link>
                  );
                })}
              </section>
            );
          })
        )}
      </div>
    </div>
  );
}
