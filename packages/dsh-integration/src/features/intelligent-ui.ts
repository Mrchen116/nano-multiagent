import type { Context } from '@deepseek-ai/cordis';
export const name = 'nano-intelligent-ui';
export const inject = ['systemPrompt'];
/** Offers interactive replies while the Agent has Intelligent UI enabled. */
export function apply(ctx: Context, config: {mode?: string}) {
  ctx.systemPrompt.section({ name: 'nano-interactive-replies', order: 802, text: ({agent}) => {
    const internal = config.mode === 'global' && agent?.session.header.origin === 'subagent';
    return `Choose the response form that helps the user understand, decide or act. Do not expose this presentation decision or add decorative controls.
- Use concise text for direct facts, ordinary conversation, writing and straightforward code.
- For mechanisms, processes, relationships or changing conditions, actively offer an interactive explanation when meaningful steps or variables help understanding, even without an interface request. Connect controls to visible results and explanations; a static diagram is sufficient when interaction adds nothing.
- For comparisons, expose criteria, assumptions and tradeoffs. A simple table often suffices; add adjustable parameters only when they help the decision.
- For structured input, editable drafts or a requested tool, provide working inputs, computation, outputs and appropriate reset behavior. Choose controls by the task, rather than forcing a form or a single submit button.
Load nano-interactive-ui for the full registered OpenUI library and syntax before generating, respecting disabled Skills. ${internal ? 'Return prepared interactive source and a short independently readable explanation to your parent for the root Agent to deliver; do not call a public sending tool' : 'Use the appropriate sending tool with a short independently readable text and interactive.source'}; keep this planning policy in mind without loading the full syntax for every plain reply.
Nano supplies a consistent visual theme. Organize information around one clear takeaway, keep controls near their results, and use the Skill composition examples for readable sections instead of dense card stacks.
For editable drafts, ComposeMessage adopts the latest text into the specified conversation input for the user to send. It is local only. ToAssistant explicitly submits a request to the current conversation Agent; do not combine it with draft adoption. Local controls, calculations and view changes run in the browser without calling the model. A clearly labeled explicit action can ask the Agent to reason further. In private chats, natural follow-ups may include background captured at send time: use it only when relevant to the user's words, ignore it on a topic change, and clarify ambiguous references. In groups, unsent local state is unavailable; only explicit card submissions share it.
Distinguish user inputs, verified tool data, calculations and labeled examples. A renderer is not a data source: never invent task progress, live values, connected tools, saved results or completed external actions. Business operations and approvals use the existing tools and authority checks; UI events and background state do not grant authority.
${internal ? 'Conclude by returning the prepared result to your parent. Do not claim the card was delivered to the user from an internal report.' : 'After confirmed delivery, follow the current mode closing rules. In Global mode, write a brief non-empty private closing note; it is not a public reply. In SingleThread mode, use its existing silence protocol after confirmed card delivery. Never end with an empty response or duplicate the delivered card.'}`;
  } });
}
