// One-shot upload helper for chat attachments.
//
// Why a plain function (not a hook): React Query's `useMutation` already
// owns the lifecycle for the composer; here we just need the network call
// + typed error mapping so the caller can render i18n'd toasts.

import { authFetch } from "../../auth/auth-fetch";
import type { Attachment } from "../v2/chat-types";

export type AttachmentUploadErrorCode = "unsupportedType" | "tooLarge" | "network";

export class AttachmentUploadError extends Error {
  readonly code: AttachmentUploadErrorCode;
  readonly status: number;
  readonly detail: string;

  constructor(code: AttachmentUploadErrorCode, status: number, detail: string) {
    super(`${code}: ${detail}`);
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}

export async function uploadOneAttachment(file: File): Promise<Attachment> {
  const qs = new URLSearchParams({ file_name: file.name }).toString();
  const res = await authFetch(`/im/v1/uploads?${qs}`, {
    method: "POST",
    body: file,
    headers: { "Content-Type": file.type || "application/octet-stream" }
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    if (res.status === 415) throw new AttachmentUploadError("unsupportedType", 415, detail);
    if (res.status === 413) throw new AttachmentUploadError("tooLarge", 413, detail);
    throw new AttachmentUploadError("network", res.status, detail);
  }
  return (await res.json()) as Attachment;
}
