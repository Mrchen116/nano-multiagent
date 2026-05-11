import { useState } from "react";

import { useTranslation } from "../../../../i18n";
import type { ToolCall } from "../chat-types";

interface ToolCallsPanelProps {
  toolCalls: ToolCall[];
}

/**
 * Collapsible tool-call sidecar attached to an agent message. Top button shows
 * the total count + a "running" hint if any call is still in flight; expanding
 * reveals one row per call with its own input/output toggle. Matches the
 * prototype's running pulse semantics — the agent will keep streaming
 * tool_call.* events so the panel re-renders on its own.
 */
export function ToolCallsPanel({ toolCalls }: ToolCallsPanelProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (toolCalls.length === 0) return null;
  const anyRunning = toolCalls.some((c) => c.status === "running");
  return (
    <div className="chat-tool-calls">
      <button
        type="button"
        className="chat-tool-calls-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span>
          {toolCalls.length} {toolCalls.length === 1 ? t("chat.messagePane.toolCall") : t("chat.messagePane.toolCalls")}
        </span>
        {anyRunning && <span className="chat-tool-calls-running">{t("chat.messagePane.running")}</span>}
      </button>
      {open && (
        <ul className="chat-tool-calls-list">
          {toolCalls.map((c) => (
            <ToolCallRow key={c.id} call={c} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ToolCallRow({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <button
        type="button"
        className={`chat-tool-call-row chat-tool-call-row--${call.status}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="chat-tool-call-name">{call.name}</span>
        <span className="chat-tool-call-status">{call.status}</span>
        {typeof call.duration_ms === "number" && (
          <span className="chat-tool-call-duration">{call.duration_ms}ms</span>
        )}
      </button>
      {open && (
        <div className="chat-tool-call-body">
          <div className="chat-tool-call-section">
            <span className="chat-tool-call-section-label">INPUT</span>
            <pre>{JSON.stringify(call.input, null, 2)}</pre>
          </div>
          {call.output !== undefined && (
            <div className="chat-tool-call-section">
              <span className="chat-tool-call-section-label">OUTPUT</span>
              <pre>{typeof call.output === "string" ? call.output : JSON.stringify(call.output, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
