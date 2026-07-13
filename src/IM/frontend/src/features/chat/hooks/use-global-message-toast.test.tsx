import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../../auth/auth-store";
import type { Conversation } from "../chat-types";
import {
  hasLocalUnreadFeedback,
  resetLocalUnreadFeedback
} from "../../notifications/local-unread-feedback";

const { listConversationsMock } = vi.hoisted(() => ({
  listConversationsMock: vi.fn()
}));

vi.mock("../chat-api", () => ({
  listConversations: listConversationsMock
}));

let streamHandler: ((event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) => void) | null = null;
let recoveryHandler: (() => Promise<void>) | null = null;

vi.mock("../../../realtime/user-stream", () => ({
  subscribeUserStream: vi.fn(
    (input: {
      onEvent: (event: { eventType: string; payload: Record<string, unknown>; eventId?: number }) => void;
      onRecovery?: () => Promise<void>;
    }) => {
      streamHandler = input.onEvent;
      recoveryHandler = input.onRecovery ?? null;
      return () => {
        streamHandler = null;
        recoveryHandler = null;
      };
    }
  )
}));

import * as userStream from "../../../realtime/user-stream";
import { useGlobalMessageToast } from "./use-global-message-toast";

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

function buildRefetchingWrapper(
  queryClient: QueryClient,
  queryFn: () => Promise<Conversation[]>,
  route = "/"
) {
  function ConversationObserver() {
    useQuery({ queryKey: ["chat", "conversations"], queryFn });
    return null;
  }
  return function Wrapper(props: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <ConversationObserver />
          {props.children}
        </MemoryRouter>
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
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    streamHandler = null;
    recoveryHandler = null;
    vi.clearAllMocks();
    sessionStorage.clear();
    resetLocalUnreadFeedback();
    listConversationsMock.mockReset();
    listConversationsMock.mockResolvedValue([]);
    useAuthStore.getState().setSession({
      access_token: "token",
      refresh_token: "refresh",
      user: {
        id: "self-user", username: "self", display_name: "Self", owner_id: "self-user", locale: "en",
        default_entry_node_id: null, owned_node_ids: [], created_at: ""
      }
    });
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

  it("ignores retired message_created and accepts canonical message.sent", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });

    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message_created",
      eventId: 1,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:peer", content: "hello" }
    });
    expect(result.current.toast).toBeNull();

    emit("conv-1", {
      eventType: "message.sent",
      eventId: 2,
      payload: { message_id: "m-1", sender_type: "user", sender_user_id: "user:peer", content: "hello" }
    });

    expect(result.current.toast?.id).toBe("message:m-1");
  });

  it("toasts an external shadow user message from its canonical created event", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["chat", "conversations"], [
      conversation("conv-external", {
        title: "Feishu chat",
        external_source: "feishu",
        external_chat_id: "oc_external"
      })
    ]);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    // This is the actual repository sequence: message.sent is only a receipt;
    // message.created carries the external sender name and visible content.
    emit("conv-external", {
      eventType: "message.sent",
      eventId: 1,
      payload: { message_id: "external-1", semantic: "persisted_to_im" }
    });
    emit("conv-external", {
      eventType: "message.created",
      eventId: 2,
      payload: {
        message_id: "external-1",
        sender_type: "user",
        sender_user_id: "user-a",
        sender_display_name: "Alice from Feishu",
        content: "hello from feishu",
        created_at: "2026-07-13T00:00:00Z"
      }
    });

    expect(result.current.toast).toMatchObject({
      id: "message:external-1",
      senderName: "Alice from Feishu",
      preview: "hello from feishu"
    });
    expect(hasLocalUnreadFeedback("conv-external")).toBe(true);
  });

  it("forces an authoritative lookup for a new external conversation even while the list cache is fresh", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 60_000 } }
    });
    queryClient.setQueryData(["chat", "conversations"], [conversation("conv-existing")]);
    listConversationsMock.mockResolvedValue([
      conversation("conv-new-external", {
        title: "New Feishu chat",
        external_source: "feishu",
        external_chat_id: "oc_new"
      })
    ]);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-new-external", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "external-new-1",
        sender_type: "user",
        sender_user_id: "self-user",
        sender_display_name: "New Feishu Sender",
        content: "first external message",
        created_at: "2026-07-13T00:00:00Z"
      }
    });

    await waitFor(() => {
      expect(listConversationsMock).toHaveBeenCalledTimes(1);
      expect(result.current.toast).toMatchObject({
        id: "message:external-new-1",
        senderName: "New Feishu Sender",
        preview: "first external message"
      });
      expect(hasLocalUnreadFeedback("conv-new-external")).toBe(true);
    });
  });

  it("does not reuse an older in-flight conversations request for external classification", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let resolveOldRequest!: (value: Conversation[]) => void;
    const oldRequest = queryClient.fetchQuery({
      queryKey: ["chat", "conversations"],
      queryFn: () => new Promise<Conversation[]>((resolve) => { resolveOldRequest = resolve; })
    }).catch(() => undefined);
    listConversationsMock.mockResolvedValue([
      conversation("conv-new-external", { external_source: "feishu", external_chat_id: "oc_new" })
    ]);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-new-external", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "external-inflight-1",
        sender_type: "user",
        sender_user_id: "self-user",
        sender_display_name: "In-flight External Sender",
        content: "classify after candidate arrival"
      }
    });
    await waitFor(() => expect(listConversationsMock).toHaveBeenCalledTimes(1));
    resolveOldRequest([conversation("conv-existing")]);
    await oldRequest;

    await waitFor(() => {
      expect(result.current.toast).toMatchObject({ id: "message:external-inflight-1" });
      expect(queryClient.getQueryData<Conversation[]>(["chat", "conversations"]))
        .toEqual(expect.arrayContaining([
          expect.objectContaining({
            id: "conv-new-external",
            external_source: "feishu",
            last_message_preview: "classify after candidate arrival",
            unread_count: 1
          })
        ]));
    });
  });

  it("does not cancel or overwrite a newer conversations refetch when authority returns later", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let resolveAuthority!: (value: Conversation[]) => void;
    listConversationsMock.mockReturnValue(
      new Promise<Conversation[]>((resolve) => { resolveAuthority = resolve; })
    );
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-new-external", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "external-newer-cache-1",
        sender_type: "user",
        sender_user_id: "self-user",
        sender_display_name: "External Sender",
        content: "new external content"
      }
    });
    await waitFor(() => expect(listConversationsMock).toHaveBeenCalledTimes(1));

    const newerConversation = conversation("conv-new-external", {
      title: "Newer refetch title",
      external_source: "feishu",
      external_chat_id: "oc_new"
    });
    await queryClient.fetchQuery({
      queryKey: ["chat", "conversations"],
      queryFn: async () => [newerConversation]
    });
    resolveAuthority([
      conversation("conv-new-external", {
        title: "Older authority title",
        external_source: "feishu",
        external_chat_id: "oc_new"
      })
    ]);

    await waitFor(() => {
      expect(result.current.toast).toMatchObject({ id: "message:external-newer-cache-1" });
      expect(queryClient.getQueryData<Conversation[]>(["chat", "conversations"]))
        .toEqual(expect.arrayContaining([
          expect.objectContaining({ id: "conv-new-external", title: "Newer refetch title" })
        ]));
    });
  });

  it("retries an unresolved external classification during stream recovery", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 60_000 } }
    });
    queryClient.setQueryData(["chat", "conversations"], [conversation("conv-existing")]);
    listConversationsMock
      .mockRejectedValueOnce(new Error("temporary conversations failure"))
      .mockResolvedValue([
        conversation("conv-new-external", {
          external_source: "feishu",
          external_chat_id: "oc_new"
        })
      ]);
    const { result } = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-new-external", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "external-retry-1",
        sender_type: "user",
        sender_user_id: "self-user",
        sender_display_name: "Recovered External Sender",
        content: "recover this notification"
      }
    });

    await waitFor(() => expect(listConversationsMock).toHaveBeenCalledTimes(1));
    expect(result.current.toast).toBeNull();
    await act(async () => {
      await recoveryHandler?.();
    });

    await waitFor(() => {
      expect(listConversationsMock).toHaveBeenCalledTimes(2);
      expect(result.current.toast).toMatchObject({
        id: "message:external-retry-1",
        senderName: "Recovered External Sender",
        preview: "recover this notification"
      });
      expect(hasLocalUnreadFeedback("conv-new-external")).toBe(true);
    });
  });

  it("does not persist an unchanged completion accumulator for streaming deltas", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    vi.stubGlobal("sessionStorage", storage);
    renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(queryClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "agent-stream-1",
        sender_type: "agent",
        sender_user_id: "agent:a",
        content: "",
        tool_calls: [],
        token_usage: null,
        delivery_status: "running",
        created_at: "2026-07-13T00:00:00Z"
      }
    });
    storage.setItem.mockClear();
    emit("conv-1", {
      eventType: "message.delta",
      eventId: 2,
      payload: { message_id: "agent-stream-1", delta_text: "token" }
    });

    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("treats relay.report and relay.completed as non-notifying receipts", async () => {
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

    expect(result.current.toast).toBeNull();
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
    queryClient.setQueryData(["chat", "conversations"], [
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
    expect(queryClient.getQueryData(["chat", "conversations"])).toEqual([
      conversation("conv-1", {
        last_message_preview: "my own message",
        last_message_at: "2026-03-26T00:01:00Z"
      })
    ]);
  });

  it("does not let a relay receipt overwrite canonical conversation preview", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["chat", "conversations"], [
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

    expect(result.current.toast).toBeNull();
    expect(queryClient.getQueryData(["chat", "conversations"])).toEqual([
      conversation("conv-2", {
        title: "Agent chat",
        last_message_preview: "11",
        last_message_at: "2026-03-26T00:00:00Z"
      })
    ]);
  });

  it("toasts a canonical agent completion and refetches authoritative unread, preview, and order", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const initial = [
      conversation("conv-current", { title: "Current", last_message_at: "2026-03-26T00:02:00Z" }),
      conversation("conv-agent", { title: "Agent", last_message_preview: "old", unread_count: 0 })
    ];
    const refreshed = [
      conversation("conv-agent", {
        title: "Agent",
        last_message_preview: "Finished in the background",
        last_message_at: "2026-03-26T00:03:00Z",
        // Another same-account browser may already have read the server row.
        // This tab must still retain visible local feedback for the live completion.
        unread_count: 0
      }),
      initial[0]!
    ];
    const queryFn = vi.fn().mockResolvedValueOnce(initial).mockResolvedValueOnce(refreshed);
    const { result } = renderHook(() => useGlobalMessageToast(), {
      wrapper: buildRefetchingWrapper(queryClient, queryFn, "/chat/conv-current")
    });
    await waitFor(() => expect(queryClient.getQueryData(["chat", "conversations"])).toEqual(initial));

    emit("conv-agent", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "agent-msg-1",
        sender_type: "agent",
        sender_user_id: "agent:planner",
        sender_display_name: "Planner",
        content: "",
        created_at: "2026-03-26T00:03:00Z"
      }
    });
    expect(result.current.toast).toBeNull();

    emit("conv-agent", {
      eventType: "message.completed",
      eventId: 2,
      payload: { message_id: "agent-msg-1", content: "Finished in the background" }
    });

    await waitFor(() => {
      expect(result.current.toast).toMatchObject({
        id: "message:agent-msg-1",
        conversationId: "conv-agent",
        senderName: "Planner",
        preview: "Finished in the background"
      });
      expect(queryFn).toHaveBeenCalledTimes(2);
      expect(queryClient.getQueryData<Conversation[]>(["chat", "conversations"])?.[0]).toMatchObject({
        id: "conv-agent",
        last_message_preview: "Finished in the background",
        unread_count: 1
      });
    });

    // A later sibling consumer may refresh authoritative unread back to zero;
    // the view layer keeps this tab's live unseen overlay until navigation.
    queryClient.setQueryData(["chat", "conversations"], refreshed);
    expect(queryClient.getQueryData<Conversation[]>(["chat", "conversations"])?.[0]?.unread_count).toBe(0);
    expect(hasLocalUnreadFeedback("conv-agent")).toBe(true);
  });

  it("restores pending sender identity when reload falls between created and completed", async () => {
    const firstClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const first = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(firstClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());
    emit("conv-agent", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "agent-msg-reload",
        sender_type: "agent",
        sender_user_id: "agent:planner",
        sender_display_name: "Planner",
        content: "",
        created_at: "2026-03-26T00:03:00Z"
      }
    });
    first.unmount();

    const secondClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const second = renderHook(() => useGlobalMessageToast(), { wrapper: buildWrapper(secondClient, "/") });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalledTimes(2));
    emit("conv-agent", {
      eventType: "message.completed",
      eventId: 2,
      payload: { message_id: "agent-msg-reload", content: "Survived reload" }
    });

    expect(second.result.current.toast).toMatchObject({
      id: "message:agent-msg-reload",
      senderName: "Planner",
      preview: "Survived reload"
    });
  });

  it("does not toast a canonical agent completion for the currently open conversation", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useGlobalMessageToast(), {
      wrapper: buildWrapper(queryClient, "/chat/conv-1")
    });
    await waitFor(() => expect(subscribeUserStreamMock).toHaveBeenCalled());

    emit("conv-1", {
      eventType: "message.created",
      eventId: 1,
      payload: {
        message_id: "agent-msg-1",
        sender_type: "agent",
        sender_user_id: "agent:planner",
        sender_display_name: "Planner",
        content: ""
      }
    });
    emit("conv-1", {
      eventType: "message.completed",
      eventId: 2,
      payload: { message_id: "agent-msg-1", content: "Done" }
    });

    expect(result.current.toast).toBeNull();
  });
});
