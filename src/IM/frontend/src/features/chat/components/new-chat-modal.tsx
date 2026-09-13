import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "../../../i18n";
import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useAuthStore } from "../../auth/auth-store";
import { listContacts, type Contact } from "../contacts-api";
import { Avatar, colorForAgentSeed } from "./avatar";

export function NewChatModal({ onClose, onSelect }: { onClose(): void; onSelect(contact: Contact): Promise<void> }) {
  const { t } = useTranslation();
  const mobile = useIsMobile();
  const self = useAuthStore(s => s.user?.id);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const query = useQuery({ queryKey: ["contacts", self, q], queryFn: () => listContacts(q), refetchInterval: 3000 });
  async function select(contact: Contact) {
    setBusy(true); setError(false);
    try { await onSelect(contact); } catch { setError(true); } finally { setBusy(false); }
  }
  return <div className={mobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <section className="chat-modal" role="dialog" aria-modal="true" aria-label={t("chat.contacts.title")}>
      <header className="chat-modal-header"><h2>{t("chat.contacts.title")}</h2><button className="chat-modal-btn-ghost" onClick={onClose}>{t("common.cancel")}</button></header>
      <div className="chat-modal-body">
        <input autoFocus type="search" className="chat-sidebar-search" placeholder={t("chat.contacts.search")} value={q} onChange={e => setQ(e.target.value)} />
        {(query.isError || error) && <p role="alert">{t("chat.contacts.failed")}</p>}
        {query.isPending && <p>{t("common.loading")}</p>}
        {query.isSuccess && !query.data.some(c => c.user_id !== self) && <p>{t("chat.contacts.empty")}</p>}
        <ul className="chat-modal-agents">{query.data?.filter(c => c.user_id !== self).map(c => <li key={c.user_id}>
          <button className="chat-modal-agent" disabled={busy} onClick={() => void select(c)}>
            <Avatar initials={c.display_name.slice(0, 2)} color={colorForAgentSeed(c.display_name)} size={34} status={c.status} />
            <span className="chat-modal-agent-body"><strong>{c.display_name}</strong><span className="chat-modal-agent-meta">{c.kind === "human" ? t("chat.contacts.person") : [c.owner_display_name, c.node_name].filter(Boolean).join(" · ")}</span></span>
          </button>
        </li>)}</ul>
      </div>
    </section>
  </div>;
}
