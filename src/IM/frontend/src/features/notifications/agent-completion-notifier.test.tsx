import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { WsEvent } from "../chat/chat-types";

const createdAgent: WsEvent = {
  type: "message.created",
  conversation_id: "conv-1",
  message_id: "msg-1",
  sender_user_id: "agent:asst-1",
  sender_type: "agent",
  content: "",
  tool_calls: [],
  token_usage: null,
  delivery_status: "running",
  created_at: "2026-05-11T00:00:00Z"
};

const createdUser: WsEvent = {
  ...createdAgent,
  message_id: "msg-user-1",
  sender_user_id: "user:alice",
  sender_type: "user"
};

const completedAgent: WsEvent = {
  type: "message.completed",
  conversation_id: "conv-1",
  message_id: "msg-1",
  content: "All tests passed.",
  token_usage: null
};

// ── Integration: real reducer + real preference + fake Notification ──
import { render, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";

import * as streamModule from "../../realtime/user-stream";
import type { UserStreamEvent } from "../../realtime/user-stream";
import { setNotificationPreference, NOTIFICATION_PREFERENCE_STORAGE_KEY } from "./notification-preference";
import { AgentCompletionNotifier } from "./agent-completion-notifier";
import { useAuthStore } from "../auth/auth-store";

let installedNotificationCalls: { title: string; options?: NotificationOptions; instance: { onclick: ((this: unknown) => void) | null; close: () => void } }[] = [];

function installFakeNotification(permission: NotificationPermission) {
  installedNotificationCalls = [];
  const calls = installedNotificationCalls;
  const fake = vi.fn(function (this: unknown, title: string, options?: NotificationOptions) {
    const instance = { onclick: null as ((this: unknown) => void) | null, close: vi.fn() };
    calls.push({ title, options, instance });
    return instance;
  }) as unknown as typeof Notification & { permission: NotificationPermission; requestPermission: () => Promise<NotificationPermission> };
  fake.permission = permission;
  fake.requestPermission = vi.fn(async () => permission);
  (globalThis as unknown as { Notification: unknown }).Notification = fake;
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => (hidden ? "hidden" : "visible")
  });
  document.dispatchEvent(new Event("visibilitychange"));
}

let capturedOnEvent: ((ev: UserStreamEvent) => void) | null = null;

function emitNotifierEvent(event: WsEvent): void {
  const { type, ...payload } = event;
  capturedOnEvent?.({ eventType: type, payload });
}

function LocationCapture({ onChange }: { onChange: (path: string) => void }) {
  const loc = useLocation();
  useEffect(() => {
    onChange(loc.pathname);
  }, [loc.pathname, onChange]);
  return null;
}

function renderHarness() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["chat", "conversations"], [
    {
      id: "conv-1",
      title: "Assistant chat",
      participants: [
        { type: "agent", id: "asst-1", display_name: "Assistant" }
      ],
      participant_ids: ["agent:asst-1"]
    }
  ]);
  let lastPath = "/";
  const onPath = (p: string) => {
    lastPath = p;
  };
  const utils = render(
    <MemoryRouter initialEntries={["/me"]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="*" element={<>
            <AgentCompletionNotifier />
            <LocationCapture onChange={onPath} />
          </>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
  return { ...utils, getPath: () => lastPath };
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  useAuthStore.getState().setSession({
    access_token: "token-a",
    refresh_token: "refresh-a",
    user: {
      id: "user-a", username: "alice", display_name: "Alice", owner_id: "user-a", locale: "en",
      default_entry_node_id: null, owned_node_ids: [], created_at: ""
    }
  });
  capturedOnEvent = null;
  vi.spyOn(streamModule, "subscribeUserStream").mockImplementation((subscriber) => {
    capturedOnEvent = subscriber.onEvent;
    return () => undefined;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (globalThis as unknown as { Notification?: unknown }).Notification;
  setHidden(false);
  localStorage.removeItem(NOTIFICATION_PREFERENCE_STORAGE_KEY);
  sessionStorage.clear();
});

describe("AgentCompletionNotifier integration", () => {
  it("fires Notification when preference on + hidden + permission granted + agent completes", async () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    const { getPath } = renderHarness();
    setHidden(true);
    act(() => {
      emitNotifierEvent(createdAgent);
      emitNotifierEvent(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(1);
    expect(installedNotificationCalls[0].title).toBe("Assistant");
    expect(installedNotificationCalls[0].options?.body).toBe("All tests passed.");

    // Click should navigate to /chat/conv-1.
    const focusSpy = vi.spyOn(window, "focus").mockImplementation(() => {});
    act(() => {
      installedNotificationCalls[0].instance.onclick?.call(installedNotificationCalls[0].instance);
    });
    expect(focusSpy).toHaveBeenCalled();
    expect(getPath()).toBe("/chat/conv-1");
  });

  it("does not fire when preference is disabled (toggle off)", () => {
    installFakeNotification("granted");
    setNotificationPreference(false);
    renderHarness();
    setHidden(true);
    act(() => {
      emitNotifierEvent(createdAgent);
      emitNotifierEvent(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not fire when document is visible (tab active)", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    renderHarness();
    setHidden(false);
    act(() => {
      emitNotifierEvent(createdAgent);
      emitNotifierEvent(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not fire when browser permission is denied", () => {
    installFakeNotification("denied");
    setNotificationPreference(true);
    renderHarness();
    setHidden(true);
    act(() => {
      emitNotifierEvent(createdAgent);
      emitNotifierEvent(completedAgent);
    });
    expect(installedNotificationCalls).toHaveLength(0);
  });

  it("does not fire for user messages echo", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    renderHarness();
    setHidden(true);
    act(() => {
      emitNotifierEvent(createdUser);
      emitNotifierEvent({ ...completedAgent, message_id: "msg-user-1" });
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not carry an in-flight notification candidate across an account switch", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    renderHarness();
    setHidden(true);
    act(() => emitNotifierEvent(createdAgent));

    act(() => useAuthStore.getState().setSession({
      access_token: "token-b",
      refresh_token: "refresh-b",
      user: {
        id: "user-b", username: "bob", display_name: "Bob", owner_id: "user-b", locale: "en",
        default_entry_node_id: null, owned_node_ids: [], created_at: ""
      }
    }));
    act(() => emitNotifierEvent(completedAgent));

    expect(installedNotificationCalls).toHaveLength(0);
  });
});
