import { afterEach, describe, expect, test, vi } from "vitest";

import { uploadOneAttachment, AttachmentUploadError } from "./use-attachment-upload";

function makeFile(name: string, type: string, size: number): File {
  const bytes = new Uint8Array(size);
  return new File([bytes], name, { type });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("uploadOneAttachment", () => {
  test("posts raw body with file_name query and Content-Type header, returns Attachment", async () => {
    const file = makeFile("hello.png", "image/png", 8);
    const fetchSpy = vi.fn(async (_url: string, _init?: RequestInit) =>
      new Response(
        JSON.stringify({
          url: "http://im.local/im/uploads/abc.png",
          content_type: "image/png",
          file_name: "hello.png"
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchSpy);

    const result = await uploadOneAttachment(file);

    expect(result.url).toBe("http://im.local/im/uploads/abc.png");
    expect(result.content_type).toBe("image/png");
    expect(result.file_name).toBe("hello.png");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [calledUrl, init] = fetchSpy.mock.calls[0]!;
    expect(calledUrl).toContain("/im/v1/uploads?file_name=hello.png");
    expect((init as RequestInit).method).toBe("POST");
    const headers = new Headers((init as RequestInit).headers as HeadersInit);
    expect(headers.get("Content-Type")).toBe("image/png");
  });

  test("maps 415 from backend to AttachmentUploadError with code unsupportedType", async () => {
    const file = makeFile("evil.sh", "application/x-sh", 4);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "unsupported" }), { status: 415 }))
    );

    await expect(uploadOneAttachment(file)).rejects.toMatchObject({
      code: "unsupportedType",
      status: 415
    });
  });

  test("maps 413 from backend to AttachmentUploadError with code tooLarge", async () => {
    const file = makeFile("big.bin", "image/png", 11 * 1024 * 1024);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "too big" }), { status: 413 }))
    );

    await expect(uploadOneAttachment(file)).rejects.toMatchObject({
      code: "tooLarge",
      status: 413
    });
  });

  test("AttachmentUploadError is throwable + carries detail", () => {
    const err = new AttachmentUploadError("tooLarge", 413, "too big");
    expect(err).toBeInstanceOf(Error);
    expect(err.code).toBe("tooLarge");
    expect(err.detail).toBe("too big");
  });
});
