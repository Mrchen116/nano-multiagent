import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getNodeCreateStateMock: vi.fn(),
  createNodeAgentMock: vi.fn(),
  listNodesMock: vi.fn(),
  listAgentSummariesMock: vi.fn(),
  nodePromptPreviewMock: vi.fn(),
}));

vi.mock("./im-agent-config-api", () => ({
  getNodeCreateState: apiMocks.getNodeCreateStateMock,
  createNodeAgent: apiMocks.createNodeAgentMock,
  listNodes: apiMocks.listNodesMock,
  listAgentSummaries: apiMocks.listAgentSummariesMock,
  nodePromptPreview: apiMocks.nodePromptPreviewMock,
}));

import { AgentCreatePage } from "./agent-create-page";

function renderCreatePage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [
      {
        path: "/settings/nodes/:nodeId/agents/new",
        element: <AgentCreatePage />,
      },
      { path: "/settings/agents/:agentId", element: <p>Agent detail</p> },
    ],
    { initialEntries: ["/settings/nodes/node-1/agents/new"] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiMocks.listAgentSummariesMock.mockResolvedValue([]);
  apiMocks.listNodesMock.mockResolvedValue([
    {
      node_id: "node-1",
      owner_id: "owner-1",
      node_name: "MacBook",
      alias: "MacBook",
      status: "online",
      last_heartbeat_at: "2026-08-07T00:00:00Z",
      agent_count: 0,
      version: "1.0.0",
    },
  ]);
  apiMocks.getNodeCreateStateMock.mockResolvedValue({
    node: {
      node_id: "node-1",
      owner_id: "owner-1",
      node_name: "MacBook",
      status: "online",
      last_heartbeat_at: "2026-08-07T00:00:00Z",
      agent_count: 0,
      version: "1.0.0",
    },
    capabilities: {
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      skills: [],
      tools: [],
      model_options: [],
      platform_default_model: null,
    },
  });
});

afterEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
});

async function fillIdentity(agentId: string) {
  fireEvent.change(await screen.findByLabelText(/^Agent ID/), {
    target: { value: agentId },
  });
  fireEvent.change(screen.getByLabelText(/^Display Name/), {
    target: { value: "Workspace Agent" },
  });
}

async function selectCustomPath(user: ReturnType<typeof userEvent.setup>, path = "") {
  await user.click(screen.getByRole("radio", { name: /Custom path/i }));
  if (path) {
    fireEvent.change(screen.getByLabelText(/^Workspace Root/), {
      target: { value: path },
    });
  }
}

describe("agent create workspace selection", () => {
  it("places Workspace between Identity and Behavior with default selected", async () => {
    renderCreatePage();
    const form = await screen.findByTestId("agent-create");

    expect(
      Array.from(form.querySelectorAll(".im-agent-card-title"))
        .slice(0, 3)
        .map((heading) => heading.textContent),
    ).toEqual(["Identity", "Workspace", "Behavior"]);
    expect(screen.getByRole("radio", { name: /Use default directory/i })).toBeChecked();
    expect(screen.queryByLabelText(/^Workspace Root/)).not.toBeInTheDocument();
  });

  it("rejects an empty custom workspace before calling the node", async () => {
    const user = userEvent.setup();
    renderCreatePage();
    await fillIdentity("agent-empty");
    await selectCustomPath(user);
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(/Enter an absolute path on the target node/i)).toBeInTheDocument();
    expect(apiMocks.createNodeAgentMock).not.toHaveBeenCalled();
  });

  it("submits a custom absolute workspace for node-side validation", async () => {
    const user = userEvent.setup();
    apiMocks.createNodeAgentMock.mockResolvedValue({
      agent_id: "agent-custom",
      workspace_root: "/srv/agents/agent-custom",
      workspace_is_default: false,
    });
    renderCreatePage();
    await fillIdentity("agent-custom");
    await selectCustomPath(user, "/srv/agents/agent-custom");
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenCalledWith(
        "node-1",
        expect.objectContaining({
          workspace_root: "/srv/agents/agent-custom",
          confirm_existing_workspace: false,
        }),
      );
    });
  });

  it("forwards a custom target-Gateway path without POSIX syntax validation", async () => {
    const user = userEvent.setup();
    apiMocks.createNodeAgentMock.mockResolvedValue({
      agent_id: "agent-windows",
      workspace_root: "C:\\Gateway Data\\agent-windows",
      workspace_is_default: false,
    });
    renderCreatePage();
    await fillIdentity("agent-windows");
    await selectCustomPath(user, "C:\\Gateway Data\\agent-windows");
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenCalledWith(
        "node-1",
        expect.objectContaining({
          workspace_root: "C:\\Gateway Data\\agent-windows",
        }),
      );
    });
  });

  it("does not classify a target-Gateway draft root as a local skill source", async () => {
    const user = userEvent.setup();
    apiMocks.getNodeCreateStateMock.mockResolvedValue({
      node: {
        node_id: "node-1", owner_id: "owner-1", node_name: "MacBook", status: "online",
        last_heartbeat_at: "2026-08-07T00:00:00Z", agent_count: 0, version: "1.0.0",
      },
      capabilities: {
        node_id: "node-1", node_name: "MacBook", node_status: "online",
        skills: [{
          name: "target-local",
          description: "Provided by the target Gateway.",
          location: "/gateway/draft/.nanoassistant/skills/target-local/SKILL.md",
        }],
        tools: [], model_options: [], platform_default_model: null,
      },
    });
    renderCreatePage();
    await screen.findByRole("radio", { name: /Custom path/i });
    await selectCustomPath(user, "/gateway/draft");

    expect(await screen.findByRole("button", { name: "target-local" })).toBeInTheDocument();
    expect(screen.queryByText("Local")).not.toBeInTheDocument();
    expect(screen.getByText("Compatibility (Claude/Codex)")).toBeInTheDocument();
  });

  it("requires acknowledgement before retrying an existing workspace", async () => {
    const user = userEvent.setup();
    apiMocks.createNodeAgentMock
      .mockRejectedValueOnce(
        Object.assign(new Error("Workspace target requires confirmation."), {
          code: "workspace_confirmation_required",
          detail: "Workspace target requires confirmation.",
        }),
      )
      .mockResolvedValueOnce({
        agent_id: "agent-existing",
        workspace_root: "/srv/existing",
        workspace_is_default: false,
      });
    renderCreatePage();
    await fillIdentity("agent-existing");
    await selectCustomPath(user, "/srv/existing");
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/existing directory/i);
    expect(apiMocks.createNodeAgentMock).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("checkbox", { name: /understand/i }));
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    await waitFor(() => {
      expect(apiMocks.createNodeAgentMock).toHaveBeenLastCalledWith(
        "node-1",
        expect.objectContaining({
          workspace_root: "/srv/existing",
          confirm_existing_workspace: true,
        }),
      );
    });
  });

  it("shows the owning Agent for a workspace assignment conflict", async () => {
    const user = userEvent.setup();
    apiMocks.createNodeAgentMock.mockRejectedValue(
      Object.assign(new Error("Workspace is already assigned."), {
        code: "workspace_already_assigned",
        detail: "Workspace is already assigned.",
        agentId: "project-analyst",
      }),
    );
    renderCreatePage();
    await fillIdentity("agent-conflict");
    await selectCustomPath(user, "/srv/assigned");
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(/project-analyst.*another path/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([
    ["workspace_parent_missing", /parent directory does not exist on MacBook/i],
    ["workspace_parent_unusable", /parent directory is not usable on MacBook/i],
    ["workspace_target_not_directory", /target exists but is not a directory/i],
    ["workspace_initialization_failed", /selected node could not initialize this workspace/i],
  ])("preserves the draft and localizes %s", async (code, expectedMessage) => {
    const user = userEvent.setup();
    apiMocks.createNodeAgentMock.mockRejectedValue(
      Object.assign(new Error("raw server detail must not render"), { code }),
    );
    renderCreatePage();
    await fillIdentity("agent-path-error");
    await selectCustomPath(user, "/srv/projects/agent-path-error");
    await user.click(screen.getByRole("button", { name: /^Create agent$/i }));

    expect(await screen.findByText(expectedMessage)).toBeInTheDocument();
    expect(screen.queryByText(/raw server detail/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^Agent ID/)).toHaveValue("agent-path-error");
    expect(screen.getByLabelText(/^Display Name/)).toHaveValue("Workspace Agent");
    expect(screen.getByRole("radio", { name: /Custom path/i })).toBeChecked();
    expect(screen.getByLabelText(/^Workspace Root/)).toHaveValue(
      "/srv/projects/agent-path-error",
    );
    expect(apiMocks.createNodeAgentMock).toHaveBeenCalledTimes(1);
  });
});
