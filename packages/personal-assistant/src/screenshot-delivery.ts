import { chatAttachments, type ChatAttachment } from '@nano/product-contracts';

export type ScreenshotUploader = (input: {
  agentId: string; conversationId: string; operationId: string; index: number;
  path: string; lifecycleRevision: number; signal: AbortSignal;
}) => Promise<ChatAttachment>;

/** Prepare ordered attachments while uploading each distinct local path once. */
export async function prepareScreenshots(
  upload: ScreenshotUploader | undefined,
  request: Omit<Parameters<ScreenshotUploader>[0], 'index' | 'path'>,
  paths: string[],
  existing: unknown,
): Promise<ChatAttachment[]> {
  if (!upload) throw new Error('Local screenshot delivery is unavailable on this node');
  const attachments = existing === undefined ? [] : chatAttachments(existing);
  if (!paths.length || paths.length + attachments.length > 5 || paths.some(path => typeof path !== 'string' || !path))
    throw new Error('Use at most five attachments with absolute screenshot paths');
  const uploaded = new Map<string, ChatAttachment>();
  const prepared = [...attachments];
  for (const [index, path] of paths.entries()) {
    request.signal.throwIfAborted();
    let image = uploaded.get(path);
    if (!image) {
      try { image = await upload({...request, path, index}); }
      catch (error) { throw new Error(`Screenshot ${index + 1} (${path}) was not uploaded: ${(error as Error).message}`); }
      uploaded.set(path, image);
    }
    prepared.push(image);
  }
  return prepared;
}

/** Expose only a query of the original operation when a screenshot receipt is uncertain. */
export function unknownScreenshotReceipt(target: string, operationId: string) {
  return {status:'unknown', target, operation_id:operationId,
    message:'Check this send with send_message using the same target and receipt_of set to operation_id.'};
}
