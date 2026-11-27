import "fake-indexeddb/auto";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../app/router";
import { composerStoreFor, resetComposerStores, writeComposerSnapshot, EMPTY_COMPOSER_SNAPSHOT } from "../features/chat/components/composer-draft-store";
import { listSendAttempts, prepareSendAttempt } from "../features/chat/components/send-attempt-store";
import { isNotificationSupported, showAgentNotification } from "../features/notifications/notification-api";
import { bindingTargetKey } from "../features/onboarding/binding-target";
import { setLanguage } from "../i18n";
import { renderRouter } from "../test/render-router";
import { setDesktopBootContextForTest } from "./desktop-context";
import { DesktopDualInstallPicker } from "./desktop-install-picker";

describe("Crewden Desktop session isolation, onboarding picker, and foreign-owner guard", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setLanguage("zh");
    resetComposerStores();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    setDesktopBootContextForTest(undefined);
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("isolates IndexedDB send attempts, composer drafts, and binding targets by imOrigin in Desktop mode", async () => {
    setDesktopBootContextForTest({
      imOrigin: "https://im-alpha.example",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    await prepareSendAttempt(
      "same-user",
      "conv-1",
      { ...EMPTY_COMPOSER_SNAPSHOT, draft: "alpha message", revision: "rev-alpha" },
      { text: "alpha message", attachments: [] },
    );
    writeComposerSnapshot(composerStoreFor("same-user"), "conv-1", {
      ...EMPTY_COMPOSER_SNAPSHOT,
      draft: "alpha draft",
    });
    expect(bindingTargetKey("same-user")).toBe("nano-onboarding-binding:same-user::https://im-alpha.example");

    // Switch Desktop target server to im-beta while keeping the same userId
    setDesktopBootContextForTest({
      imOrigin: "https://im-beta.example",
      contextEpoch: 2,
      platform: "darwin-arm64",
    });

    const betaAttempts = await listSendAttempts("same-user", "conv-1");
    expect(betaAttempts).toHaveLength(0);
    expect(composerStoreFor("same-user").get("conv-1")).toBeUndefined();
    expect(bindingTargetKey("same-user")).toBe("nano-onboarding-binding:same-user::https://im-beta.example");

    // Switch back to im-alpha: pending send attempt is preserved intact
    setDesktopBootContextForTest({
      imOrigin: "https://im-alpha.example",
      contextEpoch: 3,
      platform: "darwin-arm64",
    });
    const alphaAttempts = await listSendAttempts("same-user", "conv-1");
    expect(alphaAttempts).toHaveLength(1);
    expect(alphaAttempts[0].text).toBe("alpha message");
  });

  it("suppresses WebView Notification constructor in Desktop mode so the Rust daemon is sole owner", () => {
    const FakeNotification = Object.assign(
      vi.fn(function () {
        return { close: vi.fn(), onclick: null };
      }),
      { permission: "granted" as NotificationPermission, requestPermission: vi.fn() },
    );
    vi.stubGlobal("Notification", FakeNotification);

    setDesktopBootContextForTest(null);
    expect(isNotificationSupported()).toBe(true);

    setDesktopBootContextForTest({
      imOrigin: "https://im.example",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });
    expect(isNotificationSupported()).toBe(false);
    expect(showAgentNotification({ title: "Hi", body: "Body", onClick: () => {} })).toBeNull();
    expect(FakeNotification).not.toHaveBeenCalled();
  });

  it("renders side-by-side Desktop and lightweight node entries with Intel Mac guidance and unpublished fallback", async () => {
    const user = userEvent.setup();
    const recheck = vi.fn();
    render(
      <DesktopDualInstallPicker
        install={{
          available: true,
          origin: "https://im.example",
          command: "curl -fsSL 'https://im.example/install.sh' -o /tmp/nano-install.sh && bash /tmp/nano-install.sh",
          script_url: "https://im.example/install.sh",
          windows_x64: {
            download_url: "https://im.example/Crewden-Setup-x64.exe",
            connect_url: "crewden://connect?origin=https%3A%2F%2Fim.example",
          },
          desktop_darwin_arm64: {
            download_url: "https://im.example/Crewden-Desktop-arm64.dmg",
            connect_url: "crewden-desktop://connect?origin=https%3A%2F%2Fim.example",
            version: "1.0.0",
          },
          desktop_win32_x64: null,
        }}
        onRecheck={recheck}
        renderUnixHeadless={() => <div data-testid="unix-headless-slot">Unix CLI command</div>}
      />,
    );

    // Select macOS explicitly so the test is OS-independent on Linux CI (`ubuntu-latest`) as well as macOS.
    await user.click(screen.getByRole("button", { name: "macOS" }));
    expect(screen.getByText("下载完整 Desktop 客户端")).toBeInTheDocument();
    expect(screen.getByText("仅装轻量后台节点")).toBeInTheDocument();
    expect(screen.getByText(/Intel 芯片 Mac 请选择「仅装轻量后台节点」/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /下载 Crewden Desktop \(Apple Silicon\)/ })).toHaveAttribute(
      "href",
      "https://im.example/Crewden-Desktop-arm64.dmg",
    );

    // Switch OS to Windows where desktop_win32_x64 is unpublished (null)
    await user.click(screen.getByRole("button", { name: /Windows 10 \/ 11/ }));
    expect(screen.getByText(/暂未发布该系统的 Desktop 安装包/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "改用轻量后台节点" }));
    expect(screen.getByRole("link", { name: /Windows 安装包|Download Windows installer/i })).toHaveAttribute(
      "href",
      "https://im.example/Crewden-Setup-x64.exe",
    );
  });

  it("protects foreign-owner local nodes until explicit two-step transfer confirmation", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.example",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    const connectBodies: unknown[] = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/desktop/v1/local-node/inspect")) {
        return new Response(
          JSON.stringify({ ownership: "foreign_owner", node_name: "Air-Studio" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/desktop/v1/local-node/connect") {
        connectBodies.push(JSON.parse(String(init?.body ?? "{}")));
        return new Response(
          JSON.stringify({ ok: true, node_id: "node-1", node_name: "Air-Studio", ready: true, ownership: "managed_online" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ items: [], max_event_id: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const foreignCard = await screen.findByTestId("desktop-bind-foreign");
    expect(within(foreignCard).getByText(/这台电脑已绑定其他账号/)).toBeInTheDocument();
    expect(connectBodies).toHaveLength(0);

    // Step 1 opens explicit second-step confirmation without calling connect yet
    await user.click(within(foreignCard).getByRole("button", { name: "确认整机转移…" }));
    expect(connectBodies).toHaveLength(0);

    // Step 2 sends confirm_transfer: true
    await user.click(within(foreignCard).getByRole("button", { name: "确认转移并接管" }));
    await waitFor(() => expect(connectBodies).toEqual([{ confirm_transfer: true }]));
  });

  it("guides Daily Chrome extension install, auto-opens token page once installed, and pairs with pasted line", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      "nano_im_auth_v1",
      JSON.stringify({
        accessToken: "tok-alice",
        user: { id: "owner-alice", username: "alice", display_name: "Alice" },
      }),
    );
    setDesktopBootContextForTest({
      imOrigin: "https://im.example",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    let extensionInstalled = false;
    let pairedState: "not_paired" | "paired" = "not_paired";
    const browserActions: Record<string, unknown>[] = [];

    const makeBrowserStatus = () => ({
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
      if (url.startsWith("/desktop/v1/local-node/inspect")) {
        return new Response(
          JSON.stringify({
            ownership: "managed_online",
            node_id: "node-1",
            node_name: "Air-Studio",
            owner_id: "owner-alice",
            desktop_managed: true,
            running: true,
            ready: true,
            connected: true,
            autostart: true,
            worker_runtime: "dsh",
            workers: [],
            browser: makeBrowserStatus(),
            proxy: { enabled: false, url: "", no_proxy: "localhost,127.0.0.1,::1" },
            tool_approval_model: null,
            registered_models: [],
            environment: [],
            agents: [],
            logs: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/desktop/v1/local-node/browser") {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        browserActions.push(body);
        if (body.action === "open-guide") {
          const opened = body.target === "token" || extensionInstalled ? "token" : "store";
          if (opened === "store") {
            // Simulate user installing the extension right after store opens so next poll sees it
            extensionInstalled = true;
          }
          return new Response(JSON.stringify({ browser: makeBrowserStatus(), opened }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (body.action === "status") {
          return new Response(JSON.stringify({ browser: makeBrowserStatus() }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (body.action === "pair") {
          pairedState = "paired";
          return new Response(JSON.stringify({ browser: makeBrowserStatus() }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (body.action === "disconnect") {
          pairedState = "not_paired";
          return new Response(JSON.stringify({ browser: makeBrowserStatus() }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ items: [], max_event_id: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const strip = await screen.findByTestId("desktop-browser-strip");
    expect(within(strip).getByText("日常 Chrome 浏览器")).toBeInTheDocument();
    expect(within(strip).getByText("未配对")).toBeInTheDocument();

    // Open inline guided setup
    await user.click(within(strip).getByRole("button", { name: "连接 Chrome…" }));
    const setup = screen.getByTestId("desktop-browser-setup");

    // Step 1: click install -> opens store -> poll detects install -> auto-opens token page!
    await user.click(within(setup).getByRole("button", { name: "1. 去 Chrome 安装扩展" }));
    await waitFor(
      () =>
        expect(browserActions).toContainEqual({
          action: "open-guide",
          profile: "Default",
          target: "token",
        }),
      { timeout: 4000 },
    );
    expect(within(setup).getByText("✓ 已安装 Playwright 扩展")).toBeInTheDocument();

    // Step 2: user pastes full PLAYWRIGHT_MCP_EXTENSION_TOKEN=... line and saves
    const tokenInput = within(setup).getByLabelText("Playwright 扩展 Token");
    await user.type(tokenInput, "PLAYWRIGHT_MCP_EXTENSION_TOKEN=pw_token_1234567890abcdefghij");
    await user.click(within(setup).getByRole("button", { name: "保存配对" }));

    await waitFor(() => expect(within(strip).getByText("已配对 · Default")).toBeInTheDocument());
    expect(screen.queryByTestId("desktop-browser-setup")).not.toBeInTheDocument();

    // Disconnect returns to unpaired
    await user.click(within(strip).getByRole("button", { name: "断开" }));
    await waitFor(() => expect(within(strip).getByText("未配对")).toBeInTheDocument());
  });
});
