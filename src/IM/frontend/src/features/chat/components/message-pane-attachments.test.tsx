import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import type { Attachment, Conversation } from "../chat-types";
import { AttachmentUploadError } from "../attachments/use-attachment-upload";
import { MessagePane } from "./message-pane";

const conversation: Conversation = {
  id: "local-preview", title: "Image Review", type: "direct", direct_kind: "user",
  participants: [], participant_ids: [], owner_id: "owner", creator_id: "owner",
  is_pinned: false, is_muted: false, unread_count: 0,
  last_message_preview: null, last_message_at: null, created_at: "2026-11-02T00:00:00Z"
};

function file(name: string) {
  return new File(["image bytes"], name, { type: "image/png" });
}

function attachment(name: string): Attachment {
  return { url: `/im/v1/conversations/local-preview/attachments/${name}`, file_name: name, content_type: "image/png" };
}

function paste(files: File[]) {
  fireEvent.paste(screen.getByRole("textbox"), { clipboardData: { items: [], files } });
}

it("shows every local preview before upload completes and retries a failure on the same card", async () => {
  setLanguage("en");
  let reject!: (error: Error) => void;
  const uploadAttachment = vi.fn((_file: File): Promise<Attachment> => new Promise((_resolve, failure) => { reject = failure; }));
  const onSend = vi.fn();
  render(<MessagePane conversation={conversation} messages={[]} mentionCandidates={[]} onSend={onSend} uploadAttachment={uploadAttachment} />);
  const composer = screen.getByRole("textbox");
  composer.focus();
  paste([file("first.png"), file("second.png")]);

  expect(screen.getAllByRole("img").map(image => image.getAttribute("alt"))).toEqual(["first.png", "second.png"]);
  const originalImage = screen.getByRole("img", { name: "first.png" });
  const card = originalImage.closest(".chat-composer-attachment")!;
  const originalUrl = originalImage.getAttribute("src");
  expect(originalUrl).toMatch(/^blob:/);
  expect(screen.getByRole("status", { name: "Uploading: first.png" })).toBeInTheDocument();
  expect(screen.getByRole("status", { name: "Waiting to upload: second.png" })).toBeInTheDocument();
  expect(composer).toHaveFocus();
  await userEvent.type(composer, "Keep typing");
  expect(composer).toHaveValue("Keep typing");
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  expect(onSend).not.toHaveBeenCalled();

  await act(async () => { reject(new Error("offline")); });
  expect(screen.getByRole("img", { name: "first.png" })).toBe(originalImage);
  expect(within(card as HTMLElement).getByRole("button", { name: "Retry" })).toBeEnabled();
  uploadAttachment.mockResolvedValue(attachment("first.png"));
  await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(within(card as HTMLElement).queryByRole("button", { name: "Retry" })).not.toBeInTheDocument());
  expect(screen.getByRole("img", { name: "first.png" })).toBe(originalImage);
  expect(originalImage).toHaveAttribute("src", originalUrl);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  // The second upload stays pending; removing it unblocks the ready draft.
  await userEvent.click(screen.getByRole("button", { name: "Remove second.png" }));
  expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
});

it("removes uploading and queued files without resurrecting a late result", async () => {
  setLanguage("en");
  let complete!: (value: Attachment) => void;
  const uploadAttachment = vi.fn(() => new Promise<Attachment>(resolve => { complete = resolve; }));
  const onSend = vi.fn().mockResolvedValue(undefined);
  const { unmount } = render(<MessagePane conversation={conversation} messages={[]} mentionCandidates={[]} onSend={onSend} uploadAttachment={uploadAttachment} />);
  paste([file("uploading.png"), file("queued.png")]);
  const url = screen.getByRole("img", { name: "uploading.png" }).getAttribute("src");
  await userEvent.click(screen.getByRole("button", { name: "Remove queued.png" }));
  await userEvent.click(screen.getByRole("button", { name: "Remove uploading.png" }));
  await userEvent.type(screen.getByRole("textbox"), "text without removed images");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(onSend).toHaveBeenCalledWith("text without removed images", [], undefined, expect.any(String)));
  await act(async () => { complete(attachment("uploading.png")); });
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(uploadAttachment).toHaveBeenCalledTimes(1);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith(url);
  unmount();
});

it("keeps paste order in the sent attachments when separate uploads finish out of order", async () => {
  setLanguage("en");
  const finish: Record<string, (value: Attachment) => void> = {};
  const uploadAttachment = vi.fn((value: File) => new Promise<Attachment>(resolve => { finish[value.name] = resolve; }));
  const onSend = vi.fn().mockResolvedValue(undefined);
  render(<MessagePane conversation={conversation} messages={[]} mentionCandidates={[]} onSend={onSend} uploadAttachment={uploadAttachment} />);
  paste([file("first.png")]);
  paste([file("second.png")]);
  await act(async () => { finish["second.png"](attachment("second.png")); });
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  await act(async () => { finish["first.png"](attachment("first.png")); });
  expect(screen.getAllByRole("img").map(image => image.getAttribute("alt"))).toEqual(["first.png", "second.png"]);
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(onSend).toHaveBeenCalledWith("", [attachment("first.png"), attachment("second.png")], undefined, expect.any(String)));
  await waitFor(() => expect(screen.queryByRole("img")).not.toBeInTheDocument());
});

it("enables retry immediately after an HTTP failure long after entering the chat", async () => {
  setLanguage("en");
  const clock = vi.spyOn(Date, "now").mockReturnValue(1000);
  let reject!: (error: Error) => void;
  const uploadAttachment = vi.fn(() => new Promise<Attachment>((_resolve, fail) => { reject = fail; }));
  try {
    render(<MessagePane conversation={conversation} messages={[]} mentionCandidates={[]} onSend={() => {}} uploadAttachment={uploadAttachment} />);
    paste([file("retry.png")]);
    clock.mockReturnValue(6000);
    await act(async () => { reject(new AttachmentUploadError("network", 500, "unavailable")); });
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Retry in/ })).not.toBeInTheDocument();
  } finally {
    clock.mockRestore();
  }
});

it("keeps the open/download action on a ready document in the draft", async () => {
  setLanguage("en");
  const uploadAttachment = vi.fn().mockResolvedValue({ url: "/im/v1/conversations/local-preview/attachments/report", file_name: "report.pdf", content_type: "application/pdf" });
  render(<MessagePane conversation={conversation} messages={[]} mentionCandidates={[]} onSend={() => {}} uploadAttachment={uploadAttachment} />);
  fireEvent.drop(screen.getByRole("textbox").closest("[data-dragging]")!, {
    dataTransfer: { files: [new File(["pdf"], "report.pdf", { type: "application/pdf" })], types: ["Files"] }
  });
  expect(await screen.findByRole("button", { name: "report.pdf" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
});
