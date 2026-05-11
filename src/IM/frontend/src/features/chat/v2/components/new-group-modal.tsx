import { useId, useState } from "react";

import { useTranslation } from "../../../../i18n";
import { Avatar } from "./avatar";

interface AgentRow {
  agent_id: string;
  display_name: string;
  description?: string;
}

export interface NewGroupModalProps {
  agents: AgentRow[];
  onClose(): void;
  onCreate(payload: { agentIds: string[]; name: string }): void;
}

export function NewGroupModal({ agents, onClose, onCreate }: NewGroupModalProps) {
  const { t } = useTranslation();
  const titleId = useId();
  const nameInputId = useId();
  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState("");

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function handleCreate() {
    if (selected.length === 0) return;
    const trimmed = name.trim();
    const fallback = agents.filter((a) => selected.includes(a.agent_id)).map((a) => a.display_name).join(", ");
    onCreate({ agentIds: selected, name: trimmed || fallback });
  }

  return (
    <div className="chat-modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="chat-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="chat-modal-header">
          <h2 id={titleId}>{t("chat.newGroup.title")}</h2>
          <p>{t("chat.newGroup.subtitle")}</p>
        </header>
        <div className="chat-modal-body">
          <p className="chat-modal-section-label">{t("chat.newGroup.sectionAgents")}</p>
          <ul className="chat-modal-agents">
            {agents.map((a) => {
              const on = selected.includes(a.agent_id);
              return (
                <li key={a.agent_id}>
                  <label className={`chat-modal-agent${on ? " chat-modal-agent--on" : ""}`}>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(a.agent_id)}
                      aria-label={a.display_name}
                    />
                    <Avatar initials={a.display_name.slice(0, 2)} size={30} />
                    <span className="chat-modal-agent-body">
                      <span className="chat-modal-agent-name">{a.display_name}</span>
                      {a.description && <span className="chat-modal-agent-desc">{a.description}</span>}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          <label htmlFor={nameInputId} className="chat-modal-section-label">
            {t("chat.newGroup.groupName")}
          </label>
          <input
            id={nameInputId}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("chat.newGroup.groupNamePlaceholder")}
            className="chat-modal-name-input"
          />
        </div>
        <footer className="chat-modal-footer">
          <button type="button" className="chat-modal-btn-ghost" onClick={onClose}>
            {t("chat.newGroup.cancel")}
          </button>
          <button
            type="button"
            className="chat-modal-btn-primary"
            disabled={selected.length === 0}
            onClick={handleCreate}
          >
            {t("chat.newGroup.create")}{selected.length > 0 ? ` (${selected.length})` : ""}
          </button>
        </footer>
      </div>
    </div>
  );
}
