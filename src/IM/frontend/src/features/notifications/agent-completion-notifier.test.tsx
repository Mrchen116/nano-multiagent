import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentCompletionCandidate } from "./agent-completion-accumulator";

const completedAgent: AgentCompletionCandidate = {
  conversationId: "conv-1",
  messageId: "msg-1",
  messageKey: "message:msg-1",
  senderUserId: "agent:asst-1",
  senderName: "agent:asst-1",
  preview: "All tests passed."
};

// ── Integration: coordinator candidate + real preference + fake Notification ──
import { render, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";

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
  const view = (candidate: AgentCompletionCandidate | null) => (
    <MemoryRouter initialEntries={["/me"]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="*" element={<>
            <AgentCompletionNotifier candidate={candidate} />
            <LocationCapture onChange={onPath} />
          </>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
  const utils = render(view(null));
  return {
    ...utils,
    getPath: () => lastPath,
    pushCandidate(candidate: AgentCompletionCandidate | null) {
      utils.rerender(view(candidate));
    }
  };
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
    const { getPath, pushCandidate } = renderHarness();
    setHidden(true);
    act(() => {
      pushCandidate(completedAgent);
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
    const { pushCandidate } = renderHarness();
    setHidden(true);
    act(() => {
      pushCandidate(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not fire when document is visible (tab active)", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    const { pushCandidate } = renderHarness();
    setHidden(false);
    act(() => {
      pushCandidate(completedAgent);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not fire when browser permission is denied", () => {
    installFakeNotification("denied");
    setNotificationPreference(true);
    const { pushCandidate } = renderHarness();
    setHidden(true);
    act(() => {
      pushCandidate(completedAgent);
    });
    expect(installedNotificationCalls).toHaveLength(0);
  });

  it("does not fire without a coordinator candidate", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    const { pushCandidate } = renderHarness();
    setHidden(true);
    act(() => {
      pushCandidate(null);
    });
    expect(installedNotificationCalls.length).toBe(0);
  });

  it("does not repeat the same candidate on rerender", () => {
    installFakeNotification("granted");
    setNotificationPreference(true);
    const { pushCandidate } = renderHarness();
    setHidden(true);
    act(() => pushCandidate(completedAgent));
    act(() => pushCandidate({ ...completedAgent }));

    expect(installedNotificationCalls).toHaveLength(1);
  });
});
