import type { Attachment } from "../v2/chat-types";

export interface AttachmentChipProps {
  attachment: Attachment;
  /** When provided, renders a remove (×) button — used in the composer.
   *  Omitted in MessageBubble where the chip is read-only. */
  onRemove?(): void;
}

function isImage(contentType: string | null | undefined): boolean {
  return !!contentType && contentType.startsWith("image/");
}

export function AttachmentChip({ attachment, onRemove }: AttachmentChipProps) {
  const name = attachment.file_name ?? attachment.url.split("/").pop() ?? "file";
  if (isImage(attachment.content_type)) {
    return (
      <div className="chat-attachment-chip chat-attachment-chip--image">
        <img className="chat-attachment-thumb" src={attachment.url} alt={name} />
        {onRemove && (
          <button
            type="button"
            className="chat-attachment-remove"
            onClick={onRemove}
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
      <a className="chat-attachment-name" href={attachment.url} target="_blank" rel="noreferrer">
        {name}
      </a>
      {onRemove && (
        <button
          type="button"
          className="chat-attachment-remove"
          onClick={onRemove}
          aria-label={`Remove ${name}`}
        >
          ×
        </button>
      )}
    </div>
  );
}
