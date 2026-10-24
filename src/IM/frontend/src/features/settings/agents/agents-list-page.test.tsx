import userEvent from "@testing-library/user-event";
import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({ navigate: vi.fn() }));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => apiMocks.navigate };
});

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

const SAMPLE_AGENTS = [
  {
    agent_id: "agent-core-1",
    owner_id: "owner-1",
    display_name: "Core Planner",
    description: "Milestone execution coordinator",
    profile_version: 12,
    default_model: "codex_oauth:gpt-5.5",
    workspace_root: "/workspace/agent-core-1",
    workspace_is_default: true,
    node_id: "node-app-01",
    node_status: "online",
    updated_at: "2026-03-13T10:00:00Z"
  }
];

const SAMPLE_NODES = [
  {
    node_id: "node-app-01",
    owner_id: "owner-1",
    node_name: "MacBook",
    status: "online",
    last_heartbeat_at: "2026-03-13T10:00:00Z",
    agent_count: 1,
    version: "1.0.0"
  }
];

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function mockAgentsAndNodes(agents: unknown = SAMPLE_AGENTS, nodes: unknown = SAMPLE_NODES) {
  fetchMock.mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/im/v1/contacts?")) return jsonResponse({items: (agents as typeof SAMPLE_AGENTS).map(a => ({ user_id: a.agent_id, kind: "agent", agent_id: a.agent_id, owner_id: a.owner_id, display_name: a.display_name, owner_display_name: "Owner", node_name: "MacBook", status: a.node_status, work_mode: "single_thread" })), next_cursor: null});
    if (url.endsWith("/im/v1/nodes")) return jsonResponse(nodes);
    return new Response(null, { status: 404 });
  });
}

afterEach(() => {
  fetchMock.mockReset();
  apiMocks.navigate.mockReset();
});

describe("agents list page", () => {
  it("lists agents and opens the selected agent settings", async () => {
    const user = userEvent.setup();
    mockAgentsAndNodes();

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    await user.click(await screen.findByRole("button", { name: /Core Planner/i }));

    expect(apiMocks.navigate).toHaveBeenCalledWith("/settings/agents/agent-core-1");
  });

  it("labels each agent row with the owning device name from the nodes table", async () => {
    mockAgentsAndNodes();

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    const row = await screen.findByRole("button", { name: /Core Planner/i });
    expect(row).toHaveTextContent("MacBook");
  });

  it("identifies an agent search with no matches and restores rows when cleared", async () => {
    const user = userEvent.setup();
    mockAgentsAndNodes();
    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });
    await screen.findByRole("button", { name: /Core Planner/i });
    await user.type(screen.getByRole("searchbox"), "absent-agent");
    expect(screen.getByText("No matching agents")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Core Planner/i })).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox"));
    expect(screen.getByRole("button", { name: /Core Planner/i })).toBeInTheDocument();
  });

  it("shows an empty state with a path to nodes", async () => {
    mockAgentsAndNodes([], []);

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(await screen.findByText(/No agents yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Open Nodes/i })[0]).toHaveAttribute(
      "href",
      "/settings/nodes"
    );
  });

  it("shows the load error and retries the agent list", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/im/v1/nodes")) return jsonResponse(SAMPLE_NODES);
      if (url.includes("/im/v1/contacts?")) {
        attempts += 1;
        return attempts === 1
          ? jsonResponse({ detail: "upstream unavailable" }, 503)
          : jsonResponse({items: SAMPLE_AGENTS.map(a => ({...a, user_id:a.agent_id, kind:"agent", status:a.node_status})),next_cursor:null});
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(await screen.findByText(/upstream unavailable/i)).toBeInTheDocument();
    await user.click(within(screen.getByRole("alert")).getByRole("button", { name: /Retry/i }));

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
  });
  it("keeps the bound personal assistant separate from other agents and opens its configuration", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/im/v1/personal-agent")) return jsonResponse({binding: {agent_id:"my-pa", display_name:"My assistant", owner_user_id:"user-1", status:"active"}, creation:null});
      if (url.includes("/im/v1/contacts?")) return jsonResponse({items:[
        {user_id:"other",kind:"agent",agent_id:"other-pa",display_name:"Someone else's assistant",owner_id:"other-user",role:"personal"},
        {user_id:"mine",kind:"agent",agent_id:"my-pa",display_name:"My assistant",owner_id:"user-1",owner_display_name:"Owner only search",role:"personal"}
      ],next_cursor:null});
      return new Response(null,{status:404});
    });
    renderRouter({routes:appRoutes,initialEntries:["/settings/agents"]});
    const own = await screen.findByRole("button",{name:"My assistant"});
    expect(screen.getAllByText("My assistant")).toHaveLength(1);
    expect(screen.getByRole("button",{name:/Someone else's assistant/})).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox"), "Owner only search");
    expect(screen.getByRole("button", {name:"My assistant"})).toBeInTheDocument();
    await user.click(own);
    expect(apiMocks.navigate).toHaveBeenCalledWith("/settings/agents/my-pa");
  });

  it("keeps public agents usable when the personal assistant lookup fails", async () => {
    mockAgentsAndNodes();
    renderRouter({routes:appRoutes,initialEntries:["/settings/agents"]});
    expect(await screen.findByRole("button",{name:/Core Planner/})).toBeInTheDocument();
    expect(await screen.findByText(/Personal assistant unavailable/)).toBeInTheDocument();
  });

});
