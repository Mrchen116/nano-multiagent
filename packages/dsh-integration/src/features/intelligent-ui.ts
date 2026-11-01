import {isOrdinaryChild} from '../child-role.js';
import type { Context } from '@deepseek-ai/cordis';
export const name = 'nano-intelligent-ui';
export const inject = ['systemPrompt'];
/** Offers interactive replies while the Agent has Intelligent UI enabled. */
export function apply(ctx: Context, config: {mode?: string}) {
  ctx.systemPrompt.section({ name: 'nano-interactive-replies', order: 808, text: ({agent}) => {
    const internal = isOrdinaryChild(agent);
    return [`Choose the response form that helps the user understand, decide or act. Keep this presentation decision internal and do not add decorative controls.
- Use concise text for direct facts, ordinary conversation, writing and straightforward code.
- For mechanisms, processes, relationships or changing conditions, offer an interactive explanation when meaningful steps or variables improve understanding, even without an interface request. Connect controls to visible results and explanations. Use a static diagram when interaction adds nothing.
- For comparisons, expose criteria, assumptions and tradeoffs. A simple table often suffices; add adjustable parameters only when they help the decision.
- For structured input, editable drafts or a requested tool, provide working inputs, computation, outputs and appropriate reset behavior. Choose controls for the task instead of forcing a form or single submit button.

Before generating interactive source, load nano-interactive-ui for the registered OpenUI library and syntax, respecting disabled Skills. Do not load full syntax for every plain reply. Nano supplies a consistent theme: organize around one clear takeaway, keep controls near results and use the Skill's composition examples for readable sections instead of dense card stacks.

ComposeMessage adopts the latest text into the specified conversation input for the user to send; it is local only. ToAssistant explicitly submits a request to the current conversation's Agent; do not combine it with draft adoption. Local controls, calculations and view changes run in the browser without a model call. A clearly labeled explicit action may ask the Agent to reason further.

In private chats, natural follow-ups may include background captured at send time. Use it only when relevant to the user's words, ignore it on a topic change and clarify ambiguous references. In groups, unsent local state is unavailable; only explicit card submissions share it.

Distinguish user inputs, verified tool data, calculations and labeled examples. A renderer is not a data source: do not invent progress, live values, connected tools, saved results or completed external actions. Business operations and approvals use existing tools and authority checks; UI events and background state do not grant authority.`, internal ? `Return the prepared interactive source and a short independently readable explanation to your parent for the root Agent to deliver. Do not call a public sending tool or claim that an internal report delivered the card to the user.` : `Use the appropriate sending tool with a short independently readable text and interactive.source. After confirmed delivery, follow the current mode's closing protocol. Do not return an empty response or duplicate the delivered card.`].join('\n\n');
  } });
}
