import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import { composerStoreFor, writeComposerSnapshot, EMPTY_COMPOSER_SNAPSHOT } from "../chat/components/composer-draft-store";
import { MessagePane } from "../chat/components/message-pane";
import type { Conversation, Message } from "../chat/chat-types";
import type { TaskFocusResponse, TaskGraph, TaskGraphList, TaskNode } from "./task-graphs-api";
import { TaskGraphsPage } from "./task-graphs-page";
import { layoutTaskScope } from "./task-graph-layout";

const node = (id: string, title: string, container: string | null = "root", overrides: Partial<TaskNode> = {}): TaskNode => ({
  id,
  title,
  last_chat_id: "home",
  last_chat_title: "Startup group",
  container_id: container,
  description: "Purpose",
  mode: "none",
  status: "todo",
  result: "",
  derived_from_id: null,
  selected_candidate_id: null,
  selection_reason: "",
  links: [],
  order: 0,
  created_at: "2026-09-22T01:00:00Z",
  updated_at: "2026-09-22T01:00:00Z",
  updated_by: "Nano",
  ...overrides,
});

const sampleGraph: TaskGraph = {
  schema_version: 2,
  graph_id: "tg-1",
  root_node_id: "root",
  revision: 9,
  relative_url: "/tasks/tg-1",
  created_at: "2026-09-22T01:00:00Z",
  updated_at: "2026-09-22T01:00:00Z",
  updated_by: "Nano",
  nodes: [
    node("root", "Video product", null, { mode: "dag" }),
    node("A", "A Choose direction", "root", { mode: "explore", selected_candidate_id: "Z", selection_reason: "Lower cost" }),
    node("B", "B Implement"),
    node("C", "C Test"),
    node("D", "D Documentation"),
    node("E", "E Launch"),
    node("X", "X Generated video", "A", { status: "done", result: "Too expensive" }),
    node("Y", "Y Templates", "A", { status: "closed", result: "Does not meet the quality target", change_note: "User chose to stop this direction" }),
    node("Z", "Z Hybrid", "A", { derived_from_id: "X", mode: "dag" }),
    node("Z1", "Z1 Prototype", "Z"),
    node("Z2", "Z2 Evaluate", "Z"),
    node("Z3", "Z3 Decide", "Z"),
  ],
  dependencies: [
    { from: "A", to: "B" },
    { from: "B", to: "C" },
    { from: "A", to: "C" },
    { from: "A", to: "D" },
    { from: "C", to: "E" },
    { from: "D", to: "E" },
    { from: "Z1", to: "Z2" },
    { from: "Z2", to: "Z3" },
  ],
};

const home: Conversation = {
  id: "home",
  title: "Startup group",
  participants: [],
  participant_ids: [],
  type: "group",
  direct_kind: null,
  owner_id: "user-1",
  creator_id: "user-1",
  can_write: true,
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01",
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
  const completedItems = items.filter(item => item.status === "done" || item.status === "closed");
  return {
    needs_you,
    stashed,
    active,
    goals,
    completed: completedItems,
    completed_count: completedItems.length,
    counts: {
      needs_you: needs_you.length,
      stashed: stashed.length,
      active: active.length,
      goals: goals.length,
      completed: completedItems.length,
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
      return Response.json({ items: [] });
    }
    if (url.includes("/task-graphs/")) {
      return new Response(
        JSON.stringify(graphStatus === 200 ? currentGraph : { detail: { code: "read_failed", message: "Unavailable" } }),
        { status: graphStatus },
      );
    }
    if (url.includes("/task-graphs?") && new URL(url, "http://test").searchParams.has("statuses")) {
      const statuses = new URL(url, "http://test").searchParams.get("statuses")!.split(",");
      const items = list.items.filter(item => statuses.includes(item.status));
      return Response.json({ ...list, items, total: items.length });
    }
    return new Response(JSON.stringify(list), { status: 200 });
  });
  vi.stubGlobal("IntersectionObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("task graph browsing", () => {
  it("opens the action focus desk without selecting a tree and drills into direct children", async () => {
    list.items[0].status = "waiting";
    const { router } = renderTasks("/tasks");
    await screen.findByRole("button", { name: "View Video product" });
    expect(within(screen.getByRole("region", { name: "In progress" })).getByText("Video product")).toBeInTheDocument();
    expect(screen.queryByText("A Choose direction")).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/tasks");
    await userEvent.click(screen.getByRole("button", { name: "Enter subgraph of Video product" }));
    await screen.findByRole("button", { name: "View A Choose direction" });
    expect(screen.queryByText("Z1 Prototype")).not.toBeInTheDocument();
  });

  it("keeps waiting with ongoing while paused and review retain their groups in progress view", async () => {
    currentGraph.nodes.find(node => node.id === "B")!.status = "paused";
    currentGraph.nodes.find(node => node.id === "C")!.status = "in_review";
    currentGraph.nodes.find(node => node.id === "D")!.status = "waiting";
    renderTasks("/tasks/tg-1");
    await screen.findByRole("button", { name: "View B Implement" });
    await userEvent.click(screen.getByRole("button", { name: "Progress" }));
    expect(within(screen.getByRole("region", { name: "To do" })).getByText("Paused")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "In review" })).getByText("C Test")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "In progress" })).getByText("D Documentation")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "In progress" })).getByText("Waiting")).toBeInTheDocument();
    expect(screen.queryByText("Z1 Prototype")).not.toBeInTheDocument();
  });

  it("queries assignees across levels and opens a result at its original containing scope", async () => {
    list.items = [
      {
        ...list.items[0],
        node_id: "Z2",
        scope_id: "Z",
        title: "Z2 Evaluate",
        parent_path: [
          { id: "root", title: "Video product" },
          { id: "A", title: "A Choose direction" },
          { id: "Z", title: "Z Hybrid" },
        ],
      },
    ];
    const base = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async url =>
      url.includes("/contacts")
        ? Response.json({ items: [{ user_id: "user-1", kind: "human", display_name: "Human" }], next_cursor: null })
        : base(url),
    );
    const { router } = renderTasks("/tasks?collection=assignee&assignee_type=user&assignee_id=user-1");
    await screen.findByRole("button", { name: "View Z2 Evaluate" });
    expect(fetchMock.mock.calls.some(([url]) => url.includes("assignee_type=user") && url.includes("assignee_id=user-1"))).toBe(true);
    expect(screen.getByText(/Video product \/ A Choose direction \/ Z Hybrid/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View Z2 Evaluate" }));
    expect(router.state.location.pathname).toBe("/tasks/tg-1");
    expect(router.state.location.search).toBe("?scope=Z&node=Z2");
    expect(await screen.findByRole("dialog", { name: "Node details" })).toBeInTheDocument();
  });

  it("renders a task system event as linked content with effective mentions and opens the original task", async () => {
    home.participants = [{ type: "agent", id: "nano", user_id: "agent-user", display_name: "Nano" }];
    const { router } = renderTasks("/chat/home", [
      {
        id: "task-event",
        permission_requests: [],
        conversation_id: "home",
        sender: { type: "system", id: "system" },
        sender_type: "system",
        sender_user_id: "system",
        content: 'Owner assigned [C Test](/tasks/tg-1?scope=root&node=C) to <mention type="user" target_id="agent-user"/>',
        attachments: [],
        delivery_status: "completed",
        created_at: "2026-10-12T12:00:00Z",
        system_notice: { kind: "task_graph", graph_id: "tg-1", node_id: "C", scope_id: "root" },
      },
    ]);
    expect(await screen.findByText("@Nano")).toHaveAttribute("data-target-id", "agent-user");
    await userEvent.click(screen.getByRole("link", { name: "C Test" }));
    expect(router.state.location.search).toBe("?scope=root&node=C");
    expect(await screen.findByRole("dialog", { name: "Node details" })).toBeInTheDocument();
    home.participants = [];
  });

  it("claims an available task with the required revision and change-note envelope", async () => {
    currentGraph.nodes.find(node => node.id === "C")!.can_claim = true;
    const writes: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          writes.push(JSON.parse(init.body as string));
          return Response.json({ graph_id: "tg-1", revision: 10 });
        }
        return fetchMock(url);
      }),
    );
    renderTasks("/tasks/tg-1?scope=root&node=C");
    await userEvent.click(await screen.findByRole("button", { name: "Claim and start" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ base_revision: 9, change_note: "", operations: [{ op: "claim_task", node_id: "C" }] });
  });

  it("returns a selected node to its own latest update chat", async () => {
    currentGraph.nodes.find(node => node.id === "C")!.last_chat_id = "other";
    currentGraph.nodes.find(node => node.id === "C")!.last_chat_title = "Other discussion";
    const { router } = renderTasks("/tasks/tg-1?node=C");
    const detail = await screen.findByRole("dialog", { name: "Node details" });
    await userEvent.click(within(detail).getByRole("button", { name: "Discuss this task in chat" }));
    expect(router.state.location.pathname).toBe("/chat/other");
    expect(composerStoreFor("user-1").get("other")?.draft).toContain("C Test");
  });

  it("keeps a goal without an accessible source usable and copies a node reference", async () => {
    currentGraph.nodes.forEach(node => {
      node.last_chat_id = null;
      node.last_chat_title = null;
    });
    const user = userEvent.setup();
    renderTasks("/tasks/tg-1?node=C");
    const detail = await screen.findByRole("dialog", { name: "Node details" });
    expect(screen.queryByRole("button", { name: "Back to chat" })).not.toBeInTheDocument();
    expect(within(detail).queryByRole("button", { name: "Discuss this task in chat" })).not.toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Copy reference" }));
    expect(await navigator.clipboard.readText()).toContain("/tasks/tg-1?scope=root&node=C");
    expect(await screen.findByText("Copied. Paste this reference into any chat to discuss it.")).toHaveAttribute("role", "status");
  });

  it("shows all direct DAG edges and relationships, preserves view on reread, and navigates both nesting modes", async () => {
    const { container, router } = renderTasks("/tasks/tg-1?scope=root&node=C");
    const detail = await screen.findByRole("dialog", { name: "Node details" });
    expect(within(detail).getByRole("button", { name: "B Implement" })).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "A Choose direction" })).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "E Launch" })).toBeInTheDocument();
    await userEvent.click(within(detail).getByRole("button", { name: "Close" }));
    expect(container.querySelectorAll("path[data-edge]")).toHaveLength(6);
    expect(screen.getByText("Layer 2")).toBeInTheDocument();
    expect(screen.getByText("Parallel")).toBeInTheDocument();
    expect(container.querySelector('[data-edge="A:C"]')).toHaveTextContent("A Choose direction → C Test");
    const scroll = screen.getByLabelText("Task graph canvas, scroll to explore");
    scroll.scrollLeft = 150;
    await userEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).not.toBeDisabled());
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(scroll.scrollLeft).toBe(150);
    expect(router.state.location.search).toContain("scope=root");
    await userEvent.click(screen.getByRole("button", { name: "Enter subgraph of A Choose direction" }));
    expect(router.state.location.search).toContain("scope=A");
    expect(container.querySelector('[data-edge="X:Z"]')).toHaveAttribute("stroke-dasharray", "5 4");
    await userEvent.click(screen.getByRole("button", { name: "View Z Hybrid" }));
    expect(within(screen.getByRole("dialog", { name: "Node details" })).getByRole("button", { name: "X Generated video" })).toBeInTheDocument();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "Enter subgraph of Z Hybrid" }));
    expect(router.state.location.search).toBe("?scope=Z");
    expect(screen.getByRole("button", { name: "View Z2 Evaluate" })).toBeInTheDocument();
    const crumbs = screen.getByRole("navigation", { name: "Task hierarchy" });
    await userEvent.click(within(crumbs).getByRole("button", { name: "A Choose direction" }));
    await userEvent.click(screen.getByRole("button", { name: "View Y Templates" }));
    expect(screen.getByText("Does not meet the quality target")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Latest change" })).toBeInTheDocument();
    expect(screen.getByText("User chose to stop this direction")).toBeInTheDocument();
  });
});
