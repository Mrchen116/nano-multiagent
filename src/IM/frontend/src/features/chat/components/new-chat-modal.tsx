import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "../../../i18n";
import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useAuthStore } from "../../auth/auth-store";
import { listContacts, type Contact } from "../contacts-api";
import { Avatar } from "./avatar";

type ContactFilter = "all" | "human" | "agent";

export function NewChatModal({ onClose, onSelect }: { onClose(): void; onSelect(contact: Contact): Promise<void> }) {
  const { t } = useTranslation();
  const mobile = useIsMobile();
  const self = useAuthStore(s => s.user?.id);
  const [q, setQ] = useState("");
  const [kindFilter, setKindFilter] = useState<ContactFilter>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const query = useQuery({ queryKey: ["contacts", self, q], queryFn: () => listContacts(q), refetchInterval: 3000 });

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const { people, agents, publicPaByOwner } = useMemo(() => {
    const items = (query.data ?? []).filter(c => c.user_id !== self);
    const paMap = new Map<string, Contact>();
    for (const item of query.data ?? []) {
      if (item.kind === "agent" && item.role === "personal") {
        const ownerKey = item.owner_user_id ?? item.owner_id;
        if (ownerKey) paMap.set(ownerKey, item);
      }
    }
    const visibleItems = kindFilter === "all" ? items : items.filter(c => c.kind === kindFilter);
    return {
      people: visibleItems.filter(c => c.kind === "human"),
      agents: visibleItems.filter(c => c.kind === "agent"),
      publicPaByOwner: paMap
    };
  }, [query.data, self, kindFilter]);

  async function select(contact: Contact) {
    setBusy(true); setError(false);
    try { await onSelect(contact); } catch { setError(true); } finally { setBusy(false); }
  }

  function renderContactRow(c: Contact) {
    const pa = c.kind === "human" ? publicPaByOwner.get(c.user_id) : undefined;
    const meta = c.kind === "human"
      ? [c.username ? `@${c.username}` : t("chat.contacts.person"), pa ? t("chat.contacts.hasAssistant", { name: pa.display_name }) : null].filter(Boolean).join(" · ")
      : [c.owner_display_name, c.role === "personal" ? t("pa.label") : c.node_name].filter(Boolean).join(" · ");
    return (
      <li key={c.user_id}>
        <button type="button" className="chat-modal-agent" disabled={busy} onClick={() => void select(c)}>
          <Avatar id={c.user_id} size={34} status={c.status} />
          <span className="chat-modal-agent-body">
            <strong className="chat-modal-agent-name">{c.display_name}</strong>
            <span className="chat-modal-agent-meta">{meta}</span>
          </span>
        </button>
      </li>
    );
  }

  const hasVisibleResults = people.length > 0 || agents.length > 0;

  return <div className={mobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <section className="chat-modal chat-contacts-modal" role="dialog" aria-modal="true" aria-label={t("chat.contacts.title")}>
      <header className="chat-modal-header"><h2>{t("chat.contacts.title")}</h2><button type="button" className="chat-modal-btn-ghost" onClick={onClose}>{t("common.cancel")}</button></header>
      <div className="chat-modal-body">
        <input autoFocus type="search" className="chat-sidebar-search" placeholder={t("chat.contacts.search")} value={q} onChange={e => setQ(e.target.value)} />
        <div className="chat-contacts-filters" role="tablist" aria-label={t("chat.contacts.title")}>
          {(["all", "human", "agent"] as const).map(key => {
            const label = key === "all" ? t("chat.contacts.filterAll") : key === "human" ? t("chat.contacts.filterPeople") : t("chat.contacts.filterAgents");
            return (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={kindFilter === key}
                className={`chat-sidebar-filter${kindFilter === key ? " chat-sidebar-filter--active" : ""}`}
                onClick={() => setKindFilter(key)}
              >
                {label}
              </button>
            );
          })}
        </div>
        {(query.isError || error) && <p role="alert">{t("chat.contacts.failed")}</p>}
        {query.isPending && <p>{t("common.loading")}</p>}
        {query.isSuccess && !hasVisibleResults && <p>{t("chat.contacts.empty")}</p>}
        {people.length > 0 && (
          <div className="chat-modal-section">
            {kindFilter === "all" && <p className="chat-modal-section-label">{t("chat.contacts.sectionPeople")}</p>}
            <ul className="chat-modal-agents">{people.map(renderContactRow)}</ul>
          </div>
        )}
        {agents.length > 0 && (
          <div className="chat-modal-section">
            {kindFilter === "all" && people.length > 0 && <p className="chat-modal-section-label">{t("chat.contacts.sectionAgents")}</p>}
            <ul className="chat-modal-agents">{agents.map(renderContactRow)}</ul>
          </div>
        )}
      </div>
    </section>
  </div>;
}
