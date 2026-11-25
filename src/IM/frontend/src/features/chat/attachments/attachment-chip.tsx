import { MessageImage } from "../components/message-image";
import { AttachmentLink } from "./attachment-link";
import type { Attachment } from "../chat-types";

export interface AttachmentChipProps {
  attachment: Attachment;
  /** When provided, renders a remove (×) button — used in the composer.
   *  Omitted in MessageBubble where the chip is read-only. */
  onRemove?(): void;
  removeDisabled?: boolean;
}

const RASTER_IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);

/** Check whether an attachment MIME type is a safe inline raster image (excludes SVG/HTML). */
export function isRasterImageMime(contentType: string | null | undefined): boolean {
  if (!contentType) return false;
  return RASTER_IMAGE_MIME_TYPES.has(contentType.split(";")[0]?.trim().toLowerCase() ?? "");
}

export function AttachmentChip({ attachment, onRemove, removeDisabled = false }: AttachmentChipProps) {
  const name = attachment.file_name ?? attachment.url.split("/").pop() ?? "file";
  if (isRasterImageMime(attachment.content_type)) {
    return (
      <div className="chat-attachment-chip chat-attachment-chip--image">
        <MessageImage src={attachment.url} alt={name} />
        {onRemove && (
          <button
            type="button"
            className="chat-attachment-remove"
            onClick={onRemove}
            disabled={removeDisabled}
            aria-label={`Remove ${name}`}
          >
            ×
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="chat-attachment-chip chat-attachment-chip--doc">
      <span className="chat-attachment-icon" aria-hidden>📄</span>
      <AttachmentLink href={attachment.url} fileName={name}>{name}</AttachmentLink>
      {onRemove && (
        <button
          type="button"
          className="chat-attachment-remove"
          onClick={onRemove}
          disabled={removeDisabled}
          aria-label={`Remove ${name}`}
        >
          ×
        </button>
      )}
    </div>
  );
}
