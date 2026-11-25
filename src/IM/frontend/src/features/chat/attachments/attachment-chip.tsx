import {
  Download,
  File,
  FileArchive,
  FileAudio,
  FileCode2,
  FileSpreadsheet,
  FileText,
  FileVideo,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "../../../i18n";
import { MessageImage } from "../components/message-image";
import { AttachmentLink } from "./attachment-link";
import { attachmentPreviewKind } from "./attachment-preview";
import { AttachmentPreviewModal } from "./attachment-preview-modal";
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

export type FileAttachmentTone = "sheet" | "pdf" | "doc" | "archive" | "code" | "media" | "generic";

const EXT_TONE: Record<string, FileAttachmentTone> = {
  csv: "sheet", tsv: "sheet", xls: "sheet", xlsx: "sheet", numbers: "sheet",
  pdf: "pdf",
  doc: "doc", docx: "doc", rtf: "doc", txt: "doc", md: "doc", markdown: "doc", ppt: "doc", pptx: "doc", log: "doc",
  zip: "archive", tar: "archive", gz: "archive", tgz: "archive", bz2: "archive", "7z": "archive", rar: "archive",
  svg: "code", html: "code", htm: "code", xml: "code", json: "code", yaml: "code", yml: "code", toml: "code",
  js: "code", mjs: "code", ts: "code", tsx: "code", py: "code", sh: "code", sql: "code", diff: "code", patch: "code", css: "code",
  mp3: "media", wav: "media", ogg: "media", m4a: "media", flac: "media", mp4: "media", webm: "media", mov: "media",
};

const MIME_LABEL: Record<string, { ext: string; tone: FileAttachmentTone }> = {
  "text/csv": { ext: "CSV", tone: "sheet" },
  "text/tab-separated-values": { ext: "TSV", tone: "sheet" },
  "application/pdf": { ext: "PDF", tone: "pdf" },
  "application/zip": { ext: "ZIP", tone: "archive" },
  "application/gzip": { ext: "GZ", tone: "archive" },
  "application/x-tar": { ext: "TAR", tone: "archive" },
  "image/svg+xml": { ext: "SVG", tone: "code" },
  "text/html": { ext: "HTML", tone: "code" },
  "application/json": { ext: "JSON", tone: "code" },
  "text/yaml": { ext: "YAML", tone: "code" },
  "application/yaml": { ext: "YAML", tone: "code" },
  "application/xml": { ext: "XML", tone: "code" },
  "text/xml": { ext: "XML", tone: "code" },
  "text/markdown": { ext: "MD", tone: "doc" },
  "text/plain": { ext: "TXT", tone: "doc" },
};

/** Derive a concise uppercase badge label and visual tone from a file name and MIME type. */
export function fileAttachmentMeta(fileName: string, contentType?: string | null): { ext: string; tone: FileAttachmentTone; isVideo: boolean; isAudio: boolean } {
  const mime = contentType?.split(";")[0]?.trim().toLowerCase() ?? "";
  const dot = fileName.lastIndexOf(".");
  const rawExt = dot > 0 && dot < fileName.length - 1 ? fileName.slice(dot + 1).replace(/[^a-zA-Z0-9]/g, "") : "";
  const lowerExt = rawExt.toLowerCase();
  const mimeEntry = MIME_LABEL[mime];
  const ext = (rawExt && rawExt.length <= 5 ? rawExt.toUpperCase() : mimeEntry?.ext) ?? "FILE";
  let tone: FileAttachmentTone = EXT_TONE[lowerExt] ?? mimeEntry?.tone ?? "generic";
  const isVideo = mime.startsWith("video/") || ["mp4", "webm", "mov"].includes(lowerExt);
  const isAudio = mime.startsWith("audio/") || ["mp3", "wav", "ogg", "m4a", "flac"].includes(lowerExt);
  if (tone === "generic") {
    if (isVideo || isAudio) tone = "media";
    else if (mime.startsWith("text/")) tone = "doc";
  }
  return { ext, tone, isVideo, isAudio };
}

/** Crisp category-matched vector badge shared by sent file cards and composer drafts. */
export function FileTypeBadge({ fileName, contentType }: { fileName: string; contentType?: string | null }) {
  const { tone, isVideo, isAudio } = fileAttachmentMeta(fileName, contentType);
  const Icon = tone === "sheet" ? FileSpreadsheet
    : tone === "archive" ? FileArchive
    : tone === "code" ? FileCode2
    : tone === "media" ? (isVideo ? FileVideo : isAudio ? FileAudio : File)
    : tone === "pdf" || tone === "doc" ? FileText
    : File;
  return (
    <span className={`chat-attachment-file-badge chat-attachment-file-badge--${tone}`} aria-hidden="true">
      <Icon size={18} strokeWidth={1.75} />
    </span>
  );
}

export function AttachmentChip({ attachment, onRemove, removeDisabled = false }: AttachmentChipProps) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const [previewOpen, setPreviewOpen] = useState(false);
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
  const { ext } = fileAttachmentMeta(name, attachment.content_type);
  const previewKind = !onRemove ? attachmentPreviewKind(name, attachment.content_type) : null;

  if (previewKind) {
    return (
      <div className="chat-attachment-chip chat-attachment-chip--doc chat-attachment-chip--previewable">
        <button
          type="button"
          className="chat-attachment-card-action chat-attachment-card-action--preview"
          title={name}
          onClick={() => setPreviewOpen(true)}
        >
          <FileTypeBadge fileName={name} contentType={attachment.content_type} />
          <span className="chat-attachment-file-meta">
            <span className="chat-attachment-file-title">{name}</span>
            <span className="chat-attachment-file-sub">
              <span className="chat-attachment-file-ext">{ext}</span>
              <span className="chat-attachment-file-dot" aria-hidden="true">·</span>
              <span className="chat-attachment-file-preview-hint">{zh ? "预览" : "Preview"}</span>
            </span>
          </span>
        </button>
        <AttachmentLink
          href={attachment.url}
          fileName={name}
          title={zh ? `下载 ${name}` : `Download ${name}`}
          ariaLabel={zh ? `下载 ${name}` : `Download ${name}`}
          className="chat-attachment-card-dl-btn"
          wrapperClassName="chat-attachment-card-dl-wrap"
        >
          <Download size={14} strokeWidth={1.85} aria-hidden="true" />
        </AttachmentLink>
        <AttachmentPreviewModal
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          href={attachment.url}
          fileName={name}
          contentType={attachment.content_type}
          kind={previewKind}
        />
      </div>
    );
  }

  return (
    <div className="chat-attachment-chip chat-attachment-chip--doc">
      <AttachmentLink
        href={attachment.url}
        fileName={name}
        title={name}
        className="chat-attachment-card-action"
        wrapperClassName="chat-attachment-card-wrap"
      >
        <FileTypeBadge fileName={name} contentType={attachment.content_type} />
        <span className="chat-attachment-file-meta">
          <span className="chat-attachment-file-title">{name}</span>
          <span className="chat-attachment-file-ext">{ext}</span>
        </span>
        <span className="chat-attachment-download-icon" aria-hidden="true">
          <Download size={15} strokeWidth={1.85} />
        </span>
      </AttachmentLink>
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
