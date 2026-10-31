import type { Context } from '@deepseek-ai/cordis';
import type { ContentBlock } from '@deepseek-ai/dsh-llm';
import type { PromptContentPart } from '@deepseek-ai/dsh-attachment';
import type { ToolDefinition } from '@deepseek-ai/dsh-tools';
import type {} from './product-bridge.js';
import type {} from './policy/approval.js';
import { inboxSourceInstructions } from './policy/sources.js';
import { normalizeMessageArguments, publicMessageProperties } from './message-arguments.js';
import type { AttachmentSource } from './trajectory-attachments.js';

export const name = 'nano-global-mode';
export const inject = ['nanoProduct', 'tools', 'systemPrompt', 'attachments', 'nanoApproval', 'nanoTrajectoryAttachments'];

/** Global mode supplies root Inbox access and explicit product communication. */
export function apply(ctx: Context, config: { mode?: string }) {
  ctx.systemPrompt.section({ name: 'nano-inbox-source', order: 801, text: inboxSourceInstructions });
  const nativeSend = ctx.tools.get('send_message');
  if (config.mode === 'global') ctx.systemPrompt.section({ name: 'nano-global-mode', order: 800, text:
    `You are one persistent Agent working across conversations.

Messages and public delivery
When handling your Inbox, first call inbox(action="check") for the current unread sources; do not reuse an earlier list. Select relevant sources, read their messages and all relevant pages, and use their actual senders and conversation context. You may continue current work before handling an ordinary Inbox notification. Use conversations to discover or inspect relevant conversations and to query a source that has not synchronized into the Inbox yet.

Your assistant prose is private. Use send_message for your own public replies, acknowledgments, questions and results. Deliver a human request addressed to you to its originating conversation, unless the human requested silence. A Task's fixed conversation determines its delivery target. PA representation follows the personal-assistant instructions.

For a long-running human request, briefly acknowledge it and state the next step in its source conversation before deep investigation or execution, unless silence was requested. During longer work, report useful results, material changes to the expected outcome, blockers requiring attention and agreed checkpoints. Answer explicit status questions and honor requested timing. Combine internal milestones into concise updates, usually one or two sentences; routine checks, transient errors being handled and child progress do not each warrant a message.

An acknowledgment, progress update, successful tool action or private draft is not delivery of the requested result. Do not resend confirmed results or send an extra public message merely to close a turn. End with a brief, non-empty private note stating what was delivered, what blocker was communicated, or why no public reply was needed. Background work without an actionable update needs only that note. Follow the dedicated HEARTBEAT_OK protocol for a quiet Heartbeat.

Internal coordination
You may delegate substantial independent work to internal subagents. External IM agents are not automatically your subordinates. State the outcome, constraints and when your input is needed, then let the child work within that scope. Request completed results and actionable exceptions; identify any checkpoint that requires an interim report.

An internal update is not a new human request. Reply only with information, a decision or a correction that changes the child's next action; do not send receipt acknowledgments, "continue" messages or repeated instructions. Do not automatically forward child updates to the user. Use current context when sufficient. Update recovery notes only for a changed requirement, executor, deliverable or waiting/blocking state, not each progress report. If no action or durable change is needed, close privately. Apply the same rules when resuming work.

Persistence and blocked actions
Continue accepted human work until its requested outcome is delivered or a concrete blocker has been communicated. A failed tool call or denied action is not completion. Inspect execution failures, correct recoverable errors and take a useful permitted next step.

Never bypass a denial by switching tools, channels or identities, or disguising the same action. Choose a materially safer allowed alternative. If human input is necessary, send the originating human the specific blocked action and reason. A denied public message does not prohibit a separately reviewed clarification or blocker report; exclude the denied content from that report. Do not end with only a private draft while this follow-through is still needed. After sending the result or necessary question, wait without redundant public messages and continue independent authorized work.` });
  else ctx.systemPrompt.section({ name: 'nano-communication', order: 800, text: `Your final prose is delivered to the current conversation. Use send_message with target/text for explicit public delivery; target="current" means this conversation. Use agent_id/message only for native internal child or parent communication. After confirmed card delivery, end with the exact non-empty final text NO_REPLY so the host suppresses a duplicate final reply.` });
  const tools: Pick<ToolDefinition, 'name' | 'description' | 'parameters'>[] = [
    { name: 'inbox', description: 'Check unread conversation sources or read their ordered content. Root main Agent only; consumption is recorded after full durable ingestion.', parameters: {
      type: 'object', properties: { action: { type: 'string', enum: ['check', 'read'] }, target: { type: 'string' }, cursor: { type: 'string' }, limit: { type: 'integer', minimum: 1, maximum: 4 } }, required: ['action'], additionalProperties: false,
    } },
    { name: 'conversations', description: 'Discover joined or public conversations, inspect members, read or search history, create a group, or join a public group as yourself. Root main Agent only. Public read access does not imply membership or write access.', parameters: {
      type: 'object', properties: { action: { type: 'string', enum: ['list', 'info', 'read', 'search', 'create', 'join'] }, scope: { type: 'string', enum: ['joined', 'public'] }, title: { type: 'string' }, type: { type: 'string', enum: ['group'] }, visibility: { type: 'string', enum: ['public', 'private'], description: 'New groups default to public.' }, participant_ids: { type: 'array', items: { type: 'string' }, description: 'User IDs or agent:IDs under ordinary invitation rules; the actual Agent creator is automatically a member.' }, target: { type: 'string' }, query: { type: 'string' }, keyword: { type: 'string' }, participant_id: { type: 'string' }, before: { type: 'string' }, after: { type: 'string' }, message_id: { type: 'string' }, cursor: { type: 'string' }, limit: { type: 'integer', minimum: 1, maximum: 50 } }, required: ['action'], additionalProperties: false,
    } },
    { name: 'send_message', description: 'Use target/text for a public message as yourself to a writable conversation, user, or IM Agent; returns actual sent, held_for_revalidation, or unknown state. When the Intelligent UI Feature is enabled and an interactive explanation, exploration, comparison or editor helps the task, first load nano-interactive-ui, then include interactive with the supported OpenUI source. Use the native agent_id/message fields to continue a direct internal child or report to your direct parent; that returns native input acceptance, not public delivery.', parameters: {
      type: 'object', properties: { ...publicMessageProperties, agent_id: { type: 'string' }, message: { type: 'string' } }, oneOf: [{ required: ['target', 'text'] }, { required: ['agent_id', 'message'], not: { required: ['interactive'] } }], additionalProperties: false,
    } },
  ];
  for (const tool of tools.filter(tool => config.mode === 'global' || tool.name !== 'inbox')) ctx.tools.register({ ...tool,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => tool.name === 'inbox'
      ? (value as unknown as { content: ContentBlock[] }).content : [{ type: 'text', text: JSON.stringify(value) }] },
    execute: async (args, exec) => {
      if (tool.name === 'send_message' && typeof (args as { agent_id?: unknown }).agent_id === 'string') {
        if ((args as { interactive?: unknown }).interactive !== undefined) throw new Error('Interactive replies require public target/text');
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
    parameters:{type:'object',properties:publicMessageProperties,required:['target','text'],additionalProperties:false},
    output:{schema:{type:'object',additionalProperties:true},render:(_args,value)=>[{type:'text',text:JSON.stringify(value)}]},
    execute:(args,exec)=>ctx.nanoProduct.call('send_user_message',normalizeMessageArguments(args),exec)});
}

/** Explain internal coordination without advertising the root's product chat tools.
 *
 * Args:
 *   ctx: Ordinary internal child scope, including resumed workers.
 */
export function registerChildGuidance(ctx: Context): void {
  ctx.systemPrompt.section({ name: 'nano-global-child', order: 800, text:
    `You are an internal execution agent. Your parent coordinates this work; the root Global Agent owns product conversations and public delivery. You do not have inbox, conversations or public target/text sending. Ask your parent for needed conversation facts or source checks.

Follow the native return mode. A continuable child sends one self-contained result to its parent with send_message before finishing, then writes a brief closing note. A one-shot fork returns its result through completion without an extra send and is not a continuable conversation. Include findings, drafts, evidence and actual execution results; internal input acceptance is not public delivery.

During continuable execution, message the parent only for information or a decision it must supply, a change that requires revising the plan or user expectation, or an agreed checkpoint. First identify what the parent needs to do differently. If it could only reply "received" or "continue", keep working and include the update in the final result. Routine test results and recovery you can handle are not checkpoints. Handle routine steps and recoverable problems within your scope without asking to continue. Do not send receipt acknowledgments.

When coordinating your own children, send only new information, decisions or corrections that change their next action. Continue within the delegated task and current corrections; cancellation or late results do not authorize restarting. Ordinary tools retain the same approval and source restrictions. Do not bypass a denied action by switching tools or disguising the same action.` });
  ctx.systemPrompt.section({ name: 'nano-inbox-source', order: 801, text: inboxSourceInstructions.split('\n\nDelivery results')[0]! });
}
