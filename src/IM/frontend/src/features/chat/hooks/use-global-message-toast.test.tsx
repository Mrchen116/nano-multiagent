import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../../auth/auth-store";
import type { Conversation } from "../v2/chat-types";

let streamHandler: ((event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) => void) | null = null;

vi.mock("../v2/chat-api", () => ({
  listConversations: vi.fn(),
}));

vi.mock("../../../realtime/user-stream", () => ({
  subscribeUserStream: vi.fn(
    (input: {
      onEvent: (event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) => void;
      onRecovery?: () => Promise<void>;
    }) => {
      streamHandler = input.onEvent;
      return () => {
        streamHandler = null;
      };
    }
  )
}));

import * as chatApi from "../v2/chat-api";
import * as userStream from "../../../realtime/user-stream";
import { useGlobalMessageToast } from "./use-global-message-toast";

const listConversationsMock = vi.mocked(chatApi.listConversations);
const subscribeUserStreamMock = vi.mocked(userStream.subscribeUserStream);

function conversation(id: string, overrides: Partial<Conversation> = {}): Conversation {
  return {
    id,
    title: "Chat",
    participants: [],
    participant_ids: [],
    type: "direct",
    direct_kind: "agent",
    owner_id: "self-user",
    creator_id: "self-user",
    is_pinned: false,
    is_muted: false,
    unread_count: 0,
    last_message_preview: null,
    last_message_at: null,
    created_at: "2026-03-26T00:00:00Z",
    ...overrides
  };
}

function buildWrapper(queryClient: QueryClient, route = "/") {
  return function Wrapper(props: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{props.children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

function emit(conversationId: string, event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) {
  if (!streamHandler) {
    throw new Error("stream handler not attached");
  }
  act(() => {
    streamHandler?.({
      ...event,
      payload: { ...event.payload, conversation_id: conversationId }
    });
  });
}

describe("useGlobalMessageToast", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  beforeEach(() => {
    streamHandler = null;
    vi.clearAllMocks();
    useAuthStore.getState().setSession({
      access_token: "token",
      refresh_token: "refresh",
      user: {
        id: "self-user", username: "self", display_name: "Self", owner_id: "self-user", locale: "en",
        default_entry_node_id: null, owned_node_ids: [], created_at: ""
      }
    });
    listConversationsMock.mockResolvedValue([conversation("conv-1")]);
  });

  it("只建立一条用户流订阅", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalledTimes(1));
  });

  it("同一会话上重复 eventId 不重复提示", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 11,
      payload: { message_id: "new-1", sender_type: "user", sender_user_id: "user:peer", content: "fresh" }
    });

    expect(result.current.toast).toMatchObject({ id: "message:new-1", preview: "fresh" });

    act(() => {
      result.current.dismiss();
    });
    expect(result.current.toast).toBeNull();

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 11,
      payload: { message_id: "new-1", sender_type: "user", sender_user_id: "user:peer", content: "fresh" }
    });

    expect(result.current.toast).toBeNull();
  });

  it("dedupes message_created and message.sent for the same message id", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

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
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "relay.report",
      eventId: 1,
      payload: { message_id: "m-1", agent_id: "ops-bot", summary: "thinking" }
    });
    expect(result.current.toast).toBeNull();

    emit("conv-1", {
      eventType: "relay.completed",
      eventId: 2,
      payload: {
        message_id: "m-1",
        relay_task_id: "relay-1",
        agent_id: "ops-bot",
        detail: "Done",
        sender_display_name: "Ops Bot"
      }
    });

    expect(result.current.toast).toMatchObject({ id: "relay:m-1:relay-1", senderName: "Ops Bot", preview: "Done" });
  });

  it("suppresses NO_REPLY relay completions", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

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
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/chat/conv-1") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 1,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:peer", content: "hello" }
    });

    expect(result.current.toast).toBeNull();
  });

  it("still refreshes the cached sidebar preview for self-authored user messages", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["chat-v2", "conversations"], [
      conversation("conv-1", {
        last_message_preview: "older",
        last_message_at: "2026-03-26T00:00:00Z"
      })
    ]);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 1,
      payload: {
        message_id: "m-1",
        sender_type: "user",
        sender_user_id: "user:self-user",
        content: "my own message",
        created_at: "2026-03-26T00:01:00Z"
      }
    });

    expect(result.current.toast).toBeNull();
    expect(queryClient.getQueryData(["chat-v2", "conversations"])).toEqual([
      conversation("conv-1", {
        last_message_preview: "my own message",
        last_message_at: "2026-03-26T00:01:00Z"
      })
    ]);
  });

  it("refreshes the cached sidebar preview when an unopened conversation finishes a relay turn", async () => {
    listConversationsMock.mockResolvedValue([
      conversation("conv-2", {
        title: "Agent chat",
        last_message_preview: "11",
        last_message_at: "2026-03-26T00:00:00Z"
      })
    ]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["chat-v2", "conversations"], [
      conversation("conv-2", {
        title: "Agent chat",
        last_message_preview: "11",
        last_message_at: "2026-03-26T00:00:00Z"
      })
    ]);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-2", {
      eventType: "relay.completed",
      eventId: 1,
      payload: {
        message_id: "m-1",
        relay_task_id: "relay-1",
        agent_id: "ops-bot",
        sender_display_name: "Ops Bot",
        detail: "A\n\nGot it. What would you like to do?",
        created_at: "2026-03-26T00:02:00Z"
      }
    });

    expect(result.current.toast).toMatchObject({
      conversationId: "conv-2",
      preview: "A\n\nGot it. What would you like to do?"
    });
    expect(queryClient.getQueryData(["chat-v2", "conversations"])).toEqual([
      conversation("conv-2", {
        title: "Agent chat",
        last_message_preview: "A\n\nGot it. What would you like to do?",
        last_message_at: "2026-03-26T00:02:00Z"
      })
    ]);
  });
});
