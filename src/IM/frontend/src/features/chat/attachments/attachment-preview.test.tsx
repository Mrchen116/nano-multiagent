import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { AttachmentChip } from "./attachment-chip";
import {
  attachmentPreviewKind,
  formatByteSize,
  parseDelimitedTable,
  readBoundedTextPreview,
  TEXT_PREVIEW_MAX_BYTES,
} from "./attachment-preview";

vi.mock("../../auth/auth-fetch", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/auth-fetch";

const mockedAuthFetch = vi.mocked(authFetch);

describe("attachmentPreviewKind", () => {
  test("classifies markdown, csv/tsv, text/code, and pdf for inline preview", () => {
    expect(attachmentPreviewKind("notes.md", "text/markdown")).toBe("markdown");
    expect(attachmentPreviewKind("report.csv", "text/csv")).toBe("csv");
    expect(attachmentPreviewKind("metrics.tsv", "text/tab-separated-values")).toBe("csv");
    expect(attachmentPreviewKind("config.yaml", "text/yaml")).toBe("text");
    expect(attachmentPreviewKind("script.py", "application/octet-stream")).toBe("text");
    expect(attachmentPreviewKind("readme", "text/plain")).toBe("text");
    expect(attachmentPreviewKind("report.pdf", "application/pdf")).toBe("pdf");
  });

  test("keeps active content (SVG/HTML), raster images, and binaries out of inline doc preview", () => {
    expect(attachmentPreviewKind("diagram.svg", "image/svg+xml")).toBeNull();
    expect(attachmentPreviewKind("diagram.svg", "text/plain")).toBeNull();
    expect(attachmentPreviewKind("page.html", "text/html")).toBeNull();
    expect(attachmentPreviewKind("page.htm", "text/plain")).toBeNull();
    expect(attachmentPreviewKind("doc.xhtml", "application/xhtml+xml")).toBeNull();
    expect(attachmentPreviewKind("photo.png", "image/png")).toBeNull();
    expect(attachmentPreviewKind("bundle.zip", "application/zip")).toBeNull();
    expect(attachmentPreviewKind("deck.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBeNull();
    expect(attachmentPreviewKind("blob.bin", "application/octet-stream")).toBeNull();
  });
});

describe("parseDelimitedTable & readBoundedTextPreview", () => {
  test("parses RFC 4180 CSV with quotes, escaped quotes, and embedded commas/newlines", () => {
    const csv = 'item,note,amount\n"Widget, A","Line 1\nLine ""2""",42\nBeta,Plain,7\n';
    const parsed = parseDelimitedTable(csv, ",");
    expect(parsed.headers).toEqual(["item", "note", "amount"]);
    expect(parsed.rows).toEqual([
      ["Widget, A", 'Line 1\nLine "2"', "42"],
      ["Beta", "Plain", "7"],
    ]);
    expect(parsed.totalRows).toBe(2);
    expect(parsed.rowsTruncated).toBe(false);
  });

  test("truncates large text streams cleanly at line boundary and rejects binary NUL bytes", async () => {
    const line = "row,value\n";
    const big = new TextEncoder().encode(line.repeat(50));
    const res = new Response(big, { headers: { "content-length": String(big.byteLength) } });
    const bounded = await readBoundedTextPreview(res, 64);
    expect(bounded.status).toBe("ok");
    if (bounded.status === "ok") {
      expect(bounded.truncated).toBe(true);
      expect(bounded.totalBytes).toBe(big.byteLength);
      expect(bounded.text.endsWith("row,value")).toBe(true);
    }

    const binRes = new Response(new Uint8Array([0x50, 0x4b, 0x00, 0x04]));
    const bin = await readBoundedTextPreview(binRes, 64);
    expect(bin.status).toBe("binary");
  });

  test("cancels a slow response after receiving the preview prefix", async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array(TEXT_PREVIEW_MAX_BYTES + 1).fill(97));
      },
      cancel,
    });
    const result = await readBoundedTextPreview(new Response(stream));
    expect(result).toMatchObject({ status: "ok", truncated: true, byteLength: TEXT_PREVIEW_MAX_BYTES });
    expect(cancel).toHaveBeenCalledOnce();
  });

  test("formats byte sizes concisely", () => {
    expect(formatByteSize(512)).toBe("512 B");
    expect(formatByteSize(1536)).toBe("1.5 KB");
    expect(formatByteSize(2 * 1024 * 1024)).toBe("2 MB");
  });
});

describe("AttachmentChip in-page preview modal", () => {
  beforeEach(() => {
    setLanguage("en");
    mockedAuthFetch.mockReset();
    useAuthStore.setState({
      accessToken: "test-token",
      user: { id: "u1", username: "demo", display_name: "Demo", role: "member", owner_id: "u1" } as any,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("opens Markdown preview modal, renders GFM prose without raw HTML, and toggles source", async () => {
    mockedAuthFetch.mockResolvedValueOnce(
      new Response("# Release Notes\n\n- Shipped **attachments**\n\n<script>window.__xss=1</script>\n", {
        status: 200,
        headers: { "content-type": "text/markdown" },
      }),
    );

    render(
      <AttachmentChip
        attachment={{
          url: "/im/v1/conversations/c1/attachments/md1",
          content_type: "text/markdown",
          file_name: "release-notes.md",
        }}
      />,
    );

    // Sibling direct-download button exists without nesting inside preview button
    expect(screen.getByRole("button", { name: "Download release-notes.md" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /release-notes\.md.*Preview/i }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Release Notes" })).toBeInTheDocument();
    expect(dialog.querySelector("script")).toBeNull();

    // Switch to raw source view
    await userEvent.click(screen.getByRole("tab", { name: "Source" }));
    expect(screen.getByText("# Release Notes")).toBeInTheDocument();
  });

  test("opens CSV preview modal as a structured table", async () => {
    mockedAuthFetch.mockResolvedValueOnce(
      new Response("region,revenue,growth\nAPAC,12000,+18%\nEMEA,9400,+11%\n", {
        status: 200,
        headers: { "content-type": "text/csv" },
      }),
    );

    render(
      <AttachmentChip
        attachment={{
          url: "/im/v1/conversations/c1/attachments/csv1",
          content_type: "text/csv",
          file_name: "q4-metrics.csv",
        }}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /q4-metrics\.csv.*Preview/i }));
    expect(await screen.findByRole("columnheader", { name: "region" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "APAC" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "+18%" })).toBeInTheDocument();
  });

  test("shows errors instead of saving an interrupted attachment from the chip or preview", async () => {
    mockedAuthFetch.mockImplementation(async () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode("prefix")); },
      pull(controller) { controller.error(new Error("connection closed")); },
    })));
    const save = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<AttachmentChip attachment={{
      url: "/im/v1/conversations/c1/attachments/log", content_type: "text/plain", file_name: "server.log",
    }} />);

    await userEvent.click(screen.getByRole("button", { name: "Download server.log" }));
    expect(await screen.findByRole("alert")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: /server\.log.*Preview/i }));
    expect(await screen.findByText("Unable to load file preview.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Download file" }));
    expect(await screen.findByText("Download failed. Please try again.")).toBeVisible();
    expect(save).not.toHaveBeenCalled();
  });

  test("opens PDF preview modal using a blob iframe and revokes the blob URL on close", async () => {
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:http://localhost/pdf-preview-1");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    mockedAuthFetch.mockResolvedValueOnce(
      new Response(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34]), {
        status: 200,
        headers: { "content-type": "application/pdf" },
      }),
    );

    render(
      <AttachmentChip
        attachment={{
          url: "/im/v1/conversations/c1/attachments/pdf1",
          content_type: "application/pdf",
          file_name: "design-spec.pdf",
        }}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /design-spec\.pdf.*Preview/i }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => {
      const frame = dialog.querySelector("iframe");
      expect(frame).not.toBeNull();
      expect(frame).toHaveAttribute("src", "blob:http://localhost/pdf-preview-1");
    });
    expect(createObjectURL).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "Close preview" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:http://localhost/pdf-preview-1");
  });

  test("keeps SVG and ZIP attachments download-only without opening a preview modal", async () => {
    mockedAuthFetch.mockResolvedValue(new Response(new Uint8Array([1, 2, 3]), { status: 200 }));
    render(
      <>
        <AttachmentChip
          attachment={{
            url: "/im/v1/conversations/c1/attachments/svg1",
            content_type: "image/svg+xml",
            file_name: "diagram.svg",
          }}
        />
        <AttachmentChip
          attachment={{
            url: "/im/v1/conversations/c1/attachments/zip1",
            content_type: "application/zip",
            file_name: "logs.zip",
          }}
        />
      </>,
    );

    expect(screen.queryByText("Preview")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /diagram\.svg/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mockedAuthFetch).toHaveBeenCalledWith(
      expect.stringContaining("/im/v1/conversations/c1/attachments/svg1"),
      expect.objectContaining({ cache: "no-store", redirect: "error" }),
    );
  });
});
