import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("agent edit page", () => {
  it("loads agent form, shows bound node status, and saves edited display name via IM config APIs", async () => {
    const user = userEvent.setup();
    let currentConfig = {
      agent_id: "agent-core-1",
      owner_id: "owner-1",
      display_name: "Core Planner",
      description: "Milestone execution coordinator",
      system_prompt: "You are the planning core for IM and SDK tasks.",
      skills: ["tdd-execution-worker", "playwright"],
      tool_allowlist: ["bash", "read_file"],
      group_reply_policy: "MENTION",
      default_model: "gpt-5.2-codex",
      profile_version: 12,
      bound_nodes: ["node-1"],
      updated_at: "2026-03-13T10:00:00Z"
    };

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url === "/im/v1/nodes") {
        return new Response(
          JSON.stringify([
            {
              node_id: "node-1",
              owner_id: "owner-1",
              node_name: "MacBook",
              status: "online",
              last_heartbeat_at: "2026-03-13T10:00:00Z",
              agent_count: 1,
              version: "1.0.0"
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url === "/im/v1/agents/agent-core-1/config" && init?.method === "PATCH") {
        const payload = JSON.parse(String(init.body)) as {
          profile_version: number;
          display_name: string;
          description: string;
          system_prompt: string;
          skills: string[];
          tool_allowlist: string[];
          group_reply_policy: string;
          default_model: string;
        };

        currentConfig = {
          ...currentConfig,
          ...payload,
          profile_version: 13,
          updated_at: "2026-03-13T10:01:00Z"
        };

        return new Response(JSON.stringify(currentConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config") {
        return new Response(JSON.stringify(currentConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }

      return new Response(null, { status: 404 });
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents/agent-core-1"]
    });

    const input = await screen.findByLabelText("Display Name");
    expect(screen.getByText("MacBook")).toBeInTheDocument();
    expect(screen.getByText("online")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "No Changes to Save" })).toBeDisabled();

    await user.clear(input);
    await user.type(input, "Core Planner X");
    await user.click(screen.getByRole("button", { name: "Save Agent" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(await screen.findByText("Profile Version: 13")).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
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

  it("blocks save when required fields are empty", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config") {
        return new Response(
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
            profile_version: 12,
            bound_nodes: [],
            updated_at: "2026-03-13T10:00:00Z"
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(null, { status: 404 });
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents/agent-core-1"]
    });

    const input = await screen.findByLabelText("Display Name");
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: "Save Agent" }));

    expect(await screen.findByText("Display name is required.")).toBeInTheDocument();
    expect(screen.getByText("Fix the required fields before saving.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces real 409 conflict detail without overwriting the current version label", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config" && init?.method === "PATCH") {
        return new Response(JSON.stringify({ detail: "profile_version conflict" }), {
          status: 409,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config") {
        return new Response(
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
            profile_version: 12,
            bound_nodes: ["node-1"],
            updated_at: "2026-03-13T10:00:00Z"
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(null, { status: 404 });
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents/agent-core-1"]
    });

    const input = await screen.findByLabelText("Display Name");
    await user.clear(input);
    await user.type(input, "Core Planner X");
    await user.click(screen.getByRole("button", { name: "Save Agent" }));

    expect(await screen.findByText("409 (profile_version conflict)")).toBeInTheDocument();
    expect(screen.getByText("Profile Version: 12")).toBeInTheDocument();
  });
});
