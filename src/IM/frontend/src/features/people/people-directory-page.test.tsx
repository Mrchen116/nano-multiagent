import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { PeopleDirectoryPage } from "./people-directory-page";

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

function renderPeoplePage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/people"]}>
        <Routes>
          <Route path="/people" element={<PeopleDirectoryPage />} />
          <Route path="/chat/:conversationId" element={<div>Opened DM</div>} />
          <Route path="/settings/agents/:agentId" element={<div>Opened Agent Profile</div>} />
          <Route path="/settings/company" element={<div>Company Admin</div>} />
          <Route path="/settings/account" element={<div>Account Settings</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("PeopleDirectoryPage", () => {
  beforeEach(async () => {
    await act(async () => setLanguage("en"));
    useAuthStore.getState().setSession({
      access_token: "token",
      user: {
        id: "u-self",
        username: "alex",
        display_name: "Alex Chen",
        owner_id: "o-self",
        locale: "en",
        default_entry_node_id: null,
        membership_status: "active",
        is_company_admin: true,
        owned_node_ids: [],
        created_at: ""
      }
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useAuthStore.getState().clear();
  });

  it("lists colleagues with @username, public PA chat, specialist Agent profile links, and self badge", async () => {
    const user = userEvent.setup();
    const postBodies: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/im/v1/contacts")) {
          return jsonResponse({
            items: [
              { user_id: "u-self", kind: "human", display_name: "Alex Chen", username: "alex" },
              { user_id: "u-lin", kind: "human", display_name: "Lin Xia", username: "linxia" },
              {
                user_id: "pa-lin",
                kind: "agent",
                role: "personal",
                agent_id: "lin-pa",
                owner_id: "o-lin",
                owner_user_id: "u-lin",
                display_name: "Lin Assistant",
                status: "online"
              },
              {
                user_id: "ag-qa",
                kind: "agent",
                agent_id: "qa-bot",
                owner_id: "o-lin",
                owner_user_id: "u-lin",
                display_name: "QA Inspector",
                status: "online"
              }
            ],
            next_cursor: null
          });
        }
        if (url.endsWith("/im/v1/conversations") && init?.method === "POST") {
          postBodies.push(JSON.parse(String(init.body)));
          return jsonResponse({ id: "dm-1" });
        }
        return new Response(null, { status: 404 });
      })
    );

    renderPeoplePage();
    expect(await screen.findByText("2 members")).toBeVisible();
    expect(screen.getByRole("link", { name: "Manage members" })).toHaveAttribute("href", "/settings/company");

    const selfRow = screen.getByTestId("person-row-u-self");
    expect(within(selfRow).getByText("You")).toBeVisible();
    expect(within(selfRow).getByRole("link", { name: "Your profile" })).toHaveAttribute("href", "/settings/account");
    expect(within(selfRow).queryByRole("button", { name: "Message" })).toBeNull();

    const linRow = screen.getByTestId("person-row-u-lin");
    expect(within(linRow).getByText("@linxia")).toBeVisible();
    expect(within(linRow).getByRole("link", { name: /QA Inspector/ })).toHaveAttribute("href", "/settings/agents/qa-bot");

    await user.type(screen.getByRole("searchbox"), "@linxia");
    expect(screen.queryByTestId("person-row-u-self")).toBeNull();
    expect(screen.getByTestId("person-row-u-lin")).toBeVisible();

    await user.click(within(screen.getByTestId("person-row-u-lin")).getByRole("button", { name: /Lin Assistant/ }));
    expect(await screen.findByText("Opened DM")).toBeVisible();
    expect(postBodies).toEqual([
      {
        type: "direct",
        title: "Lin Assistant",
        participants: [{ type: "user", id: "u-self" }, { type: "agent", id: "lin-pa" }]
      }
    ]);
  });

  it("shows a retryable error state instead of masquerading as empty when contacts fail to load", async () => {
    const user = userEvent.setup();
    let failed = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        if (failed) return new Response("boom", { status: 503 });
        return jsonResponse({
          items: [{ user_id: "u-self", kind: "human", display_name: "Alex Chen", username: "alex" }],
          next_cursor: null
        });
      })
    );

    renderPeoplePage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load teammates right now.");
    expect(screen.queryByTestId("people-personal-space-guide")).toBeNull();
    failed = false;
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("1 members")).toBeVisible();
  });

  it("shows calm team-membership guidance when the account is in personal space only", async () => {
    useAuthStore.getState().setSession({
      access_token: "token",
      user: {
        id: "u-solo",
        username: "solo",
        display_name: "Solo User",
        owner_id: "o-solo",
        locale: "en",
        default_entry_node_id: null,
        membership_status: "none",
        is_company_admin: false,
        owned_node_ids: [],
        created_at: ""
      }
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          items: [{ user_id: "u-solo", kind: "human", display_name: "Solo User", username: "solo" }],
          next_cursor: null
        })
      )
    );

    renderPeoplePage();
    const guide = await screen.findByTestId("people-personal-space-guide");
    expect(within(guide).getByText("You’re in your personal space")).toBeVisible();
    expect(within(guide).getByRole("link", { name: "View team membership" })).toHaveAttribute("href", "/settings/account");
    expect(screen.queryByTestId("person-row-u-solo")).toBeNull();
    expect(screen.queryByText(/Public PA/i)).toBeNull();
    expect(screen.queryByText(/No matching teammates/i)).toBeNull();
  });
});
