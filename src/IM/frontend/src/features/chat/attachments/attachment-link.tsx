import { useEffect, useRef, useState, type ReactNode } from "react";
import { authFetch } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";
import { useTranslation } from "../../../i18n";
import { protectedResourceUrl } from "../components/message-image";

/** Download member-protected bytes through authFetch, never via a tokenized URL. */
export function AttachmentLink({ href, children, fileName }: { href: string; children: ReactNode; fileName?: string }) {
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
  if (!url) return <a className="chat-attachment-name" href={href} target="_blank" rel="noreferrer">{children}</a>;
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
  return <span><button type="button" className="chat-attachment-name" disabled={!self || busy} onClick={() => void download()}>{children}</button>{failed && <span role="alert">{t("chat.messagePane.attachmentNetwork")}</span>}</span>;
}
