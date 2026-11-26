import { conversationPreview, formatConversationDate } from "./conversation-preview";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { MessageSearchResult } from '../chat-api';

import { useTranslation } from "../../../i18n";
import { classifyConversationKind, type Conversation, type ConversationKind } from "../chat-types";
import type { Contact } from "../contacts-api";
import { Avatar, directAvatarId, GroupAvatar } from "./avatar";
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
type SidebarSearchState = { query: string; filter: FilterKey; pages: number; scrollTop: number; listFilter?: FilterKey };

const FILTER_ORDER: FilterKey[] = ["all", "direct-user", "direct-agent", "group", "agent-network"];
const CONTACT_PREVIEW_LIMIT = 5;
const UNCHATTED_COLLEAGUES_LIMIT = 6;

const FILTER_LABEL: Record<FilterKey, string> = {
  all: "chat.list.filters.all",
  "direct-agent": "chat.list.filters.agent",
  group: "chat.list.filters.group",
  "agent-network": "chat.list.filters.network",
  "direct-user": "chat.list.filters.people"
};

export interface ConversationSidebarProps {
  conversations: Conversation[];
  searchConversations?: Conversation[];
  personalAgentEntry?: ReactNode;
  emptyLabel?: string;
  selfUserId?: string | null;
  activeConversationId: string | null;
  onSelect(conversationId: string): void;
  searchMessages?(query: string, kind: string, cursor?: string, signal?: AbortSignal): Promise<MessageSearchResult>;
  onSelectMessage?(conversationId: string, messageId: string, threadRootMessageId?: string): void;
  initialSearch?: SidebarSearchState;
  onSearchChange?(state: SidebarSearchState): void;
  onDiscover?(): void;
  onNewGroup(): void;
  onNewChat?(): void;
  contacts?: Contact[];
  onStartDirectChat?(contact: Contact): void | Promise<void>;
  onOpenPeopleDirectory?(): void;
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


function formatSearchDate(iso: string): string {
  const date = new Date(iso);
  if (!Number.isNaN(date.getTime()) && date.getFullYear() !== new Date().getFullYear())
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  return formatConversationDate(iso);
}

function highlightMatch(text: string, query: string): ReactNode {
  const index = text.toLowerCase().indexOf(query.trim().toLowerCase());
  if (!query.trim() || index < 0) return text;
  return <>{text.slice(0, index)}<mark>{text.slice(index, index + query.trim().length)}</mark>{text.slice(index + query.trim().length)}</>;
}

export function ConversationSidebar({
  conversations,
  searchConversations = conversations,
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
  contacts,
  onStartDirectChat,
  onOpenPeopleDirectory,
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
  const [searchActive, setSearchActive] = useState(Boolean(initialSearch?.query));
  const [searchResult, setSearchResult] = useState<MessageSearchResult | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [retrySearch, setRetrySearch] = useState(0);
  const searchAbort = useRef<AbortController | null>(null);
  const searchState = useRef<SidebarSearchState>(initialSearch ?? {query:'',filter:'all',pages:1,scrollTop:0});
  const listFilter = useRef<FilterKey>(initialSearch?.listFilter ?? initialSearch?.filter ?? "all");
  const listRef = useRef<HTMLUListElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const restoreScroll = useRef<number | null>(initialSearch?.scrollTop ?? null);
  const [pendingContactId, setPendingContactId] = useState<string | null>(null);
  const [showAllContacts, setShowAllContacts] = useState(false);
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent);
  const shortcutLabel = isMac ? "⌘K" : "Ctrl+K";
  const saveSearch = (update: Partial<SidebarSearchState>) => {
    searchState.current = {...searchState.current, ...update};
    onSearchChange?.(searchState.current);
  };
  const [contextMenu, setContextMenu] = useState<{ conversationId: string; x: number; y: number } | null>(null);

  useEffect(() => {
    setShowAllContacts(false);
  }, [search, filter]);

  useEffect(() => {
    function handleGlobalKeyDown(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k" || event.altKey || event.shiftKey) return;
      if (distillMode || !searchInputRef.current) return;
      if (document.querySelector('[role="dialog"]')) return;
      event.preventDefault();
      if (!searchActive && searchMessages) {
        listFilter.current = filter;
        saveSearch({ listFilter: filter });
        setSearchActive(true);
      }
      searchInputRef.current.focus();
      searchInputRef.current.select();
    }
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [distillMode, filter, searchActive, searchMessages]);

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

  const previews = useMemo(() => new Map(searchConversations.map(c =>
    [c.id, conversationPreview(c, t)]
  )), [searchConversations, t]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (searchActive ? searchConversations : conversations).filter((c) => {
      const kind = classifyConversationKind(c);
      if (filter !== "all" && kind !== filter) return false;
      if (!q) return true;
      const haystack = `${c.title} ${previews.get(c.id) ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [conversations, searchConversations, searchActive, filter, search, previews]);

  const matchedContacts = useMemo(() => {
    const rawQ = search.trim().toLowerCase();
    if (!rawQ || distillMode || !contacts?.length || !onStartDirectChat) return [];
    if (filter !== "all" && filter !== "direct-user" && filter !== "direct-agent") return [];
    const userQ = rawQ.startsWith("@") ? rawQ.slice(1) : rawQ;
    const matchedDirectHumans = new Set<string>();
    const matchedDirectAgents = new Set<string>();
    for (const c of filtered) {
      if (c.type !== "direct" || c.external_source || c.direct_kind === "agent-agent" || c.is_observer) continue;
      for (const p of c.participants) {
        if (p.type === "user") {
          const uid = p.user_id ?? p.id;
          if (uid !== selfUserId) matchedDirectHumans.add(uid);
        } else if (p.type === "agent") {
          matchedDirectAgents.add(p.id);
        }
      }
    }
    return contacts
      .filter((c) => {
        if (c.user_id === selfUserId) return false;
        if (filter === "direct-user" && c.kind !== "human") return false;
        if (filter === "direct-agent" && c.kind !== "agent") return false;
        if (c.kind === "human" && matchedDirectHumans.has(c.user_id)) return false;
        if (c.kind === "agent" && c.agent_id && matchedDirectAgents.has(c.agent_id)) return false;
        const fields = [c.display_name, c.agent_id ?? "", c.owner_display_name ?? ""];
        if (fields.some((val) => val.toLowerCase().includes(rawQ))) return true;
        if (c.username && userQ) {
          const uname = c.username.toLowerCase();
          return uname.includes(rawQ) || uname.includes(userQ);
        }
        return false;
      })
      .sort((a, b) => {
        if (a.kind !== b.kind) return a.kind === "human" ? -1 : 1;
        return a.display_name.localeCompare(b.display_name);
      });
  }, [search, distillMode, contacts, onStartDirectChat, filter, filtered, selfUserId]);

  const unchattedColleagues = useMemo(() => {
    if (searchActive || search.trim() || distillMode || filter !== "direct-user" || !contacts?.length || !onStartDirectChat) {
      return [];
    }
    const existingDirectHumans = new Set<string>();
    for (const c of searchConversations) {
      if (c.type !== "direct" || c.external_source || c.direct_kind === "agent-agent" || c.is_observer) continue;
      for (const p of c.participants) {
        if (p.type === "user") {
          const uid = p.user_id ?? p.id;
          if (uid !== selfUserId) existingDirectHumans.add(uid);
        }
      }
    }
    return contacts
      .filter((c) => c.kind === "human" && c.user_id !== selfUserId && !existingDirectHumans.has(c.user_id))
      .sort((a, b) => a.display_name.localeCompare(b.display_name));
  }, [searchActive, search, distillMode, filter, contacts, onStartDirectChat, searchConversations, selfUserId]);

  const totalColleaguesCount = useMemo(
    () => (contacts ?? []).filter((c) => c.kind === "human" && c.user_id !== selfUserId).length,
    [contacts, selfUserId]
  );

  const openContactChat = (contact: Contact) => {
    if (!onStartDirectChat || pendingContactId) return;
    setPendingContactId(contact.user_id);
    void Promise.resolve(onStartDirectChat(contact)).finally(() => setPendingContactId(null));
  };

  const exitSearch = () => {
    setSearchActive(false);
    setSearch("");
    setShowAllContacts(false);
    setFilter(listFilter.current);
    restoreScroll.current = null;
    saveSearch({query:"", filter:listFilter.current, pages:1, scrollTop:0});
  };

  return (
    <aside className={`chat-sidebar${searchActive ? " chat-sidebar--searching" : ""}`} aria-label={searchActive ? t("chat.list.searchTitle") : t("chat.list.header")} onClick={() => setContextMenu(null)}>
      <header className="chat-sidebar-header">
        <div className="chat-sidebar-header-row" inert={searchActive}>
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
        <div className="chat-search-input-row">
        <button type="button" className="chat-search-back" aria-label={t("chat.list.exitSearch")} aria-hidden={!searchActive} disabled={!searchActive} tabIndex={searchActive ? 0 : -1} onClick={exitSearch}>‹</button>
        <input
          ref={searchInputRef}
          type="search"
          role="searchbox"
          className="chat-sidebar-search"
          placeholder={t("chat.list.search")}
          value={search}
          onFocus={() => { if (!searchActive && searchMessages && !distillMode) { listFilter.current = filter; saveSearch({listFilter:filter}); setSearchActive(true); } }}
          onChange={(e) => { restoreScroll.current = null; setSearch(e.target.value); saveSearch({query:e.target.value,filter,pages:1,scrollTop:0}); }}
          onKeyDown={(e) => {
            if (e.key === "Escape" && searchActive) {
              e.preventDefault();
              exitSearch();
              searchInputRef.current?.blur();
            } else if (e.key === "Enter" && !e.nativeEvent.isComposing && search.trim() && !distillMode && filtered.length === 0 && matchedContacts.length > 0) {
              e.preventDefault();
              openContactChat(matchedContacts[0]!);
            }
          }}
        />
        {!searchActive && !search && !distillMode && <kbd className="chat-search-shortcut" aria-hidden="true">{shortcutLabel}</kbd>}
        {searchActive && search && <button type="button" className="chat-search-clear" aria-label={t("chat.list.clearSearch")} onClick={() => { restoreScroll.current = null; setSearch(""); saveSearch({query:"",filter,pages:1,scrollTop:0}); }}>×</button>}
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
      {!searchActive && personalAgentEntry}
      <div className="chat-sidebar-filters" role="tablist">
        {FILTER_ORDER.map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={filter === key}
            className={`chat-sidebar-filter${filter === key ? " chat-sidebar-filter--active" : ""}`}
            onClick={() => { restoreScroll.current = null; setFilter(key); saveSearch({query:search,filter:key,pages:1,scrollTop:0}); }}
          >
            {t(FILTER_LABEL[key])}
          </button>
        ))}
      </div>
      <ul ref={listRef} className="chat-sidebar-list" onScroll={event => { if (search.trim() && !searchLoading) saveSearch({scrollTop:event.currentTarget.scrollTop}); }}>
        {searchActive && !search.trim() ? <li className="chat-search-hint">{t('chat.list.searchHint')}</li> : null}
        {search.trim() && searchMessages && !distillMode && filtered.length > 0 ? <li className="chat-search-heading">{t('chat.list.conversationResults')}</li> : null}
        {filtered.length === 0 && !searchActive && matchedContacts.length === 0 && unchattedColleagues.length === 0 ? (
          <li className="chat-sidebar-empty">{search.trim() ? t('chat.list.noConversationResults') : emptyLabel ?? t("chat.list.empty")}</li>
        ) : (
          (searchActive && !search.trim() ? [] : filtered).map((c) => {
            const active = c.id === activeConversationId;
            const dateStr = formatConversationDate(c.last_message_at);
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
                      {c.type === "group" ? <GroupAvatar groupId={c.id} size={36} label={t("chat.list.filters.group")} /> : <Avatar id={directAvatarId(c, selfUserId)} size={36} status={agentStatus} />}
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
                    {c.type === "group" ? <GroupAvatar groupId={c.id} size={36} label={t("chat.list.filters.group")} /> : <Avatar id={directAvatarId(c, selfUserId)} size={36} status={agentStatus} />}
                  </span>
                  <span className="chat-sidebar-row-body">
                    <span className="chat-sidebar-row-title-line">
                      <span className="chat-sidebar-row-title">{searchActive ? highlightMatch(c.title, search) : c.title}</span>
                      {dateStr && (
                        <span className="chat-sidebar-row-time">{dateStr}</span>
                      )}
                    </span>
                    <span className="chat-sidebar-row-preview-line">
                      <span className="chat-sidebar-row-preview">{searchActive ? highlightMatch(previews.get(c.id) ?? "", search) : previews.get(c.id) ?? ""}</span>
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
        {matchedContacts.length > 0 && !distillMode ? <>
          <li className="chat-search-heading">{t("chat.list.contactResults")}</li>
          {(showAllContacts ? matchedContacts : matchedContacts.slice(0, CONTACT_PREVIEW_LIMIT)).map((contact) => {
            const subtitle = contact.kind === "human"
              ? (contact.username ? `@${contact.username}` : t("chat.contacts.person"))
              : [contact.owner_display_name, contact.role === "personal" ? t("pa.label") : contact.node_name].filter(Boolean).join(" · ");
            return (
              <li key={`contact:${contact.user_id}`}>
                <button
                  type="button"
                  className="chat-sidebar-row"
                  disabled={pendingContactId === contact.user_id}
                  onClick={() => openContactChat(contact)}
                >
                  <span className="chat-sidebar-row-avatar">
                    <Avatar id={contact.user_id} size={36} status={contact.status} />
                  </span>
                  <span className="chat-sidebar-row-body">
                    <span className="chat-sidebar-row-title-line">
                      <span className="chat-sidebar-row-title">{highlightMatch(contact.display_name, search.replace(/^@/, ""))}</span>
                      <span className="chat-sidebar-row-time">{t("chat.list.startChat")}</span>
                    </span>
                    <span className="chat-sidebar-row-preview-line">
                      <span className="chat-sidebar-row-preview">{highlightMatch(subtitle, search)}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
          {!showAllContacts && matchedContacts.length > CONTACT_PREVIEW_LIMIT ? (
            <li>
              <button type="button" className="chat-search-more" onClick={() => setShowAllContacts(true)}>
                {t("chat.list.showAllContacts", { count: matchedContacts.length })}
              </button>
            </li>
          ) : null}
        </> : null}
        {unchattedColleagues.length > 0 ? <>
          <li className="chat-search-heading">{t("chat.list.teamColleagues")}</li>
          {unchattedColleagues.slice(0, UNCHATTED_COLLEAGUES_LIMIT).map((colleague) => {
            const pa = contacts?.find((c) => c.kind === "agent" && c.role === "personal" && (c.owner_user_id ?? c.owner_id) === colleague.user_id);
            const subtitle = [colleague.username ? `@${colleague.username}` : t("chat.contacts.person"), pa ? t("chat.contacts.hasAssistant", { name: pa.display_name }) : null].filter(Boolean).join(" · ");
            return (
              <li key={`colleague:${colleague.user_id}`}>
                <button
                  type="button"
                  className="chat-sidebar-row"
                  disabled={pendingContactId === colleague.user_id}
                  onClick={() => openContactChat(colleague)}
                >
                  <span className="chat-sidebar-row-avatar">
                    <Avatar id={colleague.user_id} size={36} />
                  </span>
                  <span className="chat-sidebar-row-body">
                    <span className="chat-sidebar-row-title-line">
                      <span className="chat-sidebar-row-title">{colleague.display_name}</span>
                      <span className="chat-sidebar-row-time">{t("chat.list.startChat")}</span>
                    </span>
                    <span className="chat-sidebar-row-preview-line">
                      <span className="chat-sidebar-row-preview">{subtitle}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
          {unchattedColleagues.length > UNCHATTED_COLLEAGUES_LIMIT && onOpenPeopleDirectory ? (
            <li>
              <button type="button" className="chat-search-more" onClick={onOpenPeopleDirectory}>
                {t("chat.list.openPeopleDirectory", { count: totalColleaguesCount })}
              </button>
            </li>
          ) : null}
        </> : null}
        {search.trim() && searchMessages && !distillMode ? <>
          {searchResult && searchResult.messages.length > 0 ? <li className="chat-search-heading">{t('chat.list.messageResults')}</li> : null}
          {searchResult?.messages.map(message => {
            const chat = searchConversations.find(c => c.id === message.conversation_id);
            return <li key={message.message_id}>
            <button type="button" className="chat-sidebar-row chat-search-result" onClick={() => message.thread_root_message_id
              ? onSelectMessage?.(message.conversation_id, message.message_id, message.thread_root_message_id)
              : onSelectMessage?.(message.conversation_id, message.message_id)}>
              <span className="chat-sidebar-row-avatar">{chat?.type === 'group' ? <GroupAvatar groupId={message.conversation_id} size={36} label={t("chat.list.filters.group")} /> : <Avatar id={chat ? directAvatarId(chat, selfUserId) : ""} size={36} />}</span>
              <span className="chat-sidebar-row-body"><span className="chat-sidebar-row-title-line"><span className="chat-sidebar-row-title">{message.conversation_name}</span><span className="chat-sidebar-row-time">{formatSearchDate(message.created_at)}</span></span>
                <span className="chat-search-snippet">{message.sender_name}: {highlightMatch(message.snippet, search)}</span></span>
            </button>
          </li>; })}
          {searchLoading ? <li className="chat-sidebar-empty" role="status">{t('chat.list.searchLoading')}</li> : null}
          {searchError ? <li className="chat-sidebar-empty" role="alert">{t('chat.list.searchError')} <button type="button" onClick={() => searchResult?.next_cursor ? loadMore() : setRetrySearch(n => n + 1)}>{t('chat.list.retrySearch')}</button></li> : null}
          {!searchLoading && !searchError && searchResult && !searchResult.messages.length && filtered.length === 0 && matchedContacts.length === 0 ? <li className="chat-search-empty">{t('chat.list.noSearchResults')}</li> : null}
          {!searchLoading && !searchError && searchResult?.next_cursor ? <li><button type="button" className="chat-search-more" onClick={loadMore}>{t('chat.list.loadMore')}</button></li> : null}
        </> : null}
      </ul>
      {!distillMode && !searchActive && (
        <footer className="chat-sidebar-secondary">
          <button type="button" onClick={() => onEnterDistillMode?.()}>
            {t("chat.list.generateSkill")}
          </button>
        </footer>
      )}
    </aside>
  );
}
