import type { Context } from '@deepseek-ai/cordis';
export const name = 'nano-intelligent-ui';
export const inject = ['systemPrompt'];
/** Offers interactive replies while the Agent has Intelligent UI enabled. */
export function apply(ctx: Context) {
  ctx.systemPrompt.section({ name: 'nano-interactive-replies', order: 802, text: 'When comparing choices, editing a draft, adjusting conditions or explaining a useful next step, you may reply with an interactive UI in Web IM. Load the nano-interactive-ui skill for the supported OpenUI catalogue before generating one, respecting disabled Skills. Use send_message with a short independently readable text and optional interactive. Keep simple answers in plain text. Buttons submit a real user message containing their visible label and choices; local edits alone authorize no business action. After a card is confirmed sent, end with the exact non-empty text NO_REPLY so the host can suppress duplicate delivery. Never end with an empty response.' });
}
