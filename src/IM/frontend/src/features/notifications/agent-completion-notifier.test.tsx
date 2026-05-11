import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { WsEvent } from "../chat/v2/chat-types";
import {
  type NotifierState,
  emptyNotifierState,
  reduceNotifierEvent,
  buildNotificationSpec
} from "./agent-completion-notifier";

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

describe("reduceNotifierEvent", () => {
  it("tracks agent message.created", () => {
    const next = reduceNotifierEvent(emptyNotifierState, createdAgent);
    expect(next.agentMessages["msg-1"]).toEqual({
      conversation_id: "conv-1",
      sender_user_id: "agent:asst-1"
    });
  });

  it("ignores user message.created", () => {
    const next = reduceNotifierEvent(emptyNotifierState, createdUser);
    expect(next).toBe(emptyNotifierState);
  });

  it("clears tracked entry on message.completed", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    const next = reduceNotifierEvent(seeded, completedAgent);
    expect(next.agentMessages["msg-1"]).toBeUndefined();
  });
});

describe("buildNotificationSpec", () => {
  const baseCtx = {
    hidden: true,
    enabled: true,
    permissionGranted: true,
    resolveAgentName: (sender: string) => (sender === "agent:asst-1" ? "Assistant" : sender),
    resolveConversationTitle: (cid: string) => (cid === "conv-1" ? "Assistant chat" : cid)
  };

  it("returns spec when agent reply completes and all gates pass", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    const spec = buildNotificationSpec(seeded, completedAgent, baseCtx);
    expect(spec).toEqual({
      title: "Assistant",
      body: "All tests passed.",
      conversationId: "conv-1",
      tag: "im-conv-conv-1"
    });
  });

  it("truncates long body to a single-line preview", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    const long = { ...completedAgent, content: "x".repeat(300) };
    const spec = buildNotificationSpec(seeded, long, baseCtx);
    expect(spec).not.toBeNull();
    expect(spec!.body.length).toBeLessThanOrEqual(140);
  });

  it("returns null when tab is in foreground", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    expect(buildNotificationSpec(seeded, completedAgent, { ...baseCtx, hidden: false })).toBeNull();
  });

  it("returns null when preference is disabled", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    expect(buildNotificationSpec(seeded, completedAgent, { ...baseCtx, enabled: false })).toBeNull();
  });

  it("returns null when permission is not granted", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    expect(buildNotificationSpec(seeded, completedAgent, { ...baseCtx, permissionGranted: false })).toBeNull();
  });

  it("returns null when message is not a tracked agent message", () => {
    const spec = buildNotificationSpec(emptyNotifierState, completedAgent, baseCtx);
    expect(spec).toBeNull();
  });

  it("ignores non-completed events", () => {
    const seeded = reduceNotifierEvent(emptyNotifierState, createdAgent);
    const delta: WsEvent = { type: "message.delta", conversation_id: "conv-1", message_id: "msg-1", delta_text: "hi" };
    expect(buildNotificationSpec(seeded, delta, baseCtx)).toBeNull();
  });
});

// ── Integration: real reducer + real preference + fake Notification ──
import { render, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";

import * as streamModule from "../chat/v2/chat-stream";
import { setNotificationPreference, NOTIFICATION_PREFERENCE_STORAGE_KEY } from "./notification-preference";
import { AgentCompletionNotifier } from "./agent-completion-notifier";

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

let capturedOnEvent: ((ev: WsEvent) => void) | null = null;

function LocationCapture({ onChange }: { onChange: (path: string) => void }) {
  const loc = useLocation();
  useEffect(() => {
    onChange(loc.pathname);
  }, [loc.pathname, onChange]);
  return null;
}

function renderHarness() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["chat-v2", "conversations"], [
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
  capturedOnEvent = null;
  vi.spyOn(streamModule, "openChatStream").mockImplementation((opts) => {
    capturedOnEvent = opts.onEvent;
    return { close: () => {} };
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (globalThis as unknown as { Notification?: unknown }).Notification;
  setHidden(false);
  localStorage.removeItem(NOTIFICATION_PREFERENCE_STORAGE_KEY);
});

describe("AgentCompletionNotifier integration", () => {
  it("fires Notification when preference on + hidden + permission granted + agent completes", async () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    const { getPath } = renderHarness();
    setHidden(true);
    act(() => {
      capturedOnEvent!(createdAgent);
      capturedOnEvent!(completedAgent);
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
      capturedOnEvent!(createdAgent);
      capturedOnEvent!(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not fire when document is visible (tab active)", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    renderHarness();
    setHidden(false);
    act(() => {
      capturedOnEvent!(createdAgent);
      capturedOnEvent!(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not fire for user messages echo", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    renderHarness();
    setHidden(true);
    act(() => {
      capturedOnEvent!(createdUser);
      capturedOnEvent!({ ...completedAgent, message_id: "msg-user-1" });
    });
    expect(installedNotificationCalls.length).toBe(0);
  });
});
