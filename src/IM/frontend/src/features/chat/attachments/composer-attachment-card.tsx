import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";

import { useTranslation } from "../../../i18n";
import type { ComposerUpload } from "../components/composer-draft-store";
import { AttachmentLink } from "./attachment-link";

/** Keep a local attachment visible through upload, retry and completion.
 *
 * Args:
 *   item: Local file and its upload state, owned by the conversation draft.
 *   busy: Whether a message submission prevents changes to this draft.
 *   retryClock: Current time used to enable retries after server cooldown.
 *   onRemove: Remove this file from the draft.
 *   onRetry: Retry the retained file in place.
 * Returns:
 *   A stable preview card with local upload feedback and actions.
 */
export function ComposerAttachmentCard({ item, busy, retryClock, onRemove, onRetry }: {
  item: ComposerUpload;
  busy: boolean;
  retryClock: number;
  onRemove(): void;
  onRetry(): void;
}) {
  const { t, i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const image = item.file.type.startsWith("image/");
  const [preview, setPreview] = useState<string>();
  useEffect(() => {
    if (!image) return;
    const url = URL.createObjectURL(item.file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [item.file, image]);

  const loading = item.status === "queued" || item.status === "uploading";
  const failed = item.status === "failed";
  const retryable = item.code === "network" || item.code === "cooldown";
  const seconds = Math.max(0, Math.ceil(((item.retryAt ?? 0) - retryClock) / 1000));
  const reason = item.code === "capacity" ? t("chat.messagePane.attachmentCapacity")
    : item.code === "tooLarge" ? t("chat.messagePane.attachmentTooLarge")
    : item.code === "unsupportedType" ? t("chat.messagePane.attachmentUnsupportedType")
    : item.code === "invalidImage" ? (zh ? "图片内容与格式不匹配，请重新复制或选择图片" : "Image contents do not match its format. Copy or choose the image again.")
    : item.code === "cooldown" ? t("chat.messagePane.attachmentCooldown")
    : t("chat.messagePane.attachmentNetwork");
  const errorLabel = item.code === "capacity" ? (zh ? "暂时无法上传" : "Uploads unavailable")
    : item.code === "tooLarge" ? (zh ? "文件过大" : "File too large")
    : item.code === "unsupportedType" ? (zh ? "格式不支持" : "Unsupported format")
    : item.code === "invalidImage" ? (zh ? "无法识别图片" : "Invalid image")
    : item.code === "cooldown" ? (zh ? "请稍后重试" : "Try again shortly")
    : (zh ? "上传失败" : "Upload failed");
  const loadingLabel = item.status === "queued" ? (zh ? "等待上传" : "Waiting to upload") : (zh ? "正在上传" : "Uploading");

  return <div className={`chat-composer-attachment${image ? " chat-composer-attachment--image" : ""}${failed ? " chat-composer-attachment--failed" : ""}`}>
    <div className="chat-composer-attachment-preview">
      {image ? <Dialog.Root>
        <Dialog.Trigger asChild>
          <button type="button" className="chat-composer-attachment-enlarge" disabled={!preview}
            aria-label={t("chat.messagePane.imageEnlarge", { name: item.file.name })}>
            {preview && <img src={preview} alt={item.file.name} />}
          </button>
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="chat-image-preview-overlay" />
          <Dialog.Content className="chat-image-preview" aria-describedby={undefined}>
            <Dialog.Title className="sr-only">{t("chat.messagePane.imagePreview")}</Dialog.Title>
            <Dialog.Close className="chat-image-preview-close" aria-label={t("chat.messagePane.imageClose")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
            </Dialog.Close>
            <img src={preview} alt={item.file.name} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root> : <div className="chat-composer-attachment-document" title={item.file.name}>
        <svg className="chat-composer-attachment-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5M8 13h8M8 17h6" />
        </svg>
        <span className="chat-composer-attachment-filename">
          {item.attachment ? <AttachmentLink href={item.attachment.url} fileName={item.attachment.file_name ?? item.file.name}>
            {item.file.name}
          </AttachmentLink> : item.file.name}
        </span>
      </div>}
      {loading && <div className="chat-composer-attachment-loading" role="status" aria-label={`${loadingLabel}: ${item.file.name}`}>
        <span className="chat-composer-attachment-spinner" aria-hidden="true" />
      </div>}
      <button type="button" className="chat-composer-attachment-remove" disabled={busy}
        aria-label={`Remove ${item.file.name}`} onClick={onRemove}>×</button>
    </div>
    {failed && <div className="chat-composer-attachment-error" role="status" aria-label={reason}>
      <span title={reason}>{errorLabel}</span>
      {retryable && <button type="button" disabled={busy || seconds > 0} onClick={onRetry}>
        {seconds > 0 ? (zh ? `${seconds} 秒后重试` : `Retry in ${seconds}s`) : (zh ? "重试" : "Retry")}
      </button>}
    </div>}
  </div>;
}
