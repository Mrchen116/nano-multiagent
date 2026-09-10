import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import type { Conversation, Message } from "../chat-types";
import { MessagePane } from "./message-pane";

const user = {
  id: "owner-a", username: "a", display_name: "A", owner_id: "owner-a", locale: "en",
  default_entry_node_id: null, owned_node_ids: [], created_at: ""
};
const imagePath = "/im/v1/conversations/c1/images/image-1";
const conversation = {
  id: "c1", title: "Planner", participants: [], participant_ids: [], type: "direct",
  direct_kind: "agent", owner_id: "owner-a", creator_id: "owner-a", is_pinned: false,
  is_muted: false, unread_count: 0, last_message_preview: null, last_message_at: null, created_at: ""
} satisfies Conversation;

function pane(content: string) {
  const message: Message = {
    id: "m1", conversation_id: "c1", sender: { type: "agent", id: "agent-a" },
    sender_user_id: "owner-a", sender_type: "agent", content, attachments: [],
    delivery_status: "completed", created_at: "2026-09-10T00:00:00Z", permission_requests: []
  };
  return <MessagePane conversation={conversation} messages={[message]} mentionCandidates={[]} onSend={() => {}} />;
}

describe("inline reply images", () => {
  beforeEach(() => {
    useAuthStore.getState().setSession({ user, access_token: "token-a", refresh_token: "refresh-a" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new Blob(["image"], { type: "image/png" }))));
    const NativeURL = URL;
    vi.stubGlobal("URL", class extends NativeURL {
      static createObjectURL = vi.fn(() => "blob:private-image");
      static revokeObjectURL = vi.fn();
    });
  });

  afterEach(() => {
    cleanup();
    useAuthStore.getState().clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps a streaming placeholder in place then loads the private image with Bearer without an attachment copy", async () => {
    const view = render(pane("Before\n\n![screenshot](nano-image-pending:0)\n\nAfter"));
    expect(screen.getByRole("status")).toHaveTextContent(/image|图片/i);
    expect(screen.queryByRole("img", { name: "screenshot" })).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    view.rerender(pane(`Before\n\n![screenshot](${imagePath})\n\nAfter`));
    const img = await screen.findByRole("img", { name: "screenshot" });
    expect(img).toHaveAttribute("src", "blob:private-image");
    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer token-a");
    expect(screen.getAllByRole("img", { name: "screenshot" })).toHaveLength(1);
    expect(view.container.querySelector(".chat-bubble-attachments")).toBeNull();
    expect(screen.getByText("Before").compareDocumentPosition(img) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(img.compareDocumentPosition(screen.getByText("After")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("refreshes an expired token through the existing auth flow and retries failed image GET in place", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ user, access_token: "fresh", refresh_token: "refresh-b" })))
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(new Blob(["image"], { type: "image/png" })));
    render(pane(`![screenshot](${imagePath})`));
    const retry = await screen.findByRole("button", { name: /retry|重试/i });
    expect(new Headers(vi.mocked(fetch).mock.calls[2][1]?.headers).get("Authorization")).toBe("Bearer fresh");
    await userEvent.click(retry);
    expect(await screen.findByRole("img", { name: "screenshot" })).toHaveAttribute("src", "blob:private-image");
    expect(vi.mocked(fetch).mock.calls[3][1]?.method ?? "GET").toBe("GET");
  });

  it("supports image decode failure, enlargement and Escape returning focus", async () => {
    render(pane(`![screenshot](${imagePath})`));
    fireEvent.error(await screen.findByRole("img", { name: "screenshot" }));
    await userEvent.click(screen.getByRole("button", { name: /retry|重试/i }));
    await screen.findByRole("img", { name: "screenshot" });
    const trigger = screen.getByRole("button", { name: /enlarge|放大/i });
    await userEvent.click(trigger);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("revokes displayed blobs on logout and prevents late image responses after unmount", async () => {
    const view = render(pane(`![screenshot](${imagePath})`));
    await screen.findByRole("img", { name: "screenshot" });
    act(() => useAuthStore.getState().clear());
    expect(screen.queryByRole("img", { name: "screenshot" })).not.toBeInTheDocument();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:private-image");
    view.unmount();
    act(() => useAuthStore.getState().setSession({ user, access_token: "a", refresh_token: "a" }));
    let resolve!: (response: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise<Response>((done) => { resolve = done; }));
    const pending = render(pane(`![screenshot](${imagePath})`));
    const signal = vi.mocked(fetch).mock.lastCall?.[1]?.signal;
    pending.unmount();
    expect(signal?.aborted).toBe(true);
    vi.mocked(URL.createObjectURL).mockClear();
    await act(async () => resolve(new Response(new Blob(["late"]))));
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it("never carries a prior account's blob into an account switch", async () => {
    const view = render(pane(`![screenshot](${imagePath})`));
    await screen.findByRole("img", { name: "screenshot" });
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(() => {}));
    act(() => useAuthStore.getState().setSession({ user: { ...user, id: "owner-b" }, access_token: "b", refresh_token: "b" }));
    expect(screen.queryByRole("img", { name: "screenshot" })).not.toBeInTheDocument();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:private-image");
    view.unmount();
  });

  it("preserves remote images and code while allowing pending only on image sources", () => {
    render(pane(`![remote](https://example.com${imagePath})\n\n![old](/im/uploads/old.png)\n\n![blocked](javascript:alert)\n\n![data](data:image/png;base64,aGVsbG8=)\n\n[not a link](nano-image-pending:0)\n\n\`![example](nano-image-pending:1)\``));
    expect(screen.getByRole("img", { name: "remote" })).toHaveAttribute("src", `https://example.com${imagePath}`);
    expect(screen.getByRole("img", { name: "old" })).toHaveAttribute("src", "/im/uploads/old.png");
    expect(screen.queryByRole("link", { name: "not a link" })).not.toBeInTheDocument();
    expect(screen.getByText("![example](nano-image-pending:1)").tagName).toBe("CODE");
    expect(fetch).not.toHaveBeenCalled();
    expect(document.querySelector('img[src^="javascript:"], img[src^="data:"], img[src^="nano-image"]')).toBeNull();
  });
});
