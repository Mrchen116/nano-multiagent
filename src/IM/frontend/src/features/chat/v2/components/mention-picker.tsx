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
 * If nothing matches we render nothing instead of an empty box so the
 * composer doesn't shift around.
 */
export function MentionPicker({ candidates, query, onSelect }: MentionPickerProps) {
  const { t } = useTranslation();
  const q = query.toLowerCase();
  const filtered = q
    ? candidates.filter((c) => c.display_name.toLowerCase().startsWith(q))
    : candidates;
  if (filtered.length === 0) return null;
  return (
    <div className="chat-mention-picker" aria-label={t("chat.mention.header")}>
      <div className="chat-mention-picker-header">{t("chat.mention.header")}</div>
      {filtered.map((c) => (
        <button
          key={c.agent_id}
          type="button"
          className="chat-mention-picker-row"
          onMouseDown={(e) => {
            // mousedown (not click) so the composer doesn't lose focus before we insert.
            e.preventDefault();
            onSelect(c);
          }}
        >
          <Avatar initials={c.initials} size={26} status={c.status} />
          <span className="chat-mention-picker-name">{c.display_name}</span>
          <span className="chat-mention-picker-handle">@{c.agent_id.replace(/^agent[_-]/, "")}</span>
        </button>
      ))}
    </div>
  );
}
