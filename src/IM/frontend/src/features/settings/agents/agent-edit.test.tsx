import userEvent from "@testing-library/user-event";
import { fireEvent, screen, waitFor } from "@testing-library/react";
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
    let currentConfig: {
      agent_id: string;
      owner_id: string;
      display_name: string;
      description: string;
      system_prompt: string;
      skills: string[];
      tool_allowlist: string[];
      group_reply_policy: string;
      default_model: string | null;
      workspace_root: string;
      workspace_is_default: boolean;
      profile_version: number;
      bound_nodes: string[];
      updated_at: string;
    } = {
      agent_id: "agent-core-1",
      owner_id: "owner-1",
      display_name: "Core Planner",
      description: "Milestone execution coordinator",
      system_prompt: "You are the planning core for IM and SDK tasks.",
      skills: ["tdd-execution-worker", "playwright"],
      tool_allowlist: ["bash", "read_file"],
      group_reply_policy: "MENTION",
      default_model: "codex_oauth:gpt-5.5",
      workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
      workspace_is_default: true,
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

      if (url === "/im/v1/agents/agent-core-1/capabilities") {
        return new Response(
          JSON.stringify({
            node_id: "node-1",
            node_name: "MacBook",
            node_status: "online",
            capabilities_updated_at: "2026-03-13T10:00:00Z",
            skills: [
              { name: "tdd-execution-worker", description: "Execute TDD tasks" },
              { name: "playwright", description: "Drive browser checks" },
              { name: "plan", description: "Plan work" }
            ],
            tools: [
              { name: "bash", description: "Run shell commands" },
              { name: "read_file", description: "Read files" },
              { name: "task", description: "Dispatch a subtask" }
            ],
            model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }, { name: "kimiCoding:K2.6", provider: "anthropic" }],
            platform_default_model: "codex_oauth:gpt-5.5",
            default_system_prompt: "You are the personal_assistant default template."
          }),
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
          workspace_root: string | null;
        };

        currentConfig = {
          ...currentConfig,
          ...payload,
          workspace_root: payload.workspace_root ?? "/Users/demo/nano-assistant/workspace/agent-core-1",
          workspace_is_default: payload.workspace_root == null,
          profile_version: 13,
          updated_at: "2026-03-13T10:01:00Z"
        };

        return new Response(JSON.stringify(currentConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config?source=mirror") {
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
    // feat-379-M3: System Prompt textarea removed; custom_prompt textarea is now the editable field.
    expect(screen.queryByLabelText("System Prompt")).toBeNull();
    expect(screen.getByLabelText("Custom Instructions")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behavior" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Access & Model" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Workspace & Runtime" })).toBeInTheDocument();
    expect(screen.getByText(/MacBook/, { selector: ".im-agent-panel-node" })).toBeInTheDocument();
    expect((screen.getByLabelText("Workspace Root") as HTMLInputElement).value).toBe(
      "/Users/demo/nano-assistant/workspace/agent-core-1"
    );

    const panel = screen.getByTestId("agent-detail");
    expect(panel.className).toContain("im-agent-panel");
    expect(panel.querySelector(".chat-avatar-status--online")).not.toBeNull();
    expect(panel.querySelector(".im-agent-panel-status-chip")).toBeNull();
    expect(panel.querySelectorAll(".im-agent-card").length).toBeGreaterThanOrEqual(4);
    expect(panel.querySelector(".im-agent-footer")).not.toBeNull();
    expect(screen.queryByLabelText("Workspace setting")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Selected 2$/)).not.toBeInTheDocument();
    expect(screen.queryByText("Needs review")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /tdd-execution-worker/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /playwright/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /bash/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /read_file/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText(/Show advanced options/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Save Agent$/ })).toBeDisabled();

    fireEvent.change(input, { target: { value: "Core Planner X" } });
    await user.click(screen.getByRole("button", { name: /playwright/i }));
    await user.click(screen.getByRole("button", { name: /^plan$/i }));
    await user.click(screen.getByRole("button", { name: /bash/i }));
    await user.click(screen.getByRole("button", { name: /^Save Agent$/ }));

    expect((await screen.findAllByText("✓ Saved")).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect((screen.getByLabelText("Profile Version") as HTMLInputElement).value).toBe("v13");
    });

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => url === "/im/v1/agents/agent-core-1/config?source=mirror")).toBe(true);
    });

    await waitFor(() => {
      // feat-379-M3: PATCH now includes features and custom_prompt; system_prompt is preserved for
      // API compat but not user-editable.
      // bugfix-390: features:{} is present because Behavior card initializes effectiveFeatures
      // from capabilityFeatures; with no capability features declared the resolved map is {}.
      expect(fetchMock).toHaveBeenCalledWith(
        "/im/v1/agents/agent-core-1/config",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            profile_version: 12,
            display_name: "Core Planner X",
            description: "Milestone execution coordinator",
            system_prompt: "You are the planning core for IM and SDK tasks.",
            features: {},
            custom_prompt: "",
            skills: ["tdd-execution-worker", "plan"],
            tool_allowlist: ["read_file"],
            group_reply_policy: "MENTION",
            default_model: "codex_oauth:gpt-5.5"
          })
        })
      );
    });
  }, 10_000);

  it("keeps the settings form usable when live capabilities are unavailable", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), {
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

      if (url === "/im/v1/agents/agent-core-1/capabilities") {
        return new Response(JSON.stringify({ detail: "target_node_id is not connected" }), {
          status: 503,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config" && init?.method === "PATCH") {
        const payload = JSON.parse(String(init.body)) as { display_name: string; default_model: string | null };
        return new Response(
          JSON.stringify({
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: payload.display_name,
            description: "",
            system_prompt: "You are the planning core for IM and SDK tasks.",
            skills: [],
            tool_allowlist: [],
            group_reply_policy: "MENTION",
            default_model: payload.default_model,
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
            profile_version: 13,
            node_id: "node-1",
            updated_at: "2026-03-13T10:01:00Z"
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url === "/im/v1/agents/agent-core-1/config?source=mirror") {
        return new Response(
          JSON.stringify({
            agent_id: "agent-core-1",
            owner_id: "owner-1",
            display_name: "Core Planner",
            description: "",
            system_prompt: "You are the planning core for IM and SDK tasks.",
            skills: [],
            tool_allowlist: [],
            group_reply_policy: "MENTION",
            default_model: "codex_oauth:gpt-5.5",
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
            profile_version: 12,
            node_id: "node-1",
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
    expect(screen.queryByText(/target_node_id is not connected/i)).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "Core Planner X" } });
    await user.click(screen.getByRole("button", { name: /^Save Agent$/ }));

    expect((await screen.findAllByText("✓ Saved")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Core Planner X" })).toBeInTheDocument();
    expect((screen.getByLabelText("Profile Version") as HTMLInputElement).value).toBe("v13");
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

      if (url === "/im/v1/agents") {
        return new Response(
          JSON.stringify({ items: [{ agent_id: "agent-core-1", display_name: "Core Planner", owner_id: "owner-1", description: "", profile_version: 1, default_model: null, workspace_root: "", workspace_is_default: false }] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url === "/im/v1/agents/agent-core-1/capabilities") {
        return new Response(
          JSON.stringify({
            skills: [],
            tools: [],
            model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }, { name: "kimiCoding:K2.6", provider: "anthropic" }],
            platform_default_model: "codex_oauth:gpt-5.5"
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" }
          }
        );
      }

      if (url === "/im/v1/agents/agent-core-1/config?source=mirror") {
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
            default_model: "codex_oauth:gpt-5.5",
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
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
    await user.click(screen.getByRole("button", { name: /^Save Agent$/ }));

    expect(await screen.findByText(/Display name is required\./i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/im/v1/agents/agent-core-1/config",
      expect.objectContaining({ method: "PATCH" })
    );
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

      if (url === "/im/v1/agents/agent-core-1/capabilities") {
        return new Response(
          JSON.stringify({
            skills: [],
            tools: [],
            model_options: [{ name: "codex_oauth:gpt-5.5", provider: "openai_compat" }, { name: "kimiCoding:K2.6", provider: "anthropic" }],
            platform_default_model: "codex_oauth:gpt-5.5"
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" }
          }
        );
      }

      if (url === "/im/v1/agents/agent-core-1/config" && init?.method === "PATCH") {
        return new Response(JSON.stringify({ detail: "profile_version conflict" }), {
          status: 409,
          headers: { "Content-Type": "application/json" }
        });
      }

      if (url === "/im/v1/agents/agent-core-1/config?source=mirror") {
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
            default_model: "codex_oauth:gpt-5.5",
            workspace_root: "/Users/demo/nano-assistant/workspace/agent-core-1",
            workspace_is_default: true,
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
    fireEvent.change(input, { target: { value: "Core Planner X" } });
    await user.click(screen.getByRole("button", { name: /^Save Agent$/ }));

    expect(await screen.findByText(/409.*profile_version conflict/i)).toBeInTheDocument();
    expect((screen.getByLabelText("Profile Version") as HTMLInputElement).value).toBe("v12");
  });
});
