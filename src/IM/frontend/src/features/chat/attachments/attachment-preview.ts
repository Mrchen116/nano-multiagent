import { isRasterImageMime } from "./attachment-chip";

export type AttachmentPreviewKind = "markdown" | "csv" | "text" | "pdf";

export const TEXT_PREVIEW_MAX_BYTES = 512 * 1024;
export const PDF_PREVIEW_MAX_BYTES = 25 * 1024 * 1024;

const DENIED_PREVIEW_EXTENSIONS = new Set(["svg", "svgz", "html", "htm", "xhtml", "mhtml"]);
const DENIED_PREVIEW_MIMES = new Set(["image/svg+xml", "text/html", "application/xhtml+xml"]);

const MARKDOWN_EXTENSIONS = new Set(["md", "markdown", "mdx"]);
const MARKDOWN_MIMES = new Set(["text/markdown", "text/x-markdown"]);

const CSV_EXTENSIONS = new Set(["csv", "tsv"]);
const CSV_MIMES = new Set(["text/csv", "text/tab-separated-values"]);

const TEXT_EXTENSIONS = new Set([
  "txt", "log", "json", "jsonl", "ndjson", "yaml", "yml", "xml", "toml", "ini", "env",
  "conf", "cfg", "properties", "py", "ts", "tsx", "js", "mjs", "cjs", "jsx", "css",
  "scss", "less", "sql", "sh", "bash", "zsh", "fish", "go", "rs", "java", "kt", "swift",
  "c", "cc", "cpp", "h", "hpp", "cs", "rb", "php", "lua", "r", "diff", "patch",
  "graphql", "gql", "proto", "dockerfile", "makefile",
]);

const TEXT_FILENAMES = new Set(["readme", "license", "makefile", "dockerfile", "procfile"]);

const TEXT_MIMES = new Set([
  "text/plain",
  "application/json",
  "text/yaml",
  "application/yaml",
  "application/x-yaml",
  "text/xml",
  "application/xml",
  "text/javascript",
  "application/javascript",
  "text/css",
  "application/toml",
  "text/x-python",
  "text/x-sh",
  "text/x-shellscript",
  "text/x-diff",
  "text/x-patch",
  "application/sql",
]);

function normalizeMime(contentType?: string | null): string {
  return contentType?.split(";")[0]?.trim().toLowerCase() ?? "";
}

function extractExtension(fileName: string): string {
  const base = fileName.split("/").pop()?.split("\\").pop() ?? fileName;
  const dot = base.lastIndexOf(".");
  if (dot <= 0 || dot >= base.length - 1) return "";
  return base.slice(dot + 1).toLowerCase();
}

/** Classify whether a non-image attachment is safe for in-page modal preview.
 *
 * Active document formats (SVG, HTML, XHTML) and unknown binaries always return null
 * so they remain download-only.
 */
export function attachmentPreviewKind(
  fileName: string,
  contentType?: string | null,
): AttachmentPreviewKind | null {
  const mime = normalizeMime(contentType);
  const ext = extractExtension(fileName);
  const baseName = (fileName.split("/").pop()?.split("\\").pop() ?? fileName).toLowerCase();

  if (DENIED_PREVIEW_EXTENSIONS.has(ext) || DENIED_PREVIEW_MIMES.has(mime)) return null;
  if (isRasterImageMime(mime)) return null;

  if (ext === "pdf" || mime === "application/pdf") return "pdf";
  if (MARKDOWN_EXTENSIONS.has(ext) || MARKDOWN_MIMES.has(mime)) return "markdown";
  if (CSV_EXTENSIONS.has(ext) || CSV_MIMES.has(mime)) return "csv";
  if (TEXT_EXTENSIONS.has(ext) || TEXT_FILENAMES.has(baseName) || TEXT_MIMES.has(mime)) return "text";
  return null;
}

/** Return true when a delimited file should split columns on tabs instead of commas. */
export function isTsvFile(fileName: string, contentType?: string | null): boolean {
  return extractExtension(fileName) === "tsv" || normalizeMime(contentType) === "text/tab-separated-values";
}

/** Format a byte count into a compact human-readable size label. */
export function formatByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) {
    const kb = bytes / 1024;
    return `${kb >= 100 ? Math.round(kb) : kb.toFixed(1).replace(/\.0$/, "")} KB`;
  }
  const mb = bytes / (1024 * 1024);
  return `${mb >= 100 ? Math.round(mb) : mb.toFixed(1).replace(/\.0$/, "")} MB`;
}

/** Trim any incomplete trailing UTF-8 sequence when slicing a byte buffer. */
function trimIncompleteUtf8Tail(bytes: Uint8Array): Uint8Array {
  if (bytes.length === 0) return bytes;
  let idx = bytes.length - 1;
  // Walk back over continuation bytes (10xxxxxx), at most 3 bytes.
  let continuations = 0;
  while (idx >= 0 && (bytes[idx]! & 0xc0) === 0x80 && continuations < 3) {
    idx -= 1;
    continuations += 1;
  }
  if (idx < 0) return bytes.subarray(0, 0);
  const lead = bytes[idx]!;
  let expectedLen = 1;
  if ((lead & 0x80) === 0x00) expectedLen = 1;
  else if ((lead & 0xe0) === 0xc0) expectedLen = 2;
  else if ((lead & 0xf0) === 0xe0) expectedLen = 3;
  else if ((lead & 0xf8) === 0xf0) expectedLen = 4;
  else return bytes.subarray(0, idx);

  const actualLen = bytes.length - idx;
  return actualLen < expectedLen ? bytes.subarray(0, idx) : bytes;
}

export type TextPreviewReadResult =
  | {
      status: "ok";
      text: string;
      truncated: boolean;
      byteLength: number;
      totalBytes: number | null;
      bytes: Uint8Array;
    }
  | {
      status: "binary";
      byteLength: number;
      totalBytes: number | null;
    };

/** Read up to `maxBytes` from a fetch Response and decode strictly as UTF-8 text.
 *
 * Cancels the underlying stream once the preview cap is reached and rejects NUL-containing
 * or invalid UTF-8 payloads as binary.
 */
export async function readBoundedTextPreview(
  response: Response,
  maxBytes = TEXT_PREVIEW_MAX_BYTES,
): Promise<TextPreviewReadResult> {
  const contentLengthHeader = response.headers?.get("content-length");
  const parsedLength = contentLengthHeader ? Number.parseInt(contentLengthHeader, 10) : Number.NaN;
  const totalBytes = Number.isFinite(parsedLength) && parsedLength >= 0 ? parsedLength : null;

  let collected: Uint8Array;
  let truncated = false;

  if (response.body && typeof response.body.getReader === "function") {
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let received = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!value || value.byteLength === 0) continue;
        if (received + value.byteLength > maxBytes) {
          const remaining = maxBytes - received;
          if (remaining > 0) {
            chunks.push(value.subarray(0, remaining));
            received += remaining;
          }
          truncated = true;
          await reader.cancel().catch(() => {});
          break;
        }
        chunks.push(value);
        received += value.byteLength;
      }
    } finally {
      reader.releaseLock();
    }
    collected = new Uint8Array(received);
    let offset = 0;
    for (const chunk of chunks) {
      collected.set(chunk, offset);
      offset += chunk.byteLength;
    }
  } else {
    const raw = new Uint8Array(await response.arrayBuffer());
    if (raw.byteLength > maxBytes) {
      collected = raw.subarray(0, maxBytes);
      truncated = true;
    } else {
      collected = raw;
    }
  }

  let view = truncated ? trimIncompleteUtf8Tail(collected) : collected;
  if (truncated) {
    // Cut back to the last newline within the trailing 4 KiB so lines/CSV rows stay intact.
    const floor = Math.max(0, view.length - 4096);
    for (let i = view.length - 1; i >= floor; i -= 1) {
      if (view[i] === 0x0a) {
        view = view.subarray(0, i);
        break;
      }
    }
  }

  for (let i = 0; i < view.length; i += 1) {
    if (view[i] === 0) {
      return { status: "binary", byteLength: view.byteLength, totalBytes };
    }
  }

  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(view);
    return {
      status: "ok",
      text,
      truncated,
      byteLength: collected.byteLength,
      totalBytes: totalBytes ?? (truncated ? null : collected.byteLength),
      bytes: collected,
    };
  } catch {
    return { status: "binary", byteLength: view.byteLength, totalBytes };
  }
}

export interface ParsedDelimitedTable {
  headers: string[];
  rows: string[][];
  totalRows: number;
  rowsTruncated: boolean;
}

/** Parse RFC 4180 CSV or TSV text into normalized header and body rows. */
export function parseDelimitedTable(
  text: string,
  delimiter: "," | "\t" = ",",
  maxRows = 2000,
): ParsedDelimitedTable {
  const input = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const allRows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < input.length; i += 1) {
    const ch = input[i]!;
    if (inQuotes) {
      if (ch === '"') {
        if (input[i + 1] === '"') {
          cell += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        cell += ch;
      }
    } else if (ch === '"' && cell.length === 0) {
      inQuotes = true;
    } else if (ch === delimiter) {
      row.push(cell);
      cell = "";
    } else if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && input[i + 1] === "\n") i += 1;
      row.push(cell);
      allRows.push(row);
      row = [];
      cell = "";
    } else {
      cell += ch;
    }
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    allRows.push(row);
  }

  // Drop trailing blank lines (e.g. from final newline)
  while (allRows.length > 0) {
    const last = allRows[allRows.length - 1]!;
    if (last.length === 1 && last[0] === "") allRows.pop();
    else break;
  }

  if (allRows.length === 0) {
    return { headers: [], rows: [], totalRows: 0, rowsTruncated: false };
  }

  const rawHeaders = allRows[0]!;
  const bodyAll = allRows.slice(1);
  const totalRows = bodyAll.length;
  const rowsTruncated = totalRows > maxRows;
  const visibleBody = rowsTruncated ? bodyAll.slice(0, maxRows) : bodyAll;

  let colCount = rawHeaders.length;
  for (const r of visibleBody) {
    if (r.length > colCount) colCount = r.length;
  }

  const headers = Array.from({ length: colCount }, (_, idx) => rawHeaders[idx] ?? `Col ${idx + 1}`);
  const rows = visibleBody.map(r => Array.from({ length: colCount }, (_, idx) => r[idx] ?? ""));

  return { headers, rows, totalRows, rowsTruncated };
}
