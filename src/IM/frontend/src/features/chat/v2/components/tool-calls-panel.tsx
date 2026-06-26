import { useState } from "react";

import { useTranslation } from "../../../../i18n";
import type { ThinkingSegment, ToolCall } from "../chat-types";
import { ToolDetailBody } from "./tool-detail-renderers";
import {
  collapsedSummary,
  failTag,
  gateVerdict,
  isCallFailed,
  isNotExecuted,
  toolEmojiFor
} from "./tool-presentation";

interface ToolCallsPanelProps {
  toolCalls: ToolCall[];
  // feat-439-M2: 整轮多段思考。与 toolCalls 按 seq merge 成一条「过程」时间线。
  thinking?: ThinkingSegment[];
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

type ProcessItem =
  | { kind: "thinking"; segment: ThinkingSegment; key: string }
  | { kind: "tool"; call: ToolCall; key: string };

/**
 * feat-439-M2: 把整轮的思考段与工具调用按真实时序 merge 成一条流。
 *
 * 思考与工具共享一个 per-message 单调递增 `seq`（由 IM 按真实到达序赋予、全局唯一），
 * 故直接按 seq 升序合并即得真实时序。旧持久化工具行无 seq（此时必无思考），回退到列表
 * 序（用一个大偏移保证它们落在所有带 seq 项之后、彼此保持原顺序）。稳定排序保证同序
 * 号项保留插入顺序。
 */
function buildTimeline(
  toolCalls: ToolCall[],
  thinking: ThinkingSegment[]
): ProcessItem[] {
  const items: { sortKey: number; item: ProcessItem }[] = [];
  for (const s of thinking) {
    items.push({ sortKey: s.seq, item: { kind: "thinking", segment: s, key: `think-${s.seq}` } });
  }
  const LEGACY_BASE = 1e9; // 无 seq 的旧工具行排到末尾，保持彼此原顺序
  toolCalls.forEach((c, i) => {
    const sortKey = typeof c.seq === "number" ? c.seq : LEGACY_BASE + i;
    items.push({ sortKey, item: { kind: "tool", call: c, key: `tool-${c.id}` } });
  });
  return items
    .map((entry, i) => ({ ...entry, i }))
    .sort((a, b) => a.sortKey - b.sortKey || a.i - b.i)
    .map((entry) => entry.item);
}

/**
 * Collapsible "process" timeline attached to an agent message (feat-439-M2, 升级自
 * feat-340 的工具折叠盘). The top button shows the tool count, the thinking-segment
 * count, and a "running" hint while any call is in flight; expanding reveals one row
 * per process item — thinking segments (💭) and tool calls interleaved by real
 * chronology. Each row has its own expand/collapse. 无思考的轮里只出现工具行，无 💭。
 *
 * Dark-theme styling with expand/collapse animation (im-components.jsx).
 */
export function ToolCallsPanel({ toolCalls, thinking }: ToolCallsPanelProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const segments = thinking ?? [];
  if (toolCalls.length === 0 && segments.length === 0) return null;
  const anyRunning = toolCalls.some((c) => c.status === "running");
  const timeline = buildTimeline(toolCalls, segments);

  // feat-434-M1: collapsed-state approval count suffix「K 次授权 · X 允许 · Y 拒绝」.
  // Audits "how many times the user approved" (bugfix-367 risk保住) without the old
  // resolved-card wall. Only non-zero segments render (prototype). Empty when no call
  // was user-decided.
  const allowCount = toolCalls.filter((c) => gateVerdict(c) === "allow").length;
  const denyCount = toolCalls.filter((c) => gateVerdict(c) === "deny").length;
  const approvalCount = allowCount + denyCount;

  return (
    <div className="chat-tool-calls">
      <button
        type="button"
        className={`chat-tool-calls-toggle ${expanded ? "chat-tool-calls-toggle--open" : ""}`}
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="chat-tool-calls-arrow">{expanded ? "▾" : "▸"}</span>
        <span className="chat-process-label">{t("chat.messagePane.process")}</span>
        {toolCalls.length > 0 && (
          <>
            <span className="chat-tool-calls-sep">·</span>
            <span>
              {anyRunning ? (
                <span className="chat-tool-calls-running-wrap">
                  <span className="chat-tool-calls-pulse" />
                  {t("chat.messagePane.toolCount", { count: toolCalls.length })} ·{" "}
                  {t("chat.messagePane.running")}
                </span>
              ) : (
                t("chat.messagePane.toolCount", { count: toolCalls.length })
              )}
            </span>
          </>
        )}
        {segments.length > 0 && (
          <>
            <span className="chat-tool-calls-sep">·</span>
            <span className="chat-process-think-count">
              {t("chat.messagePane.thinkingCount", { count: segments.length })}
            </span>
          </>
        )}
        {approvalCount > 0 && (
          <span className="chat-tool-calls-approvals">
            <span className="chat-tool-calls-sep">·</span>
            <span className="chat-tool-calls-approval-seg">
              {t("chat.messagePane.toolApprovalCount", { count: approvalCount })}
            </span>
            {allowCount > 0 && (
              <>
                <span className="chat-tool-calls-sep">·</span>
                <span
                  className="chat-tool-calls-dot chat-tool-calls-dot--allow"
                  aria-hidden="true"
                />
                <span className="chat-tool-calls-approval-seg">
                  {t("chat.messagePane.toolApprovalAllow", { count: allowCount })}
                </span>
              </>
            )}
            {denyCount > 0 && (
              <>
                <span className="chat-tool-calls-sep">·</span>
                <span
                  className="chat-tool-calls-dot chat-tool-calls-dot--deny"
                  aria-hidden="true"
                />
                <span className="chat-tool-calls-approval-seg">
                  {t("chat.messagePane.toolApprovalDeny", { count: denyCount })}
                </span>
              </>
            )}
          </span>
        )}
      </button>

      {expanded && (
        <div className="chat-tool-calls-panel chat-tool-calls-panel--open">
          <ul className="chat-tool-calls-list">
            {timeline.map((item, i) =>
              item.kind === "thinking" ? (
                <ThinkingRow key={item.key} segment={item.segment} />
              ) : (
                <ToolCallRow key={item.key} call={item.call} defaultOpen={i === 0} />
              )
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

// feat-439-M2: 一段思考行。默认收起为一行 💭 + 首行摘要；点开展示完整思考内容
// （整段呈现、不逐字滚动——内核事件管线无 token 流式）。靛紫调与工具行（青色）区分。
function ThinkingRow({ segment }: { segment: ThinkingSegment }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const firstLine = segment.text.split("\n", 1)[0] ?? "";
  const summary = firstLine.length > 60 ? `${firstLine.slice(0, 60)}…` : firstLine;
  return (
    <li className="chat-tool-call-item chat-process-item" data-testid="process-item">
      <button
        type="button"
        className={`chat-tool-call-row chat-process-think-row ${open ? "chat-process-think-row--open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-testid="process-thinking-toggle"
      >
        <span
          className="chat-tool-call-status-icon chat-process-think-icon"
          aria-hidden="true"
        >
          💭
        </span>
        <span className="chat-tool-call-name chat-process-think-name">
          {t("chat.messagePane.thinking")}
        </span>
        <span className="chat-tool-call-summary chat-process-think-summary">{summary}</span>
        <span className="chat-tool-call-arrow">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="chat-tool-call-body chat-tool-call-body--open">
          <div
            className="chat-tool-call-body-inner chat-process-think-body"
            data-testid="process-thinking-body"
          >
            {segment.text}
          </div>
        </div>
      )}
    </li>
  );
}

// bugfix-410-M2 (#97): map a sidecar reason to its i18n badge label key. Unknown
// reasons fall through to no badge (status icon alone) rather than rendering a raw code.
// bugfix-417-M3 R4 (decision 5): tool_timeout (工具自身 deadline) → "执行超时";
// stalled (watchdog liveness 收尸) → "已中断". The legacy timed_out/interrupted keys are
// kept for rows persisted before this change.
// feat-434-M1 (F5): "denied" left this map — denied now renders in the inline GATE
// region (gateVerdict, 决策 4), and ToolCallRow already excludes reason==="denied"
// from reasonKey. Keeping it here was a dead branch that could mislead future edits.
const REASON_LABEL_KEYS: Record<string, string> = {
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
  // feat-434-M1 决策 4: two orthogonal regions.
  // GATE region (贴名称右侧): 是否经用户授权. Reads gateVerdict (approval, 历史 denied
  // 回退). denied here suppresses the row-tail reason badge —「已拒绝」只印一次.
  const verdict = gateVerdict(call);
  // RESULT region (行尾): 执行结果. Non-denied reason badges (timeout/interrupted)
  // stay here; "denied" is excluded (REASON_BADGE_NAMES dropped it → key undefined).
  const reasonKey =
    call.reason && call.reason !== "denied" ? REASON_LABEL_KEYS[call.reason] : undefined;
  // 决策 4: emoji is name-keyed (visual only, generic fallback); summary text is
  // the presenter-produced `output`, not derived by name.
  const summary = collapsedSummary(call);
  const tag = failTag(call, t);
  const notExecuted = isNotExecuted(call);

  return (
    <li className="chat-tool-call-item chat-process-item" data-testid="process-item">
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
        {verdict && (
          <span className={`chat-tool-call-gate chat-tool-call-gate--${verdict}`}>
            {verdict === "allow"
              ? t("chat.messagePane.toolGateAllowed")
              : t("chat.messagePane.toolGateDenied")}
          </span>
        )}
        {summary && <span className="chat-tool-call-summary">{summary}</span>}
        {reasonKey && (
          <span className="chat-tool-call-reason" style={{ color: "oklch(0.55 0.15 25)" }}>
            {t(reasonKey)}
          </span>
        )}
        {tag && <span className="chat-tool-call-fail-tag">{tag}</span>}
        {notExecuted ? (
          <span className="chat-tool-call-not-executed">
            {t("chat.messagePane.toolNotExecuted")}
          </span>
        ) : (
          typeof call.duration_ms === "number" && (
            <span className="chat-tool-call-duration">{formatDuration(call.duration_ms)}</span>
          )
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
