import * as Dialog from "@radix-ui/react-dialog";
import { AlertCircle, Check, Copy, Download, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown, { type Components, defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { useTranslation } from "../../../i18n";
import { authFetch } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";
import { protectedResourceUrl } from "../components/message-image";
import { FileTypeBadge, fileAttachmentMeta } from "./attachment-chip";
import {
  type AttachmentPreviewKind,
  PDF_PREVIEW_MAX_BYTES,
  TEXT_PREVIEW_MAX_BYTES,
  formatByteSize,
  isTsvFile,
  parseDelimitedTable,
  readBoundedTextPreview,
} from "./attachment-preview";

export interface AttachmentPreviewModalProps {
  open: boolean;
  onOpenChange(open: boolean): void;
  href: string;
  fileName: string;
  contentType?: string | null;
  kind: AttachmentPreviewKind;
}

type PreviewState =
  | { status: "idle" | "loading" }
  | {
      status: "text";
      text: string;
      truncated: boolean;
      byteLength: number;
      totalBytes: number | null;
    }
  | {
      status: "pdf";
      blobUrl: string;
      byteLength: number;
    }
  | {
      status: "binary";
      byteLength: number;
    }
  | {
      status: "too_large";
      totalBytes: number | null;
    }
  | {
      status: "error";
    };

const markdownComponents: Components = {
  a({ href, children, ...props }) {
    return (
      <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
        {children}
      </a>
    );
  },
  table({ children, ...props }) {
    return (
      <div className="chat-file-preview-md-table-wrap">
        <table className="im-md-table" {...props}>
          {children}
        </table>
      </div>
    );
  },
};

function isSameOriginUrl(href: string): boolean {
  try {
    return new URL(href, window.location.href).origin === window.location.origin;
  } catch {
    return false;
  }
}

function triggerBlobDownload(blob: Blob, fileName: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

/** In-page preview modal for Markdown, CSV/TSV, plain text/code, and PDF attachments. */
export function AttachmentPreviewModal({
  open,
  onOpenChange,
  href,
  fileName,
  contentType,
  kind,
}: AttachmentPreviewModalProps) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const self = useAuthStore(s => (s.accessToken ? s.user?.id : undefined));
  const privateUrl = protectedResourceUrl(href);
  const { ext } = fileAttachmentMeta(fileName, contentType);

  const [state, setState] = useState<PreviewState>({ status: "idle" });
  const [viewMode, setViewMode] = useState<"rich" | "raw">("rich");
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadFailed, setDownloadFailed] = useState(false);

  const cachedBlobRef = useRef<Blob | null>(null);
  const copyTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setViewMode("rich");
    setCopied(false);
    setDownloadFailed(false);
  }, [open, href, kind]);

  useEffect(() => {
    const cancel = () => onOpenChange(false);
    window.addEventListener("im:conversation-invalidated", cancel);
    return () => window.removeEventListener("im:conversation-invalidated", cancel);
  }, [onOpenChange]);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) window.clearTimeout(copyTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!open) {
      cachedBlobRef.current = null;
      setState({ status: "idle" });
      return;
    }

    const controller = new AbortController();
    let pdfObjectUrl: string | null = null;
    cachedBlobRef.current = null;
    setState({ status: "loading" });

    async function load() {
      try {
        let response: Response;
        if (privateUrl) {
          if (!self) {
            setState({ status: "error" });
            return;
          }
          response = await authFetch(privateUrl, {
            signal: controller.signal,
            cache: "no-store",
            redirect: "error",
          });
        } else if (isSameOriginUrl(href)) {
          response = await fetch(href, {
            signal: controller.signal,
            cache: "no-store",
          });
        } else {
          setState({ status: "error" });
          return;
        }

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (controller.signal.aborted) return;

        if (kind === "pdf") {
          const lenHeader = response.headers?.get("content-length");
          const parsedLen = lenHeader ? Number.parseInt(lenHeader, 10) : Number.NaN;
          if (Number.isFinite(parsedLen) && parsedLen > PDF_PREVIEW_MAX_BYTES) {
            setState({ status: "too_large", totalBytes: parsedLen });
            return;
          }
          const rawBlob = await response.blob();
          if (controller.signal.aborted) return;
          if (rawBlob.size > PDF_PREVIEW_MAX_BYTES) {
            setState({ status: "too_large", totalBytes: rawBlob.size });
            return;
          }
          const pdfBlob =
            rawBlob.type === "application/pdf"
              ? rawBlob
              : new Blob([rawBlob], { type: "application/pdf" });
          cachedBlobRef.current = pdfBlob;
          pdfObjectUrl = URL.createObjectURL(pdfBlob);
          setState({ status: "pdf", blobUrl: pdfObjectUrl, byteLength: pdfBlob.size });
          return;
        }

        const result = await readBoundedTextPreview(response, TEXT_PREVIEW_MAX_BYTES);
        if (controller.signal.aborted) return;
        if (result.status === "binary") {
          setState({ status: "binary", byteLength: result.byteLength });
          return;
        }
        if (!result.truncated) {
          cachedBlobRef.current = new Blob([result.bytes], {
            type: contentType || "text/plain;charset=utf-8",
          });
        }
        setState({
          status: "text",
          text: result.text,
          truncated: result.truncated,
          byteLength: result.byteLength,
          totalBytes: result.totalBytes,
        });
      } catch {
        if (!controller.signal.aborted) setState({ status: "error" });
      }
    }

    void load();

    return () => {
      controller.abort();
      if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
    };
  }, [open, href, privateUrl, self, kind, contentType]);

  const parsedCsv = useMemo(() => {
    if (kind !== "csv" || state.status !== "text") return null;
    const delimiter = isTsvFile(fileName, contentType) ? "\t" : ",";
    return parseDelimitedTable(state.text, delimiter);
  }, [kind, state, fileName, contentType]);

  const lines = useMemo(() => {
    if (state.status !== "text") return [];
    return state.text.split(/\r\n|\n|\r/);
  }, [state]);

  const subtitle = useMemo(() => {
    const parts: string[] = [ext];
    if (state.status === "text") {
      if (kind === "csv" && parsedCsv) {
        parts.push(zh ? `${parsedCsv.totalRows} 行` : `${parsedCsv.totalRows} rows`);
        parts.push(zh ? `${parsedCsv.headers.length} 列` : `${parsedCsv.headers.length} cols`);
      } else {
        parts.push(zh ? `${lines.length} 行` : `${lines.length} lines`);
      }
      const sizeBytes = state.totalBytes ?? state.byteLength;
      parts.push(formatByteSize(sizeBytes));
    } else if (state.status === "pdf") {
      parts.push(formatByteSize(state.byteLength));
    }
    return parts.join(" · ");
  }, [ext, state, kind, parsedCsv, lines.length, zh]);

  async function handleCopy() {
    if (state.status !== "text") return;
    try {
      await navigator.clipboard.writeText(state.text);
      setCopied(true);
      if (copyTimerRef.current !== null) window.clearTimeout(copyTimerRef.current);
      copyTimerRef.current = window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API may be unavailable in restricted contexts.
    }
  }

  async function handleDownload() {
    if (downloading) return;
    setDownloadFailed(false);
    if (cachedBlobRef.current) {
      triggerBlobDownload(cachedBlobRef.current, fileName);
      return;
    }
    if (!privateUrl && !isSameOriginUrl(href)) {
      window.open(href, "_blank", "noreferrer");
      return;
    }
    setDownloading(true);
    try {
      const response = privateUrl
        ? await authFetch(privateUrl, { cache: "no-store", redirect: "error" })
        : await fetch(href, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      triggerBlobDownload(blob, fileName);
    } catch {
      setDownloadFailed(true);
    } finally {
      setDownloading(false);
    }
  }

  const showModeToggle = (kind === "markdown" || kind === "csv") && state.status === "text";
  const wideDialog = kind === "pdf" || kind === "csv";

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="chat-file-preview-overlay" />
        <Dialog.Content
          className={`chat-file-preview-dialog${wideDialog ? " chat-file-preview-dialog--wide" : ""}${kind === "pdf" ? " chat-file-preview-dialog--pdf" : ""}`}
          aria-describedby={undefined}
        >
          <header className="chat-file-preview-header">
            <div className="chat-file-preview-heading">
              <FileTypeBadge fileName={fileName} contentType={contentType} />
              <div className="chat-file-preview-title-block">
                <Dialog.Title className="chat-file-preview-title" title={fileName}>
                  {fileName}
                </Dialog.Title>
                <span className="chat-file-preview-subtitle">{subtitle}</span>
              </div>
            </div>
            <div className="chat-file-preview-actions">
              {showModeToggle && (
                <div className="chat-file-preview-tabs" role="tablist" aria-label={zh ? "预览模式" : "Preview mode"}>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={viewMode === "rich"}
                    className={`chat-file-preview-tab${viewMode === "rich" ? " is-active" : ""}`}
                    onClick={() => setViewMode("rich")}
                  >
                    {kind === "markdown" ? (zh ? "预览" : "Preview") : (zh ? "表格" : "Table")}
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={viewMode === "raw"}
                    className={`chat-file-preview-tab${viewMode === "raw" ? " is-active" : ""}`}
                    onClick={() => setViewMode("raw")}
                  >
                    {kind === "markdown" ? (zh ? "源码" : "Source") : (zh ? "原文" : "Raw")}
                  </button>
                </div>
              )}
              {state.status === "text" && (
                <button
                  type="button"
                  className="chat-file-preview-btn"
                  onClick={() => void handleCopy()}
                  aria-label={zh ? "复制内容" : "Copy content"}
                >
                  {copied ? <Check size={15} strokeWidth={2} /> : <Copy size={15} strokeWidth={1.85} />}
                  <span>{copied ? (zh ? "已复制" : "Copied") : (zh ? "复制" : "Copy")}</span>
                </button>
              )}
              <button
                type="button"
                className="chat-file-preview-btn chat-file-preview-btn--primary"
                onClick={() => void handleDownload()}
                disabled={downloading}
              >
                <Download size={15} strokeWidth={1.85} />
                <span>{downloading ? (zh ? "下载中…" : "Downloading…") : (zh ? "下载" : "Download")}</span>
              </button>
              <Dialog.Close
                className="chat-file-preview-close"
                aria-label={zh ? "关闭预览" : "Close preview"}
              >
                <X size={17} strokeWidth={2} />
              </Dialog.Close>
            </div>
          </header>

          {state.status === "text" && state.truncated && (
            <div className="chat-file-preview-banner" role="status">
              <AlertCircle size={15} strokeWidth={1.9} />
              <span>
                {zh
                  ? `文件较大，当前仅预览前 ${formatByteSize(TEXT_PREVIEW_MAX_BYTES)}，请下载查看完整内容。`
                  : `Showing first ${formatByteSize(TEXT_PREVIEW_MAX_BYTES)}. Download to view the complete file.`}
              </span>
            </div>
          )}

          {downloadFailed && (
            <div className="chat-file-preview-banner chat-file-preview-banner--error" role="alert">
              <AlertCircle size={15} strokeWidth={1.9} />
              <span>{zh ? "下载失败，请稍后重试。" : "Download failed. Please try again."}</span>
            </div>
          )}

          <div className={`chat-file-preview-body chat-file-preview-body--${kind}`}>
            {state.status === "loading" || state.status === "idle" ? (
              <div className="chat-file-preview-state" role="status">
                <span className="chat-composer-attachment-spinner" aria-hidden="true" />
                <span>{zh ? "正在加载预览…" : "Loading preview…"}</span>
              </div>
            ) : state.status === "error" || state.status === "binary" || state.status === "too_large" ? (
              <div className="chat-file-preview-state">
                <AlertCircle size={26} strokeWidth={1.7} className="chat-file-preview-state-icon" />
                <p className="chat-file-preview-state-title">
                  {state.status === "binary"
                    ? (zh ? "该文件为二进制或非 UTF-8 编码，暂不支持在线预览" : "This file is binary or not UTF-8 encoded and cannot be previewed inline.")
                    : state.status === "too_large"
                      ? (zh ? "文件超过在线预览上限，请直接下载查看" : "This file exceeds the inline preview size limit.")
                      : (zh ? "暂时无法加载文件预览" : "Unable to load file preview.")}
                </p>
                <button
                  type="button"
                  className="chat-file-preview-btn chat-file-preview-btn--primary"
                  onClick={() => void handleDownload()}
                  disabled={downloading}
                >
                  <Download size={15} strokeWidth={1.85} />
                  <span>{zh ? "下载完整文件" : "Download file"}</span>
                </button>
              </div>
            ) : state.status === "pdf" ? (
              <iframe
                src={state.blobUrl}
                title={fileName}
                className="chat-file-preview-pdf"
              />
            ) : kind === "markdown" && viewMode === "rich" ? (
              <div className="chat-file-preview-prose-scroll">
                <article className="im-md chat-file-preview-prose">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    urlTransform={defaultUrlTransform}
                    components={markdownComponents}
                  >
                    {state.text}
                  </ReactMarkdown>
                </article>
              </div>
            ) : kind === "csv" && viewMode === "rich" && parsedCsv && parsedCsv.headers.length > 0 ? (
              <div className="chat-file-preview-table-wrap">
                <table className="chat-file-preview-table">
                  <thead>
                    <tr>
                      <th className="chat-file-preview-table-rownum" scope="col">#</th>
                      {parsedCsv.headers.map((header, idx) => (
                        <th key={idx} scope="col">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {parsedCsv.rows.map((row, rowIdx) => (
                      <tr key={rowIdx}>
                        <td className="chat-file-preview-table-rownum">{rowIdx + 1}</td>
                        {row.map((cell, colIdx) => (
                          <td key={colIdx}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {parsedCsv.rowsTruncated && (
                  <div className="chat-file-preview-table-foot">
                    {zh
                      ? `仅展示前 ${parsedCsv.rows.length} 行（共 ${parsedCsv.totalRows} 行），下载查看完整表格。`
                      : `Showing first ${parsedCsv.rows.length} of ${parsedCsv.totalRows} rows. Download for the full sheet.`}
                  </div>
                )}
              </div>
            ) : (
              <div className="chat-file-preview-code-wrap">
                <table className="chat-file-preview-code-table" aria-label={fileName}>
                  <tbody>
                    {lines.map((line, idx) => (
                      <tr key={idx}>
                        <td className="chat-file-preview-code-ln" aria-hidden="true">{idx + 1}</td>
                        <td className="chat-file-preview-code-line"><code>{line || " "}</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
