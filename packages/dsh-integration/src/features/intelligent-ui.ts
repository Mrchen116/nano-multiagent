import {isInternalExecution} from '../child-role.js';
import type { Context } from '@deepseek-ai/cordis';
export const name = 'nano-intelligent-ui';
export const inject = ['systemPrompt'];
/** Offers interactive replies while the Agent has Intelligent UI enabled. */
export function apply(ctx: Context, config: {mode?: string}) {
  ctx.systemPrompt.section({ name: 'nano-interactive-replies', order: 808, text: ({agent}) => {
    const internal = isInternalExecution(agent);
    if (internal && config.mode === 'global') return `For an interactive deliverable, load nano-interactive-ui and follow the requested format. Return the prepared source and a short explanation to your parent for delivery. Use verified data; UI interactions do not grant business permissions.`;
    return [`Choose the format that reduces the user's effort to understand and act. Follow task-specific delivery guidance and respect requested formats. Otherwise, prefer text for brief answers, emotional conversation, and standalone writing.

Proactively use Intelligent UI for complex information, comparisons, relationships, processes, and changes, even when not requested. Before building, decide what the user should understand first, then choose the structure, layout, and visualization that make it easiest.

Make the UI visually appealing and comfortable to read, with clear hierarchy, balanced spacing, readable typography, and consistent colors. Keep it simple; add interaction only when it helps the task.

Load nano-interactive-ui before generating UI. The UI is the complete answer: put necessary explanation in it, using text, visuals and structure together. Do not add a separate summary or preface just because you are sending UI.

In private chats, natural follow-ups may include background captured at send time. Use it only when relevant to the user's words, ignore it on a topic change and clarify ambiguous references. In groups, unsent local state is unavailable; only explicit card submissions share it.`, internal ? `Return the prepared interactive source and any necessary delivery notes to your parent for the root Agent to deliver. Do not call a public sending tool or claim that an internal report delivered the card to the user.` : `Use the appropriate sending tool with interactive.source; text is optional and no separate summary is required. After confirmed delivery, follow the current mode's closing protocol. Do not return an empty response or duplicate the delivered card.`].join('\n\n');
  } });
}
