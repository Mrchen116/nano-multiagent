import { useMemo, useState } from "react";

import { useTranslation } from "../../../../i18n";
import { classifyConversationKind, type Conversation, type ConversationKind } from "../chat-types";
import { Avatar, colorForAgent, colorForAgentSeed } from "./avatar";

interface SidebarAgent {
  agent_id: string;
  display_name?: string;
  status: "online" | "offline";
}

type FilterKey = "all" | ConversationKind;

const FILTER_ORDER: FilterKey[] = ["all", "direct-agent", "group", "agent-network"];

const FILTER_LABEL: Record<FilterKey, string> = {
  all: "chat.list.filters.all",
  "direct-agent": "chat.list.filters.agent",
  group: "chat.list.filters.group",
  "agent-network": "chat.list.filters.network",
  "direct-user": "chat.list.filters.all" // unused but keeps the map total
};

export interface ConversationSidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelect(conversationId: string): void;
  onNewGroup(): void;
  agents?: SidebarAgent[];
  distillMode?: boolean;
  selectedDistillConversationIds?: Set<string>;
  onToggleDistillConversation?(conversationId: string): void;
  onEnterDistillMode?(conversationId?: string): void;
  onCancelDistillMode?(): void;
  onStartDistill?(): void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const isToday = d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
  if (isToday) {
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  }
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.getDate() === yesterday.getDate() && d.getMonth() === yesterday.getMonth() && d.getFullYear() === yesterday.getFullYear()) {
    return "Yesterday";
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNewGroup,
  agents,
  distillMode = false,
  selectedDistillConversationIds = new Set(),
  onToggleDistillConversation,
  onEnterDistillMode,
  onCancelDistillMode,
  onStartDistill
}: ConversationSidebarProps) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");
  const [contextMenu, setContextMenu] = useState<{ conversationId: string; x: number; y: number } | null>(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return conversations.filter((c) => {
      const kind = classifyConversationKind(c);
      if (filter !== "all" && kind !== filter) return false;
      if (!q) return true;
      const haystack = `${c.title} ${c.last_message_preview ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [conversations, filter, search]);

  return (
    <aside className="chat-sidebar" aria-label={t("chat.list.header")} onClick={() => setContextMenu(null)}>
      <header className="chat-sidebar-header">
        <div className="chat-sidebar-header-row">
          <span className="chat-sidebar-title">{t("chat.list.header")}</span>
          <button type="button" className="chat-sidebar-new-group" onClick={onNewGroup}>
            {t("chat.list.newGroup")}
          </button>
        </div>
        <div className="chat-sidebar-distill-actions">
          {distillMode ? (
            <>
              <button type="button" className="chat-sidebar-action" onClick={onCancelDistillMode}>
                {t("chat.list.cancel")}
              </button>
              <button
                type="button"
                className="chat-sidebar-action chat-sidebar-action--primary"
                disabled={selectedDistillConversationIds.size === 0}
                onClick={onStartDistill}
              >
                {t("chat.list.distillToSkill")}
              </button>
            </>
          ) : (
            <button type="button" className="chat-sidebar-action" onClick={() => onEnterDistillMode?.()}>
              {t("chat.list.generateSkill")}
            </button>
          )}
        </div>
        <input
          type="search"
          role="searchbox"
          className="chat-sidebar-search"
          placeholder={t("chat.list.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="chat-sidebar-filters" role="tablist">
          {FILTER_ORDER.map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={filter === key}
              className={`chat-sidebar-filter${filter === key ? " chat-sidebar-filter--active" : ""}`}
              onClick={() => setFilter(key)}
            >
              {t(FILTER_LABEL[key])}
            </button>
          ))}
        </div>
      </header>
      {contextMenu ? (
        <div
          role="menu"
          aria-label="Conversation actions"
          className="chat-sidebar-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            role="menuitem"
            className="chat-sidebar-context-menu-item"
            onClick={() => {
              const { conversationId } = contextMenu;
              setContextMenu(null);
              onEnterDistillMode?.(conversationId);
            }}
          >
            {t("chat.list.distillToSkill")}
          </button>
        </div>
      ) : null}
      <ul className="chat-sidebar-list">
        {filtered.length === 0 ? (
          <li className="chat-sidebar-empty">{t("chat.list.empty")}</li>
        ) : (
          filtered.map((c) => {
            const active = c.id === activeConversationId;
            const dateStr = formatDate(c.last_message_at);
            const kind = classifyConversationKind(c);
            const distillUnavailableReason =
              c.run_state === "running"
                ? t("chat.list.running")
                : !c.source_agent_id || !c.source_jsonl_path
                  ? t("chat.list.noTranscript")
                  : null;
            const distillDisabled = distillUnavailableReason !== null;
            const distillSelected = selectedDistillConversationIds.has(c.id);
            const agentParticipant = c.participants.find((p) => p.type === "agent");
            const agentRow = agentParticipant
              ? agents?.find((a) => a.agent_id === agentParticipant.id)
              : null;
            const agentStatus = kind === "direct-agent" && agentParticipant
              ? (agentRow?.status ?? null)
              : null;
            const avatarColor =
              kind === "direct-agent" && agentRow
                ? colorForAgent(agentRow)
                : kind === "group"
                  ? "oklch(0.52 0.14 270)"
                  : kind === "agent-network" || kind === "direct-user"
                    ? "oklch(0.52 0.14 30)"
                    : colorForAgentSeed(c.title);
            return (
              <li key={c.id}>
                {distillMode ? (
                  <label
                    className={`chat-sidebar-row chat-sidebar-row--selectable${active ? " chat-sidebar-row--active" : ""}${distillDisabled ? " chat-sidebar-row--disabled" : ""}`}
                    aria-disabled={distillDisabled ? "true" : undefined}
                  >
                    <input
                      type="checkbox"
                      className="chat-sidebar-check"
                      checked={distillSelected}
                      disabled={distillDisabled}
                      onChange={() => onToggleDistillConversation?.(c.id)}
                    />
                    <span data-testid={`conv-avatar-${c.id}`} className="chat-sidebar-row-avatar">
                      <Avatar initials={c.title.slice(0, 2)} color={avatarColor} size={36} status={agentStatus} />
                    </span>
                    <span className="chat-sidebar-row-body">
                      <span className="chat-sidebar-row-title-line">
                        <span className="chat-sidebar-row-title">{c.title}</span>
                        {distillUnavailableReason ? (
                          <span className="chat-sidebar-run-state">{distillUnavailableReason}</span>
                        ) : dateStr ? (
                          <span className="chat-sidebar-row-time">{dateStr}</span>
                        ) : null}
                      </span>
                      <span className="chat-sidebar-row-preview-line">
                        <span className="chat-sidebar-row-preview">{c.last_message_preview ?? ""}</span>
                        {c.unread_count > 0 && (
                          <span className="chat-sidebar-row-unread" aria-label={`${c.unread_count} unread`}>
                            {c.unread_count}
                          </span>
                        )}
                      </span>
                    </span>
                  </label>
                ) : (
                  <button
                    type="button"
                    className={`chat-sidebar-row${active ? " chat-sidebar-row--active" : ""}`}
                    onClick={() => onSelect(c.id)}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setContextMenu({ conversationId: c.id, x: event.clientX, y: event.clientY });
                    }}
                    aria-current={active ? "true" : undefined}
                  >
                  <span data-testid={`conv-avatar-${c.id}`} className="chat-sidebar-row-avatar">
                    <Avatar initials={c.title.slice(0, 2)} color={avatarColor} size={36} status={agentStatus} />
                  </span>
                  <span className="chat-sidebar-row-body">
                    <span className="chat-sidebar-row-title-line">
                      <span className="chat-sidebar-row-title">{c.title}</span>
                      {dateStr && (
                        <span className="chat-sidebar-row-time">{dateStr}</span>
                      )}
                    </span>
                    <span className="chat-sidebar-row-preview-line">
                      <span className="chat-sidebar-row-preview">{c.last_message_preview ?? ""}</span>
                      {c.unread_count > 0 && (
                        <span className="chat-sidebar-row-unread" aria-label={`${c.unread_count} unread`}>
                          {c.unread_count}
                        </span>
                      )}
                    </span>
                  </span>
                  </button>
                )}
              </li>
            );
          })
        )}
      </ul>
    </aside>
  );
}
