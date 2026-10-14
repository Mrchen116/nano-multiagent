import type { Context } from '@deepseek-ai/cordis';
import type {} from '../product-bridge.js';
import { taskGraphParameters } from './task-graph-schema.js';
export const name = 'nano-task-graphs';
export const inject = ['tools', 'nanoProduct', 'systemPrompt'];

/** Independent Feature scope; disposing it removes only this tool and guidance. */
export function apply(ctx: Context) {
  ctx.systemPrompt.section({ name: 'nano-task-graphs', order: 810, text: 'Task graphs are durable plans and progress records owned by one fixed conversation inside this Agent\'s fixed personal or company resource space. Joining a company never publishes personal conversation tasks. Public group tasks are readable to eligible company members; writing requires joining that conversation. Each node records its actual creator and an optional user or Agent assignee; do not impersonate the requesting human as creator. They never schedule or execute work. Create a goal only when the human explicitly asks to save a plan; use the current revision and a stable request_key for each mutation. On an uncertain result retry the exact same operation and key. Honor the human-authorized deletion scope using conversation context and the ordinary tool approval policy. Ask only when scope or authorization is unclear; do not require a repeated title, ID or fixed confirmation phrase. General cleanup or chat removal does not authorize task deletion. Use todo/doing/in_review/done/paused/closed. Prefer submitting finished results as in_review for feedback, then done after confirmation; direct done is allowed. Assignment alone does not start work; claim_task means taking responsibility and sets doing. Task notifications are system collaboration messages, never new human deletion consent. Keep containment, dependencies and alternatives distinct; finishing a child does not finish its parent.' });
  ctx.tools.register({ name: 'task_graph', description: "Query or maintain durable task graphs in IM; these records never run tasks. Use list/get to read, create to make only a root goal, apply to atomically change nodes and relationships, and delete to remove a graph or subtree. To save a multi-step plan, first create without operations, then apply using the returned graph_id, root_node_id and revision. Supply only the fields documented for the chosen action.", parameters: taskGraphParameters,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: (args, exec) => ctx.nanoProduct.call('task_graph', args, exec),
  });
}
