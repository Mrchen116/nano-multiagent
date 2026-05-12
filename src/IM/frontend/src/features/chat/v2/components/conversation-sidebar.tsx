import { useMemo, useState } from "react";

import { useTranslation } from "../../../../i18n";
import { classifyConversationKind, type Conversation, type ConversationKind } from "../chat-types";
import { Avatar } from "./avatar";

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
}

export function ConversationSidebar({ conversations, activeConversationId, onSelect, onNewGroup }: ConversationSidebarProps) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");

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
    <aside className="chat-sidebar" aria-label={t("chat.list.header")}>
      <header className="chat-sidebar-header">
        <div className="chat-sidebar-header-row">
          <span className="chat-sidebar-title">{t("chat.list.header")}</span>
          <button type="button" className="chat-sidebar-new-group" onClick={onNewGroup}>
            {t("chat.list.newGroup")}
          </button>
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
      <ul className="chat-sidebar-list">
        {filtered.length === 0 ? (
          <li className="chat-sidebar-empty">{t("chat.list.empty")}</li>
        ) : (
          filtered.map((c) => {
            const active = c.id === activeConversationId;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  className={`chat-sidebar-row${active ? " chat-sidebar-row--active" : ""}`}
                  onClick={() => onSelect(c.id)}
                  aria-current={active ? "true" : undefined}
                >
                  <span data-testid={`conv-avatar-${c.id}`} className="chat-sidebar-row-avatar">
                    <Avatar initials={c.title.slice(0, 2)} />
                  </span>
                  <span className="chat-sidebar-row-body">
                    <span className="chat-sidebar-row-title">{c.title}</span>
                    {c.last_message_preview && (
                      <span className="chat-sidebar-row-preview">{c.last_message_preview}</span>
                    )}
                  </span>
                  <span className="chat-sidebar-row-meta">
                    {c.unread_count > 0 && (
                      <span className="chat-sidebar-row-unread" aria-label={`${c.unread_count} unread`}>
                        {c.unread_count}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            );
          })
        )}
      </ul>
    </aside>
  );
}
