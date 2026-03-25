import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const streamHandlers = new Map<string, (event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) => void>();

vi.mock("../chat-api", () => ({
  listConversations: vi.fn(),
  getChatBootstrapState: vi.fn(),
  getConversationLatestEventId: vi.fn(),
  streamConversationEvents: vi.fn()
}));

import * as chatApi from "../chat-api";
import { useGlobalMessageToast } from "./use-global-message-toast";

const listConversationsMock = vi.mocked(chatApi.listConversations);
const getChatBootstrapStateMock = vi.mocked(chatApi.getChatBootstrapState);
const getConversationLatestEventIdMock = vi.mocked(chatApi.getConversationLatestEventId);
const streamConversationEventsMock = vi.mocked(chatApi.streamConversationEvents);

function buildWrapper(route = "/") {
  return function Wrapper(props: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[route]}>{props.children}</MemoryRouter>;
  };
}

function emit(conversationId: string, event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) {
  const handler = streamHandlers.get(conversationId);
  if (!handler) {
    throw new Error(`missing stream handler for ${conversationId}`);
  }
  act(() => {
    handler(event);
  });
}

describe("useGlobalMessageToast", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  beforeEach(() => {
    streamHandlers.clear();
    vi.clearAllMocks();
    listConversationsMock.mockResolvedValue([{ conversation_id: "conv-1", unread_count: 0, participants: [], title: "Chat" }]);
    getChatBootstrapStateMock.mockResolvedValue({
      selfUserId: "self-user",
      ownerId: "owner-1",
      targetNodeId: "node-1",
      targetNodeStatus: "online",
      initialConversationId: "conv-1",
      ownership: {
        nodeId: null,
        nodeLabel: null,
        nodeStatus: null,
        agentLabel: null,
        ownershipLabel: null
      }
    });
    getConversationLatestEventIdMock.mockResolvedValue(0);
    streamConversationEventsMock.mockImplementation(
      ({ conversationId, onEvent }: { conversationId: string; onEvent: (event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) => void }) => {
        streamHandlers.set(conversationId, onEvent);
        return () => streamHandlers.delete(conversationId);
      }
    );
  });

  it("suppresses replayed history at the startup baseline and only toasts newer events", async () => {
    getConversationLatestEventIdMock.mockResolvedValue(10);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalledWith(expect.objectContaining({ conversationId: "conv-1", afterEventId: 10 })));

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 10,
      payload: { message_id: "old-1", sender_type: "user", sender_user_id: "user:peer", content: "old" }
    });
    expect(result.current.toast).toBeNull();

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 11,
      payload: { message_id: "new-1", sender_type: "user", sender_user_id: "user:peer", content: "fresh" }
    });

    expect(result.current.toast).toMatchObject({ id: "message:new-1", preview: "fresh" });
  });

  it("dedupes message_created and message.sent for the same message id", async () => {
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message_created",
      eventId: 1,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:peer", content: "hello" }
    });
    expect(result.current.toast?.id).toBe("message:m-1");

    act(() => {
      result.current.dismiss();
    });
    expect(result.current.toast).toBeNull();

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 2,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:peer", content: "hello" }
    });

    expect(result.current.toast).toBeNull();
  });

  it("ignores relay.report but toasts one relay.completed reply", async () => {
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "relay.report",
      eventId: 1,
      payload: { message_id: "m-1", agent_id: "ops-bot", summary: "thinking" }
    });
    expect(result.current.toast).toBeNull();

    emit("conv-1", {
      eventType: "relay.completed",
      eventId: 2,
      payload: { message_id: "m-1", relay_task_id: "relay-1", agent_id: "ops-bot", detail: "Done", sender_display_name: "Ops Bot" }
    });

    expect(result.current.toast).toMatchObject({ id: "relay:m-1:relay-1", senderName: "Ops Bot", preview: "Done" });
  });

  it("suppresses NO_REPLY relay completions", async () => {
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "relay.completed",
      eventId: 1,
      payload: {
        message_id: "m-1",
        relay_task_id: "relay-1",
        agent_id: "ops-bot",
        detail: "suppressed_by=no_reply_token"
      }
    });

    expect(result.current.toast).toBeNull();
  });

  it("does not toast for the currently open conversation", async () => {
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/chat/conv-1") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 1,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:peer", content: "hello" }
    });

    expect(result.current.toast).toBeNull();
  });

  it("does not toast for self-authored user messages", async () => {
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 1,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:self-user", content: "my own message" }
    });

    expect(result.current.toast).toBeNull();
  });

  it("subscribes to conversations discovered after mount and toasts the replayed latest unread event", async () => {
    listConversationsMock
      .mockResolvedValueOnce([{ conversation_id: "conv-1", unread_count: 0, participants: [], title: "Chat" }])
      .mockResolvedValueOnce([
        { conversation_id: "conv-2", unread_count: 1, participants: [], title: "New chat" },
        { conversation_id: "conv-1", unread_count: 0, participants: [], title: "Chat" }
      ]);
    getConversationLatestEventIdMock.mockImplementation(async (conversationId: string) => (conversationId === "conv-2" ? 5 : 0));

    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper("/") });

    await waitFor(() => expect(streamConversationEventsMock).toHaveBeenCalledWith(expect.objectContaining({ conversationId: "conv-1", afterEventId: 0 })));
    await waitFor(
      () => expect(streamConversationEventsMock).toHaveBeenCalledWith(expect.objectContaining({ conversationId: "conv-2", afterEventId: 4 })),
      { timeout: 4000 }
    );

    emit("conv-2", {
      eventType: "message.sent",
      eventId: 5,
      payload: { message_id: "new-direct-1", sender_type: "agent", sender_display_name: "Ops Bot", content: "fresh dm" }
    });

    expect(result.current.toast).toMatchObject({
      id: "message:new-direct-1",
      conversationId: "conv-2",
      senderName: "Ops Bot",
      preview: "fresh dm"
    });
  }, 10000);
});
