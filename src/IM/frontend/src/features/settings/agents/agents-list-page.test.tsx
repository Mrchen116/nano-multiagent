import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
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
    if (url.endsWith("/im/v1/agents")) return jsonResponse(agents);
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
      if (url.endsWith("/im/v1/agents")) {
        attempts += 1;
        return attempts === 1
          ? jsonResponse({ detail: "upstream unavailable" }, 503)
          : jsonResponse(SAMPLE_AGENTS);
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(await screen.findByText(/upstream unavailable/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Retry/i }));

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
  });
});
