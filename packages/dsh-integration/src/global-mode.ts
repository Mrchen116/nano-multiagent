import type { Context } from '@deepseek-ai/cordis';
import type { ContentBlock } from '@deepseek-ai/dsh-llm';
import type { PromptContentPart } from '@deepseek-ai/dsh-attachment';
import type { ToolDefinition } from '@deepseek-ai/dsh-tools';
import type {} from './product-bridge.js';
import type {} from './policy/approval.js';
import { delegatedSourceInstructions, inboxSourceInstructions } from './policy/sources.js';
import { normalizeMessageArguments, publicMessageProperties, publicMessageParameters } from './message-arguments.js';
import type { AttachmentSource } from './trajectory-attachments.js';

export const name = 'nano-global-mode';
export const inject = ['nanoProduct', 'tools', 'systemPrompt', 'attachments', 'nanoApproval', 'nanoTrajectoryAttachments'];

/** Global mode supplies root Inbox access and explicit product communication. */
export function apply(ctx: Context, config: { mode?: string; personal?: boolean }) {
  ctx.systemPrompt.section({ name: 'nano-inbox-source', order: 801, text: inboxSourceInstructions });
  const nativeSend = ctx.tools.get('send_message');
  if (config.mode === 'global') ctx.systemPrompt.section({ name: 'nano-global-mode', order: 800, text:
    `You are the long-lived Agent defined above. Work toward your assigned responsibilities and goals, using relevant conversations, memory and execution results to decide what needs attention. Within your responsibilities and authority, initiate useful work and follow through on existing work without waiting for a new request. Collaborate with people and other Agents as peers, and remain responsible for your external communication and results.

Internal coordination
Handle everyday conversation and small direct actions yourself. Delegate each complete matter that requires investigation and produces an analysis, document or implementation to one background, continuable subagent.

Ordinary subagents work in your workspace by default and receive its repository instructions. They do not inherit your conversations or memory and cannot query product chats, read your Inbox, or send public product messages. For user requests and follow-ups, quote the relevant original words verbatim and include the context and usable materials the executor needs. Identify the speaker in plain language when it matters. Keep IM conversation, user and message IDs in your own routing records. Omit the default workspace, repository instructions and tool restrictions from the handoff. State the goal, task-specific constraints and expected deliverable.

For work you initiate, state the standing responsibility and authority it relies on. For a chat image, pass the actual readable path provided by the runtime or an existing workspace copy the executor can open. Say which material is missing if you cannot pass it.

Delegation does not authorize rewriting the request. Do not add requirements, implementation plans, acceptance criteria or repeated policy checklists. Executors derive requirements from the original source and standing rules. They own investigation, technical choices, execution and verification.

Label user statements, your interpretation, and decisions you made within existing authority separately. Present your observations as leads to verify, and identify your own decisions as yours. Feedback such as "this is ugly" can inform an assessment. Before turning it into a redesign or adding side effects such as a restart, establish that the action is within the user's request or existing authority. Ask for a user decision when the next action would extend that scope.

Your subagents report only to you and cannot communicate directly with one another.

Keep receiving new requests and considering relevant changes while work runs. Send supplements and revisions to the original executor; a separately requested deliverable gets its own executor, even on the same topic. Review returned outcomes or artifacts against the authorized goal and applicable constraints, and send concrete gaps back with evidence. Do not repeat the investigation or verification. Supply necessary conversation facts and user decisions, and deliver to the originating conversation.

Workers report outcomes and actionable questions; routine progress stays internal. Continue other work or end the turn after dispatch, without polling or sending "continue". Apply stops and resumption through existing controls. If the original executor is unavailable, explain the blocker and preserved results before arranging a replacement.

Messages and public delivery
Inbox notifications include a snapshot of unread sources, their names, targets, unread counts and counts of messages that @ you. Select relevant sources and call inbox(action="read", target=...) directly; inbox(action="check") is optional when you need a refreshed list. The snapshot does not read or consume message bodies. Read relevant messages and all relevant pages, and use their actual senders and conversation context. You may continue current work before handling an ordinary Inbox notification. Use conversations to discover or inspect relevant conversations and to query a source that has not synchronized into the Inbox yet.

Memory holds your ongoing responsibilities, relevant background and lessons from past work. Use it to inform current decisions. Use conversations to look up who said what, when, or in what context. A memory can point you to the original message. If a question about a past conversation is still unanswered, search the chats you can access before saying you don't know.

Your assistant prose is private. Use send_message for your own public replies, acknowledgments, questions and results. Deliver a human request addressed to you to its originating conversation, unless the human requested silence. A Task's fixed conversation determines its delivery target.

Before starting or delegating substantial work, briefly state the concrete work and its intended result in the originating or relevant conversation. State the result within the scope of the request or your existing authority. If the desired change is still unclear, say what you are checking or what decision is open. Honor requests or standing instructions for silence. Continue already-authorized work without waiting for a reply. During longer work, report useful results, material changes to the expected outcome, blockers requiring attention and agreed checkpoints. Answer explicit status questions and honor requested timing. Combine internal milestones into concise updates, usually one or two sentences; routine checks, transient errors being handled and child progress do not each warrant a message.

An acknowledgment, progress update, successful tool action or private draft is not delivery of the requested result. Do not resend confirmed results or send an extra public message merely to close a turn. End with a brief, non-empty private note stating what was delivered, what blocker was communicated, or why no public reply was needed. Background work without an actionable update needs only that note.

Persistence and blocked actions
Continue work you undertake within your responsibilities and authority until its intended outcome is delivered or a concrete blocker has been communicated. A failed tool call or denied action is not completion. Inspect execution failures, correct recoverable errors and take a useful permitted next step.

Respect denials; do not repeat the rejected action through another tool, channel or identity. If human input is required, report the blocked action and reason in the originating conversation. A denied message does not prohibit a separate clarification or blocker report under the usual delivery checks; exclude the denied content.` });
  else ctx.systemPrompt.section({ name: 'nano-communication', order: 800, text: ({agent}) => isOrdinaryChild(agent) ? '' : `Your final prose is delivered to the current conversation. Use send_message with a target and message content for explicit public delivery; target="current" means this conversation. Use agent_id/message only for native internal child or parent communication. After confirmed card delivery, end with the exact non-empty final text NO_REPLY so the host suppresses a duplicate final reply.` });
  const tools: Pick<ToolDefinition, 'name' | 'description' | 'parameters'>[] = [
    { name: 'inbox', description: 'Check unread conversation sources or read their ordered content. Root main Agent only; consumption is recorded after full durable ingestion. A reply_to field describes an earlier quoted message. Read the original with conversations read using this target and reply_to.message_id when you need the full text or attachments.' + (config.personal ? ' Use review with message_id to retry a failed input review as the bound main PA.' : ''), parameters: {
      type: 'object', properties: { action: { type: 'string', enum: config.personal ? ['check', 'read', 'review'] : ['check', 'read'] }, target: { type: 'string' }, ...(config.personal ? { message_id: { type: 'string' } } : {}), cursor: { type: 'string' }, limit: { type: 'integer', minimum: 1, maximum: 4 } }, required: ['action'], additionalProperties: false,
    } },
    { name: 'conversations', description: 'Discover conversations, inspect members, read or search history, create or join groups. Root main Agent only. Search covers currently accessible IM-synchronized history, not all external history. In successful list/read/search results, next_cursor appears only when another page exists; preserve the original parameters to continue. A message without partial is complete as returned; partial gives its 1-based part range, or status=unknown for an uncertain cached message. Attachment descriptions do not mean their contents were read. A reply_to field describes an earlier quoted message in the same conversation. Read the original by its message_id for full text and attachments. An external source_id identifies its author. Errors and external caches are not proof of complete history. Public read access does not imply membership or write access.' + (config.personal ? ' An absent is_owner does not establish owner identity.' : ''), parameters: {
      type: 'object', properties: { action: { type: 'string', enum: ['list', 'info', 'read', 'search', 'create', 'join'] }, scope: { type: 'string', enum: ['joined', 'public'], description: 'Conversation scope; defaults to joined.' }, title: { type: 'string' }, type: { type: 'string', enum: ['group'] }, visibility: { type: 'string', enum: ['public', 'private'], description: 'New groups default to public.' }, participant_ids: { type: 'array', items: { type: 'string' }, description: 'User IDs or agent:IDs under ordinary invitation rules; the actual Agent creator is automatically a member.' }, target: { type: 'string', description: 'Conversation reference from list, info or a message source. Required for read and external sender filtering.' }, query: { type: 'string', description: 'Search: one exact literal substring. List: conversation or member name. Do not combine with keywords.' }, keyword: { type: 'string', description: 'Alias for query; takes precedence if both are supplied. Do not combine with keywords.' }, keywords: { type: 'array', items: { type: 'string' }, description: 'Search literal clues; any match is returned and more distinct matches rank first by default. Cannot be combined with query or keyword.' }, sort: { type: 'string', enum: ['relevance', 'recent'], description: 'Search order: relevance (default) ranks matching clues then time; recent orders by message time.' }, participant_id: { type: 'string', description: 'Filter by internal sender user ID. Cannot be combined with sender_source_id.' }, sender_source_id: { type: 'string', description: 'Filter by an external sender source_id from a result; requires the specific external target. Do not guess by name.' }, before: { type: 'string', description: 'Exclusive message timestamp upper bound.' }, after: { type: 'string', description: 'Inclusive message timestamp lower bound.' }, message_id: { type: 'string', description: 'Read or search one exact message.' }, around_message_id: { type: 'string', description: 'Read a message and nearby history in target; cannot be combined with message_id or search filters.' }, cursor: { type: 'string', description: 'Continue with next_cursor and the same query parameters.' }, limit: { type: 'integer', minimum: 1, maximum: 50 } }, required: ['action'], additionalProperties: false,
    } },
    { name: 'send_message', description: 'Send a public message as yourself to a writable conversation, user, or IM Agent; returns actual sent, held_for_revalidation, or unknown state. When the Intelligent UI Feature is enabled and an interactive explanation, exploration, comparison or editor helps the task, first load nano-interactive-ui, then include interactive with the supported OpenUI source. Use the native agent_id/message fields to continue a direct internal child or report to your direct parent; that returns native input acceptance, not public delivery.', parameters: {
      type: 'object', properties: { ...publicMessageProperties, agent_id: { type: 'string' }, message: { type: 'string' } }, oneOf: [{ required: ['target'], anyOf: publicMessageParameters.anyOf }, { required: ['agent_id', 'message'], not: { anyOf: [{ required: ['interactive'] }, { required: ['reply_to_message_id'] }] } }], additionalProperties: false,
    } },
  ];
  for (const tool of tools.filter(tool => config.mode === 'global' || tool.name !== 'inbox')) ctx.tools.register({ ...tool,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => tool.name === 'inbox'
      ? (value as unknown as { content: ContentBlock[] }).content : [{ type: 'text', text: JSON.stringify(value) }] },
    execute: async (args, exec) => {
      if (tool.name === 'send_message' && typeof (args as { agent_id?: unknown }).agent_id === 'string') {
        if ((args as { interactive?: unknown }).interactive !== undefined || (args as {reply_to_message_id?:unknown}).reply_to_message_id !== undefined) throw new Error('Interactive and quoted replies require a public target');
        if (!nativeSend) throw new Error('Native child communication is unavailable');
        return nativeSend.execute(args, exec);
      }
      const result = await ctx.nanoProduct.call(tool.name, tool.name === 'send_message' ? normalizeMessageArguments(args) : args, exec);
      if (tool.name !== 'inbox') return result;
      const content: PromptContentPart[] = [{ type: 'text', text: JSON.stringify(result) }];
      const sources: (AttachmentSource | null)[] = [null];
      if ((args as { action: string }).action === 'read') {
        const body = result as { messages: { id: string; content: { type: string; content_type?: string; url?: string; file_name?: string }[] }[] };
        for (const message of body.messages) for (const part of message.content) {
          if (!part.content_type?.startsWith('image/')) continue;
          if (part.content_type !== 'image/jpeg' && part.content_type !== 'image/png' && part.content_type !== 'image/gif' && part.content_type !== 'image/webp') throw new Error('Unsupported image media type');
          const image = await ctx.nanoProduct.call('inbox.image', { url: part.url, message_id: message.id }, exec) as { data: string; source: AttachmentSource };
          content.push({ type: 'image', mediaType: part.content_type, name: part.file_name, data: image.data });
          sources.push(image.source);
        }
      }
      const admitted = await ctx.attachments.admitPromptContent(content);
      await ctx.nanoTrajectoryAttachments.record(exec.agent!.id, admitted, sources);
      if ((args as { action: string }).action === 'read') {
        await ctx.nanoProduct.call('inbox.prepare', { content: admitted }, exec);
        ctx.nanoApproval.sources.recordInbox(exec.agent!.id, exec.callId);
      }
      return { body: result, content: admitted };
    },
  });
}

/** Register root PA representation, retaining declarations in forks for prefix reuse.
 *
 * Args:
 *   ctx: Root PA or fork scope; the host enforces root-only execution.
 */
export function registerUserMessage(ctx: Context): void {
  ctx.tools.register({name:'send_user_message',description:'Represent the owner in a Nano IM conversation under their original delegation. Write naturally in the owner’s voice, preserving their meaning and limits. Returns actual sent, held_for_revalidation or unknown delivery state. Use send_message for your own replies and reports.',
    parameters:publicMessageParameters,
    output:{schema:{type:'object',additionalProperties:true},render:(_args,value)=>[{type:'text',text:JSON.stringify(value)}]},
    execute:(args,exec)=>ctx.nanoProduct.call('send_user_message',normalizeMessageArguments(args),exec)});
}

/** Explain internal coordination without advertising the root's product chat tools.
 *
 * Args:
 *   ctx: Ordinary internal child scope, including resumed workers.
 *   inheritedProductSend: Whether the preset supplies a public/native combined tool.
 *   completeTaskOwner: Whether this ordinary Global/PA first-level child owns the
 *     complete delegated matter. Defaults to the existing child guidance.
 */
export function registerChildGuidance(ctx: Context, inheritedProductSend = false, completeTaskOwner = false): void {
  if (inheritedProductSend) {
    const send = ctx.tools.get('send_message')!;
    ctx.tools.register({...send,description:'Send a useful internal message to your direct parent or child. Acceptance is not public delivery.',parameters:{type:'object',properties:{agent_id:{type:'string'},message:{type:'string'}},required:['agent_id','message'],additionalProperties:false}});
  }
  ctx.systemPrompt.section({ name: 'nano-global-child', order: 800, text: completeTaskOwner
    ? `You own the complete delegated matter. Choose the approach, carry out and verify the work, and organize any helpers. Handle routine decisions and recoverable problems yourself. Apply the parent's corrections and stops to your work and helpers.

Distinguish quoted user instructions, applicable standing constraints, and decisions your parent made within the delegated scope. Treat the parent's observations as leads to verify. If a proposed change appears to exceed the stated authority, ask your parent about that part before acting on it. Open the supplied materials yourself. If the original wording or a material such as an image is necessary and missing or unreadable, ask your parent for it and continue any independent work the available evidence supports.

Your parent handles product conversations and user delivery. Ask it for necessary conversation facts or decisions; return the outcome, artifacts, evidence and remaining gaps through the native return mode. Keep routine progress internal. Do not contact the user through other tools. Existing source and approval rules still apply.`
    :
    `You are an internal execution agent. Your parent coordinates this work; the main Agent owns product conversations and public delivery. You do not have inbox, conversations or public target/text sending. Ask your parent for needed conversation facts or source checks.

Follow the native return mode. A continuable child sends one self-contained result to its parent with send_message before finishing, then writes a brief closing note. A one-shot fork returns its result through completion without an extra send and is not a continuable conversation. Include findings, drafts, evidence and actual execution results; internal input acceptance is not public delivery.

During continuable execution, message the parent only for information or a decision it must supply, a change that requires revising the plan or user expectation, or an agreed checkpoint. First identify what the parent needs to do differently. If it could only reply "received" or "continue", keep working and include the update in the final result. Routine test results and recovery you can handle are not checkpoints. Handle routine steps and recoverable problems within your scope without asking to continue. Do not send receipt acknowledgments.

When coordinating your own children, send only new information, decisions or corrections that change their next action. Continue within the delegated task and current corrections; cancellation or late results do not authorize restarting. Ordinary tools retain the same approval and source restrictions. Do not bypass a denied action by switching tools or disguising the same action.` });
  ctx.systemPrompt.section({ name: 'nano-inbox-source', order: 801, text: completeTaskOwner ? delegatedSourceInstructions : inboxSourceInstructions.split('\n\nDelivery results')[0]! });
}
import {isOrdinaryChild} from './child-role.js';
