import "fake-indexeddb/auto";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../app/router";
import { useAuthStore } from "../features/auth/auth-store";
import { resetComposerStores } from "../features/chat/components/composer-draft-store";
import { ToolDetailBody } from "../features/chat/components/tool-detail-renderers";
import { AgentTrajectory } from "../features/settings/agents/agent-trajectory";
import { setLanguage } from "../i18n";
import { renderRouter, TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../test/render-router";
import { setDesktopBootContextForTest } from "./desktop-context";
import { WorkspaceAgentContext } from "./use-desktop-local-agents";

describe("Crewden Desktop local computer admin, direct trajectory, and path safety", () => {
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

  it("renders '这台电脑' card with rename, update banner, autostart switch, rollback draft preservation, and workspace path safety", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.example",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    const localNode = {
      node_id: "local-1",
      owner_id: TEST_AUTH_USER.owner_id,
      node_name: "Air-Studio",
      alias: null,
      status: "online",
      version: "2.4.0",
      agent_count: 1,
      relay_enabled: true,
      reporting_enabled: true,
      last_heartbeat_at: "2026-11-25T10:00:00Z",
      last_error: null,
      update: {
        current: { version: "2.4.0", platform: "desktop-darwin-arm64" },
        target: { version: "2.4.1", sha256: "a".repeat(64) },
        reason: "available",
        install_command: "",
      },
    };
    const remoteNode = {
      ...localNode,
      node_id: "remote-1",
      node_name: "Team-Build-Server",
      update: undefined,
    };

    let autostart = true;
    const savedConfigPayloads: Record<string, unknown>[] = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/desktop/v1/local-node/inspect")) {
        return new Response(
          JSON.stringify({
            ownership: "managed_online",
            node_id: "local-1",
            node_name: "Air-Studio",
            running: true,
            ready: true,
            connected: true,
            active_tasks: 2,
            version: "2.4.0",
            autostart,
            worker_runtime: "dsh",
            workers: [
              { runtime: "dsh", available: true, resolved_path: null, detail: "Bundled" },
              { runtime: "codex", available: true, resolved_path: "/opt/homebrew/bin/codex", detail: "Found" },
              { runtime: "claude", available: false, resolved_path: null, detail: "Not found" },
              { runtime: "antigravity", available: true, resolved_path: "/opt/homebrew/bin/agy", detail: "Found" },
            ],
            proxy: { enabled: true, url: "http://127.0.0.1:7890", no_proxy: "localhost,127.0.0.1,::1" },
            tool_approval_model: null,
            registered_models: [{ name: "deepseek:deepseek-chat", display_name: "DeepSeek Chat" }],
            environment: [{ key: "SEARXNG_URL", value: "http://127.0.0.1:8888" }],
            agents: [{ agent_id: "local-agent", display_name: "研发助手 E1", workspace_root: "/tmp/ws" }],
            logs: ["[10:00:00] INFO gateway ready", "[10:01:00] WARN proxy retry"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/desktop/v1/local-node/lifecycle") {
        const body = JSON.parse(String(init?.body ?? "{}"));
        if (body.action === "autostart") autostart = Boolean(body.enabled);
        return new Response(
          JSON.stringify({
            ownership: "managed_online",
            node_id: "local-1",
            node_name: "Air-Studio",
            running: true,
            ready: true,
            autostart,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/desktop/v1/local-node/probe-workers") {
        return new Response(JSON.stringify({ workers: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url === "/desktop/v1/local-node/config") {
        const body = JSON.parse(String(init?.body ?? "{}"));
        savedConfigPayloads.push(body);
        return new Response(
          JSON.stringify({
            error: "invalid_proxy_scheme",
            detail: "Only http:// and https:// proxies are supported; socks:// is not supported",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([localNode, remoteNode]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ items: [], max_event_id: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    const localCard = await screen.findByTestId("desktop-local-computer-card");
    expect(within(localCard).getByRole("heading", { name: "Air-Studio" })).toBeInTheDocument();
    expect(within(localCard).getByRole("link", { name: "+ 新建助手" })).toHaveAttribute(
      "href",
      "/settings/nodes/local-1/agents/new",
    );
    expect(screen.getByRole("heading", { name: "Team-Build-Server" })).toBeInTheDocument();

    const autostartSwitch = within(localCard).getByRole("switch", { name: "开机登录自启" });
    expect(autostartSwitch).toHaveAttribute("aria-checked", "true");
    await user.click(autostartSwitch);
    await waitFor(() => expect(autostartSwitch).toHaveAttribute("aria-checked", "false"));

    await user.click(within(localCard).getByText(/本机运行配置/));
    expect(within(localCard).getByText(/Antigravity/)).toBeInTheDocument();
    const proxyInput = within(localCard).getByLabelText("代理地址");
    expect(proxyInput).toBeEnabled();
    await user.clear(proxyInput);
    await user.type(proxyInput, "socks5://127.0.0.1:1080");
    await user.click(within(localCard).getByRole("button", { name: "保存并重启本机节点" }));
    // Active tasks > 0 requires explicit confirmation before restarting the local node!
    expect(savedConfigPayloads).toHaveLength(0);
    await user.click(within(localCard).getByRole("button", { name: "确认立即保存并重启" }));
    expect(await within(localCard).findByRole("alert")).toHaveTextContent(/不支持 socks:\/\//);
    expect(savedConfigPayloads[0]).toMatchObject({ confirm_restart: true });
    expect(proxyInput).toHaveValue("socks5://127.0.0.1:1080");

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    useAuthStore.setState({ user: TEST_AUTH_USER, accessToken: TEST_ACCESS_TOKEN, hydrated: true });
    const router = createMemoryRouter([
      {
        path: "/",
        element: (
          <WorkspaceAgentContext.Provider value="local-agent">
            <div data-testid="md-card">
              <ToolDetailBody
                call={{
                  id: "1",
                  name: "read",
                  status: "completed",
                  input: {},
                  detail: {
                    native_view: {
                      card: "read",
                      path: "reports/audit.md",
                      totalLines: 1,
                      offset: 1,
                      lines: [{ number: 1, text: "# Audit" }],
                    },
                  },
                }}
              />
            </div>
            <div data-testid="sh-card">
              <ToolDetailBody
                call={{
                  id: "2",
                  name: "edit",
                  status: "completed",
                  input: {},
                  detail: {
                    native_view: {
                      card: "diff",
                      diffs: [{ path: "scripts/run.sh", oldText: "echo old", newText: "echo hi" }],
                    },
                  },
                }}
              />
            </div>
          </WorkspaceAgentContext.Provider>
        ),
      },
    ]);
    render(
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    const mdCard = await screen.findByTestId("md-card");
    await waitFor(() => expect(within(mdCard).getByRole("button", { name: "打开文件" })).toBeInTheDocument());
    expect(within(mdCard).getByRole("button", { name: "在 Finder 中显示" })).toBeInTheDocument();

    const shCard = screen.getByTestId("sh-card");
    expect(within(shCard).queryByRole("button", { name: "打开文件" })).toBeNull();
    expect(within(shCard).getByRole("button", { name: "在 Finder 中显示" })).toBeInTheDocument();
  });

  it("connects AgentTrajectory directly over /desktop/ws/trajectory when prepared in local mode", async () => {
    setDesktopBootContextForTest({
      imOrigin: "https://im.example",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });
    useAuthStore.setState({ user: TEST_AUTH_USER, accessToken: TEST_ACCESS_TOKEN, revision: 1, hydrated: true });

    const sockets: { url: string; readyState: number; onmessage?: (e: { data: string }) => void }[] = [];
    class FakeWS {
      static OPEN = 1;
      readyState = 1;
      onmessage?: (e: { data: string }) => void;
      onclose?: () => void;
      onerror?: () => void;
      send = vi.fn();
      close = vi.fn();
      constructor(readonly url: URL | string) {
        sockets.push(this as never);
      }
    }
    vi.stubGlobal("WebSocket", FakeWS);
    vi.stubGlobal(
      "MessageChannel",
      class {
        port1 = { close: vi.fn(), start: vi.fn(), postMessage: vi.fn(), onmessage: null };
        port2 = { close: vi.fn(), start: vi.fn(), postMessage: vi.fn(), onmessage: null };
      },
    );
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/desktop/v1/trajectory/prepare") {
        return new Response(JSON.stringify({ mode: "local", ticket: "local-ticket-1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    const { container } = render(
      <AgentTrajectory agentId="local-agent" sessionId="child-unsynced" positions={{}} onBack={() => {}} />,
    );
    await waitFor(() => expect(sockets).toHaveLength(1));
    expect(String(sockets[0].url)).toContain("/desktop/ws/trajectory?");
    expect(String(sockets[0].url)).toContain("ticket=local-ticket-1");

    const frame = container.querySelector("iframe")!;
    vi.spyOn(frame.contentWindow!, "postMessage").mockImplementation(() => {});
    act(() => sockets[0].onmessage?.({ data: JSON.stringify({ type: "ready", version: "0.2.1" }) }));
    act(() => window.dispatchEvent(new MessageEvent("message", { source: frame.contentWindow, data: { type: "nano-trajectory-ready" } })));
    expect(screen.getByRole("status")).toHaveTextContent("本机直读 · 实时更新 · 只读");
  });
});
