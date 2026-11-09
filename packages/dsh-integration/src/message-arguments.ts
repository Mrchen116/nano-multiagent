import { validateJsonSchemaValue } from '@deepseek-ai/dsh-tools';

/** Shared public message fields; wire protocol constants are supplied by the host. */
export const publicMessageProperties = {
  target: {type:'string' as const,description:'A conversation, user or IM Agent target. Use conversations info to resolve current members before addressing a particular participant.'},
  text: {type:'string' as const,description:'Message text. Optional with interactive UI. Required for plain-text delivery. To address a specific Agent in a group, include <mention type="user" target_id="IM_USER_ID"/> using its actual user_id from conversations info; a plain name or Agent ID does not notify mention-only Agents.'},
  incident_ref: {type:'string' as const,description:'Bound main PA only: incident reference for the owner notice or subsequent refusal in its original conversation.'},
  attachments: {type:'array' as const,maxItems:5,items:{type:'object' as const,properties:{url:{type:'string' as const}},required:['url'],additionalProperties:false}},
  interactive: {type:'object' as const,properties:{source:{type:'string' as const,maxLength:65536},supersedes_message_id:{type:'string' as const},source_mode:{type:'string' as const,enum:['patch']}},required:['source'],additionalProperties:false},
};

export const publicMessageParameters = {type:'object' as const,properties:publicMessageProperties,required:['target'],
  anyOf:[{required:['text']},{required:['interactive']}],additionalProperties:false};

export const screenshotMessageProperties = {
  ...publicMessageProperties,
  local_images: {type:'array' as const, minItems:1, maxItems:5, items:{type:'string' as const},
    description:'Absolute paths of PNG, JPEG or WebP screenshots to attach to this Nano IM message. Existing attachments come first. Combined limit: five attachments.'},
  receipt_of: {type:'string' as const, description:'With target and no other fields, check the original operation_id from an unknown screenshot send. This does not send again.'},
};
export const screenshotMessageParameters = {
  ...publicMessageParameters, properties:screenshotMessageProperties,
  anyOf:[...publicMessageParameters.anyOf, {required:['receipt_of']}],
};

/** Normalize public content before product hashing and either independent review.
 *
 * Args:
 *   args: Public tool arguments without host protocol or identity fields.
 *   screenshots: Whether this is a self-authored send_message call.
 * Returns:
 *   Complete wire payload with the fixed interactive format and catalog.
 */
export function normalizeMessageArguments(args: unknown, screenshots = false): Record<string, unknown> {
  const violations = validateJsonSchemaValue(screenshots ? screenshotMessageParameters : publicMessageParameters, args);
  if (violations.length) throw new Error(`Invalid public message: ${violations.join('; ')}`);
  const supplied = args as Record<string, unknown>;
  if (supplied.receipt_of !== undefined) {
    if (!supplied.receipt_of || Object.keys(supplied).some(key => key !== 'target' && key !== 'receipt_of'))
      throw new Error('Check a receipt with only target and receipt_of');
    return supplied;
  }
  const localImages = supplied.local_images as string[] | undefined;
  if (localImages && (localImages.length + ((supplied.attachments as unknown[] | undefined)?.length ?? 0) > 5
      || localImages.some(path => !path.startsWith('/') && !/^[A-Za-z]:[\\/]/.test(path)) || supplied.incident_ref))
    throw new Error('Provide absolute screenshot paths and at most five attachments for a regular message');
  const input: Record<string, unknown> = {text:'', ...supplied};
  if (!(input.text as string).trim() && input.interactive === undefined) throw new Error('A message requires text or interactive content');
  return input.interactive ? {...input,interactive:{...(input.interactive as Record<string,unknown>),format:'openui',catalog_version:'nano-iui-1'}} : input;
}
