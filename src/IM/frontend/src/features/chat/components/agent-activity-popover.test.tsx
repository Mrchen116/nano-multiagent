import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import { renderRouter } from "../../../test/render-router";
import { authFetch } from "../../auth/auth-fetch";
import { AgentActivityPopover } from "./agent-activity-popover";

vi.mock("../../auth/auth-fetch", () => ({authFetch: vi.fn()}));
vi.mock("../../../realtime/user-stream", () => ({subscribeUserStream: () => () => {}}));
afterEach(() => vi.unstubAllGlobals());

it("opens the recorded worker directly and keeps older workers on the graph", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  setLanguage("zh");
  const worker = {scope: "worker", runtime: "claude", status: "running"};
  vi.mocked(authFetch).mockResolvedValue(new Response(JSON.stringify({
    revision: 1, main_execution: "idle", node_connection_state: "online", record_sync_state: "current",
    running_count: 2, waiting_permission_count: 0, sessions: [
      {...worker, session_id: "worker/one", title: "正在检查", has_work_records: true, latest_tool: {name: "Read", label: "README"}},
      {...worker, session_id: "old", title: "旧任务"},
    ],
  })));
  const anchor = {agentId: "root", name: "Global", element: document.createElement("button")};
  renderRouter({initialEntries: ["/"], routes: [{path: "/", element: <AgentActivityPopover anchor={anchor} canConfigure={false} onClose={() => {}} />}]});
  fireEvent.click(await screen.findByRole("button", {name: /2 个执行中/}));
  expect(screen.getByRole("link", {name: "正在检查"})).toHaveAttribute("href", "/settings/agents/root?view=work&work_session=worker%2Fone");
  expect(screen.getByText(/最近调用.*Read README/)).toBeVisible();
  expect(screen.getByRole("link", {name: "旧任务"})).toHaveAttribute("href", "/settings/agents/root?view=work&work_view=delegation");
});
