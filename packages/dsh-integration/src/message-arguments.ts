import { validateJsonSchemaValue } from '@deepseek-ai/dsh-tools';

/** Shared public message fields; wire protocol constants are supplied by the host. */
export const publicMessageProperties = {
  target: {type:'string' as const}, text: {type:'string' as const},
  interactive: {type:'object' as const,properties:{source:{type:'string' as const,maxLength:65536},supersedes_message_id:{type:'string' as const},source_mode:{type:'string' as const,enum:['patch']}},required:['source'],additionalProperties:false},
};

/** Normalize public content before product hashing and either independent review.
 *
 * Args:
 *   args: Public tool arguments without host protocol or identity fields.
 * Returns:
 *   Complete wire payload with the fixed interactive format and catalog.
 */
export function normalizeMessageArguments(args: unknown): Record<string, unknown> {
  const violations = validateJsonSchemaValue({type:'object' as const,properties:publicMessageProperties,required:['target','text'],additionalProperties:false}, args);
  if (violations.length) throw new Error(`Invalid public message: ${violations.join('; ')}`);
  const input = args as Record<string, unknown>;
  return input.interactive ? {...input,interactive:{...(input.interactive as Record<string,unknown>),format:'openui',catalog_version:'nano-1'}} : input;
}
