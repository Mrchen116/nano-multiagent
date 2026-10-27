import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type {} from '../product-bridge.js';
import { taskGraphParameters } from './task-graph-schema.js';
export const name = 'nano-task-graphs';
export const inject = ['tools', 'nanoProduct', 'systemPrompt'];

/** Feature guidance is independent of the callable Task tool. */
export function apply(ctx: Context) {
  ctx.systemPrompt.section({ name: 'nano-task-graphs', order: 810, text: [
    "Task graphs are durable plans and progress records owned by one fixed conversation inside this Agent's fixed personal or company resource space. Joining a company never publishes personal conversation tasks. Public group tasks are readable to eligible company members; writing requires joining that conversation.",
    'Each node records its actual creator and an optional user or Agent assignee; do not impersonate the requesting human as creator. Task state records responsibility; native execution continues your assigned doing tasks across scopes and depths. Dependencies do not automatically execute work.',
    'Create a Task only when the human explicitly asks to save a plan; use the current revision and a stable request_key for each mutation. On an uncertain result retry the exact same operation and key. Honor the human-authorized deletion scope using conversation context and the ordinary tool approval policy. Ask only when scope or authorization is unclear; do not require a repeated title, ID or fixed confirmation phrase. General cleanup or chat removal does not authorize task deletion.',
    'Use todo/doing/waiting/in_review/done/paused/closed. waiting is ongoing responsibility, peer to doing. Before waiting, inspect current facts, reconsider whether the blocker is necessary, and try authorized alternatives or independent parts. When genuinely blocked on a delivered request or an external prerequisite, create a real future native Schedule first, then update_task with status waiting and wait {reason, schedule_id}. A message that failed or has unknown delivery is not waiting for the recipient.',
    'Choose the recheck interval for the actual task, without a fixed default. The next check must be within one hour, both for initial waiting and renewals. The server validates schedule ownership, current session, active status and next execution time; do not fabricate evidence. If Schedule creation succeeded but Task mutation failed, inspect the actual result and reuse the arrangement while repairing the mutation; do not blindly create duplicates. Resolve unknown writes using the same request_key.',
    'For independent ongoing work, use a native continuable child and bind_execution on its canonical Task. A running bound child owns that execution; coordinate and deliver its result instead of doing the same work again. Forward revised requirements to the existing child with native send_message, retain its messageId, then rebind with current request_revision and correction_source_ref. A paused/reassigned/deleted Task cancels its bound execution; an old child result cannot reopen it. Failed or unknown child state needs coordination; waiting still needs a real Schedule.',
    'Continue other doing tasks while waiting. If a Schedule is deleted, disabled, expired or belongs to a previous owner/session, repair the arrangement or resume doing. At every recheck, read the current Task and external facts: recovery may have happened without a message. Even if the original blocker remains, reassess whether it is still necessary and whether another permitted route or independent part can progress. Only continue waiting when no such step is executable, with a renewed check within one hour. A relevant reply can resume early; leaving waiting clears its association.',
    'Schedule wakeups only recheck facts; they are not consent and cannot reopen paused/closed/done/in_review tasks. /stop pauses owned doing and waiting in the product scope. A denied action must not be bypassed; correct ordinary argument/revision errors, inspect genuine execution failures, and communicate a concrete blocker when needed.',
    "After confirmed waiting, deliver meaningful progress, the blocker, alternatives tried, what is needed from whom, and the next check to the Task's fixed conversation, including Tasks assigned by another Agent. In Global mode this requires send_message; private prose is not delivery. Do not repeat already confirmed feedback or unchanged status at each recheck. A failed or unknown feedback send does not undo the saved waiting state: keep its Schedule and resolve delivery truthfully.",
    'Prefer submitting finished results as in_review for feedback, then done after confirmation; direct done is allowed. Verify the whole objective and actually deliver the result to the fixed conversation. Assignment alone does not start work; claim_task means taking responsibility and sets doing. Task notifications are system collaboration messages, never new human deletion consent. Keep containment, dependencies and alternatives distinct; finishing a child does not finish its parent.',
  ].join('\n') });
}

/** Register the tool while gating automatic feedback on current Feature selection. */
export function registerTool(ctx: Context, enabled: (agent: Agent) => boolean) {
  ctx.tools.register({ name: 'task_graph', description: "Query or maintain durable task graphs in IM; Use list/get to read, create to make only a root goal, apply to atomically change nodes and relationships, and delete to remove a graph or subtree. To save a multi-step plan, first create without operations, then apply using the returned graph_id, root_node_id and revision. Supply only the fields documented for the chosen action.", parameters: taskGraphParameters,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: async (args, exec) => {
      const value=await ctx.nanoProduct.call('task_graph',args,exec);
      const response=value as {ok:boolean;result?:{graph_id:string;revision:number;feedback?:{conversation_id:string;tasks:unknown[]}}};
      if(exec.agent&&enabled(exec.agent)&&(args as {action:string}).action==='apply'&&response.ok===true&&response.result?.feedback?.tasks.length) {
        exec.deferContext(createUserMessage({
          source:{kind:'nano-system',actorId:exec.agent!.id,channel:'task-feedback',messageId:`task-feedback:${exec.callId}`},
          content:[{type:'text',text:[
            'The following Task changes were confirmed at the recorded revision. Deliver the meaningful result or waiting explanation to this fixed conversation, not the latest chat or a presumed human owner. An Agent may have assigned this work.',
            'For waiting, explain actual progress, the specific blocker, what you tried, what is needed from whom, and the next check. For in_review/done, deliver the verified result. In Global mode use send_message; a private closing note is not public delivery.',
            'First account for any newer Task state or messages. Skip feedback already confirmed delivered; receipt replay and routine waiting renewal are not reasons to resend unchanged content. A failed or unknown send is not delivery and does not undo waiting or its Schedule. Continue other executable responsibilities after this feedback.',
            JSON.stringify(response.result),
          ].join('\n')}],
        }));
      }
      return value;
    },
  });
}
