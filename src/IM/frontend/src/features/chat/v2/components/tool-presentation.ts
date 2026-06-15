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
 */
export const REASON_BADGE_NAMES: ReadonlySet<string> = new Set([
  "denied",
  "timed_out",
  "interrupted"
]);

/**
 * Short fail tag shown inline on a failed collapsed row. bash failures often
 * carry an exit code in detail; otherwise fall back to a generic "failed" label
 * (the red row styling already conveys failure). Suppressed when a reason badge
 * is already shown for this call (cr4-frontend: no double "已拒绝" + "failed").
 */
export function failTag(call: ToolCall): string | null {
  if (!isCallFailed(call)) return null;
  if (call.reason && REASON_BADGE_NAMES.has(call.reason)) return null;
  const exit = call.detail?.exit_code;
  if (typeof exit === "number" && exit !== 0) return `exit ${exit}`;
  return "failed";
}
