import { focusManager } from "@tanstack/react-query";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { setLanguage } from "../../../i18n";
import { renderRouter } from "../../../test/render-router";
import type { PolicyProfile } from "../im-settings-api";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function mockPolicies() {
  const state = {
    policy: {
      default_model: "codex_oauth:gpt-5.5",
      max_turn_per_run: 14,
      max_attachment_size_mb: 15,
      retention_days: 30,
      audit_level: "basic",
      rate_limit_per_min: 45,
    } as PolicyProfile,
    failWrite: false,
    failRead: false,
    failCapacity: false,
    reads: 0,
  };
  fetchMock.mockImplementation(async (input, init) => {
    if (input === "/im/v1/policies") {
      if (init?.method === "PATCH") {
        if (state.failWrite) return json({ detail: "unavailable" }, 503);
        state.policy = JSON.parse(String(init.body));
      } else {
        state.reads += 1;
        if (state.failRead) return json({ detail: "unavailable" }, 503);
      }
      return json(state.policy);
    }
    if (input === "/im/v1/attachments/capacity")
      return state.failCapacity
        ? json({}, 503)
        : json({
            service: {
              used_bytes: 100,
              reserved_bytes: 20,
              limit_bytes: 1024,
              full: false,
            },
            owners: [],
          });
    if (input === "/im/v1/nodes") return json([]);
    if (input === "/im/v1/sync") return json({ items: [], max_event_id: 0 });
    if (input === "/im/v1/conversations") return json({ items: [] });
    return json({}, 404);
  });
  return state;
}
function mount() {
  renderRouter({ routes: appRoutes, initialEntries: ["/settings/policies"] });
}
beforeEach(() => setLanguage("en"));
afterEach(() => {
  focusManager.setFocused(undefined);
  fetchMock.mockReset();
});

describe("policies page", () => {
  it("saves the complete policy and distinguishes presets from actual capacity", async () => {
    const state = mockPolicies();
    const user = userEvent.setup();
    mount();
    const model = await screen.findByLabelText("Default Model");
    await user.clear(model);
    await user.type(model, "claude-sonnet-4");
    await user.selectOptions(screen.getByLabelText("Audit Level"), "strict");
    await user.clear(screen.getByLabelText("Max Turn Per Run"));
    await user.type(screen.getByLabelText("Max Turn Per Run"), "24");
    await user.clear(screen.getByLabelText("Rate Limit / Min"));
    await user.type(screen.getByLabelText("Rate Limit / Min"), "88");
    await user.click(screen.getByRole("button", { name: "Save Policies" }));
    await waitFor(() =>
      expect(state.policy).toEqual({
        default_model: "claude-sonnet-4",
        max_turn_per_run: 24,
        max_attachment_size_mb: 15,
        retention_days: 30,
        audit_level: "strict",
        rate_limit_per_min: 88,
      }),
    );
    expect(screen.getByRole("meter")).toHaveAttribute(
      "aria-valuetext",
      "120 B / 1 KiB",
    );
    expect(
      screen.getByRole("button", { name: "Save Policies" }),
    ).toBeDisabled();
  });

  it("retains incomplete and failed drafts while capacity failures stay independent", async () => {
    const state = mockPolicies();
    state.failWrite = true;
    state.failCapacity = true;
    const user = userEvent.setup();
    mount();
    const field = await screen.findByLabelText("Max Turn Per Run");
    const form = screen.getByRole("form", { name: "policies-form" });
    await user.clear(field);
    expect(field).toHaveValue(null);
    expect(
      within(form).getByRole("button", { name: "Save Policies" }),
    ).toBeDisabled();
    await user.type(field, "1.5");
    expect(
      within(form).getByRole("button", { name: "Save Policies" }),
    ).toBeDisabled();
    await user.clear(field);
    await user.type(field, "24");
    await user.click(
      within(form).getByRole("button", { name: "Save Policies" }),
    );
    expect(await within(form).findByRole("alert")).toHaveTextContent(
      /retained/i,
    );
    expect(field).toHaveValue(24);
    expect(
      within(form).getByRole("button", { name: "Save Policies" }),
    ).toBeEnabled();
    await user.click(within(form).getByRole("button", { name: /discard/i }));
    expect(field).toHaveValue(14);
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  });

  it("keeps the policy draft when a background read updates saved values", async () => {
    const state = mockPolicies();
    const user = userEvent.setup();
    mount();
    const model = await screen.findByLabelText("Default Model");
    await user.clear(model);
    await user.type(model, "unfinished-model");
    state.policy = { ...state.policy, default_model: "server-model" };
    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });
    await waitFor(() => expect(state.reads).toBeGreaterThan(1));
    expect(model).toHaveValue("unfinished-model");
    await user.click(screen.getByRole("button", { name: /discard/i }));
    await waitFor(() => expect(model).toHaveValue("server-model"));
  });

  it("retries a policy load failure while actual storage stays available", async () => {
    const state = mockPolicies();
    state.failRead = true;
    mount();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toBeInTheDocument();
    state.failRead = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByLabelText("Default Model")).toHaveValue(
      "codex_oauth:gpt-5.5",
    );
  });
});
