import userEvent from "@testing-library/user-event";
import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  createDirectConversationMock: vi.fn(),
  navigateMock: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => apiMocks.navigateMock
  };
});

vi.mock("../../chat/chat-api", () => ({
  createDirectConversation: apiMocks.createDirectConversationMock
}));

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
  apiMocks.createDirectConversationMock.mockReset();
  apiMocks.navigateMock.mockReset();
  await setViewport(1280);
});

describe("agents list page", () => {
  it("renders a compact card list on mobile without desktop table chrome", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner",
            description: "Milestone execution coordinator",
            profile_version: 12,
            default_model: "gpt-5.2-codex",
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
            node_id: "node-app-01",
            updated_at: "2026-03-13T10:00:00Z"
          }
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-agent-core-1" });

    await setViewport(375);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(screen.getByText("Milestone execution coordinator")).toBeInTheDocument();
    expect(screen.getByText("gpt-5.2-codex")).toBeInTheDocument();
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("/Users/demo/nano-assistant/workspace/agent-core-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open direct chat" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace settings" })).toHaveAttribute("href", "/settings/agents/agent-core-1#workspace-settings");
    expect(screen.getByText("node-app-01")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/im/v1/agents", expect.any(Object));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("opens direct chat from the list card", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner",
            description: "Milestone execution coordinator",
            profile_version: 12,
            default_model: "gpt-5.2-codex",
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
            node_id: "node-app-01",
            updated_at: "2026-03-13T10:00:00Z"
          }
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    apiMocks.createDirectConversationMock.mockResolvedValue({ conversation_id: "conv-agent-core-1" });

    await setViewport(375);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    await user.click(await screen.findByRole("button", { name: "Open direct chat" }));

    await waitFor(() => {
      expect(apiMocks.createDirectConversationMock).toHaveBeenCalledWith({ agentId: "agent-core-1" });
    });
    await waitFor(() => {
      expect(apiMocks.navigateMock).toHaveBeenCalledWith("/chat/conv-agent-core-1");
    });
  });

  it("renders desktop cards with summary sections instead of a dense table", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner",
            description: "Milestone execution coordinator",
            profile_version: 12,
            default_model: "gpt-5.2-codex",
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
            bound_nodes: [],
            updated_at: "2026-03-12T08:00:00Z"
          }
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    await setViewport(1280);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(screen.getByText("Review each agent's role, access, and workspace before opening settings.")).toBeInTheDocument();
    expect(screen.getByText("Active agents")).toBeInTheDocument();
    expect(screen.getByText("2 profiles")).toBeInTheDocument();
    expect(screen.getAllByText("Workspace")).toHaveLength(2);
    expect(screen.getAllByText("Access")).toHaveLength(2);
    expect(screen.getByText("Owning node: node-app-01")).toBeInTheDocument();
    expect(screen.getByText("Owning node: Not assigned")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders an empty state with a creation CTA when there are no agents", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })
    );

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("No agents yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Nodes" })).toHaveAttribute("href", "/settings/nodes");
  });

  it("shows load errors and retries the query", async () => {
    const user = userEvent.setup();
    let attempts = 0;

    fetchMock.mockImplementation(async () => {
      attempts += 1;

      if (attempts === 1) {
        return new Response(JSON.stringify({ detail: "upstream unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" }
        });
      }

      return new Response(
        JSON.stringify([
          {
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner",
            description: "Milestone execution coordinator",
            profile_version: 12,
            default_model: "gpt-5.2-codex",
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
            bound_nodes: [],
            updated_at: "2026-03-13T10:00:00Z"
          }
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Could not load agents.")).toBeInTheDocument();
    expect(screen.getByText("503 (upstream unavailable)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
