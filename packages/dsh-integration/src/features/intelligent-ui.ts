import type { Context } from '@deepseek-ai/cordis';
export const name = 'nano-intelligent-ui';
export const inject = ['systemPrompt'];
/** Offers interactive replies while the Agent has Intelligent UI enabled. */
export function apply(ctx: Context) {
  ctx.systemPrompt.section({ name: 'nano-interactive-replies', order: 802, text: 'Choose the most useful response form for the user: text, visual explanation, interactive exploration, comparison or editing. When understanding a process, relationship, changing conditions or tradeoffs benefits from trying controls and seeing results, actively use interactive UI in Web IM even if the user did not ask for an interface. Do not reduce knowledge explanations to plain text by default. Load nano-interactive-ui for the full OpenUI library and syntax before generating, respecting disabled Skills. Use send_message with a short independently readable text and interactive. Local state, calculations and actions run in the browser without model calls; explicit requests continue the conversation with current state. Single facts can remain concise text. Actual business operations use normal tools and authority. After confirmed card delivery, end with the exact non-empty text NO_REPLY.' });
}
