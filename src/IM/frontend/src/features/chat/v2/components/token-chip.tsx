import { useTranslation } from "../../../../i18n";
import type { TokenUsage } from "../chat-types";

interface TokenChipProps {
  usage: TokenUsage | null | undefined;
}

/**
 * Compact token usage chip — surfaces context utilisation so the user can see
 * how close the active conversation is to its window cap (decision: model the
 * 70%/90% bands explicitly so the UI itself communicates risk, instead of
 * silently letting the agent fail at 100%).
 */
export function TokenChip({ usage }: TokenChipProps) {
  const { t } = useTranslation();
  if (!usage) return null;
  const pct = usage.context_window > 0 ? usage.context_used / usage.context_window : 0;
  const variant = pct >= 0.9 ? "critical" : pct >= 0.7 ? "warn" : "normal";
  const cls = variant === "normal" ? "chat-token-chip" : `chat-token-chip chat-token-chip--${variant}`;
  // M17/R8-3: prefer the per-turn total (prompt+completion) so the chip
  // communicates real token consumption; fall back to ``output`` for legacy
  // payloads persisted before the total field shipped.
  const displayed = usage.total && usage.total > 0 ? usage.total : usage.output;
  return (
    <button type="button" className={cls} title={t("chat.messagePane.tokenContext", {
      used: usage.context_used,
      window: usage.context_window,
      pct: Math.round(pct * 100)
    })}>
      {displayed} {t("chat.messagePane.tokenSuffix")}
    </button>
  );
}
