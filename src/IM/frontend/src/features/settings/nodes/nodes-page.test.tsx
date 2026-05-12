import userEvent from "@testing-library/user-event";
import { act, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

async function setViewport(width: number) {
  await act(async () => {
    window.innerWidth = width;
    window.dispatchEvent(new Event("resize"));
  });
}

afterEach(async () => {
  fetchMock.mockReset();
  await setViewport(1280);
});

describe("nodes page", () => {
  it("shows node-scoped create entry only for online nodes and edits aliases via IM APIs", async () => {
    const user = userEvent.setup();
    const nodes = [
      {
        node_id: "node-app-01",
        owner_id: "owner-1",
        node_name: "node-app-01",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 4,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: null
      },
      {
        node_id: "node-app-02",
        owner_id: "owner-1",
        node_name: "node-app-02",
        status: "offline",
        last_heartbeat_at: "2026-03-13T09:00:00Z",
        agent_count: 1,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: "gateway disconnected"
      }
    ];
    const patchedNode = { ...nodes[0], alias: "node-app-01-prod" };
    const nodesAfter = [patchedNode];

    let nodesCallCount = 0;
    let patchCall: { url: string; init?: RequestInit } | null = null;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes" && (init?.method ?? "GET") === "GET") {
        nodesCallCount += 1;
        const payload = nodesCallCount === 1 ? nodes : nodesAfter;
        return Promise.resolve(
          new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      if (url === "/im/v1/nodes/node-app-01/config" && init?.method === "PATCH") {
        patchCall = { url, init };
        return Promise.resolve(
          new Response(JSON.stringify(patchedNode), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } })
        );
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/nodes"]
    });

    expect(await screen.findByRole("link", { name: "Create agent on node-app-01" })).toHaveAttribute("href", "/settings/nodes/node-app-01/agents/new");
    expect(screen.queryByRole("link", { name: "Create agent on node-app-02" })).not.toBeInTheDocument();

    const aliasInput = await screen.findByLabelText("Alias node-app-01");
    await user.clear(aliasInput);
    await user.type(aliasInput, "node-app-01-prod");
    await user.click(screen.getByRole("button", { name: "Save node-app-01" }));

    expect(await screen.findByDisplayValue("node-app-01-prod")).toBeInTheDocument();
    expect(patchCall).not.toBeNull();
    expect(patchCall!.init!.body).toBe(
      JSON.stringify({ alias: "node-app-01-prod", relay_enabled: true, reporting_enabled: true })
    );
  });

  // M19/R11-5: prototype `im-extra-pages.jsx::NodesPage` 顶部 4 KPI 卡 (Total nodes /
  // Online / Offline / Total agents),每个 NodeCard 头部 🖥/💤 38×38 圆角 icon +
  // alias + status badge + 右上 agent_count / vXXX 双 stat 组。relay_enabled /
  // reporting_enabled checkboxes 不在 prototype,需移除。
  it("R11-5: renders 4 KPI stat cards (total / online / offline / total agents)", async () => {
    const nodes = [
      { node_id: "n1", owner_id: "o", node_name: "n1", status: "online", last_heartbeat_at: "2026-03-13T10:00:00Z", agent_count: 3, version: "1.8.2", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null },
      { node_id: "n2", owner_id: "o", node_name: "n2", status: "offline", last_heartbeat_at: null, agent_count: 1, version: "1.8.2", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null }
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return Promise.resolve(new Response(JSON.stringify(nodes), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const grid = await screen.findByTestId("nodes-kpi-grid");
    expect(grid).not.toBeNull();
    expect(screen.getByTestId("nodes-kpi-total").textContent).toMatch(/2/);
    expect(screen.getByTestId("nodes-kpi-online").textContent).toMatch(/1/);
    expect(screen.getByTestId("nodes-kpi-offline").textContent).toMatch(/1/);
    expect(screen.getByTestId("nodes-kpi-agents").textContent).toMatch(/4/);
  });

  it("R11-5: each NodeCard header carries a 🖥 / 💤 status icon and a version badge", async () => {
    const nodes = [
      { node_id: "n1", owner_id: "o", node_name: "n1", status: "online", last_heartbeat_at: "2026-03-13T10:00:00Z", agent_count: 3, version: "1.8.2", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null },
      { node_id: "n2", owner_id: "o", node_name: "n2", status: "offline", last_heartbeat_at: null, agent_count: 1, version: "1.7.0", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null }
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return Promise.resolve(new Response(JSON.stringify(nodes), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const n1Icon = await screen.findByTestId("node-icon-n1");
    expect(n1Icon.textContent).toMatch(/🖥/);
    const n2Icon = screen.getByTestId("node-icon-n2");
    expect(n2Icon.textContent).toMatch(/💤/);

    // version badge / agent_count 在卡头右侧
    expect(screen.getByTestId("node-version-n1").textContent).toMatch(/v1\.8\.2/);
    expect(screen.getByTestId("node-agent-count-n1").textContent).toMatch(/3/);
  });

  // M19/R10-Nodes: prototype `im-extra-pages.jsx::NodesPage` 在 mobile viewport
  // 顶端有 `PageBackHeader` (sticky, height 48, "‹" 按钮 + "Nodes" 标题),用户
  // 从 Me 页直达,需要一个回退入口返回 /me。
  it("R10-Nodes: mobile viewport renders a sticky back header with '‹' that links to /me", async () => {
    await setViewport(375);
    const nodes = [
      { node_id: "n1", owner_id: "o", node_name: "n1", status: "online", last_heartbeat_at: "2026-03-13T10:00:00Z", agent_count: 1, version: "1.8.2", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null }
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return Promise.resolve(new Response(JSON.stringify(nodes), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const back = await screen.findByTestId("nodes-page-back");
    expect(back).toHaveAttribute("href", "/me");
    expect(back.textContent).toMatch(/‹/);
  });

  it("R11-5: relay_enabled / reporting_enabled checkboxes are hidden (prototype omits these)", async () => {
    const nodes = [
      { node_id: "n1", owner_id: "o", node_name: "n1", status: "online", last_heartbeat_at: "2026-03-13T10:00:00Z", agent_count: 1, version: "1.8.2", relay_enabled: true, reporting_enabled: true, alias: null, last_error: null }
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return Promise.resolve(new Response(JSON.stringify(nodes), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      if (url === "/im/v1/agents") {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    await screen.findByRole("link", { name: /Create agent on n1/i });
    expect(screen.queryByLabelText(/Relay/i)).toBeNull();
    expect(screen.queryByLabelText(/Reporting/i)).toBeNull();
  });
});
