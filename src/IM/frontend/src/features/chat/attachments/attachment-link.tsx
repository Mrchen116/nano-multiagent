import { useEffect, useRef, useState, type ReactNode } from "react";
import { authFetch } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";
import { useTranslation } from "../../../i18n";
import { protectedResourceUrl } from "../components/message-image";

/** Download member-protected bytes through authFetch, never via a tokenized URL. */
export function AttachmentLink({
  href,
  children,
  fileName,
  className = "chat-attachment-name",
  wrapperClassName = "chat-attachment-link-wrap",
  title,
  ariaLabel,
}: {
  href: string;
  children: ReactNode;
  fileName?: string;
  className?: string;
  wrapperClassName?: string;
  title?: string;
  ariaLabel?: string;
}) {
  const { t } = useTranslation();
  const self = useAuthStore(s => s.accessToken ? s.user?.id : undefined);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const url = protectedResourceUrl(href);
  useEffect(() => {
    const cancel = () => request.current?.abort();
    window.addEventListener("im:conversation-invalidated", cancel);
    return () => { cancel(); window.removeEventListener("im:conversation-invalidated", cancel); };
  }, [self, href]);
  if (!url) return <a className={className} href={href} target="_blank" rel="noreferrer" title={title} aria-label={ariaLabel}>{children}</a>;
  async function download() {
    if (!self || !url || busy) return;
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setFailed(false);
    try {
      const response = await authFetch(url, { signal: controller.signal, cache: "no-store", redirect: "error" });
      if (!response.ok) throw new Error("Attachment download failed");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl; anchor.download = fileName ?? "attachment";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch { if (!controller.signal.aborted) setFailed(true); }
    finally { setBusy(false); }
  }
  return (
    <span className={wrapperClassName} data-busy={busy ? "true" : undefined}>
      <button type="button" className={className} disabled={!self || busy} title={title} aria-label={ariaLabel} onClick={() => void download()}>
        {children}
      </button>
      {failed && <span className="chat-attachment-link-error" role="alert">{t("chat.messagePane.attachmentNetwork")}</span>}
    </span>
  );
}
