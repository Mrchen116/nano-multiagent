import { createContext, type ComponentProps, type ReactNode } from "react";

/** The host resolves one-based image positions within the current message. */
export const CardAttachmentImage = createContext<((index: number, alt: string) => ReactNode) | null>(null);

/** Open an image even when its surrounding card's form controls are disabled. */
export function AttachmentPreviewTrigger({onActivate, ...props}: ComponentProps<"span"> & {onActivate(): void}) {
  return <span {...props} onClick={onActivate} className="iui-attachment-preview" data-attachment-preview role="button" tabIndex={0}
    onKeyDown={event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      onActivate();
    }} />;
}
