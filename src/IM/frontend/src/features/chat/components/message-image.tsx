import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";
import { defaultUrlTransform, type UrlTransform } from "react-markdown";

import { useTranslation } from "../../../i18n";
import { authFetch } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";

const PENDING_IMAGE = /^nano-image-pending:\d+$/;
const PRIVATE_IMAGE_PATH = /^\/im\/v1\/conversations\/[a-zA-Z0-9_-]+\/images\/[a-zA-Z0-9_-]+$/;

/** Allow the display-only pending protocol on images without changing link sanitization. */
export const messageImageUrlTransform: UrlTransform = (url, key, node) =>
  node.tagName === "img" && key === "src" && PENDING_IMAGE.test(url) ? url : defaultUrlTransform(url);

function privateImageUrl(src: string): string | null {
  try {
    const url = new URL(src, window.location.href);
    // Never forward a session token to a Markdown-supplied foreign origin or arbitrary API.
    return url.origin === window.location.origin && PRIVATE_IMAGE_PATH.test(url.pathname)
      && !url.search && !url.hash && !url.username && !url.password
      ? url.href : null;
  } catch {
    return null;
  }
}

/** Render an inline reply image, binding private bytes to the currently signed-in user. */
export function MessageImage({ src = "", alt = "", title }: { src?: string; alt?: string; title?: string }) {
  const { t } = useTranslation();
  const userId = useAuthStore((state) => state.accessToken ? state.user?.id : undefined);
  if (PENDING_IMAGE.test(src)) {
    return <span className="chat-message-image-state" role="status">{t("chat.messagePane.imageLoading")}</span>;
  }
  const privateUrl = privateImageUrl(src);
  if (privateUrl) {
    // Remount on account/source changes so old bytes and open previews cannot survive a switch.
    return <PrivateMessageImage key={`${userId ?? ""}:${privateUrl}`} url={privateUrl} signedIn={!!userId} alt={alt} title={title} />;
  }
  if (!src) {
    return <span className="chat-message-image-state chat-message-image-state--error" role="status">{t("chat.messagePane.imageFailed")}</span>;
  }
  return <img src={src} alt={alt} title={title} />;
}

function PrivateMessageImage({ url, signedIn, alt, title }: { url: string; signedIn: boolean; alt: string; title?: string }) {
  const { t } = useTranslation();
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!signedIn) return;
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setBlobUrl(null);
    setFailed(false);
    void (async () => {
      try {
        const response = await authFetch(url, { signal: controller.signal, cache: "no-store", redirect: "error" });
        if (!response.ok) throw new Error("Image request failed");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    })();
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, signedIn, attempt]);

  if (failed || !signedIn) {
    return (
      <span className="chat-message-image-state chat-message-image-state--error" role="status">
        {t("chat.messagePane.imageFailed")}
        {signedIn && <button type="button" onClick={() => setAttempt((value) => value + 1)}>{t("chat.messagePane.imageRetry")}</button>}
      </span>
    );
  }
  if (!blobUrl) {
    return <span className="chat-message-image-state" role="status">{t("chat.messagePane.imageLoading")}</span>;
  }
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button className="chat-message-image" type="button" aria-label={t("chat.messagePane.imageEnlarge", { name: alt })}>
          <img src={blobUrl} alt={alt} title={title} onError={() => setFailed(true)} />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="chat-image-preview-overlay" />
        <Dialog.Content className="chat-image-preview" aria-describedby={undefined}>
          <Dialog.Title className="sr-only">{t("chat.messagePane.imagePreview")}</Dialog.Title>
          <Dialog.Close className="chat-image-preview-close" aria-label={t("chat.messagePane.imageClose")}>
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </Dialog.Close>
          <img src={blobUrl} alt={alt} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
