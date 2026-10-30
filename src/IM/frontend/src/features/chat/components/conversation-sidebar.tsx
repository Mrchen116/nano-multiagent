import { mentionNameMap, mentionPlainText } from "./mention-parser";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { MessageSearchResult } from '../chat-api';

import { useTranslation } from "../../../i18n";
import { formatSystemNotice } from "../system-notice";
import { classifyConversationKind, type Conversation, type ConversationKind } from "../chat-types";
import { Avatar, GroupAvatar, colorForAgent, colorForAgentSeed, directPersonAvatarName } from "./avatar";
import { NewConversationMenu } from "./new-conversation-menu";
import {
  getDistillConversationUnavailableKey,
  isDistillConversationEligible,
} from "./distill-selection";

interface SidebarAgent {
  agent_id: string;
  display_name?: string;
  status: "online" | "offline";
}

type FilterKey = "all" | ConversationKind;
type SidebarSearchState = { query: string; filter: FilterKey; pages: number; scrollTop: number };

const FILTER_ORDER: FilterKey[] = ["all", "direct-user", "direct-agent", "group", "agent-network"];

const FILTER_LABEL: Record<FilterKey, string> = {
  all: "chat.list.filters.all",
  "direct-agent": "chat.list.filters.agent",
  group: "chat.list.filters.group",
  "agent-network": "chat.list.filters.network",
  "direct-user": "chat.list.filters.people"
};

export interface ConversationSidebarProps {
  conversations: Conversation[];
  personalAgentEntry?: ReactNode;
  emptyLabel?: string;
  selfUserId?: string | null;
  activeConversationId: string | null;
  onSelect(conversationId: string): void;
  searchMessages?(query: string, kind: string, cursor?: string, signal?: AbortSignal): Promise<MessageSearchResult>;
  onSelectMessage?(conversationId: string, messageId: string): void;
  initialSearch?: SidebarSearchState;
  onSearchChange?(state: SidebarSearchState): void;
  onDiscover?(): void;
  onNewGroup(): void;
  onNewChat?(): void;
  agents?: SidebarAgent[];
  distillMode?: boolean;
  selectedDistillConversationIds?: Set<string>;
  selectedDistillSourceNodeId?: string | null;
  selectedDistillEligibleCount?: number;
  distillNotice?: string | null;
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

function formatSearchDate(iso: string): string {
  const date = new Date(iso);
  if (!Number.isNaN(date.getTime()) && date.getFullYear() !== new Date().getFullYear())
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  return formatDate(iso);
}

export function ConversationSidebar({
  conversations,
  personalAgentEntry,
  emptyLabel,
  selfUserId = null,
  activeConversationId,
  onSelect,
  searchMessages,
  onSelectMessage,
  initialSearch,
  onSearchChange,
  onDiscover,
  onNewGroup,
  onNewChat,
  agents,
  distillMode = false,
  selectedDistillConversationIds = new Set(),
  selectedDistillSourceNodeId = null,
  selectedDistillEligibleCount = 0,
  distillNotice = null,
  onToggleDistillConversation,
  onEnterDistillMode,
  onCancelDistillMode,
  onStartDistill
}: ConversationSidebarProps) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<FilterKey>(initialSearch?.filter ?? "all");
  const [search, setSearch] = useState(initialSearch?.query ?? "");
  const [searchResult, setSearchResult] = useState<MessageSearchResult | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [retrySearch, setRetrySearch] = useState(0);
  const searchAbort = useRef<AbortController | null>(null);
  const searchState = useRef<SidebarSearchState>(initialSearch ?? {query:'',filter:'all',pages:1,scrollTop:0});
  const listRef = useRef<HTMLUListElement>(null);
  const restoreScroll = useRef<number | null>(initialSearch?.scrollTop ?? null);
  const saveSearch = (update: Partial<SidebarSearchState>) => {
    searchState.current = {...searchState.current, ...update};
    onSearchChange?.(searchState.current);
  };
  const [contextMenu, setContextMenu] = useState<{ conversationId: string; x: number; y: number } | null>(null);

  useEffect(() => {
    const q = search.trim();
    if (!q || !searchMessages || distillMode) { setSearchResult(null); setSearchError(false); setSearchLoading(false); return; }
    const controller = new AbortController(); searchAbort.current = controller;
    setSearchResult(null); setSearchError(false); setSearchLoading(true);
    const pages = searchState.current.pages;
    const timer = setTimeout(() => {
      void (async () => {
        let result = await searchMessages(q, filter, undefined, controller.signal);
        const messages = [...result.messages];
        for (let page = 1; page < pages && result.next_cursor && !controller.signal.aborted; page++) {
          result = await searchMessages(q, filter, result.next_cursor, controller.signal);
          messages.push(...result.messages);
        }
        return {...result, messages};
      })().then(result => {
        if (!controller.signal.aborted) setSearchResult(result);
      }).catch(() => { if (!controller.signal.aborted) setSearchError(true); })
        .finally(() => { if (!controller.signal.aborted) setSearchLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search, filter, searchMessages, distillMode, retrySearch]);

  useEffect(() => {
    if (searchResult && restoreScroll.current !== null && listRef.current) {
      listRef.current.scrollTop = restoreScroll.current;
      restoreScroll.current = null;
    }
  }, [searchResult]);

  const loadMore = () => {
    if (!searchMessages || !searchResult?.next_cursor || searchLoading) return;
    const signal = searchAbort.current?.signal;
    setSearchLoading(true); setSearchError(false);
    void searchMessages(search.trim(), filter, searchResult.next_cursor, signal).then(result => {
      if (!signal?.aborted) {
        setSearchResult(previous => ({ ...result, messages: [...(previous?.messages ?? []), ...result.messages] }));
        saveSearch({pages:searchState.current.pages+1});
      }
    }).catch(() => { if (!signal?.aborted) setSearchError(true); })
      .finally(() => { if (!signal?.aborted) setSearchLoading(false); });
  };

  const previews = useMemo(() => new Map(conversations.map((c) => [
    c.id, formatSystemNotice(t, c.last_message_system_notice, c.type === "direct")
      ?? mentionPlainText(c.last_message_preview ?? "", mentionNameMap(c.participants))
  ])), [conversations, t]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return conversations.filter((c) => {
      const kind = classifyConversationKind(c);
      if (filter !== "all" && kind !== filter) return false;
      if (!q) return true;
      const haystack = `${c.title} ${previews.get(c.id) ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [conversations, filter, search, previews]);

  return (
    <aside className="chat-sidebar" aria-label={t("chat.list.header")} onClick={() => setContextMenu(null)}>
      <header className="chat-sidebar-header">
        <div className="chat-sidebar-header-row">
          <span className="chat-sidebar-title">{t("chat.list.header")}</span>
          <NewConversationMenu onNewChat={onNewChat} onNewGroup={onNewGroup} onDiscover={onDiscover} />
        </div>
        {distillMode && (
          <div className="chat-sidebar-distill-actions">
            <button type="button" className="chat-sidebar-action" onClick={onCancelDistillMode}>
              {t("chat.list.cancel")}
            </button>
            <button
              type="button"
              className="chat-sidebar-action chat-sidebar-action--primary"
              disabled={selectedDistillEligibleCount === 0}
              onClick={onStartDistill}
            >
              {t("chat.list.distillToSkill")}
            </button>
          </div>
        )}
        {distillMode && distillNotice ? (
          <p className="chat-distill-error" role="alert">
            {distillNotice}
          </p>
        ) : null}
        <input
          type="search"
          role="searchbox"
          className="chat-sidebar-search"
          placeholder={t("chat.list.search")}
          value={search}
          onChange={(e) => { setSearch(e.target.value); saveSearch({query:e.target.value,filter,pages:1,scrollTop:0}); }}
        />
        <div className="chat-sidebar-filters" role="tablist">
          {FILTER_ORDER.map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={filter === key}
              className={`chat-sidebar-filter${filter === key ? " chat-sidebar-filter--active" : ""}`}
              onClick={() => { setFilter(key); saveSearch({query:search,filter:key,pages:1,scrollTop:0}); }}
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
      {personalAgentEntry}
      <ul ref={listRef} className="chat-sidebar-list" onScroll={event => { if (search.trim() && !searchLoading) saveSearch({scrollTop:event.currentTarget.scrollTop}); }}>
        {search.trim() && searchMessages && !distillMode ? <li className="chat-search-heading">{t('chat.list.conversationResults')}</li> : null}
        {filtered.length === 0 ? (
          <li className="chat-sidebar-empty">{search.trim() ? t('chat.list.noConversationResults') : emptyLabel ?? t("chat.list.empty")}</li>
        ) : (
          filtered.map((c) => {
            const active = c.id === activeConversationId;
            const dateStr = formatDate(c.last_message_at);
            const kind = classifyConversationKind(c);
            const distillUnavailableKey = getDistillConversationUnavailableKey(c);
            const crossGateway = Boolean(
              selectedDistillSourceNodeId
              && c.source_node_id
              && c.source_node_id !== selectedDistillSourceNodeId
            );
            const distillUnavailableReason = crossGateway
              ? t("chat.list.differentGateway")
              : distillUnavailableKey
              ? t(`chat.list.${distillUnavailableKey}`)
              : null;
            const distillDisabled = distillUnavailableReason !== null;
            const distillSelected = isDistillConversationEligible(c)
              && selectedDistillConversationIds.has(c.id);
            const agentParticipant = c.participants.find((p) => p.type === "agent");
            const agentRow = agentParticipant
              ? agents?.find((a) => a.agent_id === agentParticipant.id)
              : null;
            const agentStatus = kind === "direct-agent" && agentParticipant
              ? (agentRow?.status ?? null)
              : null;
            const avatarName = kind === "direct-user" ? directPersonAvatarName(c, selfUserId) : c.title;
            const avatarColor =
              kind === "direct-agent" && agentRow
                ? colorForAgent(agentRow)
                : colorForAgentSeed(avatarName);
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
                      {c.type === "group" ? <GroupAvatar size={36} label={t("chat.list.filters.group")} /> : <Avatar initials={avatarName.slice(0, 2)} color={avatarColor} size={36} status={agentStatus} />}
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
                        <span className="chat-sidebar-row-preview">{previews.get(c.id) ?? ""}</span>
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
                    {c.type === "group" ? <GroupAvatar size={36} label={t("chat.list.filters.group")} /> : <Avatar initials={avatarName.slice(0, 2)} color={avatarColor} size={36} status={agentStatus} />}
                  </span>
                  <span className="chat-sidebar-row-body">
                    <span className="chat-sidebar-row-title-line">
                      <span className="chat-sidebar-row-title">{c.title}</span>
                      {dateStr && (
                        <span className="chat-sidebar-row-time">{dateStr}</span>
                      )}
                    </span>
                    <span className="chat-sidebar-row-preview-line">
                      <span className="chat-sidebar-row-preview">{previews.get(c.id) ?? ""}</span>
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
        {search.trim() && searchMessages && !distillMode ? <>
          <li className="chat-search-heading">{t('chat.list.messageResults')}</li>
          {searchResult?.messages.map(message => <li key={message.message_id}>
            <button type="button" className="chat-sidebar-row chat-search-result" onClick={() => onSelectMessage?.(message.conversation_id, message.message_id)}>
              <span className="chat-sidebar-row-body"><span className="chat-sidebar-row-title-line"><span className="chat-sidebar-row-title">{message.conversation_name}</span><span className="chat-sidebar-row-time">{formatSearchDate(message.created_at)}</span></span>
                <span className="chat-search-snippet">{message.sender_name}: {message.snippet}</span></span>
            </button>
          </li>)}
          {searchLoading ? <li className="chat-sidebar-empty" role="status">{t('chat.list.searchLoading')}</li> : null}
          {searchError ? <li className="chat-sidebar-empty" role="alert">{t('chat.list.searchError')} <button type="button" onClick={() => searchResult?.next_cursor ? loadMore() : setRetrySearch(n => n + 1)}>{t('chat.list.retrySearch')}</button></li> : null}
          {!searchLoading && !searchError && searchResult && !searchResult.messages.length ? <li className="chat-sidebar-empty">{t('chat.list.noMessageResults')}</li> : null}
          {!searchLoading && !searchError && searchResult?.next_cursor ? <li><button type="button" className="chat-search-more" onClick={loadMore}>{t('chat.list.loadMore')}</button></li> : null}
        </> : null}
      </ul>
      {!distillMode && (
        <footer className="chat-sidebar-secondary">
          <button type="button" onClick={() => onEnterDistillMode?.()}>
            {t("chat.list.generateSkill")}
          </button>
        </footer>
      )}
    </aside>
  );
}
