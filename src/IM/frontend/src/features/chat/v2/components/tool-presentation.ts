// feat-409-M2: pure presentation helpers for tool-call rows.
//
// 决策 4: the collapsed-row *text* is the presenter-produced summary (carried
// in `ToolCall.output`); the front-end does NOT derive collapsed text by tool
// name. The only name-keyed thing here is the emoji prefix — a pure visual
// affordance that gracefully degrades to a generic icon for unknown / DIY / MCP
// tools (which the IM cannot know about). Keeping it a lookup table (not a
// switch with logic) keeps adding a tool from touching IM behaviour.

import type { ToolCall } from "../chat-types";

const GENERIC_TOOL_EMOJI = "🔧";

/**
 * name → emoji prefix for built-in tools. Mirrors the prototype. Read tool
 * also appears in agent transcripts though it has no detail card; map it too so
 * its row gets a recognisable icon.
 */
const TOOL_EMOJI: Record<string, string> = {
  bash: "💻",
  read: "📖",
  edit: "📝",
  write: "✍️",
  web_fetch: "🌐",
  agent: "🔀",
  memory: "🧠",
  skill_manage: "📚",
  task_stop: "⏹"
};

/** Emoji prefix for a tool name, falling back to a generic icon for unknowns. */
export function toolEmoji(name: string): string {
  return TOOL_EMOJI[name] ?? GENERIC_TOOL_EMOJI;
}

/**
 * Collapsed-row emoji for a tool call (feat-425 决策 1): event-first, name-table
 * fallback. A tool/presenter that carries its own emoji owns its icon — custom /
 * MCP / product tools no longer all collapse to the generic 🔧. Rows without a
 * carried emoji (historical rows, in-flight rows whose tool_start relay omits it)
 * fall back to the name table, so built-ins keep their icon and unknown tools get 🔧.
 */
export function toolEmojiFor(call: ToolCall): string {
  if (typeof call.emoji === "string" && call.emoji) return call.emoji;
  return toolEmoji(call.name);
}

/**
 * Collapsed-row summary text. Prefers the presenter summary (`output`); for
 * historical rows persisted before feat-409 (no output) returns "" so the row
 * still renders cleanly with just emoji + name.
 */
export function collapsedSummary(call: ToolCall): string {
  return typeof call.output === "string" ? call.output : "";
}

/**
 * Whether a tool call failed. Two failure channels (Round-3 fix):
 *  - `call.status === "failed"` — kernel reported a result.error (out-of-band).
 *  - `detail.success === false` — tools that never raise (memory/skill_manage
 *    return {success:False, error}); the kernel sees no error so status stays
 *    "completed", but the call did fail. The collapsed row + cards must treat
 *    these as failures (spec: failed tool calls are red).
 */
export function isCallFailed(call: ToolCall): boolean {
  return call.status === "failed" || call.detail?.success === false;
}

/**
 * Reasons that render a dedicated badge on the collapsed row (kept in sync with
 * REASON_LABEL_KEYS in tool-calls-panel). When one of these is present the badge
 * already conveys the failure, so failTag is suppressed to avoid a confusing
 * double identifier (cr4-frontend: "已拒绝" + "failed").
 *
 * feat-434-M1 决策 4: "denied" left this set — denied now renders in the inline
 * GATE region (gateVerdict), not as a row-tail reason badge. Keeping it here too
 * would print 已拒绝 twice. The remaining reasons (timeout/interrupted) are真正的
 * 执行结果 and stay in the row-tail result region.
 */
export const REASON_BADGE_NAMES: ReadonlySet<string> = new Set([
  // bugfix-417-M3 R4: tool_timeout (执行超时) / stalled (已中断) join the legacy
  // timed_out / interrupted reasons (kept for rows persisted before the change).
  "timed_out",
  "tool_timeout",
  "interrupted",
  "stalled"
]);

/**
 * feat-434-M1 决策 1/4: the inline GATE verdict — whether a USER decided this call.
 * Reads ``approval`` (kernel-stamped). Historical denied rows carry ``reason==="denied"``
 * but no approval; fall back to "deny" so the gate region still shows 已拒绝 for them.
 * None → no gate region (auto-allowed / plain tools). Orthogonal to the result region.
 */
export function gateVerdict(call: ToolCall): "allow" | "deny" | null {
  if (call.approval === "user_allow") return "allow";
  if (call.approval === "user_deny") return "deny";
  // Historical denied rows (reason badge era) had no approval field.
  if (call.reason === "denied") return "deny";
  return null;
}

/**
 * feat-434-M1: a denied call was never executed — its result region标 "未执行"
 * instead of a duration/error. True only for the gate-deny verdict.
 */
export function isNotExecuted(call: ToolCall): boolean {
  return gateVerdict(call) === "deny";
}

/**
 * Short fail tag shown inline on a failed collapsed row, now i18n-driven (feat-434
 * 决策 5): bash failures carry an exit code → "退出码 N" / "exit N"; otherwise a
 * generic "失败" / "failed" (the red row styling already conveys failure). Suppressed
 * when a reason badge or the gate-deny verdict already conveys the terminal — no
 * double identifier (cr4-frontend / 决策 4: a denied row's gate region owns 已拒绝,
 * and its result region is 未执行, so no fail tag).
 */
export function failTag(call: ToolCall, t: (key: string, opts?: Record<string, unknown>) => string): string | null {
  if (!isCallFailed(call)) return null;
  if (call.reason && REASON_BADGE_NAMES.has(call.reason)) return null;
  if (gateVerdict(call) === "deny") return null;
  const exit = call.detail?.exit_code;
  if (typeof exit === "number" && exit !== 0) return t("chat.messagePane.toolFailExit", { code: exit });
  return t("chat.messagePane.toolFailGeneric");
}
