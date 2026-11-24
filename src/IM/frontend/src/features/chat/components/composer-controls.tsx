import { useLayoutEffect, useRef, type RefObject } from "react";
import { Paperclip } from "lucide-react";
import { useTranslation } from "../../../i18n";

export function ComposerAttachmentButton({ onAdd, disabled }: {
  onAdd(files: File[]): void; disabled: boolean;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLInputElement>(null);
  const label = t("chat.messagePane.threadAttach");
  return <>
    <input ref={ref} type="file" multiple hidden onChange={event => {
      onAdd(Array.from(event.target.files ?? []));
      event.target.value = "";
    }} />
    <button type="button" className="chat-composer-attach" title={label} aria-label={label}
      disabled={disabled} onClick={() => ref.current?.click()}><Paperclip size={17} /></button>
  </>;
}

/** Keep wrapped lines within the same height limits on both reading surfaces. */
export function useComposerHeight(ref: RefObject<HTMLTextAreaElement | null>, draft: string, visible: boolean) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!visible || !el) return;
    const resize = () => {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight + 2}px`;
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [ref, draft, visible]);
}
