import { validateJsonSchemaValue } from '@deepseek-ai/dsh-tools';

/** Shared public message fields; wire protocol constants are supplied by the host. */
export const publicMessageProperties = {
  target: {type:'string' as const,description:'A conversation, user or IM Agent target. Use conversations info to resolve current members before addressing a particular participant.'},
  text: {type:'string' as const,description:'Message body. To address a specific Agent in a group, include <mention type="user" target_id="IM_USER_ID"/> using its actual user_id from conversations info; a plain name or Agent ID does not notify mention-only Agents.'},
  interactive: {type:'object' as const,properties:{source:{type:'string' as const,maxLength:65536},supersedes_message_id:{type:'string' as const},source_mode:{type:'string' as const,enum:['patch']}},required:['source'],additionalProperties:false},
};

export const personalDeliveryProperties = {attention_id:{type:'string' as const},attention_revision:{type:'integer' as const},task_ref:{type:'object' as const,properties:{graph_id:{type:'string' as const},node_id:{type:'string' as const}},required:['graph_id','node_id'],additionalProperties:false}};

/** Normalize public content before product hashing and either independent review.
 *
 * Args:
 *   args: Public tool arguments without host protocol or identity fields.
 * Returns:
 *   Complete wire payload with the fixed interactive format and catalog.
 */
export function normalizeMessageArguments(args: unknown, personalDelivery = false): Record<string, unknown> {
  const violations = validateJsonSchemaValue({type:'object' as const,properties:{...publicMessageProperties,...(personalDelivery?personalDeliveryProperties:{})},required:['target','text'],additionalProperties:false}, args);
  if (violations.length) throw new Error(`Invalid public message: ${violations.join('; ')}`);
  const input = args as Record<string, unknown>;
  return input.interactive ? {...input,interactive:{...(input.interactive as Record<string,unknown>),format:'openui',catalog_version:'nano-1'}} : input;
}
