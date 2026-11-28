import "fake-indexeddb/auto";
import type { DesktopUpdaterSnapshot } from "@nano/product-contracts/desktop-local";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../app/router";
import { AppShell } from "../app/shell/app-shell";
import { UserMenu } from "../app/shell/user-menu";
import {
  clearDesktopComposerDraftStorage,
  composerStoreFor,
  EMPTY_COMPOSER_SNAPSHOT,
  forgetComposerUser,
  resetComposerStores,
  threadDraftKey,
  writeComposerSnapshot,
} from "../features/chat/components/composer-draft-store";
import { MePage } from "../features/me/me-page";
import { setLanguage } from "../i18n";
import { renderRouter } from "../test/render-router";
import { setDesktopBootContextForTest } from "./desktop-context";
import {
  DesktopNarrowUpdateBanner,
  DesktopRailUpdatePill,
} from "./desktop-update-pill";
import { useDesktopUnsavedForm } from "./use-desktop-unsaved-form";
import { buildReloadTargetUrl, setDesktopUserMenuOpen } from "./use-desktop-updater";

function makeSnapshot(overrides: Partial<DesktopUpdaterSnapshot> = {}): DesktopUpdaterSnapshot {
  return {
    platform: "darwin-arm64",
    current_version: "1.3.2",
    auto_update: true,
    phase: "up_to_date",
    mode: null,
    target: null,
    progress: null,
    active_tasks: 0,
    last_checked_at: "2026-04-20T08:00:00.000Z",
    just_updated_version: null,
    capsule_dismissed: false,
    active_ui_sha256: "a".repeat(64),
    reload_generation: 1,
    error_code: null,
    ...overrides,
  };
}

describe("Crewden Desktop seamless updates, draft preservation, and zero-jargon UX", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setLanguage("zh");
    setDesktopUserMenuOpen(false);
    resetComposerStores();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    setDesktopUserMenuOpen(false);
    setDesktopBootContextForTest(undefined);
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("persists composer drafts, mentions, reply quotes, and thread drafts across hot reload while isolating by server, epoch, and user", () => {
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 4,
      platform: "darwin-arm64",
    });

    const storeBeforeReload = composerStoreFor("user-1");
    writeComposerSnapshot(storeBeforeReload, "conv-42", {
      ...EMPTY_COMPOSER_SNAPSHOT,
      revision: "rev-live-1",
      draft: "帮我整理今晚发布清单 @小助手 ",
      draftMentions: [{ label: "小助手", type: "agent", target_id: "agent-1" }],
      replyTo: {
        message_id: "msg-9",
        sender: { type: "agent", id: "agent-1", display_name: "小助手" },
        content: "上一轮构建已完成",
        attachments: [],
      },
    });
    const threadKey = threadDraftKey("conv-42", "root-7");
    writeComposerSnapshot(
      storeBeforeReload,
      threadKey,
      {
        ...EMPTY_COMPOSER_SNAPSHOT,
        draft: "子话题补充说明",
      },
      "conv-42",
    );

    const rawSaved = sessionStorage.getItem(
      "crewden:composer-drafts::https://im.crewden.work::4::user-1",
    );
    expect(rawSaved).toBeTruthy();

    // Simulate WebView location.replace reload: clear in-memory Map while keeping sessionStorage intact
    const snapshotCopy = rawSaved!;
    resetComposerStores();
    sessionStorage.setItem(
      "crewden:composer-drafts::https://im.crewden.work::4::user-1",
      snapshotCopy,
    );

    const storeAfterReload = composerStoreFor("user-1");
    expect(storeAfterReload.get("conv-42")).toMatchObject({
      revision: "rev-live-1",
      draft: "帮我整理今晚发布清单 @小助手 ",
      draftMentions: [{ label: "小助手", type: "agent", target_id: "agent-1" }],
      replyTo: expect.objectContaining({ message_id: "msg-9" }),
    });
    expect(storeAfterReload.get(threadKey)?.draft).toBe("子话题补充说明");

    // Different user on same Desktop context never sees user-1's draft
    expect(composerStoreFor("user-2").get("conv-42")).toBeUndefined();

    // Bumping contextEpoch (e.g. server switch) isolates and prunes stale epoch keys
    setDesktopBootContextForTest({
      imOrigin: "http://192.168.1.25:8080",
      contextEpoch: 5,
      platform: "darwin-arm64",
    });
    expect(composerStoreFor("user-1").get("conv-42")).toBeUndefined();
    expect(
      sessionStorage.getItem("crewden:composer-drafts::https://im.crewden.work::4::user-1"),
    ).toBeNull();

    // Sign-out wipes persisted sessionStorage drafts for that user
    writeComposerSnapshot(composerStoreFor("user-1"), "conv-99", {
      ...EMPTY_COMPOSER_SNAPSHOT,
      draft: "内网草稿",
    });
    expect(
      sessionStorage.getItem("crewden:composer-drafts::http://192.168.1.25:8080::5::user-1"),
    ).toBeTruthy();
    forgetComposerUser("user-1");
    expect(
      sessionStorage.getItem("crewden:composer-drafts::http://192.168.1.25:8080::5::user-1"),
    ).toBeNull();
    clearDesktopComposerDraftStorage();
  });

  it("preserves pathname and existing query parameters when appending _desktop_reload", () => {
    const url = buildReloadTargetUrl("/chat/conv-88", "?thread=msg-12&filter=unread");
    expect(url).toMatch(/^\/chat\/conv-88\?thread=msg-12&filter=unread&_desktop_reload=\d+$/);
  });

  it("renders bottom-left ready capsule, expands highlights, suppresses popover while UserMenu is open, and applies hot switch", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    let currentSnap = makeSnapshot({
      phase: "ready_to_switch",
      mode: "hot_bundle",
      target: {
        version: "1.4.0",
        release_notes: "- 桌面端秒级无感换新\n- 聊天输入框草稿完整保留",
      },
    });
    const actions: string[] = [];
    let flushedBeforeReload = false;
    window.addEventListener("crewden:before-hot-reload", () => {
      flushedBeforeReload = true;
    });

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/desktop/v1/updater" && (!init?.method || init.method === "GET")) {
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/apply" && init?.method === "POST") {
        actions.push("apply");
        currentSnap = makeSnapshot({
          current_version: "1.4.0",
          phase: "up_to_date",
          just_updated_version: "1.4.0",
        });
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/dismiss" && init?.method === "POST") {
        actions.push(`dismiss:${String(init.body)}`);
        currentSnap = { ...currentSnap, just_updated_version: null };
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

    renderRouter({
      routes: [
        {
          path: "/chat",
          element: (
            <div>
              <DesktopRailUpdatePill />
              <UserMenu />
            </div>
          ),
        },
      ],
      initialEntries: ["/chat"],
    });

    const readyCard = await screen.findByTestId("desktop-capsule-ready");
    expect(within(readyCard).getByText("✨ 新版 v1.4.0 已备好")).toBeInTheDocument();

    // Expand release notes
    await user.click(within(readyCard).getByRole("button", { name: "看看更新了什么 ▾" }));
    expect(within(readyCard).getByText("桌面端秒级无感换新")).toBeInTheDocument();

    // Opening UserMenu suppresses the floating capsule card so popovers never overlap
    await user.click(screen.getByRole("button", { name: "You" }));
    expect(screen.getByTestId("user-menu-update-box")).toBeInTheDocument();
    expect(screen.queryByTestId("desktop-capsule-ready")).not.toBeInTheDocument();

    // Closing UserMenu restores the capsule card
    await user.keyboard("{Escape}");
    const restoredCard = await screen.findByTestId("desktop-capsule-ready");

    // Click one-click hot switch -> flushes draft event & transitions to post-update confirmation
    await user.click(within(restoredCard).getByTestId("desktop-capsule-switch-now"));
    await waitFor(() => expect(actions).toContain("apply"));
    expect(flushedBeforeReload).toBe(true);

    const updatedCard = await screen.findByTestId("desktop-capsule-just-updated");
    expect(within(updatedCard).getByText("✓ 已换上 v1.4.0")).toBeInTheDocument();
    await user.click(within(updatedCard).getByRole("button", { name: "收起" }));
    await waitFor(() =>
      expect(screen.queryByTestId("desktop-capsule-just-updated")).not.toBeInTheDocument(),
    );
  });

  it("handles waiting_for_tasks cancellation and shell_protocol > 1 installer progress + macOS DMG guide without jargon", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    let currentSnap = makeSnapshot({
      phase: "waiting_for_tasks",
      mode: "hot_bundle",
      active_tasks: 2,
      target: { version: "1.4.0" },
    });
    const calls: string[] = [];

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/desktop/v1/updater") {
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/cancel" && init?.method === "POST") {
        calls.push("cancel");
        currentSnap = makeSnapshot({
          phase: "downloading_installer",
          mode: "installer",
          target: {
            version: "2.0.0",
            macos_distribution: "unnotarized",
          },
          progress: {
            stage: "downloading",
            downloaded_bytes: 12 * 1024 * 1024,
            total_bytes: 48 * 1024 * 1024,
          },
        });
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/open-installer" && init?.method === "POST") {
        calls.push("open-installer");
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

    renderRouter({
      routes: [{ path: "/chat", element: <DesktopRailUpdatePill /> }],
      initialEntries: ["/chat"],
    });

    const waitingCard = await screen.findByTestId("desktop-capsule-waiting");
    expect(within(waitingCard).getByText(/等待任务收尾/)).toBeInTheDocument();
    await user.click(within(waitingCard).getByRole("button", { name: "取消本次换新" }));
    await waitFor(() => expect(calls).toContain("cancel"));

    const installerCard = await screen.findByTestId("desktop-capsule-installer");
    expect(within(installerCard).getByTestId("desktop-installer-progress")).toHaveTextContent(
      "12.0 MB / 48.0 MB",
    );

    // Advance snapshot to installer_ready and notify hook
    currentSnap = makeSnapshot({
      phase: "installer_ready",
      mode: "installer",
      target: {
        version: "2.0.0",
        macos_distribution: "unnotarized",
      },
    });
    window.dispatchEvent(new Event("crewden:updater-changed"));

    const dmgGuide = await screen.findByTestId("desktop-mac-dmg-guide");
    expect(dmgGuide).toHaveTextContent("Applications");
    expect(dmgGuide).toHaveTextContent("仍要打开");
    expect(document.body.textContent).not.toMatch(
      /shell_protocol|incompatible|SHA-256|relay_gated/i,
    );

    await user.click(screen.getByTestId("desktop-capsule-installer-cta"));
    await waitFor(() => expect(calls).toContain("open-installer"));
  });

  it("renders narrow (<768px) banner on /chat, hides duplicate banner on /me, and supports manual check & auto-update toggle on MePage", async () => {
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

  it("reports has_unsaved_form to /desktop/v1/attention when an editable form becomes dirty", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    const attentionPayloads: Array<Record<string, unknown>> = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/desktop/v1/attention" && init?.method === "POST") {
        attentionPayloads.push(JSON.parse(String(init.body ?? "{}")));
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater") {
        return new Response(JSON.stringify(makeSnapshot()), {
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
      if (url === "/im/v1/conversations" || url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }) as typeof fetch;

    function DirtyProbeForm() {
      const [dirty, setDirty] = useState(false);
      useDesktopUnsavedForm(dirty);
      return (
        <button type="button" onClick={() => setDirty((v) => !v)}>
          toggle-dirty
        </button>
      );
    }

    renderRouter({
      routes: [
        {
          path: "/settings/account",
          element: (
            <AppShell>
              <DirtyProbeForm />
            </AppShell>
          ),
        },
      ],
      initialEntries: ["/settings/account"],
    });

    await waitFor(() =>
      expect(attentionPayloads).toContainEqual(
        expect.objectContaining({
          current_route: "/settings/account",
          has_unsaved_form: false,
        }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "toggle-dirty" }));
    await waitFor(() =>
      expect(attentionPayloads).toContainEqual(
        expect.objectContaining({
          current_route: "/settings/account",
          has_unsaved_form: true,
        }),
      ),
    );
  });
});
