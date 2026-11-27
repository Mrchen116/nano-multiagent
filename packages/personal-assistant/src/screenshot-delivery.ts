import { chatAttachments, type ChatAttachment } from '@nano/product-contracts';

export type ScreenshotUploader = (input: {
  agentId: string; conversationId: string; operationId: string; index: number;
  path: string; lifecycleRevision: number; signal: AbortSignal;
}) => Promise<ChatAttachment>;

export type AttachmentUploader = ScreenshotUploader;

export type AttachmentDownloader = (input: {
  agentId: string; attachmentId: string; url: string; fileName?: string;
  workspace?: string; signal: AbortSignal;
}) => Promise<{
  attachment_id: string;
  local_path: string;
  file_name: string;
  content_type: string;
  byte_size: number;
  sha256: string;
}>;

/** Prepare ordered local images and files while uploading each distinct path once.
 *
 * Order is fixed as `[...existing, ...localImages, ...localFiles]` so 1-based
 * `AttachmentImage` indices remain stable when non-image files are also attached.
 */
export async function prepareLocalAttachments(
  uploadImage: ScreenshotUploader | undefined,
  uploadFile: AttachmentUploader | undefined,
  request: Omit<Parameters<ScreenshotUploader>[0], 'index' | 'path'>,
  imagePaths: string[] | undefined,
  filePaths: string[] | undefined,
  existing: unknown,
  options?: { includeLocalPath?: boolean },
): Promise<Array<ChatAttachment & { local_path?: string }>> {
  const images = imagePaths ?? [];
  const files = filePaths ?? [];
  const attachments = existing === undefined ? [] : chatAttachments(existing);
  if (images.length && !uploadImage) throw new Error('Local screenshot delivery is unavailable on this node');
  if (files.length && !uploadFile) throw new Error('Local file delivery is unavailable on this node');
  if ((!images.length && !files.length) || images.length + files.length + attachments.length > 5
      || images.some(path => typeof path !== 'string' || !path)
      || files.some(path => typeof path !== 'string' || !path)) {
    throw new Error('Use at most five attachments with absolute local paths');
  }
  const prepared: Array<ChatAttachment & { local_path?: string }> = [...attachments];
  const uploadedImages = new Map<string, ChatAttachment & { local_path?: string }>();
  for (const [index, path] of images.entries()) {
    request.signal.throwIfAborted();
    let image = uploadedImages.get(path);
    if (!image) {
      try {
        const uploaded = await uploadImage!({ ...request, path, index });
        image = options?.includeLocalPath ? { ...uploaded, local_path: path } : uploaded;
      }
      catch (error) { throw new Error(`Screenshot ${index + 1} (${path}) was not uploaded: ${(error as Error).message}`); }
      uploadedImages.set(path, image);
    }
    prepared.push(image);
  }
  const uploadedFiles = new Map<string, ChatAttachment & { local_path?: string }>();
  for (const [index, path] of files.entries()) {
    request.signal.throwIfAborted();
    let file = uploadedFiles.get(path);
    if (!file) {
      try {
        const uploaded = await uploadFile!({ ...request, path, index });
        file = options?.includeLocalPath ? { ...uploaded, local_path: path } : uploaded;
      }
      catch (error) { throw new Error(`File ${index + 1} (${path}) was not uploaded: ${(error as Error).message}`); }
      uploadedFiles.set(path, file);
    }
    prepared.push(file);
  }
  return prepared;
}

/** Prepare ordered attachments while uploading each distinct local path once. */
export async function prepareScreenshots(
  upload: ScreenshotUploader | undefined,
  request: Omit<Parameters<ScreenshotUploader>[0], 'index' | 'path'>,
  paths: string[],
  existing: unknown,
): Promise<ChatAttachment[]> {
  return prepareLocalAttachments(upload, undefined, request, paths, undefined, existing);
}

/** Expose only a query of the original operation when a local attachment receipt is uncertain. */
export function unknownScreenshotReceipt(target: string, operationId: string) {
  return {status:'unknown', target, operation_id:operationId,
    message:'Check this send with send_message using the same target and receipt_of set to operation_id.'};
}
