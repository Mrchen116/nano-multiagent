import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();

globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const sanitizedInit = init ? Object.fromEntries(Object.entries(init).filter(([key]) => key !== "signal")) as RequestInit : init;
  return fetchMock(input, sanitizedInit);
}) as typeof fetch;

afterEach(() => {
  fetchMock.mockReset();
});

describe("agent create page", () => {
  it("creates a new agent and redirects to its detail page", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ node_id: "node-1", owner_id: "owner-1", node_name: "MacBook", status: "online", last_heartbeat_at: "2026-03-13T10:00:00Z", agent_count: 0, version: "1.0.0" }]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        if (input === "/im/v1/agents/agent-new/config" && (!init?.method || init.method === "GET")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                agent_id: "agent-new",
                owner_id: "owner-1",
                display_name: "Agent New",
                description: "runtime-created helper",
                system_prompt: "You are Agent New.",
                skills: ["plan"],
                tool_allowlist: ["read"],
                group_reply_policy: "MENTION",
                default_model: "claude-sonnet-4",
                profile_version: 1,
                bound_nodes: ["node-1"],
                updated_at: "2026-03-13T10:00:00Z"
              }),
              { status: 200, headers: { "Content-Type": "application/json" } }
            )
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" }
          })
        );
      })
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            agent_id: "agent-new",
            owner_id: "owner-1",
            display_name: "Agent New",
            description: "runtime-created helper",
            system_prompt: "You are Agent New.",
            skills: ["plan"],
            tool_allowlist: ["read"],
            group_reply_policy: "MENTION",
            default_model: "claude-sonnet-4",
            profile_version: 1,
            bound_nodes: ["node-1"],
            updated_at: "2026-03-13T10:00:00Z"
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              agent_id: "agent-new",
              owner_id: "owner-1",
              display_name: "Agent New",
              description: "runtime-created helper",
              profile_version: 1,
              default_model: "claude-sonnet-4",
              bound_nodes: ["node-1"],
              updated_at: "2026-03-13T10:00:00Z"
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            agent_id: "agent-new",
            owner_id: "owner-1",
            display_name: "Agent New",
            description: "runtime-created helper",
            system_prompt: "You are Agent New.",
            skills: ["plan"],
            tool_allowlist: ["read"],
            group_reply_policy: "MENTION",
            default_model: "claude-sonnet-4",
            profile_version: 1,
            bound_nodes: ["node-1"],
            updated_at: "2026-03-13T10:00:00Z"
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

    const listRouteRender = renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents"]
    });

    const createEntry = await screen.findByRole("link", { name: "New Agent" });
    expect(createEntry.getAttribute("href")).toBe("/settings/agents/new");
    listRouteRender.unmount();
    const createRouteRender = renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/agents/new"]
    });
    void createRouteRender;
    await user.type(await screen.findByLabelText("Agent ID"), "agent-new");
    await user.type(screen.getByLabelText("Display Name"), "Agent New");
    await user.type(screen.getByLabelText("Description"), "runtime-created helper");
    await user.type(screen.getByLabelText("System Prompt"), "You are Agent New.");
    await user.type(screen.getByLabelText("Skills Allowlist"), "plan");
    await user.type(screen.getByLabelText("Tool Allowlist"), "read");
    await user.selectOptions(screen.getByLabelText("Node"), "node-1");
    await user.type(screen.getByLabelText("Default Model"), "claude-sonnet-4");
    await user.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(await screen.findByText("Agent Detail")).toBeInTheDocument();
    expect(await screen.findByText("Profile Version: 1")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/im/v1/agents", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        agent_id: "agent-new",
        owner_id: "",
        display_name: "Agent New",
        description: "runtime-created helper",
        system_prompt: "You are Agent New.",
        skills: ["plan"],
        tool_allowlist: ["read"],
        group_reply_policy: "MENTION",
        default_model: "claude-sonnet-4",
        node_id: "node-1"
      })
    }));
  });
});
