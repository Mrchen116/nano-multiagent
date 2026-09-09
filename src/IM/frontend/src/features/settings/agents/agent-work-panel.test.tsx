import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, useLocation, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentWorkPanel } from "./agent-work-panel";
import type { WorkView } from "./agent-work-api";

const mocks = vi.hoisted(() => ({ fetch: vi.fn(), subscribe: vi.fn() }));
vi.mock("../../auth/auth-fetch", () => ({ authFetch: mocks.fetch }));
vi.mock("../../../realtime/user-stream", () => ({ subscribeUserStream: mocks.subscribe }));
let view: WorkView;
function ChatTarget() { const location = useLocation(); const navigate = useNavigate(); return <div><p>Real chat route</p><button onClick={() => navigate(location.state.workReturnUrl)}>Return to work</button></div>; }
function renderWork() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/settings/agents/global", element: <AgentWorkPanel agentId="global" /> }, { path: "/chat/:id", element: <ChatTarget /> }], { initialEntries: ["/settings/agents/global?view=work"] });
  return { ...render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>), router };
}
beforeEach(() => {
  sessionStorage.clear(); mocks.subscribe.mockReset(); mocks.subscribe.mockReturnValue(() => {}); mocks.fetch.mockReset();
  view = { root_agent_id: "global", main_session_id: "main", revision: 1, node_connection_state: "online", main_execution: "running", latest_main_usage: null, other_executions: [], next_cursor: null, turns: [{ session_id: "main", turn_id: "turn", status: "running", origin: "user", trigger: { kind: "inbox" }, model_id: "fixture", usage: null, next_items_cursor: null, items: [{ item_id: "tool:read", seq: 1, kind: "tool", payload: { id: "read", name: "inbox", status: "running", input: { action: "read", target: "group-a" }, detail: { action: "read", target: "group-a" } } }] }] };
  mocks.fetch.mockImplementation(async () => new Response(JSON.stringify(view), { status: 200 }));
});

describe("Agent work view", () => {
  it("updates the same tool row from durable refresh and retains expansion after real Chat navigation", async () => {
    const { router } = renderWork();
    fireEvent.click(await screen.findByText("收件箱通知"));
    fireEvent.click(await screen.findByRole("button", { name: /inbox/ }));
    expect(screen.queryByText("没有匹配记录")).not.toBeInTheDocument();
    view = { ...view, revision: 2, turns: [{ ...view.turns[0], items: [{ ...view.turns[0].items[0], payload: { ...view.turns[0].items[0].payload, status: "completed", detail: { action: "read", target: "group-a", has_more: false, messages: [{ message_id: "m-a", sender: { name: "Alice" }, content: [{ type: "text", text: "Actual message" }], source: { conversation_id: "group-a" } } ] } } }] }] };
    act(() => mocks.subscribe.mock.calls[0][0].onEvent({ eventType: "agent.work.updated", payload: { agent_id: "global", revision: 2 } }));
    expect(await screen.findByText("Actual message")).toBeInTheDocument();
    expect(screen.getAllByTestId("process-item")).toHaveLength(1);
    fireEvent.click(screen.getByRole("link", { name: "原消息" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/chat/group-a"));
    expect(router.state.location.search).toBe("?message_id=m-a");
    fireEvent.click(screen.getByRole("button", { name: "Return to work" }));
    expect(await screen.findByText("Actual message")).toBeVisible();
  });

  it("shows actual background results and opens only the linked child session", async () => {
    view = { ...view, other_executions: [{ session_id: "child-session", scope: "subagent", parent_session_id: "main", child_agent_id: "researcher", description: "Research child" }], turns: [{ ...view.turns[0], items: [{ item_id: "message:result", seq: 2, kind: "assistant_message", payload: { content: "Parent response", background_returns: [{ task_id: "task-a", task_type: "agent", agent_id: "researcher", status: "completed", description: "Research child", result: "Actual child result" }] } }] }] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url.includes("/sessions/") ? { turns: [], next_cursor: null } : view), { status: 200 }));
    renderWork();
    fireEvent.click(await screen.findByText("收件箱通知"));
    fireEvent.click(screen.getByTestId("process-background-return-toggle"));
    expect(screen.getByText("Actual child result")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "查看关联执行 · Research child" }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("/im/v1/agents/global/work/sessions/child-session/turns"));
    expect(screen.getByRole("button", { name: "关闭子轨迹" })).toBeVisible();
  });

  it("shows a repeated background source once while retaining distinct task returns", async () => {
    const result = { task_id: "task-a", task_type: "agent", agent_id: "researcher", status: "completed", result: "Shared result" };
    view = { ...view, turns: [{ ...view.turns[0], items: [
      { item_id: "message:first", seq: 1, kind: "assistant_message", payload: { content: "Reasoning result", background_returns: [result] } },
      { item_id: "message:second", seq: 2, kind: "assistant_message", payload: { content: "Delivery result", background_returns: [result] } },
      { item_id: "message:third", seq: 3, kind: "assistant_message", payload: { content: "Other task", background_returns: [{ ...result, task_id: "task-b" }] } }
    ] }] };
    renderWork();
    fireEvent.click(await screen.findByText("收件箱通知"));
    expect(screen.getAllByTestId("process-background-return-toggle")).toHaveLength(2);
  });

  it.each([["manual", "Cron · 手动执行"], ["scheduled", "Cron · 定时执行"], [undefined, "Cron"]])("shows %s Cron metadata and actual session delivery with navigation", async (trigger, label) => {
    view = { ...view, other_executions: [{ session_id: "cron-session", scope: "cron", job_id: "report", trigger }] };
    const page = { turns: [{ ...view.turns[0], session_id: "cron-session", turn_id: "cron-turn", scope: "cron", job_id: "report", origin: "model", trigger: { kind: "cron", source: trigger }, items: [] }], next_cursor: null, control_items: [
      { item_id: "cron-trigger", kind: "cron_trigger", seq: 4, payload: { job_id: "report", trigger } },
      { item_id: "cron-delivery", kind: "cron_delivery", seq: 5, payload: { conversation_id: "target-chat", message_id: "sent-message", text: "Actual scheduled report" } }
    ] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url.includes("/sessions/") ? page : view), { status: 200 }));
    const { router } = renderWork();
    fireEvent.click(await screen.findByText("其他执行与关联 Session · 1"));
    fireEvent.click(screen.getByRole("button", { name: `${label} · report cron-session` }));
    await screen.findByText("执行记录");
    expect(screen.getAllByText(`${label} · report`).length).toBeGreaterThanOrEqual(3);
    if (!trigger) expect(screen.queryByText(/Cron · (手动|定时)执行/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("执行记录"));
    expect(screen.getByText("Actual scheduled report")).toBeVisible();
    fireEvent.click(screen.getByRole("link", { name: "投递聊天 · 原消息" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/chat/target-chat"));
    expect(router.state.location.search).toBe("?message_id=sent-message");
  });

  it("labels a registered workflow execution using its real scope", async () => {
    view = { ...view, other_executions: [{ session_id: "workflow-session", scope: "workflow", title: "workflow:raw-title" }] };
    const page = { turns: [{ ...view.turns[0], session_id: "workflow-session", scope: "workflow", origin: "model", trigger: null, items: [] }], next_cursor: null, control_items: [] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url.includes("/sessions/") ? page : view), { status: 200 }));
    renderWork();
    fireEvent.click(await screen.findByText("其他执行与关联 Session · 1"));
    fireEvent.click(screen.getByRole("button", { name: "Workflow 执行 workflow-session" }));
    await waitFor(() => expect(screen.getAllByText("Workflow 执行").length).toBeGreaterThanOrEqual(3));
    expect(screen.queryByText("workflow:raw-title")).not.toBeInTheDocument();
  });

  it("keeps unavailable statistics unknown and disables offline permissions", async () => {
    view = { ...view, node_connection_state: "offline", main_execution: "unknown", turns: [{ ...view.turns[0], status: "waiting_permission", items: [{ item_id: "permission:p", seq: 2, kind: "permission", payload: { request_id: "p", tool_name: "bash", tool_input: { command: "pwd" }, question: "Allow execution?", status: "pending", options: [{ id: "allow_once", label: "Allow", description: "" }] } }] }] };
    renderWork();
    fireEvent.click(await screen.findByText("收件箱通知"));
    expect(screen.getAllByText("Token 未报告").length).toBeGreaterThan(0);
    expect(screen.getByText(/节点离线，正在显示已保存记录/)).toBeInTheDocument();
    const allow = await screen.findByRole("button", { name: /Allow once|允许一次|允许/ });
    expect(allow).toBeDisabled();
  });
});
