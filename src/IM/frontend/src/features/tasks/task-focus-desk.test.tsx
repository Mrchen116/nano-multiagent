import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import type { TaskFocusResponse, TaskGraph, TaskGraphSummary, TaskNode } from "./task-graphs-api";
import { TaskGraphsPage } from "./task-graphs-page";
import { TaskStatusBadge } from "./task-status-badge";

const makeSummary = (overrides: Partial<TaskGraphSummary>): TaskGraphSummary => ({
  graph_id: "tg-1",
  root_node_id: "root",
  node_id: "root",
  revision: 3,
  updated_at: "2026-11-25T10:00:00Z",
  updated_by: "pa-1",
  relative_url: "/tasks/tg-1",
  title: "Sample task",
  description: "Background",
  mode: "none",
  status: "todo",
  can_edit: true,
  conversation: {
    id: "pa-dm",
    title: "My PA",
    visibility: "private",
    dissolved_at: null,
    is_member: true,
    can_write: true,
  },
  ...overrides,
});

const makeNode = (id: string, title: string, overrides: Partial<TaskNode> = {}): TaskNode => ({
  id,
  container_id: "root",
  title,
  description: "Stage details",
  mode: "none",
  status: "todo",
  result: "",
  derived_from_id: null,
  selected_candidate_id: null,
  selection_reason: "",
  links: [],
  order: 0,
  created_at: "2026-11-25T09:00:00Z",
  updated_at: "2026-11-25T09:00:00Z",
  updated_by: "pa-1",
  last_chat_id: "pa-dm",
  last_chat_title: "My PA",
  can_edit: true,
  ...overrides,
});

let focusPayload: TaskFocusResponse;
let panoramaGraph: TaskGraph;
let writes: { url: string; body: Record<string, any> }[];

function renderFocus(path = "/tasks") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const router = createMemoryRouter(
    [
      { path: "/tasks", element: <TaskGraphsPage /> },
      { path: "/tasks/:graphId", element: <TaskGraphsPage /> },
    ],
    { initialEntries: [path] },
  );
  const view = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...view, router, client };
}

beforeEach(() => {
  setLanguage("zh");
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
  useAuthStore.getState().setSession({ access_token: TEST_ACCESS_TOKEN, user: TEST_AUTH_USER });
  writes = [];

  focusPayload = {
    needs_you: [
      makeSummary({
        graph_id: "tg-ready",
        node_id: "n-ready",
        root_node_id: "n-ready",
        title: "整理周五演示大纲",
        status: "proposed",
        prereq_blocked: false,
        proposal: {
          rationale: "周五上午就要给客户演示，提前备好框架",
          on_approve: "先拉取本周改动生成首版大纲",
        },
        assignee: { type: "agent", id: "pa-1", display_name: "小满" },
      }),
      makeSummary({
        graph_id: "tg-blocked",
        node_id: "n-blocked",
        root_node_id: "root-goal",
        root_title: "季度搬家计划",
        title: "预约搬家公司",
        status: "proposed",
        prereq_blocked: true,
        proposal: {
          rationale: "签约完成后即可锁定车次",
          on_approve: "对比三家报价发你挑选",
        },
      }),
    ],
    stashed: [
      makeSummary({
        graph_id: "tg-stash",
        node_id: "n-stash",
        root_node_id: "n-stash",
        title: "调研家庭 NAS 方案",
        status: "backlog",
      }),
    ],
    active: [
      makeSummary({
        graph_id: "tg-wait",
        node_id: "n-wait",
        root_node_id: "root-goal",
        root_title: "季度搬家计划",
        title: "等待房东回传合同",
        status: "waiting",
        wait: {
          reason: "周四下午复查合同",
          question: "是否接受押一付三？",
          asked_user_id: "user-1",
          next_check_at: "2026-11-27T06:00:00Z",
        },
        assignee: { type: "agent", id: "pa-1", display_name: "小满" },
      }),
    ],
    goals: [
      {
        ...makeSummary({
          graph_id: "tg-goal-1",
          root_node_id: "root-goal",
          node_id: "root-goal",
          title: "季度搬家计划",
          mode: "dag",
          status: "doing",
          root_goal_summary: "十二月底前顺利入住新居并办妥宽带过户",
        }),
        progress: { done: 1, total: 3 },
        stage_nodes: [
          { id: "s1", title: "筛选房源", status: "done", mode: "none", child_count: 0 },
          { id: "s2", title: "签约合同", status: "doing", mode: "none", child_count: 0 },
          { id: "s3", title: "预约搬家", status: "proposed", mode: "none", child_count: 0 },
        ],
      },
    ],
    completed_count: 1,
    counts: { needs_you: 2, stashed: 1, active: 1, goals: 1, completed: 1 },
    next_cursors: { needs_you: null, stashed: null, active: null, goals: null, completed: null },
  };

  panoramaGraph = {
    schema_version: 2,
    graph_id: "tg-goal-1",
    root_node_id: "root",
    revision: 5,
    relative_url: "/tasks/tg-goal-1",
    created_at: "2026-11-25T08:00:00Z",
    updated_at: "2026-11-25T10:00:00Z",
    updated_by: "pa-1",
    nodes: [
      makeNode("root", "季度搬家计划", {
        container_id: null,
        mode: "dag",
        status: "doing",
        description: "十二月底前顺利入住新居",
      }),
      makeNode("s1", "筛选房源", { status: "done", result: "已选定阳光花园" }),
      makeNode("s2", "核对合同条款", { status: "doing" }),
      makeNode("s3", "预约搬家车队", {
        status: "proposed",
        proposal: { rationale: "合同敲定后马上锁档期", on_approve: "联系三家搬家车队询价" },
      }),
    ],
    dependencies: [
      { from: "s1", to: "s2" },
      { from: "s2", to: "s3" },
    ],
  };

  vi.stubGlobal("IntersectionObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(init.body as string);
        writes.push({ url, body });
        return Response.json({ graph_id: "tg-new", revision: 6 });
      }
      if (url.includes("/conversations")) {
        return Response.json({
          items: [
            {
              id: "pa-dm",
              title: "小满",
              type: "direct",
              can_write: true,
              dissolved_at: null,
              participants: [{ type: "agent", id: "pa-1", role: "personal", display_name: "小满" }],
              participant_ids: ["pa-1"],
            },
            {
              id: "team-1",
              title: "产品周会群",
              type: "group",
              can_write: true,
              dissolved_at: null,
              participants: [],
              participant_ids: [],
            },
          ],
        });
      }
      if (url.includes("/task-graphs/focus")) {
        if (url.includes("section=completed")) {
          return Response.json({
            ...focusPayload,
            completed: [makeSummary({ graph_id: "tg-done", title: "开通燃气账户", status: "done" })],
          });
        }
        return Response.json(focusPayload);
      }
      if (url.includes("/task-graphs/tg-goal-1")) {
        return Response.json(panoramaGraph);
      }
      if (url.includes("/task-graphs/tg-ready")) {
        return Response.json({
          schema_version: 2,
          graph_id: "tg-ready",
          root_node_id: "n-ready",
          revision: 1,
          relative_url: "/tasks/tg-ready",
          created_at: "2026-11-26T00:00:00Z",
          updated_at: "2026-11-26T00:00:00Z",
          updated_by: "pa-1",
          nodes: [makeNode("n-ready", "整理周五演示大纲", { container_id: null, mode: "none", status: "proposed" })],
          dependencies: [],
        });
      }
      if (url.includes("/task-graphs?") && url.includes("statuses=done%2Cclosed")) {
        return Response.json({
          items: [makeSummary({ graph_id: "tg-done", title: "开通燃气账户", status: "done" })],
          next_cursor: null,
          total: 1,
        });
      }
      return Response.json({ items: [], next_cursor: null, total: 0 });
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("progressive focus desk and mobile stage spine", () => {
  it("defaults to mine scope with custom pill popovers (zero native selects) and switches between Actions and Goals lenses", async () => {
    const { container, router } = renderFocus("/tasks");
    await screen.findByText("整理周五演示大纲");

    expect(container.querySelectorAll(".tasks-focus-topbar select, .tasks-quick-create select")).toHaveLength(0);
    expect(screen.getByRole("button", { name: /与我有关/ })).toBeInTheDocument();

    // Waiting badge strictly keeps its canonical word; question/reason render outside the badge pill.
    const waitCard = screen.getByText("等待房东回传合同").closest("article")!;
    const badge = waitCard.querySelector(".tasks-badge")!;
    expect(badge).toHaveTextContent("等待中");
    expect(within(waitCard).getByText("是否接受押一付三？")).toBeInTheDocument();
    expect(within(waitCard).getByText("所属目标：季度搬家计划")).toBeInTheDocument();

    // Switch to Long-term Goals lens and enter panorama
    await userEvent.click(screen.getByRole("tab", { name: /长线目标/ }));
    expect(router.state.location.search).toContain("lens=goals");
    expect(screen.getByText(/十二月底前顺利入住新居并办妥宽带过户/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /季度搬家计划/ }));
    expect(router.state.location.pathname).toBe("/tasks/tg-goal-1");
  });

  it("captures a lightweight single-card task on Enter with mode 'none' and status 'todo'", async () => {
    renderFocus("/tasks");
    const input = await screen.findByLabelText("快速新建单卡事项");
    await userEvent.type(input, "顺路取干洗衣服{Enter}");

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]!.url).toBe("/im/v1/task-graphs");
    expect(writes[0]!.body).toMatchObject({
      title: "顺路取干洗衣服",
      conversation_id: "pa-dm",
      mode: "none",
      status: "todo",
    });
  });

  it("distinguishes 批准开工 vs 批准立项 via approve_task, supports 先存着 switcher actions, and expands folded completed records", async () => {
    const { router } = renderFocus("/tasks");
    const readyCard = (await screen.findByText("整理周五演示大纲")).closest("article")!;
    const blockedCard = screen.getByText("预约搬家公司").closest("article")!;

    expect(within(readyCard).getByRole("button", { name: "批准开工" })).toBeInTheDocument();
    expect(within(blockedCard).getByRole("button", { name: "批准立项" })).toBeInTheDocument();

    await userEvent.click(within(readyCard).getByRole("button", { name: "批准开工" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]!.body.operations).toEqual([{ op: "approve_task", node_id: "n-ready" }]);

    await userEvent.click(within(blockedCard).getByRole("button", { name: "批准立项" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]!.body.operations).toEqual([{ op: "approve_task", node_id: "n-blocked" }]);

    // Switch candidate pool to Stashed (先存着)
    await userEvent.click(screen.getByRole("tab", { name: /先存着/ }));
    const stashCard = (await screen.findByText("调研家庭 NAS 方案")).closest("article")!;
    await userEvent.click(within(stashCard).getByRole("button", { name: "↑ 提上日程" }));
    await waitFor(() => expect(writes).toHaveLength(3));
    expect(writes[2]!.body.operations).toEqual([
      { op: "update_task", node_id: "n-stash", patch: { status: "todo" } },
    ]);

    await userEvent.click(within(stashCard).getByRole("button", { name: "展开成目标图" }));
    await waitFor(() => expect(writes).toHaveLength(4));
    expect(writes[3]!.body.operations).toEqual([
      { op: "update_task", node_id: "n-stash", patch: { mode: "dag" } },
    ]);
    expect(router.state.location.pathname).toBe("/tasks/tg-stash");

    // Return to /tasks and expand folded completed drawer
    await userEvent.click(await screen.findByRole("link", { name: "‹ 返回任务聚焦" }));
    await userEvent.click(await screen.findByRole("button", { name: /查看已完结记录/ }));
    expect(await screen.findByText("开通燃气账户")).toBeInTheDocument();
  });

  it("opens the 9-status flow guide modal and gracefully falls back on unknown status strings", async () => {
    const { unmount } = render(<TaskStatusBadge status="future_custom_state" />);
    expect(screen.getByText("未知状态")).toHaveAttribute("data-status", "unknown");
    unmount();

    renderFocus("/tasks");
    await userEvent.click(await screen.findByRole("button", { name: "查看状态流转说明" }));
    const dialog = await screen.findByRole("dialog", { name: "一张图看懂任务状态与页面分区" });
    for (const label of ["待拍板", "待办", "推进中", "等待中", "待确认", "先存着", "已暂缓", "已完成", "已关闭"]) {
      expect(within(dialog).getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("defaults mobile /tasks/:graphId (390px) to vertical stage spine with collapsible completed earlier stages", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    renderFocus("/tasks/tg-goal-1");

    const spine = await screen.findByLabelText("纵向阶段脉络流");
    expect(within(spine).getByText("前序 1 个已完成阶段")).toBeInTheDocument();
    expect(within(spine).queryByText(/筛选房源/)).not.toBeInTheDocument();

    await userEvent.click(within(spine).getByRole("button", { name: /前序 1 个已完成阶段/ }));
    expect(within(spine).getByText(/筛选房源/)).toBeInTheDocument();

    // Downstream proposed stage is blocked by unfinished s2 -> shows 批准立项
    const sproutCard = within(spine).getByText("预约搬家车队").closest("article")!;
    await userEvent.click(within(sproutCard).getByRole("button", { name: "批准立项" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]!.body.operations).toEqual([{ op: "approve_task", node_id: "s3" }]);
  });

  it("redirects single-card /tasks/:graphId?node=... links to Focus Desk + Drawer without fake North Star banner", async () => {
    const { container, router } = renderFocus("/tasks/tg-ready?scope=n-ready&node=n-ready&return_chat=pa-dm");
    const backChatLink = await screen.findByRole("link", { name: "‹ 返回原聊天" });
    expect(backChatLink).toHaveAttribute("href", "/chat/pa-dm");
    expect(router.state.location.pathname).toBe("/tasks");
    expect(router.state.location.search).toContain("graph=tg-ready");
    expect(container.querySelector(".tasks-north-star-banner")).toBeNull();
  });
});
