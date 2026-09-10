import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, type ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import "../../../i18n";
import type { Conversation } from "../chat-types";
import type { ComposerSnapshot } from "./composer-draft-store";
import { MessagePane } from "./message-pane";

const CONV_A: Conversation = {
  id: "c1",
  title: "Planner",
  participants: [{ type: "agent", id: "a-planner", display_name: "Planner" }],
  participant_ids: ["a-planner"],
  type: "direct",
  direct_kind: "agent",
  owner_id: "u1",
  creator_id: "u1",
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01T00:00:00Z"
};

const CONV_B: Conversation = {
  ...CONV_A,
  id: "c2",
  title: "Writer"
};

function pane(conversation: Conversation, extra: Partial<ComponentProps<typeof MessagePane>> = {}) {
  return (
    <MessagePane
      conversation={conversation}
      messages={[]}
      mentionCandidates={[]}
      onSend={() => {}}
      {...extra}
    />
  );
}

describe("MessagePane composer drafts are per conversation", () => {
  it("does not carry an unsent draft into another conversation", async () => {
    const user = userEvent.setup();
    const { rerender } = render(pane(CONV_A));
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "only for planner");

    rerender(pane(CONV_B));

    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
  });

  it("restores the unsent draft after switching away and back", async () => {
    const user = userEvent.setup();
    const { rerender } = render(pane(CONV_A));
    await user.type(screen.getByRole("textbox"), "only for planner");

    rerender(pane(CONV_B));
    await user.type(screen.getByRole("textbox"), "only for writer");
    rerender(pane(CONV_A));

    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("only for planner");

    rerender(pane(CONV_B));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("only for writer");
  });

  it("keeps pending attachments with the conversation that added them", async () => {
    const uploadAttachment = vi.fn().mockResolvedValue({
      url: "http://im.local/im/uploads/shot.png",
      content_type: "image/png",
      file_name: "shot.png"
    });
    const { rerender } = render(pane(CONV_A, { uploadAttachment }));
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.drop(composer.closest("[data-dragging]") as HTMLElement, {
      dataTransfer: { files: [new File(["img"], "shot.png", { type: "image/png" })], types: ["Files"] }
    });
    expect(await screen.findByRole("button", { name: "Remove shot.png" })).toBeInTheDocument();

    rerender(pane(CONV_B, { uploadAttachment }));
    expect(screen.queryByRole("button", { name: "Remove shot.png" })).not.toBeInTheDocument();

    rerender(pane(CONV_A, { uploadAttachment }));
    expect(screen.getByRole("button", { name: "Remove shot.png" })).toBeInTheDocument();
  });

  it("clears the sent conversation's draft after unmount if send later succeeds", async () => {
    const user = userEvent.setup();
    let resolveSend: () => void = () => {};
    const onSend = vi.fn(() => new Promise<void>((resolve) => {
      resolveSend = resolve;
    }));
    const store = new Map<string, ComposerSnapshot>();
    const { unmount } = render(pane(CONV_A, { onSend, composerStore: store }));
    await user.type(screen.getByRole("textbox"), "send then leave");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
    unmount();

    resolveSend();
    await waitFor(() => {
      expect(store.get(CONV_A.id)?.draft ?? "").toBe("");
    });

    render(pane(CONV_A, { onSend, composerStore: store }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
  });

  it("clears a remounted pane when send succeeds after leaving the chat", async () => {
    const user = userEvent.setup();
    let resolveSend: () => void = () => {};
    const onSend = vi.fn(() => new Promise<void>((resolve) => {
      resolveSend = resolve;
    }));
    const store = new Map<string, ComposerSnapshot>();
    const { unmount } = render(pane(CONV_A, { onSend, composerStore: store }));
    await user.type(screen.getByRole("textbox"), "send then come back");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
    unmount();

    render(pane(CONV_A, { onSend, composerStore: store }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("send then come back");
    resolveSend();
    await waitFor(() => {
      expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
    });
  });

  it("keeps a completed upload on the conversation that started it", async () => {
    let resolveUpload: (attachment: { url: string; content_type: string; file_name: string }) => void = () => {};
    const uploadAttachment = vi.fn(() => new Promise<{ url: string; content_type: string; file_name: string }>((resolve) => {
      resolveUpload = resolve;
    }));
    const { rerender } = render(pane(CONV_A, { uploadAttachment }));
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.drop(composer.closest("[data-dragging]") as HTMLElement, {
      dataTransfer: { files: [new File(["img"], "shot.png", { type: "image/png" })], types: ["Files"] }
    });
    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledTimes(1));

    rerender(pane(CONV_B, { uploadAttachment }));
    resolveUpload({
      url: "http://im.local/im/uploads/shot.png",
      content_type: "image/png",
      file_name: "shot.png"
    });
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Remove shot.png" })).not.toBeInTheDocument();
    });

    rerender(pane(CONV_A, { uploadAttachment }));
    expect(await screen.findByRole("button", { name: "Remove shot.png" })).toBeInTheDocument();
  });

  it("lets another conversation keep typing while a send is in flight", async () => {
    const user = userEvent.setup();
    let resolveSend: () => void = () => {};
    const onSend = vi.fn(() => new Promise<void>((resolve) => {
      resolveSend = resolve;
    }));
    const { rerender } = render(pane(CONV_A, { onSend }));
    await user.type(screen.getByRole("textbox"), "send from planner");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));

    rerender(pane(CONV_B, { onSend }));
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(composer).not.toBeDisabled();
    await user.type(composer, "writer can still type");
    expect(composer.value).toBe("writer can still type");
    resolveSend();
  });

  it("applies a distill seed to the target conversation only", async () => {
    const user = userEvent.setup();
    const seed = {
      id: "distill-c2",
      conversationId: CONV_B.id,
      text: "/skill:conversation-skill-distiller"
    };
    const { rerender } = render(pane(CONV_A));
    await user.type(screen.getByRole("textbox"), "unrelated planner draft");

    rerender(pane(CONV_A, { draftSeed: seed }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("unrelated planner draft");

    rerender(pane(CONV_B, { draftSeed: seed }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
      "/skill:conversation-skill-distiller"
    );

    rerender(pane(CONV_A, { draftSeed: seed }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("unrelated planner draft");
  });

  it("does not apply a leftover distill seed after remounting another conversation", async () => {
    const user = userEvent.setup();
    const store = new Map<string, ComposerSnapshot>();
    const seed = {
      id: "distill-c2",
      conversationId: CONV_B.id,
      text: "/skill:conversation-skill-distiller"
    };
    const { unmount } = render(pane(CONV_A, { composerStore: store }));
    await user.type(screen.getByRole("textbox"), "keep planner draft");
    unmount();

    render(pane(CONV_A, { composerStore: store, draftSeed: seed }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("keep planner draft");
  });

  it("does not clear another conversation's draft when a previous send succeeds", async () => {
    const user = userEvent.setup();
    let resolveSend: () => void = () => {};
    const onSend = vi.fn(() => new Promise<void>((resolve) => {
      resolveSend = resolve;
    }));
    const { rerender } = render(pane(CONV_A, { onSend }));
    await user.type(screen.getByRole("textbox"), "send from planner");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));

    rerender(pane(CONV_B, { onSend }));
    await user.type(screen.getByRole("textbox"), "keep writer draft");
    resolveSend();

    await waitFor(() => {
      expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("keep writer draft");
    });
    rerender(pane(CONV_A, { onSend }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
  });

  it("keeps a failed send's draft on the original conversation", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockRejectedValue(new Error("send failed"));
    const { rerender } = render(pane(CONV_A, { onSend }));
    await user.type(screen.getByRole("textbox"), "retry later");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));

    rerender(pane(CONV_B, { onSend }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
    rerender(pane(CONV_A, { onSend }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("retry later");
  });

  it("restores the draft after the pane unmounts and remounts onto the same store", async () => {
    const user = userEvent.setup();
    const store = new Map<string, ComposerSnapshot>();
    const { unmount } = render(pane(CONV_A, { composerStore: store }));
    await user.type(screen.getByRole("textbox"), "survives leaving the chat");
    unmount();

    render(pane(CONV_A, { composerStore: store }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("survives leaving the chat");
  });

  it("restores the draft after remount under StrictMode", async () => {
    const user = userEvent.setup();
    const store = new Map<string, ComposerSnapshot>();
    const { unmount } = render(<StrictMode>{pane(CONV_A, { composerStore: store })}</StrictMode>);
    await user.type(screen.getByRole("textbox"), "survives leaving the chat");
    unmount();

    render(<StrictMode>{pane(CONV_A, { composerStore: store })}</StrictMode>);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("survives leaving the chat");
  });
});
