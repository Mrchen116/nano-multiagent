/**
 * PermissionCard: inline permission request card rendered inside agent message bubbles.
 *
 * bugfix-367 修复点:
 *  - 删除 useState(() => initialState(request)) 反模式: resolved 分支直接由
 *    `request.status === "resolved"` 派生, prop 变化时组件自然 re-render
 *    到正确状态(同 message 多次 ask 时也无需依赖 React key 强行 remount)。
 *  - 卡内直接渲染 tool_input + description(若 bash/task/agent 工具的入参里有
 *    `description` 字段则作为人类可读摘要)。用户不再需要去点开"上面的工具
 *    调用详情"才能看到要授权什么命令/参数。
 *  - 仅 submitting / error 是真正的临时态, 保留在 useState 中。
 *
 * 视觉与 chat-permission-* 系列对齐(global.css 已备好的 dark mono 体系)。
 */
import { useState } from "react";

import { authFetch } from "../../../auth/auth-fetch";
import { useTranslation } from "../../../../i18n";

import type { PermissionOption, PermissionRequest } from "../chat-types";

export interface PermissionCardProps {
  request: PermissionRequest;
  conversationId: string;
  messageId: string;
  /** Called with the chosen decision string after a successful POST. */
  onResolved(decision: string): void;
  /** Test seam: override fetch. Defaults to authFetch (injects Authorization header). */
  fetchFn?: (url: string, init?: RequestInit) => Promise<Response>;
}

type TransientState =
  | { kind: "idle" }
  | { kind: "submitting"; chosenId: string }
  | { kind: "error"; chosenId: string; message: string };

// feat-434-M1 (F1): map the stable backend option id → i18n key so the待决卡 buttons
// follow the interface language (原型: 允许 / 本会话内允许 / 拒绝 / 总是允许). Unknown ids
// fall back to the backend-supplied opt.label. The ids come from broker.PermissionOption.
const OPTION_LABEL_KEYS: Record<string, string> = {
  allow_once: "chat.permission.optionAllowOnce",
  allow_session: "chat.permission.optionAllowSession",
  allow_always: "chat.permission.optionAllowAlways",
  deny: "chat.permission.optionDeny",
};

function readDescription(input: Record<string, unknown> | null | undefined): string | null {
  // bugfix-367: bash / task / agent 工具的 input_schema 给 LLM 留了 `description`
  // 字段(参见 src/agent/platform/tools/builtins/{bash,task,agent}.py)。LLM 会
  // 填一句人类可读摘要, 授权卡显示这条比单看 raw JSON 更易判断。其他工具
  // 没有该字段, 跳过渲染描述行。
  if (!input || typeof input !== "object") return null;
  const value = (input as Record<string, unknown>).description;
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function stripDescription(input: Record<string, unknown> | null | undefined): Record<string, unknown> {
  // 原始参数块去掉 description, 避免与上方摘要行重复。
  if (!input || typeof input !== "object") return {};
  const { description: _description, ...rest } = input as Record<string, unknown>;
  void _description;
  return rest;
}

function formatToolInput(input: Record<string, unknown> | null | undefined): string {
  // bugfix-367: 与 tool-calls-panel.tsx 的 INPUT 区一致 ——
  // JSON.stringify(rest, null, 2), 所有工具一视同仁, 多参全展示。
  const rest = stripDescription(input);
  return JSON.stringify(rest, null, 2);
}

/**
 * Inline permission request card shown below an agent message while the agent
 * is awaiting a user decision (auto_mode_gate ask flow).
 */
export function PermissionCard({
  request,
  conversationId,
  messageId,
  onResolved,
  fetchFn = authFetch,
}: PermissionCardProps) {
  const { t } = useTranslation();
  const [transient, setTransient] = useState<TransientState>({ kind: "idle" });
  // feat-440-M1: 常驻选填理由框。拒绝时若有内容则随 POST 透传给 LLM 的回传文本;
  // 留空走默认 REJECT_MESSAGE。允许类决策后端忽略该值(见 spec Q4 形态 A)。
  const [reason, setReason] = useState("");

  async function handleChoice(option: PermissionOption) {
    setTransient({ kind: "submitting", chosenId: option.id });
    const trimmedReason = reason.trim();
    try {
      const resp = await fetchFn(
        `/im/v1/conversations/${conversationId}/permissions/${request.request_id}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message_id: messageId,
            decision: option.id,
            // Omit the key entirely when empty so the backend sees no reason.
            ...(trimmedReason ? { reason: trimmedReason } : {}),
          }),
        }
      );
      if (!resp.ok) {
        const text = await resp.text().catch(() => "Unknown error");
        throw new Error(text || `HTTP ${resp.status}`);
      }
      // 不再写本地 resolved state —— 服务端的 permission.resolved WS 事件会通过
      // reducer 把 request.status 更新为 "resolved", 组件自然重渲染。
      onResolved(option.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : t("chat.permission.submitError");
      setTransient({ kind: "error", chosenId: option.id, message });
    }
  }

  // feat-434 决策 3: 已决审批不再渲染独立卡 —— 它已并入工具调用行的闸门区
  // （读 tool_call.approval → 已授权/已拒绝）。resolved 时本组件渲染空，由工具面板承载呈现。
  // PermissionCard 自此只负责「待决」职责（pending）。
  if (request.status === "resolved") {
    return null;
  }

  const isSubmitting = transient.kind === "submitting";
  const errorMessage = transient.kind === "error" ? transient.message : null;

  const description = readDescription(request.tool_input);
  const formattedInput = formatToolInput(request.tool_input);

  return (
    <div
      className="chat-permission-card"
      role="region"
      aria-label={t("chat.permission.ariaCard", { toolName: request.tool_name })}
    >
      {/* feat-434 决策 Q3 / 原型: 待决卡无锁图标；醒目提示用脉冲圆点 + 「需要确认」。 */}
      <div className="chat-permission-header">
        <span className="chat-permission-tool-name">{request.tool_name}</span>
        <span className="chat-permission-hint">
          <span className="chat-permission-pulse" aria-hidden="true" />
          {t("chat.permission.hint")}
        </span>
      </div>
      {/* bugfix-367 §A: tool_input.description (bash/task/agent 工具有此字段) */}
      {description && (
        <p data-testid="permission-description" className="chat-permission-desc">
          {description}
        </p>
      )}
      {/* bugfix-367 §A: 原始 tool_input 区, 多参一视同仁全展示 */}
      <pre data-testid="permission-tool-input" className="chat-permission-cmd">
        {formattedInput}
      </pre>
      <p className="chat-permission-question">{request.question}</p>
      {errorMessage && (
        <div role="alert" className="chat-permission-error">
          {errorMessage}
        </div>
      )}
      {/* feat-440-M1: 常驻选填拒绝理由框,在按钮区上方(spec Q4 形态 A)。 */}
      <textarea
        data-testid="permission-reason-input"
        className="chat-permission-reason"
        rows={2}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        disabled={isSubmitting}
        placeholder={t("chat.permission.reasonPlaceholder")}
        aria-label={t("chat.permission.reasonLabel")}
      />
      <div className="chat-permission-options" role="group" aria-label={t("chat.permission.ariaOptions")}>
        {request.options.map((opt) => {
          const isChosen = isSubmitting && (transient as { chosenId: string }).chosenId === opt.id;
          const variant =
            opt.id === "allow_once" ? " chat-permission-btn--primary"
            : opt.id === "deny" ? " chat-permission-btn--danger"
            : "";
          return (
            <button
              key={opt.id}
              type="button"
              className={`chat-permission-btn${variant}`}
              onClick={() => handleChoice(opt)}
              disabled={isSubmitting}
              aria-busy={isChosen}
              title={opt.description}
            >
              {OPTION_LABEL_KEYS[opt.id] ? t(OPTION_LABEL_KEYS[opt.id]) : opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
