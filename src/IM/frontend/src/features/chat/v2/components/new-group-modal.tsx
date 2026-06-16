import { useId, useState } from "react";

import { useTranslation } from "../../../../i18n";
import { useIsMobile } from "../../../../hooks/use-is-mobile";
import { Avatar, colorForAgent } from "./avatar";

interface AgentRow {
  agent_id: string;
  display_name: string;
  description?: string;
  status?: "online" | "offline";
}

export interface NewGroupModalProps {
  agents: AgentRow[];
  onClose(): void;
  onCreate(payload: { agentIds: string[]; name: string }): void;
}

export function NewGroupModal({ agents, onClose, onCreate }: NewGroupModalProps) {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
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
    onCreate({ agentIds: selected, name: trimmed || selectedNames });
  }

  const selectedNames = agents
    .filter((a) => selected.includes(a.agent_id))
    .map((a) => a.display_name)
    .join(", ");

  const inner = (
    <>
      <header className="chat-modal-header" style={{ background: "#fff" }}>
        {isMobile && (
          <div className="chat-modal-sheet-handle">
            <div className="chat-modal-sheet-handle-bar" />
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 id={titleId} style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.02em" }}>
              {t("chat.newGroup.title")}
            </h2>
            <p style={{ margin: "3px 0 0", fontSize: 12.5, color: "oklch(0.55 0.01 240)" }}>
              {t("chat.newGroup.subtitle")}
            </p>
          </div>
          {!isMobile && (
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                border: "1px solid oklch(0.87 0.006 240)",
                borderRadius: 8,
                padding: "5px 12px",
                font: "inherit",
                fontSize: 12,
                fontWeight: 600,
                color: "oklch(0.45 0.01 240)",
                cursor: "pointer"
              }}
            >
              ✕
            </button>
          )}
        </div>
      </header>
      <div className="chat-modal-body">
        <p className="chat-modal-section-label">{t("chat.newGroup.sectionAgents")}</p>
        <ul className="chat-modal-agents">
          {agents.map((a) => {
            const on = selected.includes(a.agent_id);
            return (
              <li key={a.agent_id}>
                <label
                  className={`chat-modal-agent${on ? " chat-modal-agent--on" : ""}`}
                  style={{
                    padding: "11px 12px",
                    minHeight: 52,
                    borderRadius: 12,
                    background: on ? "oklch(0.93 0.06 180)" : "oklch(0.97 0.004 240)",
                    border: on ? "1px solid oklch(0.75 0.12 180)" : "1px solid oklch(0.88 0.005 240)"
                  }}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => toggle(a.agent_id)}
                    aria-label={a.display_name}
                    style={{ width: 16, height: 16, accentColor: "oklch(0.52 0.14 180)", flexShrink: 0 }}
                  />
                  <Avatar initials={a.display_name.slice(0, 2)} size={30} status={a.status} color={colorForAgent({ display_name: a.display_name, agent_id: a.agent_id })} />
                  <span className="chat-modal-agent-body">
                    <span className="chat-modal-agent-name">{a.display_name}</span>
                    {a.description && <span className="chat-modal-agent-desc">{a.description}</span>}
                  </span>
                  {a.status && (
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 99,
                        flexShrink: 0,
                        background: a.status === "online" ? "oklch(0.93 0.10 145)" : "oklch(0.93 0.005 240)",
                        color: a.status === "online" ? "oklch(0.35 0.14 145)" : "oklch(0.55 0.01 240)"
                      }}
                    >
                      {t(`chat.status.${a.status}`)}
                    </span>
                  )}
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
          placeholder={selectedNames || t("chat.newGroup.groupNamePlaceholder")}
          className="chat-modal-name-input"
        />
      </div>
      <footer
        className="chat-modal-footer"
        style={{
          background: "#fff",
          paddingBottom: isMobile ? "calc(12px + env(safe-area-inset-bottom, 0px))" : "12px"
        }}
      >
        {!isMobile && (
          <button type="button" className="chat-modal-btn-ghost" onClick={onClose}>
            {t("chat.newGroup.cancel")}
          </button>
        )}
        <button
          type="button"
          className="chat-modal-btn-primary"
          disabled={selected.length === 0}
          onClick={handleCreate}
          style={{ flex: isMobile ? 1 : undefined }}
        >
          {t("chat.newGroup.create")}{selected.length > 0 ? ` (${selected.length})` : ""}
        </button>
      </footer>
    </>
  );

  if (isMobile) {
    return (
      <div
        className="chat-modal-bottom-sheet"
        onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      >
        <div className="chat-modal">
          {inner}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="chat-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        {inner}
      </div>
    </div>
  );
}
