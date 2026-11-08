import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { useAuthStore } from "../../auth/auth-store";
import type { UserStreamEvent } from "../../../realtime/user-stream";
import { InAppToast } from "../components/in-app-toast";
import { useGlobalMessageToast } from "./use-global-message-toast";

const { getConversation, subscribeUserStream } = vi.hoisted(() => ({
  getConversation: vi.fn(), subscribeUserStream: vi.fn()
}));
vi.mock("../chat-api", () => ({ getConversation, listConversations: vi.fn() }));
vi.mock("../../../realtime/user-stream", () => ({ subscribeUserStream }));

function ToastSurface() {
  const { toast, dismiss } = useGlobalMessageToast();
  return toast && <InAppToast conversationTitle={toast.conversationTitle} senderName={toast.isGroup ? toast.senderName : undefined}
    preview={toast.preview} conversationId={toast.conversationId} onDismiss={dismiss} />;
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  useAuthStore.getState().setSession({ access_token: "test", user: {
    id: "self", username: "nano", display_name: "Test User", owner_id: "self", locale: "en",
    membership_status: "active", is_company_admin: true, default_entry_node_id: null, owned_node_ids: [], created_at: ""
  } });
});

it.each([
  { type: "direct", senderType: "agent", title: "周末出行计划", sender: "旅行助手", showSender: false },
  { type: "group", senderType: "agent", title: "产品讨论群", sender: "项目助手", showSender: true },
  { type: "group", senderType: "user", title: "产品讨论群", sender: "小陈", showSender: true }
])("resolves $type / $senderType reminder source with an initially empty chat cache", async ({ type, senderType, title, sender, showSender }) => {
  getConversation.mockResolvedValue({ id: "room", type, title, participants: [] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/settings/agents"]}>
    <ToastSurface />
  </MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(subscribeUserStream).toHaveBeenCalled());
  const { onEvent } = subscribeUserStream.mock.lastCall![0] as { onEvent(event: UserStreamEvent): void };
  act(() => {
    onEvent({ eventType: "message.created", eventId: 1, payload: {
      conversation_id: "room", message_id: "message", sender_type: senderType,
      sender_user_id: "ab3e25b7-c05e-4e8f-9524-88363180ab99",
      sender: { id: "ab3e25b7-c05e-4e8f-9524-88363180ab99", display_name: sender },
      content: senderType === "user" ? "方案已整理完成。" : ""
    } });
    if (senderType === "agent") onEvent({ eventType: "message.completed", eventId: 2, payload: {
      conversation_id: "room", message_id: "message", content: "方案已整理完成。"
    } });
  });
  expect(await screen.findByText(title)).toBeInTheDocument();
  expect(screen.getByText("方案已整理完成。")).toBeInTheDocument();
  expect(Boolean(screen.queryByText(sender))).toBe(showSender);
  expect(screen.queryByText("ab3e25b7-c05e-4e8f-9524-88363180ab99")).not.toBeInTheDocument();
  expect(screen.getByRole("link")).toHaveAttribute("href", "/chat/room");
  client.clear();
});
