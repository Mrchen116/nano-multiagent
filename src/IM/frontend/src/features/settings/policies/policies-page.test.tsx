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

describe("policies page", () => {
  it("loads and saves policies through IM APIs", async () => {
    const user = userEvent.setup();
    let policies = {
      default_model: "codex_oauth:gpt-5.5",
      max_turn_per_run: 14,
      max_attachment_size_mb: 15,
      retention_days: 30,
      audit_level: "basic",
      rate_limit_per_min: 45
    };

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/policies" && init?.method === "PATCH") {
        policies = JSON.parse(String(init.body)) as typeof policies;
        return new Response(JSON.stringify(policies), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url === "/im/v1/policies") {
        return new Response(JSON.stringify(policies), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({
      routes: appRoutes,
      initialEntries: ["/settings/policies"]
    });

    await user.clear(await screen.findByLabelText("Default Model"));
    await user.type(screen.getByLabelText("Default Model"), "claude-sonnet-4");
    await user.selectOptions(screen.getByLabelText("Audit Level"), "strict");
    await user.clear(screen.getByLabelText("Max Turn Per Run"));
    await user.type(screen.getByLabelText("Max Turn Per Run"), "24");
    await user.clear(screen.getByLabelText("Rate Limit / Min"));
    await user.type(screen.getByLabelText("Rate Limit / Min"), "88");
    await user.click(screen.getByRole("button", { name: "Save Policies" }));

    expect(await screen.findByDisplayValue("claude-sonnet-4")).toBeInTheDocument();
    expect(screen.getByDisplayValue("24")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/im/v1/policies", expect.any(Object));
    expect(fetchMock).toHaveBeenCalledWith(
      "/im/v1/policies",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          default_model: "claude-sonnet-4",
          max_turn_per_run: 24,
          max_attachment_size_mb: 15,
          retention_days: 30,
          audit_level: "strict",
          rate_limit_per_min: 88
        })
      })
    );
  });
});
