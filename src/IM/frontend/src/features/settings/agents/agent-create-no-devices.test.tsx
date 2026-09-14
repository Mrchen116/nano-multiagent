import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../../i18n";
import { AgentCreatePage } from "./agent-create-page";

const api = vi.hoisted(() => ({ listNodes: vi.fn(), getNodeCreateState: vi.fn() }));
vi.mock("./im-agent-config-api", async importOriginal => ({
  ...await importOriginal<typeof import("./im-agent-config-api")>(),
  ...api,
}));
vi.mock("./public-agents", () => ({ listPublicAgents: async () => [] }));

function renderCreate() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([
    { path: "/settings/agents/new", element: <AgentCreatePage /> },
    { path: "/settings/nodes", element: <p>Device management</p> },
    { path: "/settings/agents", element: <p>Agent list</p> },
  ], { initialEntries: ["/settings/agents/new"] });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

afterEach(() => vi.resetAllMocks());

describe("Agent creation without a preselected device", () => {
  it("finishes loading after an empty device response and offers a way forward", async () => {
    let resolveNodes!: (nodes: []) => void;
    api.listNodes.mockReturnValue(new Promise<[]>(resolve => { resolveNodes = resolve; }));
    renderCreate();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    await act(async () => resolveNodes([]));

    expect(await screen.findByRole("heading", { name: "Bind a device before creating an Agent" })).toBeVisible();
    expect(screen.queryByText("Loading…")).toBeNull();
    expect(api.getNodeCreateState).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Back to Agents" })).toHaveAttribute("href", "/settings/agents");
    await userEvent.click(screen.getByRole("link", { name: "Manage devices" }));
    expect(await screen.findByText("Device management")).toBeVisible();
  });

  it("still selects an available device and loads its creation form", async () => {
    const node = { node_id: "node-1", node_name: "MacBook", status: "online" };
    api.listNodes.mockResolvedValue([node]);
    api.getNodeCreateState.mockResolvedValue({ node, capabilities: {
      ...node, node_status: "online", skills: [], tools: [], model_options: [],
    } });
    renderCreate();
    expect(await screen.findByRole("heading", { name: "New agent" })).toBeVisible();
    expect(api.getNodeCreateState).toHaveBeenCalledWith("node-1");
    expect(screen.queryByText("Bind a device before creating an Agent")).toBeNull();
  });
});
