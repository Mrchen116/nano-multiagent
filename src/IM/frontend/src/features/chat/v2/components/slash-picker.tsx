import { useEffect, useId, useMemo, useState } from "react";

import { useTranslation } from "../../../../i18n";
import type {
  SlashCandidate,
  SlashCommandCandidate,
  SlashSkillCandidate,
} from "./slash-candidates";

export interface SlashPickerProps {
  /** Enabled skills for this conversation (single agent, or group union). */
  skills: SlashSkillCandidate[];
  /** Prefix after `/` or `/skill:`. */
  query: string;
  /** True when already in the `/skill:` namespace → only skills are shown. */
  skillMode: boolean;
  /** Group conversations show each skill's source agents. */
  isGroup: boolean;
  onSelect(candidate: SlashCandidate): void;
  onClose(): void;
}

/**
 * feat-430: slash command / skill picker shown above the composer when the user
 * types `/` at the start of the input. Mirrors the mention-picker interaction but
 * inserts plain text (`/stop ` or `/skill:name `) instead of wire XML (决策 1).
 *
 * Interaction (design.md slash picker checklist + prototype):
 * - `/stop` command + skills, prefix-filtered together; `/skill:` mode filters skills only.
 * - ↑/↓ cycle highlight (always scrolled into view), Enter/Tab confirm, Esc closes.
 * - hover only toggles the active class (never rebuilds the list — that breaks clicks);
 *   selection uses mousedown+preventDefault so the composer keeps focus.
 * - description is single-line truncated; group rows label their source agents.
 */
export function SlashPicker({
  skills,
  query,
  skillMode,
  isGroup,
  onSelect,
  onClose,
}: SlashPickerProps) {
  const { t } = useTranslation();

  const candidates = useMemo<SlashCandidate[]>(() => {
    const q = query.toLowerCase();
    const matchedSkills = skills.filter((s) => s.name.toLowerCase().startsWith(q));
    if (skillMode) return matchedSkills;
    const allCommands: SlashCommandCandidate[] = [
      { kind: "command", name: "stop", description: t("chat.slash.stopDesc") },
    ];
    const commands = allCommands.filter((c) => c.name.toLowerCase().startsWith(q));
    return [...commands, ...matchedSkills];
  }, [skills, query, skillMode, t]);

  const [highlighted, setHighlighted] = useState(0);
  const baseId = useId();
  const optionId = (idx: number) => `${baseId}-opt-${idx}`;

  // fix-r2 (P1.3): reset highlight when the candidate *content* changes, not only its
  // length — a background skills refresh can swap items while keeping the count, which
  // would otherwise leave the highlight pointing at a different entry than the user sees.
  const candidatesKey = candidates.map((c) => `${c.kind}:${c.name}`).join("|");
  useEffect(() => {
    setHighlighted(0);
  }, [candidatesKey]);

  // Keep the highlighted item scrolled into view (long lists overflow internally).
  // Resolve by element id (no render-body ref mutation — P2.7); scrollIntoView is absent
  // in jsdom, so guard the call for the test environment.
  useEffect(() => {
    document.getElementById(optionId(highlighted))?.scrollIntoView?.({ block: "nearest" });
    // optionId is derived from baseId (stable per mount); highlighted drives the effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlighted, baseId]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // fix-r2 (P1.2): ignore keystrokes during IME composition so committing a CJK
      // candidate with Enter is not hijacked as a picker selection (mirrors message-pane).
      if (e.isComposing) return;
      if (candidates.length === 0) {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
        }
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlighted((i) => (i + 1) % candidates.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlighted((i) => (i - 1 + candidates.length) % candidates.length);
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        // fix-r2 (P1.3): guard against a stale/out-of-range highlight (content just
        // changed before the reset effect ran) so we never call onSelect(undefined).
        const choice = candidates[highlighted];
        if (choice) onSelect(choice);
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [candidates, highlighted, onSelect, onClose]);

  if (candidates.length === 0) {
    return (
      <div className="chat-slash-picker" aria-label={t("chat.slash.header")}>
        <div className="chat-slash-picker-empty">{t("chat.slash.noMatch")}</div>
      </div>
    );
  }

  let lastKind: SlashCandidate["kind"] | null = null;
  return (
    <div
      className="chat-slash-picker"
      role="listbox"
      aria-label={t("chat.slash.header")}
      aria-activedescendant={optionId(highlighted)}
    >
      {candidates.map((c, idx) => {
        const header =
          c.kind !== lastKind ? (
            <div key={`head-${c.kind}`} className="chat-slash-picker-header">
              {c.kind === "command" ? t("chat.slash.commands") : t("chat.slash.skills")}
            </div>
          ) : null;
        lastKind = c.kind;
        const fromLabel =
          isGroup && c.kind === "skill" && (c as SlashSkillCandidate).fromAgents.length > 0
            ? t("chat.slash.from", { agents: (c as SlashSkillCandidate).fromAgents.join(", ") })
            : null;
        return (
          <div key={`row-${c.kind}-${idx}`}>
            {header}
            <button
              type="button"
              role="option"
              id={optionId(idx)}
              aria-selected={idx === highlighted}
              className={`chat-slash-picker-row${idx === highlighted ? " is-active" : ""}`}
              // mousedown (not click) + preventDefault so the composer keeps focus and
              // the row is not rebuilt out from under the pointer before selection.
              onMouseDown={(e) => {
                e.preventDefault();
                onSelect(c);
              }}
              onMouseEnter={() => setHighlighted(idx)}
            >
              <span className="chat-slash-picker-row1">
                <span className="chat-slash-picker-name">
                  {c.kind === "command" ? `/${c.name}` : c.name}
                </span>
                {fromLabel && <span className="chat-slash-picker-from">{fromLabel}</span>}
              </span>
              {c.description && (
                <span className="chat-slash-picker-desc">{c.description}</span>
              )}
            </button>
          </div>
        );
      })}
    </div>
  );
}
