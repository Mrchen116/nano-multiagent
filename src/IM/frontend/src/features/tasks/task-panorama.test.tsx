import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import {
  composerStoreFor,
  readingPositionStoreFor,
  writeComposerSnapshot,
  EMPTY_COMPOSER_SNAPSHOT,
} from "../chat/components/composer-draft-store";
import { MessagePane } from "../chat/components/message-pane";
import type { Conversation, Message } from "../chat/chat-types";
import type { TaskFocusResponse, TaskGraph, TaskGraphList, TaskNode } from "./task-graphs-api";
import { TaskGraphsPage } from "./task-graphs-page";
import { layoutTaskScope } from "./task-graph-layout";

const node = (id: string, title: string, container: string | null = "root", overrides: Partial<TaskNode> = {}): TaskNode => ({
  id, title, last_chat_id: "home", last_chat_title: "Startup group", container_id: container, description: "Purpose",
  mode: "none", status: "todo", result: "", derived_from_id: null, selected_candidate_id: null, selection_reason: "",
  links: [], order: 0, created_at: "2026-09-22T01:00:00Z", updated_at: "2026-09-22T01:00:00Z", updated_by: "Nano", ...overrides,
});

const sampleGraph: TaskGraph = {
  schema_version: 2, graph_id: "tg-1", root_node_id: "root", revision: 9, relative_url: "/tasks/tg-1",
  created_at: "2026-09-22T01:00:00Z", updated_at: "2026-09-22T01:00:00Z", updated_by: "Nano",
  nodes: [
    node("root", "Video product", null, { mode: "dag" }),
    node("A", "A Choose direction", "root", { mode: "explore", selected_candidate_id: "Z", selection_reason: "Lower cost" }),
    node("B", "B Implement"), node("C", "C Test"), node("D", "D Documentation"), node("E", "E Launch"),
    node("X", "X Generated video", "A", { status: "done", result: "Too expensive" }),
    node("Y", "Y Templates", "A", { status: "closed", result: "Does not meet the quality target", change_note: "User chose to stop this direction" }),
    node("Z", "Z Hybrid", "A", { derived_from_id: "X", mode: "dag" }),
    node("Z1", "Z1 Prototype", "Z"), node("Z2", "Z2 Evaluate", "Z"), node("Z3", "Z3 Decide", "Z"),
  ],
  dependencies: [
    { from: "A", to: "B" }, { from: "B", to: "C" }, { from: "A", to: "C" },
    { from: "A", to: "D" }, { from: "C", to: "E" }, { from: "D", to: "E" },
    { from: "Z1", to: "Z2" }, { from: "Z2", to: "Z3" },
  ],
};

const home: Conversation = {
  id: "home", title: "Startup group", participants: [], participant_ids: [], type: "group", direct_kind: null,
  owner_id: "user-1", creator_id: "user-1", can_write: true, is_pinned: false, is_muted: false,
  unread_count: 0, last_message_preview: null, last_message_at: null, created_at: "2026-01-01",
};

let currentGraph: TaskGraph;
let graphStatus: number;
let list: TaskGraphList;
let fetchMock: ReturnType<typeof vi.fn<(url: string) => Promise<Response>>>;

function buildFocusFromList(items = list.items): TaskFocusResponse {
  const needs_you = items.filter(item => item.status === "proposed" || item.status === "in_review");
  const stashed = items.filter(item => item.status === "backlog" || item.status === "paused");
  const active = items.filter(item => ["todo", "doing", "waiting"].includes(item.status));
  const goals = items.filter(item => item.mode !== "none" && (!item.node_id || item.node_id === item.root_node_id));
  const completed = items.filter(item => item.status === "done" || item.status === "closed");
  return {
    needs_you,
    stashed,
    active,
    goals,
    completed,
    completed_count: completed.length,
    counts: {
      needs_you: needs_you.length,
      stashed: stashed.length,
      active: active.length,
      goals: goals.length,
      completed: completed.length,
    },
    next_cursors: { needs_you: null, stashed: null, active: null, goals: null, completed: null },
  };
}

function renderTasks(path: string, messages: Message[] = [], gcTime = 0) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime } } });
  const onSend = vi.fn();
  const router = createMemoryRouter(
    [
      { path: "/chat/other", element: <div>Other discussion</div> },
      { path: "/tasks", element: <TaskGraphsPage /> },
      { path: "/tasks/:graphId", element: <TaskGraphsPage /> },
      {
        path: "/chat/home",
        element: (
          <MessagePane
            conversation={home}
            messages={messages}
            readingPositions={readingPositionStoreFor("user-1")}
            mentionCandidates={[]}
            onSend={onSend}
            selfUserId="user-1"
            composerStore={composerStoreFor("user-1")}
          />
        ),
      },
    ],
    { initialEntries: [path] },
  );
  const result = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...result, router, client, onSend };
}

beforeEach(() => {
  setLanguage("en");
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
  useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, user: TEST_AUTH_USER });
  currentGraph = structuredClone(sampleGraph);
  graphStatus = 200;
  list = { items: [{ ...sampleGraph, title: "Video product", mode: "dag", status: "todo" }], next_cursor: null, total: 1 };
  fetchMock = vi.fn(async (url: string) => {
    if (url.includes("/conversations") && !url.includes("/task-activity")) {
      return Response.json({ items: [home] });
    }
    if (url.includes("/task-graphs/focus")) {
      const q = new URL(url, "http://test").searchParams.get("query")?.toLowerCase();
      const filtered = q ? list.items.filter(item => item.title.toLowerCase().includes(q)) : list.items;
      return Response.json(buildFocusFromList(filtered));
    }
    if (url.includes("/task-graphs/nodes")) {
      return Response.json({
        items: [{ ...sampleGraph, node_id: "C", scope_id: "root", title: "C Test", mode: "none", status: "todo" }],
      });
    }
    if (url.includes("/task-graphs/")) {
      return new Response(
        JSON.stringify(graphStatus === 200 ? currentGraph : { detail: { code: "read_failed", message: "Unavailable" } }),
        { status: graphStatus },
      );
    }
    return new Response(JSON.stringify(list), { status: 200 });
  });
  vi.stubGlobal("IntersectionObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("panorama, focus pagination, and chat return context", () => {
  it("retains old records with a stale warning but removes protected cached content after access is revoked", async () => {
    const { client } = renderTasks("/tasks/tg-1?scope=root");
    await screen.findByRole("button", { name: "View A Choose direction" });
    graphStatus = 503;
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("previously loaded graph");
    expect(screen.getByRole("button", { name: "View A Choose direction" })).toBeInTheDocument();
    graphStatus = 404;
    await userEvent.click(within(screen.getByRole("alert")).getByRole("button", { name: "Refresh" }));
    await screen.findByRole("heading", { name: "This task does not exist or you no longer have access." });
    expect(screen.queryByText("Video product")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "View A Choose direction" })).not.toBeInTheDocument();
    expect(client.getQueriesData({ queryKey: ["task-graphs"] }).every(([, value]) => value === null)).toBe(true);
  });

  it("opens an Agent task link and returns a reference while preserving the full composer without sending", async () => {
    const pending = [{ url: "/im/uploads/design.pdf", file_name: "design.pdf", content_type: "application/pdf" }];
    writeComposerSnapshot(composerStoreFor("user-1"), "home", {
      draft: "@Nano Please check",
      draftMentions: [{ label: "@Nano", type: "agent", target_id: "nano" }],
      pending,
      slashDismissed: true,
    });
    const { router, onSend } = renderTasks("/chat/home", [
      {
        id: "saved-plan",
        conversation_id: "home",
        sender: { type: "agent", id: "nano", display_name: "Nano" },
        sender_user_id: "nano",
        sender_type: "agent",
        content: `[Saved plan](${window.location.origin}/tasks/tg-1?scope=A&node=Z)`,
        attachments: [],
        delivery_status: "completed",
        created_at: "2026-01-01T00:00:00Z",
        permission_requests: [],
      },
    ]);
    await userEvent.click(screen.getByRole("link", { name: "Saved plan" }));
    await screen.findByRole("button", { name: "Discuss this task in chat" });
    await userEvent.click(screen.getByRole("button", { name: "Discuss this task in chat" }));
    expect(router.state.location.pathname).toBe("/chat/home");
    expect(screen.getByRole("textbox")).toHaveValue("@Nano Please check\n\n[Task: Z Hybrid](/tasks/tg-1?scope=A&node=Z)\n");
    expect(screen.getByText("design.pdf")).toBeInTheDocument();
    expect(composerStoreFor("user-1").get("home")?.draftMentions).toEqual([{ label: "@Nano", type: "agent", target_id: "nano" }]);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("restores a mobile nested deep link, closes detail without moving canvas, and rejects invalid scopes", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    const { router, unmount } = renderTasks("/tasks/tg-1?scope=Z&node=Z2");
    const dialog = await screen.findByRole("dialog", { name: "Node details" });
    expect(within(dialog).getByRole("heading", { name: "Z2 Evaluate" })).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "Internal structure" }));
    const scroll = screen.getByLabelText("Task graph canvas, scroll to explore");
    scroll.scrollLeft = 112;
    await userEvent.click(screen.getByRole("button", { name: "View Z2 Evaluate" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(router.state.location.search).toBe("?scope=Z");
    expect(scroll.scrollLeft).toBe(112);
    await userEvent.click(screen.getByRole("link", { name: "‹ Back to Tasks" }));
    expect(router.state.location.pathname).toBe("/tasks");
    unmount();

    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
    renderTasks("/tasks/tg-1?scope=unknown&node=C");
    expect(await screen.findByRole("alert")).toHaveTextContent("scope or node does not exist");
    await userEvent.click(screen.getByRole("button", { name: "Back to root goal" }));
    expect(screen.getByRole("button", { name: "View A Choose direction" })).toBeInTheDocument();
  });

  it.each([
    ["Paused", "paused", "To do"],
    ["Resume progress", "doing", "In progress"],
  ])("%s saves an explicit status and refreshes waiting details", async (label, status, group) => {
    const waiting = currentGraph.nodes.find(node => node.id === "B")!;
    Object.assign(waiting, {
      status: "waiting",
      can_edit: true,
      wait: { reason: "Wait for budget, then purchase", schedule_id: "s", owner_agent_id: "a", session_id: "main", next_check_at: "2026-10-22T12:00:00Z" },
    });
    const fetchBefore = fetchMock.getMockImplementation()!;
    const writes: Record<string, any>[] = [];
    fetchMock.mockImplementation(async (url: string, ...args: unknown[]) => {
      const init = args[0] as RequestInit | undefined;
      if (init?.method === "POST") {
        const body = JSON.parse(init.body as string);
        writes.push(body);
        Object.assign(waiting, { status: body.operations[0].patch.status, wait: undefined });
        return Response.json({ graph_id: currentGraph.graph_id });
      }
      return fetchBefore(url);
    });
    renderTasks("/tasks/tg-1?node=B");
    const dialog = await screen.findByRole("dialog", { name: "Node details" });
    await userEvent.click(within(dialog).getByRole("button", { name: label }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ base_revision: 9, change_note: "", operations: [{ op: "update_task", node_id: "B", patch: { status } }] });
    await waitFor(() => expect(within(dialog).queryByText("Wait for budget, then purchase")).not.toBeInTheDocument());
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "Progress" }));
    expect(within(screen.getByRole("region", { name: group })).getByText("B Implement")).toBeVisible();
  });

  it("loads focus section cursors (including completed) on demand and resets for search", async () => {
    const firstActive = { ...list.items[0], title: "Todo first", mode: "none" as const };
    const appendedActive = { ...firstActive, graph_id: "tg-more", title: "Todo tail", status: "doing" as const };
    const doneSubtask = { ...firstActive, graph_id: "tg-done", node_id: "n2", title: "Finished stage", status: "done" as const };
    fetchMock.mockImplementation(async url => {
      if (url.includes("/conversations")) return Response.json({ items: [home] });
      const params = new URL(url, "http://test").searchParams;
      if (url.includes("/task-graphs/focus")) {
        if (params.get("query") === "other") return Response.json(buildFocusFromList([]));
        if (params.get("section") === "completed") {
          return Response.json({
            ...buildFocusFromList([]),
            completed: [doneSubtask],
            completed_count: 1,
            counts: { needs_you: 0, stashed: 0, active: 2, goals: 0, completed: 1 },
          });
        }
        if (params.get("section") === "active" && params.get("cursor") === "active-next") {
          return Response.json({ ...buildFocusFromList([appendedActive]), next_cursors: { needs_you: null, stashed: null, active: null, goals: null, completed: null } });
        }
        return Response.json({
          ...buildFocusFromList([firstActive]),
          completed_count: 1,
          counts: { needs_you: 0, stashed: 0, active: 2, goals: 0, completed: 1 },
          next_cursors: { needs_you: null, stashed: null, active: "active-next", goals: null, completed: null },
        });
      }
      return Response.json(list);
    });

    const { router, client } = renderTasks("/tasks", [], 300_000);
    await screen.findByRole("button", { name: "View Todo first" });
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("button", { name: "View Todo tail" });
    await userEvent.click(screen.getByRole("button", { name: /View completed records/i }));
    await screen.findByRole("button", { name: "View Finished stage" });
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/task-graphs/focus") && url.includes("section=completed"))).toBe(true);
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["task-graphs"] });
    });
    expect(screen.getByRole("button", { name: "View Todo tail" })).toBeInTheDocument();

    fetchMock.mockClear();
    await userEvent.type(screen.getByRole("textbox", { name: "Search goal names" }), "other{Enter}");
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.includes("query=other"))).toBe(true));
    expect(router.state.location.search).toContain("query=other");
  });

  it("orders DAG layout columns cleanly and preserves embedded task_cards return reading context", async () => {
    const { positions, routes } = layoutTaskScope(sampleGraph, sampleGraph.nodes[0]);
    expect(positions.get("B")!.x).toBe(positions.get("D")!.x);
    expect(routes).toHaveLength(6);
    expect(positions.has("Z1")).toBe(false);

    const { container, router } = renderTasks("/chat/home", [
      {
        id: "m-brief",
        conversation_id: "home",
        sender: { type: "agent", id: "nano", display_name: "Nano" },
        sender_user_id: "nano",
        sender_type: "agent",
        content: "Morning brief",
        attachments: [],
        task_cards: [{ graph_id: "tg-1", node_id: "C" }],
        delivery_status: "completed",
        created_at: "2026-01-01T00:00:00Z",
        permission_requests: [],
      },
      {
        id: "m-later",
        conversation_id: "home",
        sender: { type: "user", id: "user-1", display_name: "Owner" },
        sender_user_id: "user-1",
        sender_type: "user",
        content: "Later note",
        attachments: [],
        delivery_status: "completed",
        created_at: "2026-01-01T00:05:00Z",
        permission_requests: [],
      },
    ]);
    const card = await screen.findByTestId("chat-task-card-tg-1-C");
    const scroller = container.querySelector(".chat-pane-messages") as HTMLElement;
    Object.defineProperty(scroller, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(scroller, "clientHeight", { configurable: true, value: 400 });
    scroller.scrollTop = 180;
    const briefRow = container.querySelector<HTMLElement>('[data-message-id="m-brief"]')!;
    vi.spyOn(briefRow, "getBoundingClientRect").mockReturnValue(new DOMRect(0, -10, 100, 60));

    await userEvent.click(card);
    expect(router.state.location.pathname).toBe("/tasks/tg-1");
    expect(router.state.location.search).toContain("return_message=m-brief");
    expect(readingPositionStoreFor("user-1").get("home")).toMatchObject({ anchorId: "m-brief", latestId: "m-later" });
    await userEvent.click(await screen.findByRole("link", { name: "Discuss in chat" }));
    expect(router.state.location.pathname).toBe("/chat/home");
  });

  it("opens group activity in the same graph and returns without changing the chat draft", async () => {
    const { GroupTaskPanel } = await import("./group-task-panel");
    const originalFetch = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (url: string) =>
      url.includes("/task-activity")
        ? Response.json({
            items: [{ graph_id: "tg-1", node_id: "C", scope_id: "root", title: "C Test", root_title: "Video product", status: "todo", updated_at: "2026-09-30T01:00:00Z" }],
          })
        : originalFetch(url),
    );
    writeComposerSnapshot(composerStoreFor("user-1"), "home", { ...EMPTY_COMPOSER_SNAPSHOT, draft: "Keep my draft" });
    const router = createMemoryRouter(
      [
        { path: "/chat/home", element: <GroupTaskPanel conversationId="home" onClose={() => undefined} /> },
        { path: "/tasks/:graphId", element: <TaskGraphsPage /> },
      ],
      { initialEntries: ["/chat/home"] },
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("link", { name: /C Test/ }));
    expect(router.state.location.pathname).toBe("/tasks/tg-1");
    expect(router.state.location.search).toContain("return_chat=home");
    await userEvent.click(await screen.findByRole("link", { name: "Discuss in chat" }));
    expect(router.state.location.pathname).toBe("/chat/home");
    expect(composerStoreFor("user-1").get("home")?.draft).toBe("Keep my draft");
  });
});
