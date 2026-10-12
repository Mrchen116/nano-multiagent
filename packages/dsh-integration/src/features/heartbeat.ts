import type { Context } from '@deepseek-ai/cordis';
export const name = 'nano-heartbeat';
export const inject = ['systemPrompt'];
/** Runtime guidance shares the Feature lifetime; the node owns its sole timer. */
export function apply(ctx: Context) {
  ctx.systemPrompt.section({ name: 'nano-heartbeat', order: 815, text: 'Heartbeat is a system wake, never a new human instruction or approval. Read the selected HEARTBEAT.md tasks; do not repeat old unrelated work. If nothing needs attention, return HEARTBEAT_OK and do not call send_message. In global mode publish actionable updates explicitly to the appropriate human conversation. Keep schedule and heartbeat sources distinct from live human requests.' });
}
