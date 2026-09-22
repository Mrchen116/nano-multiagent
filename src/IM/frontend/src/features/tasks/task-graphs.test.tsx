import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import { composerStoreFor, writeComposerSnapshot } from "../chat/components/composer-draft-store";
import { MessagePane } from "../chat/components/message-pane";
import type { Conversation, Message } from "../chat/chat-types";
import type { TaskGraph, TaskGraphList, TaskNode } from "./task-graphs-api";
import { ConversationTasksLink, TaskGraphsPage } from "./task-graphs-page";
import { layoutTaskScope } from "./task-graph-layout";

const node = (id: string, title: string, container: string | null = "root", overrides: Partial<TaskNode> = {}): TaskNode => ({
  id, title, container_id: container, description: "Purpose", mode: "none", status: "todo", result: "",
  derived_from_id: null, selected_candidate_id: null, selection_reason: "", links: [], order: 0,
  created_at: "2026-09-22T01:00:00Z", updated_at: "2026-09-22T01:00:00Z", updated_by: "Nano", ...overrides
});
const sampleGraph: TaskGraph = {
  schema_version: 1, graph_id: "tg-1", root_node_id: "root", home_conversation_id: "home", home_conversation_title: "Startup group",
  revision: 9, relative_url: "/tasks/tg-1", created_at: "2026-09-22T01:00:00Z", updated_at: "2026-09-22T01:00:00Z", updated_by: "Nano",
  nodes: [node("root", "Video product", null, { mode: "dag" }),
    node("A", "A Choose direction", "root", { mode: "explore", selected_candidate_id: "Z", selection_reason: "Lower cost" }),
    node("B", "B Implement"), node("C", "C Test"), node("D", "D Documentation"), node("E", "E Launch"),
    node("X", "X Generated video", "A", { status: "done", result: "Too expensive" }),
    node("Y", "Y Templates", "A", { status: "dropped", result: "Does not meet the quality target", change_note: "User chose to stop this direction" }),
    node("Z", "Z Hybrid", "A", { derived_from_id: "X", mode: "dag" }),
    node("Z1", "Z1 Prototype", "Z"), node("Z2", "Z2 Evaluate", "Z"), node("Z3", "Z3 Decide", "Z")],
  dependencies: [{ from: "A", to: "B" }, { from: "B", to: "C" }, { from: "A", to: "C" }, { from: "A", to: "D" }, { from: "C", to: "E" }, { from: "D", to: "E" }, { from: "Z1", to: "Z2" }, { from: "Z2", to: "Z3" }]
};
const home: Conversation = {
  id: "home", title: "Startup group", participants: [], participant_ids: [], type: "group", direct_kind: null, owner_id: "user-1", creator_id: "user-1",
  is_pinned: false, is_muted: false, unread_count: 0, last_message_preview: null, last_message_at: null, created_at: "2026-01-01"
};
let currentGraph: TaskGraph;
let graphStatus: number;
let list: TaskGraphList;
let fetchMock: ReturnType<typeof vi.fn>;

function renderTasks(path: string, messages: Message[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const onSend = vi.fn();
  const router = createMemoryRouter([
    { path: "/tasks", element: <TaskGraphsPage /> }, { path: "/tasks/:graphId", element: <TaskGraphsPage /> },
    { path: "/chat/home", element: <MessagePane conversation={home} messages={messages} mentionCandidates={[]} onSend={onSend} selfUserId="user-1" composerStore={composerStoreFor("user-1")} headerActions={<ConversationTasksLink conversationId="home" />} /> }
  ], { initialEntries: [path] });
  const result = render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return { ...result, router, client, onSend };
}

beforeEach(() => {
  setLanguage("en");
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
  useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, refresh_token: "test-refresh", user: TEST_AUTH_USER });
  currentGraph = structuredClone(sampleGraph);
  graphStatus = 200;
  list = { items: [{ ...sampleGraph, title: "Video product", mode: "dag", status: "todo" }], next_cursor: null, total: 1 };
  fetchMock = vi.fn(async (url: string) => {
    if (url.includes("/task-graphs/")) return new Response(JSON.stringify(graphStatus === 200 ? currentGraph : { detail: { code: "read_failed", message: "Unavailable" } }), { status: graphStatus });
    return new Response(JSON.stringify(list), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("task graph browsing", () => {
  it("shows all direct DAG edges and relationships, preserves view on reread, and navigates both nesting modes", async () => {
    const { container, router } = renderTasks("/tasks/tg-1?scope=root&node=C");
    const detail = await screen.findByRole("complementary", { name: "Node details" });
    expect(within(detail).getByRole("button", { name: "B Implement" })).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "A Choose direction" })).toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "E Launch" })).toBeInTheDocument();
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
    expect(router.state.location.search).toContain("node=C");
    await userEvent.click(screen.getByRole("button", { name: "Enter subgraph of A Choose direction" }));
    expect(router.state.location.search).toContain("scope=A");
    expect(container.querySelector('[data-edge="X:Z"]')).toHaveAttribute("stroke-dasharray", "5 4");
    await userEvent.click(screen.getByRole("button", { name: "View Z Hybrid" }));
    expect(within(screen.getByRole("complementary", { name: "Node details" })).getByRole("button", { name: "X Generated video" })).toBeInTheDocument();
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

  it("retains old records with a stale warning but removes protected cached content after access is revoked", async () => {
    const { client } = renderTasks("/tasks/tg-1?scope=root&node=C");
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
    writeComposerSnapshot(composerStoreFor("user-1"), "home", { draft: "@Nano Please check", draftMentions: [{ label: "@Nano", type: "agent", target_id: "nano" }], pending, slashDismissed: true });
    const { router, onSend } = renderTasks("/chat/home", [{
      id: "saved-plan", conversation_id: "home", sender: { type: "agent", id: "nano", display_name: "Nano" },
      sender_user_id: "nano", sender_type: "agent", content: `[Saved plan](${window.location.origin}/tasks/tg-1?scope=A&node=Z)`,
      attachments: [], delivery_status: "completed", created_at: "2026-01-01T00:00:00Z", permission_requests: [],
    }]);
    await userEvent.click(screen.getByRole("link", { name: "Saved plan" }));
    await screen.findByRole("button", { name: "Discuss this task in chat" });
    await userEvent.click(screen.getByRole("button", { name: "Discuss this task in chat" }));
    expect(router.state.location.pathname).toBe("/chat/home");
    expect(screen.getByRole("textbox")).toHaveValue("@Nano Please check\n\n[Task: Z Hybrid](/tasks/tg-1?scope=A&node=Z)\n");
    expect(screen.getByText("design.pdf")).toBeInTheDocument();
    expect(composerStoreFor("user-1").get("home")?.draftMentions).toEqual([{ label: "@Nano", type: "agent", target_id: "nano" }]);
    expect(onSend).not.toHaveBeenCalled();
    expect(await screen.findByRole("link", { name: "Tasks 1" })).toHaveAttribute("href", "/tasks?conversation_id=home");
  });

  it("restores a mobile nested deep link and closes the detail drawer without moving the graph", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    const { router } = renderTasks("/tasks/tg-1?scope=Z&node=Z2");
    const dialog = await screen.findByRole("dialog", { name: "Node details" });
    expect(within(dialog).getByRole("heading", { name: "Z2 Evaluate" })).toBeInTheDocument();
    const scroll = screen.getByLabelText("Task graph canvas, scroll to explore");
    scroll.scrollLeft = 112;
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(router.state.location.search).toBe("?scope=Z");
    expect(scroll.scrollLeft).toBe(112);
    await userEvent.click(screen.getByRole("button", { name: "Goals" }));
    expect(await screen.findByRole("dialog", { name: "Goals" })).toBeInTheDocument();
  });

  it("does not silently open another scope when a deep link is invalid", async () => {
    renderTasks("/tasks/tg-1?scope=unknown&node=C");
    expect(await screen.findByRole("alert")).toHaveTextContent("scope or node does not exist");
    expect(screen.queryByLabelText("Task graph canvas, scroll to explore")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Back to root goal" }));
    expect(screen.getByRole("button", { name: "View A Choose direction" })).toBeInTheDocument();
  });

  it("filters conversation lists, supports search and pagination, and shows genuine empty results", async () => {
    list.next_cursor = "next-page";
    list.total = 21;
    const { router } = renderTasks("/tasks?conversation_id=home");
    await screen.findByRole("link", { name: /Video product/ });
    list = { items: [], next_cursor: null, total: 21 };
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.includes("cursor=next-page") && url.includes("conversation_id=home"))).toBe(true));
    await screen.findByText(/No task graphs yet/);
    await userEvent.type(screen.getByRole("textbox", { name: "Search goal names" }), "other");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByText("No matching goals.");
    expect(router.state.location.search).toContain("query=other");
  });
});


describe("task graph layout", () => {
  it("orders independent branches by their connections instead of crossing them by input order", () => {
    const graph = { ...sampleGraph, nodes: [sampleGraph.nodes[0], node("A", "A"), node("B", "B"), node("C", "C"), node("D", "D")],
      dependencies: [{ from: "A", to: "D" }, { from: "B", to: "C" }] };
    const { positions, routes } = layoutTaskScope(graph, graph.nodes[0]);
    expect(positions.get("A")!.x).toBe(positions.get("B")!.x);
    expect(positions.get("C")!.x).toBe(positions.get("D")!.x);
    expect(positions.get("A")!.x).toBeLessThan(positions.get("D")!.x);
    const sourceOrder = Math.sign(positions.get("A")!.y - positions.get("B")!.y);
    expect(Math.sign(positions.get("D")!.y - positions.get("C")!.y)).toBe(sourceOrder);
    expect(routes.map(({ from, to }) => `${from}:${to}`).sort()).toEqual(["A:D", "B:C"]);
  });

  it("keeps tasks in their earliest dependency column, retaining direct skip edges and nested scope isolation", () => {
    const { positions, routes } = layoutTaskScope(sampleGraph, sampleGraph.nodes[0]);
    expect(positions.get("B")!.x).toBe(positions.get("D")!.x);
    for (const [from, to] of [["A", "B"], ["B", "C"], ["C", "E"]]) {
      expect(positions.get(from)!.x).toBeLessThan(positions.get(to)!.x);
    }
    expect(routes).toHaveLength(6);
    expect(routes.some(edge => edge.from === "A" && edge.to === "C")).toBe(true);
    expect(positions.has("Z1")).toBe(false);
    expect(sampleGraph.nodes[1].status).toBe("todo");
  });
});
