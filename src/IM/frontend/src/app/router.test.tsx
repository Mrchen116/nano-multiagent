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
import { setLanguage } from "../i18n";
import { renderRouter, TEST_AUTH_USER } from "../test/render-router";

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: width });
  window.dispatchEvent(new Event("resize"));
}

describe("app routes", () => {
  beforeEach(() => {
    setLanguage("en");
    setViewportWidth(1280);
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
      if (url.endsWith("/im/v1/me")) return Response.json({
        ...TEST_AUTH_USER,
        user_id: TEST_AUTH_USER.id,
        avatar_version: null
      });
      if (url.endsWith("/im/v1/policies")) return Response.json({
        default_model: "fixture-model",
        max_turn_per_run: 12,
        max_attachment_size_mb: 15,
        retention_days: 30,
        audit_level: "basic",
        rate_limit_per_min: 45
      });
      if (url.includes("/im/v1/attachments/capacity")) return Response.json({
        service: { used_bytes: 0, reserved_bytes: 0, limit_bytes: 1024, full: false },
        owners: []
      });
      if (url.endsWith("/im/v1/onboarding")) return Response.json({
        nodes: [],
        agents: [],
        install: { available: false, origin: "", command: "", script_url: "" }
      });
      if (url.includes("/im/v1/company/members")) return Response.json({ members: [], next_cursor: null });
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

  it("redirects desktop /me to /settings/account and hides mobile /me back links across desktop settings pages", async () => {
    setViewportWidth(1280);
    const meRender = renderRouter({ routes: appRoutes, initialEntries: ["/me"] });
    expect(await screen.findByLabelText(/display name/i)).toBeInTheDocument();
    expect(screen.queryByTestId("me-page")).not.toBeInTheDocument();
    expect(meRender.container.querySelector('a[href="/me"]')).toBeNull();
    meRender.unmount();

    for (const path of ["/settings/account", "/settings/nodes", "/settings/policies", "/settings/models", "/settings/company"]) {
      const view = renderRouter({ routes: appRoutes, initialEntries: [path] });
      await screen.findByRole("navigation", { name: "primary" });
      await screen.findByRole("heading", { level: 1 });
      expect(view.container.querySelector('a[href="/me"]')).toBeNull();
      view.unmount();
    }
  });

  it("retains /me and renders localized ‹ Me back links on narrow mobile settings subpages", async () => {
    setViewportWidth(390);
    const meView = renderRouter({ routes: appRoutes, initialEntries: ["/me"] });
    expect(await screen.findByTestId("me-page")).toBeInTheDocument();
    meView.unmount();

    for (const [path, testId] of [
      ["/settings/account", "account-page-back"],
      ["/settings/nodes", "nodes-page-back"],
      ["/settings/policies", "policies-page-back"],
      ["/settings/models", "models-page-back"]
    ] as const) {
      const view = renderRouter({ routes: appRoutes, initialEntries: [path] });
      const backLink = await screen.findByTestId(testId);
      expect(backLink).toHaveAttribute("href", "/me");
      expect(backLink).toHaveTextContent(/Me/);
      view.unmount();
    }
  });
});
