import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import { TaskDetailDrawer } from "./task-detail-drawer";
import { TaskAgentRuntime, TaskWaitInfo } from "./task-wait";
import type { TaskGraph, TaskNode, TaskWaitHealth } from "./task-graphs-api";

const wait = { reason: "Await budget approval. Resume purchasing once approved.", schedule_id: "s", owner_agent_id: "a", session_id: "main", next_check_at: "2026-10-22T12:00:00Z" };
beforeEach(() => setLanguage("en"));
afterEach(() => vi.unstubAllGlobals());

it.each(["valid", "invalid", "unknown", undefined] as const)("keeps the business wait separate from %s schedule health", state => {
  const health: TaskWaitHealth | undefined = state ? { state, checked_at: "2026-10-22T11:00:00Z" } : undefined;
  render(<TaskWaitInfo wait={wait} health={health} />);
  expect(screen.getByText(wait.reason)).toBeVisible();
  if (state === "valid") {
    expect(screen.getByText(/Next check ·/)).toBeVisible();
    expect(screen.queryByText(/could not be verified/)).not.toBeInTheDocument();
  } else if (state === "invalid") {
    expect(screen.getByText(/Schedule needs attention/)).toBeVisible();
    expect(screen.getByText(/No valid schedule/)).toBeVisible();
  } else {
    expect(screen.getByText(/Schedule could not be verified/)).toBeVisible();
    expect(screen.getByText(/Saved schedule time/)).toBeVisible();
  }
  expect(screen.getByText(/not an execution receipt/)).toBeVisible();
});

it("uses observed Agent state and removes stale running evidence when the node disconnects or reading fails", async () => {
  let response: Response = Response.json({state:"running"});
  vi.stubGlobal("fetch",vi.fn(async()=>response.clone()));
  const client = new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  render(<QueryClientProvider client={client}><TaskAgentRuntime agentId="a" graphId="g" nodeId="n" /></QueryClientProvider>);
  expect(await screen.findByText("Assignee execution · Running")).toBeVisible();
  response = Response.json({state:"offline"});
  await client.invalidateQueries({queryKey:["task-agent-runtime"]});
  await waitFor(()=>expect(screen.getByText("Assignee execution · Node offline")).toBeVisible());
  response = Response.json({detail:"unavailable"},{status:503});
  await client.invalidateQueries({queryKey:["task-agent-runtime"]});
  await waitFor(()=>expect(screen.getByText("Assignee execution · Could not be verified")).toBeVisible());
});

it("reads the assignee through the Task route for Single Thread and Global Agents alike", async () => {
  const fetch = vi.fn(async(_url: string)=>Response.json({state:"idle"}));
  vi.stubGlobal("fetch",fetch);
  const client = new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  render(<QueryClientProvider client={client}><TaskAgentRuntime agentId="a" graphId="g" nodeId="n" /></QueryClientProvider>);
  expect(await screen.findByText("Assignee execution · Idle")).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(String(fetch.mock.calls[0][0])).toContain("/task-graphs/g/runtime?node_id=n");
});

it("renders schedule-less silent waiting with user question cleanly without schedule errors", () => {
  render(
    <TaskWaitInfo
      wait={{
        reason: "Indoor booth or terrace table?",
        asked_user_id: "user-1",
        next_check_at: null,
        schedule_id: null,
      }}
    />,
  );
  expect(screen.getByText("Question awaiting reply")).toBeVisible();
  expect(screen.getByText(/Indoor booth or terrace table\?/)).toBeVisible();
  expect(screen.queryByText(/could not be verified/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument();
  expect(screen.queryByText(/not an execution receipt/)).not.toBeInTheDocument();
});

it("declutters TaskDetailDrawer with clickable Agent avatar popover and floating More menu", async () => {
  setLanguage("zh");
  useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, user: TEST_AUTH_USER });
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("EventSource", class { addEventListener() {} removeEventListener() {} close() {} });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/runtime")) {
        return Response.json({ state: "idle" });
      }
      if (url.includes("/work/activity")) {
        return Response.json({
          agent_id: "pa_demo",
          revision: 1,
          node_connection_state: "online",
          record_sync_state: "current",
          main_execution: "idle",
          running_count: 0,
          sessions: [],
          next_cursor: null,
        });
      }
      return Response.json({});
    }),
  );

  const node: TaskNode = {
    id: "n1",
    container_id: null,
    title: "起草一页《Nano 0.9 内测体验速查表》",
    description:
      "内测邀请发出时附一页简洁速查表，能让朋友无需翻长文档直接体验重点。批准后：在本私聊起草一页 3 分钟亮点速查表供你审阅，绝不对外发送。",
    mode: "none",
    status: "proposed",
    assignee: { type: "agent", id: "pa_demo", display_name: "PA · 个人助手" },
    created_by: { type: "user", id: "u_5mguhd", display_name: "Test User" },
    result: "",
    change_note: "主人说明误点并要求停下",
    derived_from_id: null,
    selected_candidate_id: null,
    selection_reason: "",
    links: [],
    order: 0,
    created_at: "2026-11-26T00:24:15Z",
    updated_at: "2026-11-26T00:24:15Z",
    updated_by: "Test User (u_5mguhd)",
    last_chat_id: "c_bmtbq8",
    last_chat_title: "PA · 个人助手",
    can_edit: true,
    can_delete: true,
  };
  const graph: TaskGraph = {
    schema_version: 2,
    graph_id: "tg_demo",
    root_node_id: "n1",
    revision: 1,
    relative_url: "/tasks/tg_demo",
    created_at: "2026-11-26T00:24:15Z",
    updated_at: "2026-11-26T00:24:15Z",
    updated_by: "u_5mguhd",
    conversation: {
      id: "c_bmtbq8",
      title: "PA · 个人助手",
      visibility: "private",
      dissolved_at: null,
      is_member: true,
      can_write: true,
    },
    nodes: [node],
    dependencies: [],
  };

  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TaskDetailDrawer
          graph={graph}
          node={node}
          busy={false}
          error=""
          onClose={() => {}}
          onSelect={() => {}}
          onEnter={() => {}}
          onDiscuss={() => {}}
          onCopy={() => {}}
          onEdit={() => {}}
          onAct={async () => {}}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  const drawer = await screen.findByRole("dialog", { name: "节点详情" });
  expect(within(drawer).queryByText(/负责人执行状态/)).not.toBeInTheDocument();
  expect(within(drawer).queryByText(/u_5mguhd/)).not.toBeInTheDocument();
  expect(within(drawer).queryByRole("heading", { name: "最近变更说明" })).not.toBeInTheDocument();
  expect(within(drawer).getByText(/主人说明误点并要求停下/)).toBeVisible();
  expect(within(drawer).getByText("提议事项 · 你点批准前不会自动执行")).toBeVisible();
  expect(within(drawer).getByRole("heading", { name: "任务说明" })).toBeVisible();
  expect(within(drawer).getByRole("button", { name: "不采纳" })).toBeVisible();
  expect(within(drawer).queryByRole("menuitem", { name: "删除" })).not.toBeInTheDocument();

  // Clicking More opens floating dropdown menu with Delete
  await userEvent.click(within(drawer).getByRole("button", { name: "更多" }));
  expect(within(drawer).getByRole("menuitem", { name: "删除" })).toBeVisible();

  // Clicking Assignee avatar/name pill opens Chat-consistent AgentActivityPopover
  await userEvent.click(within(drawer).getByRole("button", { name: "查看PA · 个人助手的工作状态" }));
  const activityPopover = await screen.findByRole("dialog", { name: "PA · 个人助手" });
  expect(within(activityPopover).getByText("工作状态")).toBeVisible();
  expect(await within(activityPopover).findByRole("link", { name: /打开工作记录/ })).toHaveAttribute(
    "href",
    "/settings/agents/pa_demo?view=work",
  );
});
