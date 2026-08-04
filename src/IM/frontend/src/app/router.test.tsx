import { screen } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

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

  it("opens the chat workspace from the authenticated root entry", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/"] });

    expect((await screen.findAllByText("You & Teammate")).length).toBeGreaterThan(0);
  });

  it("renders the bind confirmation route", async () => {
    renderRouter({ routes: appRoutes, initialEntries: ["/bind/confirm?token=test-token"] });

    expect(await screen.findByText("Bind this Gateway")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue to chat" })).toBeEnabled();
  });

  it("renders the settings agents entry", async () => {
    const { container } = renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    // "Agents" appears multiple times (shell nav + page title), use getAllByText
    const agentsTexts = await screen.findAllByText("Agents");
    expect(agentsTexts.length).toBeGreaterThanOrEqual(1);
    // M19/R11-2: Settings 二级 sub-nav 已移除 — 每子页直渲。
    expect(container.querySelector('nav[aria-label="Settings Sections"]')).toBeNull();
  });

  it("renders the node-scoped agent creation route", async () => {
    const { container } = renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/nodes/node-1/agents/new"]
    });

    expect(await screen.findByText(/Could not load agents\.|New agent/i)).toBeInTheDocument();
    expect(container.querySelector('nav[aria-label="Settings Sections"]')).toBeNull();
  });
});
