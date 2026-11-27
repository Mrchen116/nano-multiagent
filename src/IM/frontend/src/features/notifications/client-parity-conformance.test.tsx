import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  computeConversationRowUnread,
  computeUnreadBadgeTotal,
  timelineDividerMessageIds,
  type UserStreamNotificationHint
} from "@nano/product-contracts/client-parity";

import unreadVectors from "../../../../shared/unread-badge-test-cases.json";
import dividerVectors from "../../../../shared/timeline-divider-test-cases.json";
import { AppShell } from "../../app/shell/app-shell";
import { setLanguage } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import type { Conversation } from "../chat/chat-types";
import { InAppToast } from "../chat/components/in-app-toast";
import { useGlobalMessageToast } from "../chat/hooks/use-global-message-toast";
import { AgentCompletionNotifier } from "./agent-completion-notifier";
import { resetLocalUnreadFeedback } from "./local-unread-feedback";

const { listConversationsMock, getConversationMock, showAgentNotificationMock } = vi.hoisted(() => ({
  listConversationsMock: vi.fn(),
  getConversationMock: vi.fn(),
  showAgentNotificationMock: vi.fn()
}));

let streamOnEvent:
  | ((event: {
      eventType: string;
      payload: Record<string, unknown>;
      eventId?: number;
      notificationHint?: UserStreamNotificationHint;
    }) => void)
  | null = null;

vi.mock("../chat/chat-api", async () => {
  const actual = await vi.importActual<typeof import("../chat/chat-api")>("../chat/chat-api");
  return { ...actual, listConversations: listConversationsMock, getConversation: getConversationMock };
});

vi.mock("../../realtime/user-stream", () => ({
  subscribeUserStream: vi.fn((sub: { onEvent: typeof streamOnEvent }) => {
    streamOnEvent = sub.onEvent;
    return () => {
      streamOnEvent = null;
    };
  })
}));

vi.mock("./notification-api", () => ({
  ensureNotificationPermission: vi.fn(),
  isNotificationSupported: () => true,
  showAgentNotification: showAgentNotificationMock
}));

vi.mock("./document-visibility", () => ({
  isDocumentHidden: () => true,
  subscribeDocumentVisibility: () => () => undefined
}));

vi.mock("./notification-preference", () => ({
  useNotificationPreference: () => [true, vi.fn()] as const
}));

function makeConversation(id: string, overrides: Partial<Conversation> = {}): Conversation {
  return {
    id,
    title: `Chat ${id}`,
    participants: [],
    participant_ids: [],
    type: "group",
    direct_kind: null,
    owner_id: "self-user",
    creator_id: "self-user",
    is_pinned: false,
    is_muted: false,
    unread_count: 0,
    last_message_preview: null,
    last_message_system_notice: null,
    last_message_at: null,
    created_at: "2026-10-20T00:00:00Z",
    ...overrides
  };
}

describe("Web multi-platform parity conformance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetLocalUnreadFeedback();
    setLanguage("en");
    listConversationsMock.mockResolvedValue([]);
    getConversationMock.mockResolvedValue(undefined);
    vi.stubGlobal("Notification", { permission: "granted" });
    useAuthStore.getState().setSession({
      access_token: "token",
      user: {
        id: "self-user",
        username: "self",
        display_name: "Self",
        owner_id: "self-user",
        locale: "en",
        default_entry_node_id: null,
        membership_status: "active",
        is_company_admin: true,
        owned_node_ids: [],
        created_at: ""
      }
    });
  });

  it("matches src/IM/shared/unread-badge-test-cases.json for per-row and global non-muted badge totals", () => {
    for (const testCase of unreadVectors.cases) {
      for (const conv of testCase.conversations) {
        const expectedRow =
          testCase.expected_row_unread[conv.id as keyof typeof testCase.expected_row_unread];
        expect(computeConversationRowUnread(conv), `${testCase.id}:${conv.id}`).toBe(expectedRow);
      }
      expect(computeUnreadBadgeTotal(testCase.conversations), testCase.id).toBe(
        testCase.expected_badge_total
      );
    }
  });

  it("matches src/IM/shared/timeline-divider-test-cases.json and preserves non-resetting notice invariants", () => {
    for (const testCase of dividerVectors.cases) {
      expect(timelineDividerMessageIds(testCase.items, testCase.timezone), testCase.id).toEqual(
        testCase.expected_divider_ids
      );
    }

    // Property invariant: inserting system notices or config boundaries never changes ordinary message divider IDs
    let seed = 0x5f3759df;
    const nextRand = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      return seed / 0x100000000;
    };
    for (let run = 0; run < 25; run++) {
      let ts = Date.parse("2026-10-21T14:00:00Z");
      const plain: Array<{ type: string; id: string; created_at: string; has_system_notice?: boolean }> = [];
      const noisy: typeof plain = [];
      for (let idx = 0; idx < 12; idx++) {
        ts += Math.floor(nextRand() * 600_000);
        const msg = { type: "message", id: `m-${idx}`, created_at: new Date(ts).toISOString() };
        plain.push(msg);
        noisy.push(msg);
        if (nextRand() > 0.5) {
          noisy.push({
            type: "message",
            id: `sys-${idx}`,
            created_at: new Date(ts + 30_000).toISOString(),
            has_system_notice: true
          });
        } else {
          noisy.push({
            type: "agent_config_changed",
            id: `cfg-${idx}`,
            created_at: new Date(ts + 15_000).toISOString()
          });
        }
      }
      expect(timelineDividerMessageIds(noisy, "Asia/Shanghai")).toEqual(
        timelineDividerMessageIds(plain, "Asia/Shanghai")
      );
    }
  });

  it("renders non-muted total unread on both desktop rail and mobile Chat tab without duplicating on Me", async () => {
    listConversationsMock.mockResolvedValue([
      makeConversation("c-active", { unread_count: 3, is_muted: false }),
      makeConversation("c-muted", { unread_count: 9, is_muted: true })
    ]);

    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1280 });
    window.dispatchEvent(new Event("resize"));

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { unmount } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/tasks"]}>
          <Routes>
            <Route path="/*" element={<AppShell><div>page</div></AppShell>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    const rail = screen.getByRole("banner");
    await waitFor(() => {
      expect(within(rail).getByTestId("shell-chat-unread")).toHaveTextContent("3");
    });
    unmount();

    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 390 });
    window.dispatchEvent(new Event("resize"));
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/tasks"]}>
          <Routes>
            <Route path="/*" element={<AppShell><div>page</div></AppShell>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    const mobile = screen.getByRole("navigation", { name: /mobile/i });
    await waitFor(() => {
      expect(within(mobile).getByTestId("shell-chat-unread")).toHaveTextContent("3");
    });
    expect(screen.queryByTestId("shell-me-unread")).not.toBeInTheDocument();
  });

  it("suppresses muted background notifications unless @mentioned, routes thread/Work hints, and syncs conversation.read", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(
      ["chat", "conversations"],
      [
        makeConversation("muted-grp", { title: "Muted Room", is_muted: true, unread_count: 2 }),
        makeConversation("open-grp", { title: "Active Room", is_muted: false, unread_count: 4 })
      ]
    );

    function Harness({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={["/tasks"]}>{children}</MemoryRouter>
        </QueryClientProvider>
      );
    }

    const { result } = renderHook(
      () => {
        const state = useGlobalMessageToast();
        return state;
      },
      {
        wrapper: ({ children }) => (
          <Harness>
            {children}
          </Harness>
        )
      }
    );

    await waitFor(() => expect(streamOnEvent).not.toBeNull());

    // 1) Muted Agent reply completion: neither InAppToast nor AgentCompletionCandidate fires
    act(() => {
      streamOnEvent!({
        eventType: "message.completed",
        eventId: 10,
        payload: { conversation_id: "muted-grp", message_id: "m-muted", content: "quiet reply" },
        notificationHint: {
          eligible: true,
          kind: "message_completed",
          dedupe_key: "message:m-muted",
          is_muted: true,
          mentions_viewer: false,
          conversation_id: "muted-grp",
          conversation_type: "group",
          conversation_title: "Muted Room",
          conversation_unread: 3,
          sender_name: "Bot",
          preview_text: "quiet reply",
          target_route: "/chat/muted-grp"
        }
      });
    });
    expect(result.current.toast).toBeNull();
    expect(result.current.agentCompletionCandidate).toBeNull();

    // 2) Muted @mention: allowed through mute with thread target_route
    act(() => {
      streamOnEvent!({
        eventType: "message.created",
        eventId: 11,
        payload: { conversation_id: "muted-grp", message_id: "m-mention", sender_type: "user", sender_user_id: "bob", content: "@Self hi" },
        notificationHint: {
          eligible: true,
          kind: "mention",
          dedupe_key: "message:m-mention",
          is_muted: true,
          mentions_viewer: true,
          conversation_id: "muted-grp",
          conversation_type: "group",
          conversation_title: "Muted Room",
          thread_root_message_id: "root-7",
          sender_name: "Bob",
          preview_text: "@Self hi",
          target_route: "/chat/muted-grp?thread=root-7"
        }
      });
    });
    expect(result.current.toast).toMatchObject({
      targetRoute: "/chat/muted-grp?thread=root-7",
      conversationTitle: "Muted Room"
    });

    // 3) Work permission notification routes to `/settings/agents/:id?view=work` in both Toast and Notifier
    act(() => {
      streamOnEvent!({
        eventType: "agent.work.updated",
        payload: { agent_id: "pa_main", revision: 5 },
        notificationHint: {
          eligible: true,
          kind: "work_permission",
          dedupe_key: "work-perm:pa_main:s1:t1",
          is_muted: false,
          mentions_viewer: false,
          agent_id: "pa_main",
          sender_name: "PA Assistant",
          target_route: "/settings/agents/pa_main?view=work"
        }
      });
    });
    expect(result.current.toast?.targetRoute).toBe("/settings/agents/pa_main?view=work");
    expect(result.current.agentCompletionCandidate?.targetRoute).toBe("/settings/agents/pa_main?view=work");

    render(
      <Harness>
        <AgentCompletionNotifier candidate={result.current.agentCompletionCandidate} />
        <InAppToast
          conversationTitle={result.current.toast!.conversationTitle}
          preview={result.current.toast!.preview}
          conversationId={result.current.toast!.conversationId}
          targetRoute={result.current.toast!.targetRoute}
          onDismiss={() => {}}
        />
      </Harness>
    );
    expect(screen.getByRole("link", { name: "View message" })).toHaveAttribute(
      "href",
      "/settings/agents/pa_main?view=work"
    );
    expect(showAgentNotificationMock).toHaveBeenCalledTimes(1);

    // 4) conversation.read immediately zeroes unread_count in query cache
    act(() => {
      streamOnEvent!({
        eventType: "conversation.read",
        payload: { conversation_id: "open-grp", unread_count: 0, is_muted: false }
      });
    });
    const updated = client.getQueryData<Conversation[]>(["chat", "conversations"])!;
    expect(updated.find((c) => c.id === "open-grp")?.unread_count).toBe(0);
  });
});
