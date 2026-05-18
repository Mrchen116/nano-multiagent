import { useEffect, useState } from "react";

import { useTranslation } from "../../../../i18n";
import type { MentionCandidate } from "../chat-types";
import { Avatar } from "./avatar";

export interface MentionPickerProps {
  candidates: MentionCandidate[];
  query: string;
  onSelect(candidate: MentionCandidate): void;
  onClose(): void;
}

/**
 * Dropdown shown above the composer when the user types `@` in a group chat.
 * Filter is a prefix match (case-insensitive) on display_name — matches the
 * prototype's `name.toLowerCase().startsWith(query.toLowerCase())` behaviour.
 * Keyboard navigation (ArrowUp/ArrowDown/Enter) is supported so the user can
 * select without leaving the keyboard.
 *
 * bugfix-358: handle column (@agent_id) is always shown on every row so the
 * user can verify the wire ID of the candidate they are about to select.
 * Disambiguation under duplicate display_names is then a natural consequence
 * of two distinct agent_ids being visible.
 */
export function MentionPicker({ candidates, query, onSelect, onClose }: MentionPickerProps) {
  const { t } = useTranslation();
  const q = query.toLowerCase();
  const filtered = q
    ? candidates.filter((c) => c.display_name.toLowerCase().startsWith(q))
    : candidates;
  const [highlighted, setHighlighted] = useState(0);

  // Reset highlight when filtered list changes
  useEffect(() => {
    setHighlighted(0);
  }, [filtered.length, q]);

  // Global keydown for arrow navigation and Enter selection
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (filtered.length === 0) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlighted((i) => (i + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlighted((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        onSelect(filtered[highlighted]!);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [filtered, highlighted, onSelect]);

  if (candidates.length === 0) {
    return (
      <div className="chat-mention-picker" aria-label={t("chat.mention.header")}>
        <div className="chat-mention-picker-header">{t("chat.mention.header")}</div>
        <div className="chat-mention-picker-row" style={{ cursor: "default", opacity: 0.6 }}>
          {t("chat.mention.noAgents")}
        </div>
      </div>
    );
  }

  if (filtered.length === 0) {
    return null;
  }

  return (
    <div className="chat-mention-picker" aria-label={t("chat.mention.header")}>
      <div className="chat-mention-picker-header">{t("chat.mention.header")}</div>
      {filtered.map((c, idx) => (
        <button
          key={c.agent_id}
          type="button"
          className="chat-mention-picker-row"
          style={idx === highlighted ? { background: "var(--im-surface-2)" } : undefined}
          onMouseDown={(e) => {
            // mousedown (not click) so the composer doesn't lose focus before we insert.
            e.preventDefault();
            onSelect(c);
          }}
          onMouseEnter={() => setHighlighted(idx)}
        >
          <Avatar initials={c.initials} size={26} />
          <span className="chat-mention-picker-name">{c.display_name}</span>
          <span className="chat-mention-picker-handle">@{c.agent_id.replace(/^agent[_-]/, "")}</span>
        </button>
      ))}
    </div>
  );
}
