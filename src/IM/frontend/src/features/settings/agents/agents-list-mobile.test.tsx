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

describe("agents list page", () => {
  it("renders card list from IM agent summaries without desktop table on mobile", async () => {
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
            bound_nodes: ["node-app-01"],
            updated_at: "2026-03-13T10:00:00Z"
          }
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    await setViewport(375);

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(screen.getByText("Milestone execution coordinator")).toBeInTheDocument();
    expect(screen.getByText("gpt-5.2-codex")).toBeInTheDocument();
    expect(screen.getByText("Managed default")).toBeInTheDocument();
    expect(screen.getByText("/Users/demo/nano-assistant/workspace/agent-core-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace settings" })).toHaveAttribute("href", "/settings/agents/agent-core-1#workspace-settings");
    expect(screen.getByText("node-app-01")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/im/v1/agents", expect.any(Object));
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
    expect(screen.getByRole("link", { name: "Create First Agent" })).toHaveAttribute("href", "/settings/agents/new");
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
