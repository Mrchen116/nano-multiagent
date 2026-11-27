import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { setDesktopBootContextForTest } from "../../../desktop/desktop-context";
import { setLanguage } from "../../../i18n";
import { renderRouter } from "../../../test/render-router";
import { AttachmentLink } from "../../chat/attachments/attachment-link";
import { BrowserPairingSection } from "./browser-pairing-section";

describe("Web IM Daily Chrome pairing across computer drawer, agent tool callout, and chat deep-link", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setLanguage("zh");
    setDesktopBootContextForTest(null);
    localStorage.clear();
    sessionStorage.clear();
    setLanguage("zh");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setDesktopBootContextForTest(undefined);
    vi.restoreAllMocks();
  });

  it("auto-opens the online computer drawer via /settings/nodes?pair_browser=1 and guides Web Chrome pairing", async () => {
    const user = userEvent.setup();
    let extensionInstalled = false;
    let pairedState: "not_paired" | "paired" = "not_paired";
    const browserCalls: Record<string, unknown>[] = [];

    const makeBrowser = () => ({
      supported: true,
      state: pairedState,
      chrome_installed: true,
      chrome_running: true,
      chrome_version_ok: true,
      ...(pairedState === "paired" ? { paired_profile: "Default" } : {}),
      selected_profile: "Default",
      extension_installed: extensionInstalled,
      profiles: [{ profile: "Default", extension_installed: extensionInstalled }],
    });

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/im/v1/nodes")) {
        return new Response(
          JSON.stringify([
            {
              node_id: "mac-studio",
              owner_id: "user-1",
              node_name: "Mac-Studio",
              alias: "Mac-Studio",
              status: "online",
              last_heartbeat_at: "2026-11-27T02:00:00Z",
              agent_count: 1,
              version: "0.4.2",
              relay_enabled: true,
              reporting_enabled: true,
              last_error: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/im/v1/onboarding")) {
        return new Response(
          JSON.stringify({ nodes: [], agents: [], install: { available: false, origin: "", command: "", script_url: "" } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/im/v1/nodes/mac-studio/browser")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        browserCalls.push(body);
        if (body.action === "open-guide") {
          const opened = body.target === "token" || extensionInstalled ? "token" : "store";
          if (opened === "store") {
            extensionInstalled = true;
          }
          return new Response(JSON.stringify({ browser: makeBrowser(), opened }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (body.action === "pair") {
          pairedState = "paired";
        }
        return new Response(JSON.stringify({ browser: makeBrowser() }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ items: [], max_event_id: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes?pair_browser=1"] });

    // Deep-link automatically opens Mac-Studio's drawer with expanded browser setup!
    const drawerSetup = await screen.findByTestId("node-drawer-browser-setup");
    expect(within(drawerSetup).getByText(/在「Mac-Studio」的日常 Chrome 中安装官方 Playwright 扩展/)).toBeInTheDocument();

    await user.click(within(drawerSetup).getByRole("button", { name: "1. 去 Mac-Studio 安装扩展" }));
    await waitFor(
      () =>
        expect(browserCalls).toContainEqual({
          action: "open-guide",
          profile: "Default",
          target: "token",
        }),
      { timeout: 4000 },
    );

    const tokenInput = within(drawerSetup).getByLabelText("Playwright 扩展 Token");
    await user.type(tokenInput, "PLAYWRIGHT_MCP_EXTENSION_TOKEN=pw_web_token_1234567890abcdef");
    await user.click(within(drawerSetup).getByRole("button", { name: "保存配对" }));

    const drawerCard = await screen.findByTestId("node-drawer-browser-pairing");
    await waitFor(() => expect(within(drawerCard).getByText("已配对 · Default")).toBeInTheDocument());
  });

  it("pairs inside an outer Agent form on Enter without triggering outer form submission, and routes /settings/ chat links in-app", async () => {
    const user = userEvent.setup();
    const outerSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    let paired = false;

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/im/v1/nodes/node-1/browser")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        if (body.action === "pair") paired = true;
        return new Response(
          JSON.stringify({
            browser: {
              supported: true,
              state: paired ? "paired" : "not_paired",
              chrome_installed: true,
              chrome_running: true,
              chrome_version_ok: true,
              ...(paired ? { paired_profile: "Default" } : {}),
              selected_profile: "Default",
              extension_installed: true,
              profiles: [{ profile: "Default", extension_installed: true }],
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response("{}", { status: 200 });
    }) as typeof fetch;

    function LocationReadout() {
      const loc = useLocation();
      return <span data-testid="loc">{loc.pathname + loc.search}</span>;
    }

    const router = createMemoryRouter(
      [
        {
          path: "/chat",
          element: (
            <div>
              <form onSubmit={outerSubmit}>
                <BrowserPairingSection variant="agent-callout" nodeId="node-1" computerName="MacBook" online />
              </form>
              <AttachmentLink href="/settings/nodes?pair_browser=1">连接日常 Chrome</AttachmentLink>
              <LocationReadout />
            </div>
          ),
        },
        { path: "/settings/nodes", element: <LocationReadout /> },
      ],
      { initialEntries: ["/chat"] },
    );

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    const callout = await screen.findByTestId("agent-computer-use-browser-callout");
    expect(within(callout).getByText(/尚未连接日常 Chrome/)).toBeInTheDocument();

    await user.click(within(callout).getByRole("button", { name: "连接 Chrome…" }));
    const setup = screen.getByTestId("agent-browser-setup");
    const input = within(setup).getByLabelText("Playwright 扩展 Token");
    await user.type(input, "pw_agent_token_1234567890abcdef");
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => expect(within(callout).getByText("已配对 · Default")).toBeInTheDocument());
    expect(outerSubmit).not.toHaveBeenCalled();

    // Clicking /settings/nodes?pair_browser=1 in chat navigates in-place via SPA Router
    await user.click(screen.getByRole("link", { name: "连接日常 Chrome" }));
    expect(screen.getByTestId("loc")).toHaveTextContent("/settings/nodes?pair_browser=1");
  });
});
