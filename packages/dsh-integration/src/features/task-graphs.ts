import type { Context } from '@deepseek-ai/cordis';
import type {} from '../product-bridge.js';
import { taskGraphParameters } from './task-graph-schema.js';
export const name = 'nano-task-graphs';
export const inject = ['tools', 'nanoProduct', 'systemPrompt'];

/** Independent Feature scope; disposing it removes only this tool and guidance. */
export function apply(ctx: Context) {
  ctx.systemPrompt.section({ name: 'nano-task-graphs', order: 810, text: 'Task graphs are durable company-shared plans and progress records. They never schedule or execute work. Create a goal only when the human explicitly asks to save a plan; use the current revision and a stable request_key for each mutation. On an uncertain result retry the exact same operation and key. Honor the human-authorized deletion scope using conversation context and the ordinary tool approval policy. Ask only when scope or authorization is unclear; do not require a repeated title, ID or fixed confirmation phrase. General cleanup or chat removal does not authorize task deletion. Keep containment, dependencies and alternatives distinct; finishing a child does not finish its parent.' });
  ctx.tools.register({ name: 'task_graph', description: 'Create, query, or atomically update shared task graph records through IM. Optional target records the source discussion. Mutations require a unique request_key; uncertain retries preserve it and the exact arguments. The tool does not launch agents or run plans.', parameters: taskGraphParameters,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
    execute: (args, exec) => ctx.nanoProduct.call('task_graph', args, exec),
  });
}
