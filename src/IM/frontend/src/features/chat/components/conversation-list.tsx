import clsx from "clsx";
import { UIEvent, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { getConversationPreviewSnapshot } from "../im-chat-api";
import { ConversationKind, ConversationSummary } from "../types";

let conversationListScrollTop = 0;

const FILTER_OPTIONS: Array<{ key: "all" | ConversationKind; label: string }> = [
  { key: "all", label: "All" },
  { key: "direct-agent", label: "Agent" },
  { key: "direct-user", label: "People" },
  { key: "group", label: "Groups" },
  { key: "agent-network", label: "Agent ↔ Agent" },
  { key: "system", label: "System" }
];

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

function isPriorityConversation(item: ConversationSummary) {
  return Boolean(item.is_pinned || item.kind_label === "主 Agent 会话" || item.title.startsWith("主 Agent · "));
}

function matchesSearch(item: ConversationSummary, query: string) {
  if (!query) {
    return true;
  }
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }
  return [item.title, item.target_label, item.discoverability_hint, item.kind_label, ...item.participants]
    .filter(Boolean)
    .some((value) => value!.toLowerCase().includes(normalizedQuery));
}

function compareRecency(left: ConversationSummary, right: ConversationSummary) {
  return (right.last_message_at ?? "").localeCompare(left.last_message_at ?? "");
}

function avatarInitialsFromTitle(title: string): string {
  return (title || "?").trim().slice(0, 2).toUpperCase();
}

function avatarBackgroundFor(item: ConversationSummary): string {
  if (item.kind === "group") return "bg-[oklch(0.52_0.14_270)]";
  if (item.kind === "agent-network") return "bg-[oklch(0.52_0.14_30)]";
  return "bg-[oklch(0.52_0.14_180)]";
}

// M19/R11-10: prototype ConvItem 行内 = avatar + 标题/时间 + 预览/未读 badge;不渲染
// kind_label chip。direct-agent 行在 avatar 右下叠 online/offline status dot,数据源是
// summary.node_status(agent 宿主节点状态)。
function ConversationCard(props: {
  item: ConversationSummary;
  activeId?: string;
  onRememberScrollPosition: () => void;
}) {
  const isActive = props.item.conversation_id === props.activeId;
  const isDirectAgent = props.item.kind === "direct-agent" || (!props.item.kind && Boolean(props.item.agent_label));
  const statusDot = isDirectAgent && props.item.node_status
    ? props.item.node_status === "online" ? "online" : "offline"
    : null;
  return (
    <Link
      to={`/chat/${props.item.conversation_id}`}
      onClick={props.onRememberScrollPosition}
      className={clsx(
        "mb-2 flex items-center gap-[11px] rounded-[10px] border px-3 py-3 transition",
        isActive
          ? "border-[oklch(0.40_0.08_180)] bg-[oklch(0.96_0.02_180)]"
          : "border-transparent bg-white hover:border-[var(--im-border)] hover:bg-slate-50"
      )}
    >
      <span className="relative shrink-0">
        <span
          data-testid={`conv-avatar-${props.item.conversation_id}`}
          aria-hidden="true"
          className={clsx(
            "flex h-9 w-9 items-center justify-center rounded-full text-[12px] font-bold text-white",
            avatarBackgroundFor(props.item)
          )}
        >
          {avatarInitialsFromTitle(props.item.title)}
        </span>
        {statusDot ? (
          <span
            data-testid={`conv-status-dot-${props.item.conversation_id}`}
            data-status-dot={statusDot}
            className={clsx(
              "absolute -bottom-0.5 -right-0.5 h-[10px] w-[10px] rounded-full border-2 border-white",
              statusDot === "online" ? "bg-[oklch(0.62_0.18_145)]" : "bg-[oklch(0.70_0.005_240)]"
            )}
          />
        ) : null}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-[13px] font-semibold text-slate-900">{props.item.title}</p>
          <span className="shrink-0 text-[11px] text-slate-500">
            {formatTime(props.item.last_message_at) || "New"}
          </span>
        </div>
        <div className="mt-[2px] flex items-center justify-between gap-2">
          <p className="truncate text-[12px] text-slate-500">{formatPreview(props.item)}</p>
          {props.item.unread_count > 0 && (
            <span className="shrink-0 rounded-full bg-[oklch(0.52_0.14_180)] px-[7px] py-[1px] text-[11px] font-bold text-white">
              {props.item.unread_count}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export function ConversationList(props: {
  items: ConversationSummary[];
  activeId?: string;
  compact?: boolean;
  isLoading?: boolean;
  onCreateGroupChat?: () => void;
}) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | ConversationKind>("all");

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

  const hydratedItems = useMemo(() => props.items.map(withLatestPreviewSnapshot), [props.items]);
  const filteredItems = useMemo(() => {
    const matchingItems = hydratedItems.filter((item) => {
      const matchesKind = activeFilter === "all" || item.kind === activeFilter;
      return matchesKind && matchesSearch(item, searchQuery);
    });
    const priorityItems = matchingItems.filter(isPriorityConversation).sort(compareRecency);
    const recentItems = matchingItems.filter((item) => !isPriorityConversation(item)).sort(compareRecency);
    return { priorityItems, recentItems, totalMatches: matchingItems.length };
  }, [activeFilter, hydratedItems, searchQuery]);

  return (
    <div
      className={clsx(
        "im-card flex h-full flex-col overflow-hidden",
        props.compact ? "min-h-0" : "min-h-[420px]"
      )}
    >
      <div className={clsx("border-b border-[var(--im-border)] px-4 py-4", props.compact && "px-3 py-3")}>
        <div className="flex items-start justify-between gap-4 overflow-hidden">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="im-title text-xl font-bold">Conversations</h1>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                {filteredItems.totalMatches}
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
        <div className="mt-4 space-y-3">
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search conversations"
            className="im-input w-full"
            aria-label="Search conversations"
          />
          <div
            className={clsx(
              "flex gap-2",
              props.compact ? "flex-nowrap overflow-x-auto overscroll-x-contain pb-0.5 [-webkit-overflow-scrolling:touch]" : "flex-wrap"
            )}
          >
            {FILTER_OPTIONS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setActiveFilter(option.key)}
                className={clsx(
                  "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                  activeFilter === option.key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div
        ref={scrollContainerRef}
        data-testid="conversation-list-scroll-container"
        className="min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-y-contain p-2 [-webkit-overflow-scrolling:touch]"
        onScroll={handleScroll}
      >
        {filteredItems.totalMatches === 0 ? (
          <div className="flex h-full min-h-[260px] items-center justify-center px-6 py-8 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              {props.isLoading ? "Loading conversations..." : searchQuery || activeFilter !== "all" ? "No matching conversations" : "No conversations yet"}
            </p>
          </div>
        ) : (
          <>
            {filteredItems.priorityItems.length > 0 && (
              <section className="mb-4">
                <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Priority</p>
                {filteredItems.priorityItems.map((item) => (
                  <ConversationCard
                    key={item.conversation_id}
                    item={item}
                    activeId={props.activeId}
                    onRememberScrollPosition={rememberScrollPosition}
                  />
                ))}
              </section>
            )}
            {filteredItems.recentItems.length > 0 && (
              <section>
                <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Recent</p>
                {filteredItems.recentItems.map((item) => (
                  <ConversationCard
                    key={item.conversation_id}
                    item={item}
                    activeId={props.activeId}
                    onRememberScrollPosition={rememberScrollPosition}
                  />
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
