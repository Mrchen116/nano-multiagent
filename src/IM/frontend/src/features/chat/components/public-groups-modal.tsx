import { useEffect, useRef, useState } from "react";
import { useTranslation } from "../../../i18n";
import { useIsMobile } from "../../../hooks/use-is-mobile";
import type { Conversation } from "../chat-types";
import { GroupAvatar } from "./avatar";

export function PublicGroupsModal({ groups = [], pending, error, onRetry, onClose, onSelect }: {
  groups?: Conversation[]; pending: boolean; error: boolean;
  onRetry(): void; onClose(): void; onSelect(group: Conversation): void;
}) {
  const { t } = useTranslation();
  const mobile = useIsMobile();
  const [search, setSearch] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    input.current?.focus();
    const dismiss = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); onClose(); } };
    document.addEventListener("keydown", dismiss);
    return () => { document.removeEventListener("keydown", dismiss); trigger?.focus(); };
  }, [onClose]);
  const filtered = groups.filter(group => group.title.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  return <div className={mobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="chat-modal chat-contacts-modal" role="dialog" aria-modal="true" aria-label={t("tasks.discover")}>
      <header className="chat-modal-header"><h2>{t("tasks.discover")}</h2><button className="chat-modal-btn-ghost" onClick={onClose}>{t("tasks.close")}</button></header>
      <div className="chat-modal-body">
        <input ref={input} type="search" className="chat-sidebar-search" aria-label={t("tasks.searchGroups")} placeholder={t("tasks.searchGroups")} value={search} onChange={event => setSearch(event.target.value)} />
        {pending && <p role="status">{t("common.loading")}</p>}
        {error && <p role="alert">{t("tasks.readFailed")} <button className="chat-modal-btn-ghost" onClick={onRetry}>{t("tasks.refresh")}</button></p>}
        {!pending && !error && filtered.length === 0 && <p>{t("tasks.noGroups")}</p>}
        <ul className="chat-modal-agents">{filtered.map(group => <li key={group.id}>
          <button className="chat-modal-agent" onClick={() => onSelect(group)}>
            <GroupAvatar size={34} label={t("chat.list.filters.group")} />
            <span className="chat-modal-agent-body"><strong className="chat-modal-agent-name">{group.title}</strong><span className="chat-modal-agent-meta">{[group.is_member ? t("tasks.joined") : "", t("chat.groupSettings.memberCount", { count: group.participants.length })].filter(Boolean).join(" · ")}</span></span>
            <span aria-hidden="true">›</span>
          </button>
        </li>)}</ul>
      </div>
    </section>
  </div>;
}
