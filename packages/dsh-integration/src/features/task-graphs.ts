import {isInternalExecution} from '../child-role.js';
import type { Context } from '@deepseek-ai/cordis';
import type { AgentConfiguration } from '../index.js';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type {} from '../product-bridge.js';
import { taskGraphParameters } from './task-graph-schema.js';
export const name = 'nano-task-graphs';
export const inject = ['tools', 'nanoProduct', 'systemPrompt'];

/** Feature guidance is independent of the callable Task tool. */
export function apply(ctx: Context, config: {mode?: string}) {
  ctx.systemPrompt.section({ name: 'nano-task-graphs', order: 810, text: ({agent}) => isInternalExecution(agent) ? 'You execute an internal delegated task. Read Task facts when needed and report findings, actual changes, blockers and evidence to your parent. The main Agent owns public delivery, waiting arrangements and ongoing Task responsibility. Inherited Task state is context, not a fresh assignment; respect corrections and stops. Do not fabricate human consent or claim completion from a draft or internal handoff.' : [
    `Task ownership, progressive goal graphs, and changes
Task graphs are durable plans, candidate proposals, and progress records in one fixed conversation within this Agent's fixed personal or company resource space. Joining a company never publishes personal-conversation Tasks. Eligible company members can read public-group Tasks; writing requires membership in the conversation.

Start small and expand progressively: create standalone commitments or candidate proposals with mode="none" (the default single-card root), and upgrade a leaf card in place to mode="dag" or mode="explore" via apply (or pass initial operations on create) only when ordered stages or parallel alternatives are genuinely needed. Deep subtasks carry their root North Star goal (root_title and root_goal_summary); keep every child action aligned with that root objective.

Each node records its actual creator and optional human or Agent assignee. Do not impersonate a human as creator. Use the current revision and a unique request_key for each mutation; on uncertain results, retry with the exact same operation and request_key. Delete only within human-authorized scope.

Lifecycle states and event-driven execution
Use proposed, todo, doing, waiting, in_review, done, paused, backlog, and closed:
- proposed: candidate idea or frontier next step awaiting human approval (requires a non-blank description stating why this item is worth doing and what concrete action/scope will run upon approval; never auto-execute speculative work before approval). When approved (approve_task or owner confirmation), an unblocked Agent-assigned node enters doing; blocked or human-assigned nodes enter todo.
- backlog: stashed for later without reminders or nudges; promote to todo when ready.
- doing: active execution. Entering, resuming, or being reassigned into doing triggers a single event wake; make concrete progress during that turn, after which the session naturally settles to idle without idle polling loops.
- waiting: active responsibility blocked on a future time or external reply. Always record a clear wait.reason (stating the blocker or question awaiting reply). When a timed recheck or cross-day follow-up is needed, first create a native Schedule (up to 180 days out) for the current root session and pass wait={reason, schedule_id}. When waiting on a human reply or unscheduled external event, omit schedule_id (and set asked_user_id when waiting on a human member's reply) instead of creating nagging 1-hour timers.

Control and completion
Schedule reminders recheck facts; read current Task state and Inbox messages first, and do not reopen paused, backlog, closed, done, or in_review Tasks from a timer alone. /stop pauses owned doing and waiting within the product scope.

Verify the whole objective and record evidence before completion. Prefer in_review when human confirmation is expected, or done when directly verified. When presenting actionable cards in Nano IM, you may attach live task_cards=[{graph_id, node_id}] on send_message so users can act on them inline.`,
    `Deliver results and meaningful waiting questions to the Task's fixed conversation. Skip already-confirmed feedback and unchanged routine progress. A state-change system message is passive context—it does not wake Inbox or replace substantive result delivery.`,
  ].join('\n\n') });
}

/** Register the tool while gating automatic feedback on current Feature selection. */
export function registerTool(ctx: Context, configuration: (agent: Agent) => AgentConfiguration | undefined) {
  ctx.tools.register({ name: 'task_graph', description: "Query or maintain progressive task graphs and single-card tasks in IM. Use list/get to read, create to make a single-card root (default mode='none') or a multi-step goal graph (mode='dag'|'explore' with optional initial operations), apply to atomically update/expand/approve nodes and dependencies, and delete to remove an authorized graph or subtree. Supply only the fields documented for the chosen action.", parameters: taskGraphParameters,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: async (args, exec) => {
      const value=await ctx.nanoProduct.call('task_graph',args,exec);
      const response=value as {ok:boolean;result?:{graph_id:string;revision:number;feedback?:{conversation_id:string;tasks:{status:string;[key:string]:unknown}[]}}};
      const config = exec.agent && configuration(exec.agent);
      const internal = exec.agent?.session.header.origin === 'subagent';
      if(exec.agent&&config?.features?.task_graph !== false&&(args as {action:string}).action==='apply'&&response.ok===true&&response.result?.feedback?.tasks.length) {
        exec.deferContext(createUserMessage({
          source:{kind:'nano-system',actorId:exec.agent!.id,channel:'task-feedback',messageId:`task-feedback:${exec.callId}`},
          content:[{type:'text',text:[
            "The following Task changes were confirmed at the recorded revision. Check newer Task state and messages before responding. Use each Task's fixed conversation, not the latest chat or a presumed human owner; another Agent may have assigned the work.",
            JSON.stringify({graph_id:response.result.graph_id,revision:response.result.revision,...response.result.feedback}),
            ...(response.result.feedback.tasks.some(task=>task.status==='waiting')?['For waiting Tasks, communicate actual progress, the specific blocker, alternatives tried, what is needed from whom and the next check.']:[]),
            ...(response.result.feedback.tasks.some(task=>task.status==='in_review'||task.status==='done')?['For in_review or done Tasks, communicate the verified result and evidence needed to use or assess it.']:[]),
            internal?"Report this meaningful feedback to your parent with the fixed conversation for the root's public delivery. Internal send_message uses agent_id/message; accepted input is not public delivery.":'Deliver this meaningful feedback to the fixed conversation. In Global mode use send_message; a private closing note is not delivery.',
            'Skip feedback already confirmed delivered. Receipt replay or routine waiting renewal is not a reason to resend unchanged content. A failed or unknown send is not delivery and does not undo waiting or its valid Schedule. Continue other executable responsibilities after this feedback.',
          ].join('\n')}],
        }));
      }
      return value;
    },
  });
}
