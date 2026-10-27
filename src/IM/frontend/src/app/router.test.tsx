import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

const listConversations = vi.fn();

vi.mock("../realtime/user-stream", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../realtime/user-stream")>();
  return { ...actual, subscribeUserStream: vi.fn(() => () => undefined) };
});

vi.mock("../features/chat/chat-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../features/chat/chat-api")>();
  return {
    ...actual,
    listConversations: () => listConversations()
  };
});

import { appRoutes } from "./router";
import { renderRouter } from "../test/render-router";

describe("app routes", () => {
  beforeEach(() => {
    const nodes = ["node-1", "node-2"].map(node_id => ({
      node_id, owner_id: "user-1", node_name: node_id === "node-2" ? "Route Mini" : "Default Laptop",
      status: "online", last_heartbeat_at: "2026-10-28T00:00:00Z", agent_count: 1, version: "test"
    }));
    vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
      const url = String(input);
      if (url.includes("/im/v1/contacts?")) return Response.json({items: [{
        user_id: "agent-user", kind: "agent", agent_id: "route-agent", owner_id: "user-1",
        display_name: "Route Planner", node_name: "Route Mini", status: "online", work_mode: "single_thread"
      }], next_cursor: null});
      if (url.endsWith("/im/v1/nodes")) return Response.json(nodes);
      if (url.endsWith("/im/v1/nodes/node-2/capabilities")) return Response.json({
        node_id: "node-2", node_name: "Route Mini", node_status: "online", skills: [], tools: [], features: [],
        model_options: [{name: "fixture-model", provider: "fixture"}], platform_default_model: "fixture-model"
      });
      if (url.includes("/im/v1/nodes/node-2/approval?")) return Response.json({inherited_approval_rules: "codex"});
      if (url.endsWith("/im/v1/me/personal-agent")) return Response.json({binding: null, creation: null});
      return new Response(null, {status: 404});
    });
    listConversations.mockResolvedValue([
      {
        id: "conv-1",
        title: "You & Teammate",
        participants: [
          { type: "user", id: "user-1", display_name: "You" },
          { type: "user", id: "user-2", display_name: "Teammate" }
        ],
        participant_ids: ["user-1", "user-2"],
        type: "direct",
        direct_kind: "user-user",
        owner_id: "user-1",
        creator_id: "user-1",
        is_pinned: false,
        is_muted: false,
        last_message_preview: "",
        last_message_at: null,
        unread_count: 0,
        created_at: "2026-01-01T00:00:00Z"
      }
    ]);
  });

  afterEach(() => vi.restoreAllMocks());

  it("opens the chat workspace from the authenticated root entry", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/"] });

    expect((await screen.findAllByText("You & Teammate")).length).toBeGreaterThan(0);
  });

  it("renders the bind confirmation route", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/bind/confirm#token=test-token"] });

    expect(await screen.findByRole("heading", { name: "Connect your computer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect this computer" })).toBeDisabled();
  });

  it("renders the settings agents entry", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });
    const agent = await screen.findByRole("button", {name: "Route Planner"});
    expect(within(agent).getByText("Route Mini")).toBeVisible();
    expect(screen.getByRole("searchbox")).toBeEnabled();
  });

  it("renders the node-scoped agent creation route", async () => {
    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/nodes/node-2/agents/new"]
    });
    const form = within(await screen.findByTestId("agent-create"));
    expect(form.getByRole("heading", {name: "New agent"})).toBeVisible();
    expect(form.getByRole("textbox", {name: /Agent ID/})).toBeEnabled();
    expect(form.getByRole("textbox", {name: /Display name/i})).toBeEnabled();
    expect(form.getByRole("combobox", {name: /Owning node/i})).toHaveValue("node-2");
    expect(screen.queryByText("Could not load agents.")).not.toBeInTheDocument();
  });
});
