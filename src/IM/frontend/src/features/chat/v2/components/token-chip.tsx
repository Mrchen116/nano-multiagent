import { useState } from "react";

import { useTranslation } from "../../../../i18n";
import type { TokenUsage } from "../chat-types";

interface TokenChipProps {
  usage: TokenUsage | null | undefined;
  dataTestId?: string;
}

/**
 * Compact token usage chip — surfaces context utilisation so the user can see
 * how close the active conversation is to its window cap (decision: model the
 * 70%/90% bands explicitly so the UI itself communicates risk, instead of
 * silently letting the agent fail at 100%).
 *
 * Clicking the chip expands a detail panel showing prompt/completion/total/context
 * breakdown, matching the prototype's TokenChip interaction (im-components.jsx).
 */
export function TokenChip({ usage, dataTestId }: TokenChipProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (!usage) return null;

  const hasWindow = usage.context_window > 0;
  const pct = hasWindow ? usage.context_used / usage.context_window : 0;
  const variant = hasWindow && pct >= 0.9 ? "critical" : hasWindow && pct >= 0.7 ? "warn" : "normal";
  // Prototype (im-components.jsx) always shows output tokens in the chip button.
  const displayed = usage.output;
  const pctInt = Math.round(pct * 100);

  const barColor =
    pct >= 0.9
      ? "oklch(0.55 0.15 25)"
      : pct >= 0.7
        ? "oklch(0.65 0.18 60)"
        : "oklch(0.52 0.14 180)";

  const fmtK = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  return (
    <div className="chat-token-chip-wrapper">
      <button
        type="button"
        className={`chat-token-chip ${variant !== "normal" ? `chat-token-chip--${variant}` : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-testid={dataTestId}
      >
        <span className="chat-token-chip-arrow">{open ? "▾" : "▸"}</span>
        <span>{fmtK(displayed)} {t("chat.messagePane.tokenSuffix")}</span>
        <span className="chat-token-chip-dot">·</span>
        {hasWindow && (
          <span
            className={
              pct >= 0.9
                ? "chat-token-chip-ctx-critical"
                : pct >= 0.7
                  ? "chat-token-chip-ctx-warn"
                  : ""
            }
          >
            {t("chat.messagePane.tokenContextShort", { pct: pctInt })}
          </span>
        )}
      </button>

      {open && (
        <div className="chat-token-chip-detail">
          <div className="chat-token-chip-detail-row">
            <span className="chat-token-chip-detail-label">{t("chat.messagePane.tokenOutput")}</span>
            <span className="chat-token-chip-detail-value">{usage.output.toLocaleString()}</span>
          </div>
          {usage.total !== undefined && usage.total > 0 && (
            <div className="chat-token-chip-detail-row">
              <span className="chat-token-chip-detail-label">{t("chat.messagePane.tokenTotal")}</span>
              <span className="chat-token-chip-detail-value">{usage.total.toLocaleString()}</span>
            </div>
          )}
          <div className="chat-token-chip-detail-row">
            <span className="chat-token-chip-detail-label">{t("chat.messagePane.tokenContextUsed")}</span>
            <span className="chat-token-chip-detail-value">
              {hasWindow
                ? `${usage.context_used.toLocaleString()} / ${(usage.context_window / 1000).toFixed(0)}k`
                : usage.context_used.toLocaleString()}
            </span>
          </div>
          {hasWindow && (
            <div className="chat-token-chip-detail-bar-wrap">
              <div className="chat-token-chip-detail-bar-track">
                <div
                  className="chat-token-chip-detail-bar-fill"
                  style={{ width: `${pctInt}%`, background: barColor }}
                />
              </div>
              <span
                className="chat-token-chip-detail-bar-pct"
                style={{
                  color:
                    pct >= 0.9
                      ? "oklch(0.70 0.15 25)"
                      : pct >= 0.7
                        ? "oklch(0.75 0.18 60)"
                        : "oklch(0.65 0.10 180)"
                }}
              >
                {pctInt}%
              </span>
            </div>
          )}
          {hasWindow && pct >= 0.7 && (
            <p className={`chat-token-chip-detail-warn ${pct >= 0.9 ? "critical" : ""}`}>
              {pct >= 0.9
                ? t("chat.messagePane.tokenWarnCritical")
                : t("chat.messagePane.tokenWarn")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
