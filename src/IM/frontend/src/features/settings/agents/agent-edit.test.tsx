import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("agent edit page", () => {
  it("loads agent form and saves edited display name via IM config APIs", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner",
            description: "Milestone execution coordinator",
            system_prompt: "You are the planning core for IM and SDK tasks.",
            skills: ["tdd-execution-worker", "playwright"],
            tool_allowlist: ["bash", "read_file"],
            group_reply_policy: "MENTION",
            default_model: "gpt-5.2-codex",
            profile_version: 12
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner X",
            description: "Milestone execution coordinator",
            system_prompt: "You are the planning core for IM and SDK tasks.",
            skills: ["tdd-execution-worker", "playwright"],
            tool_allowlist: ["bash", "read_file"],
            group_reply_policy: "MENTION",
            default_model: "gpt-5.2-codex",
            profile_version: 13
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              agent_id: "agent-core-1",
              owner_id: "owner-1",
              display_name: "Core Planner X",
              description: "Milestone execution coordinator",
              profile_version: 13,
              default_model: "gpt-5.2-codex"
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner X",
            description: "Milestone execution coordinator",
            system_prompt: "You are the planning core for IM and SDK tasks.",
            skills: ["tdd-execution-worker", "playwright"],
            tool_allowlist: ["bash", "read_file"],
            group_reply_policy: "MENTION",
            default_model: "gpt-5.2-codex",
            profile_version: 13
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents/agent-core-1"]
    });

    const input = await screen.findByLabelText("Display Name");
    await user.clear(input);
    await user.type(input, "Core Planner X");
    await user.click(screen.getByRole("button", { name: "Save Agent" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(await screen.findByText("Profile Version: 13")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/im/v1/agents/agent-core-1/config", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/im/v1/agents/agent-core-1/config",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          profile_version: 12,
          display_name: "Core Planner X",
          description: "Milestone execution coordinator",
          system_prompt: "You are the planning core for IM and SDK tasks.",
          skills: ["tdd-execution-worker", "playwright"],
          tool_allowlist: ["bash", "read_file"],
          group_reply_policy: "MENTION",
          default_model: "gpt-5.2-codex"
        })
      })
    );
  });
});
