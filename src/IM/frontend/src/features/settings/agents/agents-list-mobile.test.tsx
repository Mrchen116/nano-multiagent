import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("agents list mobile", () => {
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
            default_model: "gpt-5.2-codex"
          }
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    expect(await screen.findByText("Core Planner")).toBeInTheDocument();
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/im/v1/agents", expect.any(Object));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
