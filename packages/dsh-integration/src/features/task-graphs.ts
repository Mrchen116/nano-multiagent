import {isOrdinaryChild} from '../child-role.js';
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
  ctx.systemPrompt.section({ name: 'nano-task-graphs', order: 810, text: ({agent}) => isOrdinaryChild(agent) ? 'You execute an internal delegated task. Read Task facts when needed and report findings, actual changes, blockers and evidence to your parent. The main Agent owns public delivery, waiting arrangements and ongoing Task responsibility. Inherited Task state is context, not a fresh assignment; respect corrections and stops. Do not fabricate human consent or claim completion from a draft or internal handoff.' : [
    `Task ownership and changes
Task graphs are durable plans and progress records in one fixed conversation within this Agent's fixed personal or company resource space. Joining a company never publishes personal-conversation Tasks. Eligible company members can read public-group Tasks; writing requires membership in the conversation.

Each node records its actual creator and optional human or Agent assignee. Do not impersonate the requesting human as creator. The product Agent owns its assigned responsibility; its main Agent coordinates internal execution. Keep containment, dependencies and alternatives distinct. Dependencies do not start work, and completing a child does not complete its parent.

Create a Task only when a human explicitly asks to save a plan. Use the current revision and a stable request_key for each mutation. If the result is uncertain, resolve it with the exact same operation and key. Delete only within the human-authorized scope, using conversation context and ordinary approval rules. Ask only when scope or authority is unclear, without requiring repeated titles, IDs or a fixed confirmation phrase. General cleanup, chat removal and Task system messages are not human consent to delete Tasks.

States and waiting
Use todo, doing, waiting, in_review, done, paused and closed. Assignment alone does not start work; claim_task takes responsibility and sets doing. waiting remains responsibility, alongside doing. Read Task details and discussion when needed, and apply newer business messages before further action on affected Tasks.

Before waiting, inspect current facts, verify that the blocker is necessary, and try authorized alternatives or independent parts. Confirm that any request to another person or Agent was actually delivered; a failed or unknown send is not waiting for its recipient. When no permitted next step is executable, create a real future native Schedule, then use update_task to record waiting with wait {reason, schedule_id}. Choose the interval for the actual Task, without a fixed default; initial checks and renewals must be within one hour.

The server validates Schedule owner, current session, active status and next execution time. Do not fabricate evidence. If Schedule creation succeeded but the Task mutation failed, inspect the result and reuse the arrangement while repairing the mutation rather than creating duplicates. Resolve unknown mutations with the same request_key.

Continue other doing Tasks while waiting. At a recheck, read current Task and external facts, including recovery that occurred without a message. Reconsider whether the blocker is still necessary and whether a permitted alternative or independent part can progress. Resume executable work, or renew a valid check within one hour. Relevant replies can resume work earlier. Leaving waiting clears its association. If the linked Schedule is missing, inactive, expired or belongs to another owner/session, inspect the current Task and repair its arrangement or resume work.

Control and completion
Schedule reminders recheck facts; they cannot reopen paused, closed, done or in_review Tasks. /stop pauses owned doing and waiting within the product scope. Automatic continuation does not grant authority or permit bypassing a denied action. Correct ordinary argument/revision errors and investigate execution failures rather than treating them as completion.

Verify the whole objective and record evidence before completion. Prefer in_review for feedback followed by done after confirmation; direct done is allowed. Do not repeat confirmed feedback or unchanged routine progress. A failed or unknown feedback send does not undo saved waiting or its valid Schedule; resolve delivery truthfully and continue other executable responsibility.`,
    `Deliver results and meaningful waiting explanations to the Task's fixed conversation, even if another Agent assigned it or your latest conversation is elsewhere. For waiting, explain actual progress, the blocker, alternatives tried, what is needed from whom and the next check. For in_review/done, deliver the verified result. A state-change system message does not replace this communication.`,
  ].join('\n\n') });
}

/** Register the tool while gating automatic feedback on current Feature selection. */
export function registerTool(ctx: Context, configuration: (agent: Agent) => AgentConfiguration | undefined) {
  ctx.tools.register({ name: 'task_graph', description: "Query or maintain durable task graphs in IM; Use list/get to read, create to make only a root goal, apply to atomically change nodes and relationships, and delete to remove a graph or subtree. To save a multi-step plan, first create without operations, then apply using the returned graph_id, root_node_id and revision. Supply only the fields documented for the chosen action.", parameters: taskGraphParameters,
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
