import userEvent from "@testing-library/user-event";
import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  navigateMock: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => apiMocks.navigateMock
  };
});

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";
import { setLanguage } from "../../../i18n";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

async function setViewport(width: number) {
  await act(async () => {
    window.innerWidth = width;
    window.dispatchEvent(new Event("resize"));
  });
}

const SAMPLE_AGENTS = [
  {
    agent_id: "agent-core-1",
    owner_id: "owner-1",
    display_name: "Core Planner",
    description: "Milestone execution coordinator",
    profile_version: 12,
    default_model: "codex_oauth:gpt-5.4",
    workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
    workspace_is_default: true,
    node_id: "node-app-01",
    updated_at: "2026-03-13T10:00:00Z"
  },
  {
    agent_id: "agent-writer-1",
    owner_id: "owner-1",
    display_name: "Writer",
    description: "Drafts product updates",
    profile_version: 3,
    default_model: null,
    workspace_root: "/Users/demo/nano-assistant/workspace/agent-writer-1",
    workspace_is_default: false,
    node_id: null,
    updated_at: "2026-03-12T08:00:00Z"
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

afterEach(async () => {
  fetchMock.mockReset();
  apiMocks.navigateMock.mockReset();
  setLanguage("en");
  await setViewport(1280);
});

describe("agents list page (M5 rewrite)", () => {
  it("renders prototype-aligned desktop sidebar with agent rows, status dot and + New CTA linking to nodes", async () => {
    mockAgentsAndNodes();
    await setViewport(1280);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(screen.getByText("Writer")).toBeInTheDocument();

    expect(screen.getByText("agent-core-1")).toBeInTheDocument();
    expect(screen.getByText("agent-writer-1")).toBeInTheDocument();

    const newLink = screen.getByRole("link", { name: /\+ New/i });
    expect(newLink).toHaveAttribute("href", "/settings/agents/new");

    const planner = screen.getByRole("button", { name: /Core Planner/i });
    expect(planner).toBeInTheDocument();

    expect(screen.getByLabelText("online")).toBeInTheDocument();
    expect(screen.getAllByLabelText("offline").length).toBeGreaterThanOrEqual(1);

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open direct chat/i })).not.toBeInTheDocument();
  });

  it("renders full-width mobile layout with descriptions visible per row", async () => {
    mockAgentsAndNodes();
    await setViewport(375);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(screen.getByText("Milestone execution coordinator")).toBeInTheDocument();
    expect(screen.getByText("Drafts product updates")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /\+ New/i })).toHaveAttribute("href", "/settings/agents/new");

    // Agent rows are now buttons (matching prototype AgentListView)
    expect(screen.getByRole("button", { name: /Core Planner/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Writer/i })).toBeInTheDocument();
  });

  // M19/R10-AgentsList: prototype `im-mypage.jsx` / `im-settings-page.jsx` 中所有
  // 行式导航项尾部都带一个浅灰 "›" chevron 表示"可点开二级页",AgentsList 在 mobile
  // 当作 navigation list 必须保持同一视觉契约。
  it("R10-AgentsList: each mobile row carries a trailing '›' chevron", async () => {
    mockAgentsAndNodes();
    await setViewport(375);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    await screen.findByText("Core Planner");
    // Chevron is rendered as a text node without data-testid in prototype-aligned implementation
    const coreRow = screen.getByRole("button", { name: /Core Planner/i });
    const writerRow = screen.getByRole("button", { name: /Writer/i });
    expect(coreRow.textContent).toMatch(/›/);
    expect(writerRow.textContent).toMatch(/›/);
  });

  it("renders empty state with CTA to nodes when no agents", async () => {
    mockAgentsAndNodes([], []);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText(/No agents yet/i)).toBeInTheDocument();
    const ctas = screen.getAllByRole("link", { name: /Open Nodes/i });
    expect(ctas[0]).toHaveAttribute("href", "/settings/nodes");
  });

  it("shows load error then retries", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/im/v1/nodes")) return jsonResponse(SAMPLE_NODES);
      if (url.endsWith("/im/v1/agents")) {
        attempts += 1;
        if (attempts === 1) {
          return jsonResponse({ detail: "upstream unavailable" }, 503);
        }
        return jsonResponse(SAMPLE_AGENTS);
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText(/Could not load agents/i)).toBeInTheDocument();
    expect(screen.getByText(/upstream unavailable/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Retry/i }));

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
  });

  it("sends Authorization Bearer header via authFetch", async () => {
    mockAgentsAndNodes();

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const call = fetchMock.mock.calls.find((c) => {
      const url = typeof c[0] === "string" ? c[0] : c[0].toString();
      return url.endsWith("/im/v1/agents");
    });
    expect(call).toBeDefined();
    const init = call![1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("translates list empty state to Chinese when locale switches", async () => {
    mockAgentsAndNodes([], []);
    setLanguage("zh");

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("还没有 Agent")).toBeInTheDocument();
  });
});
