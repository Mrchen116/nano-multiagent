import { useState } from "react";

import { useTranslation } from "../../../../i18n";
import type { ToolCall } from "../chat-types";

interface ToolCallsPanelProps {
  toolCalls: ToolCall[];
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem > 0 ? `${m}m ${rem.toFixed(0)}s` : `${m}m`;
}

function totalDuration(toolCalls: ToolCall[]): number {
  return toolCalls.reduce((sum, tc) => sum + (tc.duration_ms ?? 0), 0);
}

/**
 * Collapsible tool-call sidecar attached to an agent message. Top button shows
 * the total count + a "running" hint if any call is still in flight; expanding
 * reveals one row per call with its own input/output toggle. Matches the
 * prototype's running pulse semantics — the agent will keep streaming
 * tool_call.* events so the panel re-renders on its own.
 *
 * Dark-theme styling with expand/collapse animation (im-components.jsx).
 */
export function ToolCallsPanel({ toolCalls }: ToolCallsPanelProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  if (toolCalls.length === 0) return null;
  const anyRunning = toolCalls.some((c) => c.status === "running");
  const total = totalDuration(toolCalls);

  return (
    <div className="chat-tool-calls">
      <button
        type="button"
        className={`chat-tool-calls-toggle ${expanded ? "chat-tool-calls-toggle--open" : ""}`}
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="chat-tool-calls-arrow">{expanded ? "▾" : "▸"}</span>
        <span>
          {anyRunning ? (
            <span className="chat-tool-calls-running-wrap">
              <span className="chat-tool-calls-pulse" />
              {toolCalls.length}{" "}
              {toolCalls.length === 1
                ? t("chat.messagePane.toolCall")
                : t("chat.messagePane.toolCalls")}{" "}
              · {t("chat.messagePane.running")}
            </span>
          ) : (
            `${toolCalls.length} ${toolCalls.length === 1 ? t("chat.messagePane.toolCall") : t("chat.messagePane.toolCalls")} · ${formatDuration(total)}`
          )}
        </span>
      </button>

      {expanded && (
        <div className="chat-tool-calls-panel chat-tool-calls-panel--open">
          <ul className="chat-tool-calls-list">
            {toolCalls.map((c, i) => (
              <ToolCallRow key={c.id} call={c} defaultOpen={i === 0} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// bugfix-410-M2 (#97): map a sidecar reason to its i18n badge label key. Unknown
// reasons fall through to no badge (status icon alone) rather than rendering a raw code.
const REASON_LABEL_KEYS: Record<string, string> = {
  denied: "chat.messagePane.toolReasonDenied",
  timed_out: "chat.messagePane.toolReasonTimedOut",
  interrupted: "chat.messagePane.toolReasonInterrupted",
};

function ToolCallRow({ call, defaultOpen = false }: { call: ToolCall; defaultOpen?: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const statusColor =
    call.status === "completed"
      ? "oklch(0.55 0.18 145)"
      : call.status === "running"
        ? "oklch(0.70 0.18 60)"
        : "oklch(0.55 0.15 25)";
  const statusIcon = call.status === "running" ? "◌" : call.status === "completed" ? "●" : "✕";
  const reasonKey = call.reason ? REASON_LABEL_KEYS[call.reason] : undefined;

  return (
    <li className="chat-tool-call-item">
      <button
        type="button"
        className={`chat-tool-call-row chat-tool-call-row--${call.status}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="chat-tool-call-status-icon" style={{ color: statusColor }}>
          {statusIcon}
        </span>
        <span className="chat-tool-call-name">{call.name}</span>
        {reasonKey && (
          <span className="chat-tool-call-reason" style={{ color: "oklch(0.55 0.15 25)" }}>
            {t(reasonKey)}
          </span>
        )}
        {typeof call.duration_ms === "number" && (
          <span className="chat-tool-call-duration">{formatDuration(call.duration_ms)}</span>
        )}
        <span className="chat-tool-call-arrow">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="chat-tool-call-body chat-tool-call-body--open">
          <div className="chat-tool-call-body-inner">
            {call.input != null && (
              <div className="chat-tool-call-section">
                <span className="chat-tool-call-section-label">INPUT</span>
                <pre className="chat-tool-call-pre">
                  {typeof call.input === "string" ? call.input : JSON.stringify(call.input, null, 2)}
                </pre>
              </div>
            )}
            {call.output != null && (
              <div className="chat-tool-call-section">
                <span className="chat-tool-call-section-label">OUTPUT</span>
                <pre className="chat-tool-call-pre">
                  {typeof call.output === "string" ? call.output : JSON.stringify(call.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </li>
  );
}
