import "fake-indexeddb/auto";
import userEvent from "@testing-library/user-event";
import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../app/router";
import { resetComposerStores } from "../features/chat/components/composer-draft-store";
import { MePage } from "../features/me/me-page";
import { setLanguage } from "../i18n";
import { renderRouter } from "../test/render-router";
import { setDesktopBootContextForTest } from "./desktop-context";
import { DesktopNarrowUpdateBanner } from "./desktop-update-pill";
import { resetDesktopAttentionReporterForTest } from "./use-desktop-unsaved-form";
import { setDesktopUserMenuOpen } from "./use-desktop-updater";
import { makeSnapshot } from "./desktop-updater-test-fixture";

describe("Desktop update entry points", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setLanguage("zh");
    setDesktopUserMenuOpen(false);
    resetDesktopAttentionReporterForTest();
    resetComposerStores();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    setDesktopUserMenuOpen(false);
    setDesktopBootContextForTest(undefined);
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("renders narrow (<768px) banner on /chat, hides duplicate banner on /me, and supports manual check & auto-update toggle on MePage", async () => {
    vi.stubGlobal("innerWidth", 420);
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "http://192.168.1.25:8080",
      contextEpoch: 1,
      platform: "win32-x64",
    });

    let currentSnap = makeSnapshot({
      platform: "win32-x64",
      phase: "ready_to_switch",
      mode: "hot_bundle",
      target: { version: "1.4.0" },
    });
    const prefPayloads: unknown[] = [];

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/desktop/v1/updater") {
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/check" && init?.method === "POST") {
        currentSnap = makeSnapshot({
          platform: "win32-x64",
          phase: "up_to_date",
          mode: null,
        });
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/preferences" && init?.method === "PUT") {
        const parsed = JSON.parse(String(init.body ?? "{}")) as { auto_update: boolean };
        prefPayloads.push(parsed);
        currentSnap = { ...currentSnap, auto_update: parsed.auto_update };
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.startsWith("/desktop/v1/local-node/inspect")) {
        return new Response(JSON.stringify({ ownership: "unbound" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }) as typeof fetch;

    const { unmount } = renderRouter({
      routes: [{ path: "/chat", element: <DesktopNarrowUpdateBanner /> }],
      initialEntries: ["/chat"],
    });
    expect(await screen.findByTestId("desktop-narrow-ready")).toHaveTextContent(
      "新版 v1.4.0 已备好",
    );
    unmount();

    currentSnap = makeSnapshot({ platform: "win32-x64", phase: "idle" });
    renderRouter({
      routes: [
        {
          path: "/me",
          element: (
            <div>
              <DesktopNarrowUpdateBanner />
              <MePage />
            </div>
          ),
        },
      ],
      initialEntries: ["/me"],
    });

    expect(screen.queryByTestId("desktop-narrow-ready")).not.toBeInTheDocument();
    const meBox = await screen.findByTestId("me-page-update-box");
    await user.click(within(meBox).getByTestId("me-page-update-box-check"));
    await waitFor(() =>
      expect(within(meBox).getByText(/已是最新版本 ✓/)).toBeInTheDocument(),
    );

    const toggle = within(meBox).getByTestId("me-page-update-box-auto-switch");
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await user.click(toggle);
    await waitFor(() => expect(prefPayloads).toEqual([{ auto_update: false }]));
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("renders DesktopClientUpdateCard on /settings/nodes for both unbound chat-only clients and bound nodes needing recovery", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    let inspectPayload: Record<string, unknown> = { ownership: "unbound" };
    let nodesPayload: unknown[] = [];
    const controlCalls: unknown[] = [];

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/desktop/v1/updater") {
        return new Response(
          JSON.stringify(
            makeSnapshot({
              phase: "available",
              mode: "hot_bundle",
              auto_update: false,
              target: { version: "1.4.0", release_notes: "未绑定节点也能直接更新桌面端" },
            }),
          ),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.startsWith("/desktop/v1/local-node/inspect")) {
        return new Response(JSON.stringify(inspectPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/local-node/lifecycle" && init?.method === "POST") {
        controlCalls.push(JSON.parse(String(init.body ?? "{}")));
        return new Response(JSON.stringify(inspectPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify(nodesPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ items: [], max_event_id: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const { unmount } = renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    // Unbound pure-chat Desktop still renders top DesktopClientUpdateCard above bind onboarding card!
    const clientCard = await screen.findByTestId("desktop-client-update-card");
    expect(within(clientCard).getByText("Crewden 桌面端")).toBeInTheDocument();
    expect(within(clientCard).getByText("✨ 发现新版本 v1.4.0")).toBeInTheDocument();
    expect(within(clientCard).getByTestId("desktop-client-apply-btn")).toHaveTextContent("立即更新");
    expect(await screen.findByTestId("desktop-bind-fresh")).toBeInTheDocument();
    unmount();

    // Now test bound local node with remote relay_gated recovery_required
    inspectPayload = {
      ownership: "managed_stopped",
      node_id: "node-1",
      node_name: "MacBook-Pro",
      owner_id: "user-1",
      version: "1.3.2",
      desktop_managed: true,
      running: false,
      ready: false,
      connected: false,
    };
    nodesPayload = [
      {
        node_id: "node-1",
        owner_id: "user-1",
        node_name: "MacBook-Pro",
        status: "offline",
        last_heartbeat_at: "",
        agent_count: 1,
        version: "1.3.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: null,
        update: {
          installation: "managed",
          current: { version: "1.3.2", platform: "desktop-darwin-arm64" },
          target: { version: "1.4.0", sha256: "a".repeat(64) },
          available: true,
          reason: "available",
          operation: {
            id: "op-1",
            state: "interrupted",
            cancel_requested: false,
            relay_gated: true,
            request_id: "req-1",
          },
          install_command: "",
        },
      },
    ];

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });
    const recoveryCard = await screen.findByTestId("desktop-client-update-card");
    const recoverBtn = await within(recoveryCard).findByTestId("desktop-client-recover-btn");
    expect(within(recoveryCard).getByText("需要重启恢复")).toBeInTheDocument();
    await user.click(recoverBtn);
    await waitFor(() => expect(controlCalls).toEqual([{ action: "restart" }]));
  });
});
