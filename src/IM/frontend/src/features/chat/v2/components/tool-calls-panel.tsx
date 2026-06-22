import { useState } from "react";

import { useTranslation } from "../../../../i18n";
import type { ToolCall } from "../chat-types";
import { ToolDetailBody } from "./tool-detail-renderers";
import { collapsedSummary, failTag, isCallFailed, toolEmojiFor } from "./tool-presentation";

interface ToolCallsPanelProps {
  toolCalls: ToolCall[];
}

// feat-414: 抽共享工具，供单工具行与气泡耗时复用（message-pane.tsx import 它）。
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem > 0 ? `${m}m ${rem.toFixed(0)}s` : `${m}m`;
}
// feat-414 决策 4: totalDuration 求和已移除 —— 该聚合值等于各工具并发重叠之和，
// 并不等于 wall-clock 墙钟；气泡现在展示后端计算的真实墙钟（elapsed_ms）。

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
            // feat-414 决策 4: 折叠态只显示次数，去掉求和时长（用气泡 elapsed_ms 替代）。
            `${toolCalls.length} ${toolCalls.length === 1 ? t("chat.messagePane.toolCall") : t("chat.messagePane.toolCalls")}`
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
// bugfix-417-M3 R4 (decision 5): tool_timeout (工具自身 deadline) → "执行超时";
// stalled (watchdog liveness 收尸) → "已中断". The legacy timed_out/interrupted keys are
// kept for rows persisted before this change.
const REASON_LABEL_KEYS: Record<string, string> = {
  denied: "chat.messagePane.toolReasonDenied",
  timed_out: "chat.messagePane.toolReasonTimedOut",
  tool_timeout: "chat.messagePane.toolReasonTimedOut",
  interrupted: "chat.messagePane.toolReasonInterrupted",
  stalled: "chat.messagePane.toolReasonInterrupted",
};

function ToolCallRow({ call, defaultOpen = false }: { call: ToolCall; defaultOpen?: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  // Failure derives from isCallFailed (status OR detail.success===false), so
  // never-raising tools (memory/skill failures) also render red (Round-3 fix).
  const failed = isCallFailed(call);
  const statusColor = failed
    ? "oklch(0.55 0.15 25)"
    : call.status === "running"
      ? "oklch(0.70 0.18 60)"
      : "oklch(0.55 0.18 145)";
  const statusIcon = failed ? "✕" : call.status === "running" ? "◌" : "●";
  const rowStatus = failed ? "failed" : call.status;
  const reasonKey = call.reason ? REASON_LABEL_KEYS[call.reason] : undefined;
  // 决策 4: emoji is name-keyed (visual only, generic fallback); summary text is
  // the presenter-produced `output`, not derived by name.
  const summary = collapsedSummary(call);
  const tag = failTag(call);

  return (
    <li className="chat-tool-call-item">
      <button
        type="button"
        className={`chat-tool-call-row chat-tool-call-row--${rowStatus}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="chat-tool-call-status-icon" style={{ color: statusColor }}>
          {statusIcon}
        </span>
        <span className="chat-tool-call-name">
          <span className="chat-tool-call-emoji" aria-hidden="true">
            {toolEmojiFor(call)}
          </span>{" "}
          {call.name}
        </span>
        {summary && <span className="chat-tool-call-summary">{summary}</span>}
        {reasonKey && (
          <span className="chat-tool-call-reason" style={{ color: "oklch(0.55 0.15 25)" }}>
            {t(reasonKey)}
          </span>
        )}
        {tag && <span className="chat-tool-call-fail-tag">{tag}</span>}
        {typeof call.duration_ms === "number" && (
          <span className="chat-tool-call-duration">{formatDuration(call.duration_ms)}</span>
        )}
        <span className="chat-tool-call-arrow">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="chat-tool-call-body chat-tool-call-body--open">
          <div className="chat-tool-call-body-inner">
            <ToolDetailBody call={call} />
          </div>
        </div>
      )}
    </li>
  );
}
