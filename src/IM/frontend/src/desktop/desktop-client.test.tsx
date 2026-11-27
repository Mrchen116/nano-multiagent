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
import { classifyDesktopImOrigin, setDesktopBootContextForTest } from "./desktop-context";
import { DesktopDualInstallPicker } from "./desktop-install-picker";
import { DesktopServerBar } from "./desktop-server-bar";
import { DesktopServerSwitchModal } from "./desktop-server-switch-modal";
import { ProductHeader } from "../features/home/product-header";

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

  it("enforces strict HTTPS vs private-LAN HTTP classification and in-place DesktopServerBar editing", async () => {
    expect(classifyDesktopImOrigin("https://im.crewden.work").kind).toBe("https");
    expect(classifyDesktopImOrigin("http://im.crewden.work").kind).toBe("rejected_public_http");
    expect(classifyDesktopImOrigin("http://crewden.work").kind).toBe("rejected_public_http");
    expect(classifyDesktopImOrigin("http://10.evil.com").kind).toBe("rejected_public_http");
    expect(classifyDesktopImOrigin("http://100.64.0.1:8080").kind).toBe("rejected_public_http");
    expect(classifyDesktopImOrigin("http://127.0.0.1:8080").kind).toBe("loopback_http");
    expect(classifyDesktopImOrigin("http://192.168.1.25:8080").kind).toBe("private_http");
    expect(classifyDesktopImOrigin("http://crewden-box.local:8080").kind).toBe("private_http");

    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "http://192.168.1.25:8080",
      contextEpoch: 1,
      platform: "win32-x64",
    });
    expect(document.documentElement.dataset.crewdenDesktop).toBe("true");

    render(<DesktopServerBar />);
    expect(screen.getByTestId("desktop-private-http-badge")).toHaveTextContent("内网 HTTP");

    // Clicking "切换服务" replaces the bar in place with Cancel + Save & switch
    await user.click(screen.getByRole("button", { name: "切换服务" }));
    expect(screen.queryByTestId("desktop-server-bar")).not.toBeInTheDocument();
    expect(screen.getByTestId("desktop-server-editor")).toBeInTheDocument();
    expect(screen.getByTestId("desktop-private-http-hint")).toBeInTheDocument();

    // Public/official HTTP is blocked inline without calling switch
    const input = screen.getByLabelText("IM 服务地址");
    await user.clear(input);
    await user.type(input, "http://im.crewden.work");
    await user.click(screen.getByRole("button", { name: "保存切换" }));
    expect(screen.getByRole("alert")).toHaveTextContent("https://");

    // Cancel restores the compact bar
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByTestId("desktop-server-bar")).toBeInTheDocument();
  });

  it("renders cross-origin server switch confirmation with cleartext warning and blocks public HTTP deep links", async () => {
    const user = userEvent.setup();
    let dismissed = 0;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/desktop/v1/context") {
        return new Response(
          JSON.stringify({
            im_origin: "https://im.crewden.work",
            context_epoch: 1,
            platform: "win32-x64",
            seed_ready: true,
            pending_server_switch: {
              target_origin: "http://10.0.0.18:8080",
              is_cleartext_http: true,
            },
            deep_link_error: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/desktop/v1/server/pending/dismiss" && init?.method === "POST") {
        dismissed += 1;
        return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("{}", { status: 200 });
    }) as typeof fetch;

    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "win32-x64",
      pendingServerSwitch: {
        target_origin: "http://10.0.0.18:8080",
        is_cleartext_http: true,
      },
    });

    const { unmount } = render(<DesktopServerSwitchModal />);
    expect(await screen.findByTestId("desktop-server-switch-modal")).toBeInTheDocument();
    expect(screen.getByTestId("desktop-cleartext-http-warning")).toBeInTheDocument();
    expect(screen.getByText("http://10.0.0.18:8080")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "保留原服务" }));
    await waitFor(() => expect(dismissed).toBe(1));
    expect(screen.queryByTestId("desktop-server-switch-modal")).not.toBeInTheDocument();
    unmount();

    // Now test blocked public HTTP deep link alert modal
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/desktop/v1/context") {
        return new Response(
          JSON.stringify({
            im_origin: "https://im.crewden.work",
            context_epoch: 1,
            platform: "win32-x64",
            seed_ready: true,
            pending_server_switch: null,
            deep_link_error: "官方与公网 IM 服务必须使用 https:// 加密连接",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }) as typeof fetch;

    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "win32-x64",
      deepLinkError: "官方与公网 IM 服务必须使用 https:// 加密连接",
    });

    render(<DesktopServerSwitchModal />);
    const errModal = await screen.findByTestId("desktop-deep-link-error-modal");
    expect(within(errModal).getByText(/已拦截不安全的明文连接请求/)).toBeInTheDocument();
    expect(within(errModal).getByText("https://im.crewden.work")).toBeInTheDocument();
  });

  it("keeps ProductHeader brand navigation inside the app (/login or /chat) in Desktop mode", () => {
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "win32-x64",
    });
    renderRouter({
      routes: [{ path: "/login", element: <ProductHeader page="login" /> }],
      initialEntries: ["/login"],
      auth: null,
    });
    const brandLink = screen.getByRole("link", { name: /Crewden/i });
    expect(brandLink).toHaveAttribute("href", "/login");
  });
});
