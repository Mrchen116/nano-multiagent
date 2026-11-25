import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import {
  UserStreamRecoveryError,
  validateCanonicalUserStreamEvent,
} from "../../../realtime/user-stream/canonical-event";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../../test/render-router";
import { useAuthStore } from "../../auth/auth-store";
import { applyWsEvent, emptyConversationState } from "../chat-stream-reducer";
import type { Conversation, Message } from "../chat-types";
import type { TaskGraphSummary } from "../../tasks/task-graphs-api";
import { composerStoreFor } from "./composer-draft-store";
import { MessagePane } from "./message-pane";

const conversation: Conversation = {
  id: "conv-pa",
  title: "小满",
  type: "direct",
  direct_kind: "user_agent",
  owner_id: "user-1",
  creator_id: "user-1",
  can_write: true,
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-11-25T00:00:00Z",
  participant_ids: ["user-1", "pa-1"],
  participants: [{ type: "agent", id: "pa-1", role: "personal", display_name: "小满" }],
};

describe("embedded live task_cards in MessagePane and stream sync", () => {
  let cardItems: TaskGraphSummary[];
  let writes: { url: string; body: Record<string, unknown> }[];
  let fetchCalls: string[];

  beforeEach(() => {
    setLanguage("zh");
    useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, user: TEST_AUTH_USER });
    writes = [];
    fetchCalls = [];
    cardItems = [
      {
        graph_id: "tg-1",
        root_node_id: "root",
        node_id: "n-prop",
        scope_id: "root",
        root_title: "周五客户演示",
        revision: 4,
        updated_at: "2026-11-25T10:00:00Z",
        updated_by: "pa-1",
        relative_url: "/tasks/tg-1",
        title: "拉取最新指标截图",
        mode: "none",
        status: "proposed",
        prereq_blocked: false,
        can_edit: true,
        proposal: {
          rationale: "演示 PPT 第 4 页需要本周最新活跃曲线",
          on_approve: "自动导出仪表盘 PNG 并贴回会话",
        },
        conversation: {
          id: "conv-pa",
          title: "小满",
          visibility: "private",
          dissolved_at: null,
          is_member: true,
          can_write: true,
        },
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        fetchCalls.push(url);
        if (init?.method === "POST") {
          const body = JSON.parse(init.body as string) as Record<string, unknown>;
          writes.push({ url, body });
          cardItems = [{ ...cardItems[0]!, status: "doing", revision: 5 }];
          return Response.json({ graph_id: "tg-1", revision: 5 });
        }
        if (url.includes("/im/v1/task-graphs/nodes")) {
          return Response.json({ items: cardItems });
        }
        return Response.json({});
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  function renderChatWithCards(messages: Message[]) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    const router = createMemoryRouter(
      [
        {
          path: "/chat/conv-pa",
          element: (
            <MessagePane
              conversation={conversation}
              messages={messages}
              mentionCandidates={[]}
              onSend={vi.fn()}
              selfUserId="user-1"
              composerStore={composerStoreFor("user-1")}
            />
          ),
        },
        { path: "/tasks/:graphId", element: <div data-testid="panorama-route">Panorama</div> },
      ],
      { initialEntries: ["/chat/conv-pa"] },
    );
    const view = render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    return { ...view, router, client };
  }

  it("renders live task_cards, unavailable fallback for deleted nodes, inline approval, and panorama navigation", async () => {
    const message: Message = {
      id: "m-1",
      conversation_id: "conv-pa",
      sender: { type: "agent", id: "pa-1", display_name: "小满" },
      sender_type: "agent",
      sender_user_id: "pa-1",
      content: "早安，昨晚我帮你备好了今天的一步：",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-11-25T08:00:00Z",
      permission_requests: [],
      task_cards: [
        { graph_id: "tg-1", node_id: "n-prop" },
        { graph_id: "tg-gone", node_id: "n-deleted" },
      ],
    };

    const { router } = renderChatWithCards([message]);

    const card = await screen.findByTestId("chat-task-card-tg-1-n-prop");
    expect(fetchCalls.some(url => url.includes("/im/v1/task-graphs/nodes?refs=tg-1%3An-prop%2Ctg-gone%3An-deleted"))).toBe(true);
    expect(within(card).getByText("待拍板")).toBeInTheDocument();
    expect(within(card).getByText("拉取最新指标截图")).toBeInTheDocument();
    expect(within(card).getByText(/演示 PPT 第 4 页需要本周最新活跃曲线/)).toBeInTheDocument();
    expect(screen.getByTestId("chat-task-card-unavailable")).toHaveTextContent("该任务已删除或你无权查看");

    // Approve inline -> sends approve_task and updates badge to 推进中
    await userEvent.click(within(card).getByRole("button", { name: "批准开工" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]!.url).toBe("/im/v1/task-graphs/tg-1/apply");
    expect(writes[0]!.body).toMatchObject({
      base_revision: 4,
      operations: [{ op: "approve_task", node_id: "n-prop" }],
    });
    expect(await within(card).findByText("推进中")).toBeInTheDocument();

    // Clicking the card navigates to panorama with node & return_chat
    await userEvent.click(card);
    expect(router.state.location.pathname).toBe("/tasks/tg-1");
    expect(router.state.location.search).toBe("?scope=root&node=n-prop&return_chat=conv-pa&return_message=m-1");
  });

  it("refreshes embedded task_cards immediately when task_graph.changed arrives and preserves task_cards in reducer", async () => {
    const streamPayload = { graph_id: "tg-1", conversation_id: "conv-pa", revision: 6, node_ids: ["n-prop"] };
    expect(() => validateCanonicalUserStreamEvent("task_graph.changed", streamPayload)).not.toThrow();
    expect(() =>
      validateCanonicalUserStreamEvent("task_graph.changed", { graph_id: 123 as unknown as string }),
    ).toThrow(UserStreamRecoveryError);

    const message: Message = {
      id: "m-2",
      conversation_id: "conv-pa",
      sender: { type: "agent", id: "pa-1", display_name: "小满" },
      sender_type: "agent",
      sender_user_id: "pa-1",
      content: "跟进卡片：",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-11-25T08:05:00Z",
      permission_requests: [],
      task_cards: [{ graph_id: "tg-1", node_id: "n-prop" }],
    };

    renderChatWithCards([message]);
    const card = await screen.findByTestId("chat-task-card-tg-1-n-prop");
    expect(within(card).getByText("待拍板")).toBeInTheDocument();

    // External update arrives over user stream
    cardItems = [{ ...cardItems[0]!, status: "in_review", revision: 6, result: "截图已导出" }];
    await act(async () => {
      window.dispatchEvent(new CustomEvent("im:task-graph-changed", { detail: streamPayload }));
    });
    expect(await within(card).findByText("待确认")).toBeInTheDocument();

    // Stream reducer preserves task_cards across message.created & message.reconciled
    const createdState = applyWsEvent(
      { ...emptyConversationState, conversation_id: "conv-pa" },
      {
        type: "message.created",
        message_id: "m-stream",
        conversation_id: "conv-pa",
        sender_type: "agent",
        sender_user_id: "pa-1",
        content: "新的筹划卡片",
        delivery_status: "completed",
        created_at: "2026-11-25T09:00:00Z",
        tool_calls: [],
        token_usage: null,
        task_cards: [{ graph_id: "tg-1", node_id: "n-prop" }],
      },
    );
    expect(createdState.messages[0]?.task_cards).toEqual([{ graph_id: "tg-1", node_id: "n-prop" }]);

    const reconciledState = applyWsEvent(createdState, {
      type: "message.reconciled",
      message_id: "m-stream",
      conversation_id: "conv-pa",
      sender_type: "agent",
      sender_user_id: "pa-1",
      content: "新的筹划卡片（已确认）",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-11-25T09:00:00Z",
      tool_calls: [],
      thinking: [],
      token_usage: null,
      elapsed_ms: null,
      kernel_message_id: null,
    });
    expect(reconciledState.messages[0]?.task_cards).toEqual([{ graph_id: "tg-1", node_id: "n-prop" }]);
  });
});
