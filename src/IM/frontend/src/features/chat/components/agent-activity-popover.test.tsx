import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";
import { renderRouter } from "../../../test/render-router";
import { authFetch } from "../../auth/auth-fetch";
import { AgentActivityPopover } from "./agent-activity-popover";

vi.mock("../../auth/auth-fetch", () => ({authFetch: vi.fn()}));
vi.mock("../../../realtime/user-stream", () => ({subscribeUserStream: () => () => {}}));
afterEach(() => vi.unstubAllGlobals());

it("shows active assignments on open and links each to its available records", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  setLanguage("zh");
  const worker = {scope: "worker", runtime: "claude", status: "running"};
  vi.mocked(authFetch).mockResolvedValue(new Response(JSON.stringify({
    revision: 1, main_execution: "idle", node_connection_state: "online", record_sync_state: "current",
    running_count: 2, waiting_permission_count: 0, sessions: [
      {...worker, session_id: "worker/one", title: "检查登录超时原因", has_work_records: true, latest_tool: {name: "Read", label: "README"}},
      {...worker, session_id: "old", title: "核对部署清单"},
    ],
  })));
  const anchor = {agentId: "root", name: "Global", element: document.createElement("button")};
  renderRouter({initialEntries: ["/"], routes: [{path: "/", element: <AgentActivityPopover anchor={anchor} canConfigure={false} onClose={() => {}} />}]});
  const toggle = await screen.findByRole("button", {name: /2 个执行中/});
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", {name: "检查登录超时原因"})).toHaveAttribute("href", "/settings/agents/root?view=work&work_session=worker%2Fone");
  expect(screen.getByText(/最近调用.*Read README/)).toBeVisible();
  expect(screen.getByRole("link", {name: "核对部署清单"})).toHaveAttribute("href", "/settings/agents/root?view=work&work_view=delegation");
  fireEvent.click(toggle);
  expect(screen.queryByRole("link", {name: "检查登录超时原因"})).toBeNull();
  fireEvent.click(toggle);
  expect(screen.getByRole("link", {name: "检查登录超时原因"})).toBeVisible();
});
