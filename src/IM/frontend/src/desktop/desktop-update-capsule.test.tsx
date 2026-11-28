import "fake-indexeddb/auto";
import userEvent from "@testing-library/user-event";
import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UserMenu } from "../app/shell/user-menu";
import { resetComposerStores } from "../features/chat/components/composer-draft-store";
import { setLanguage } from "../i18n";
import { renderRouter } from "../test/render-router";
import { setDesktopBootContextForTest } from "./desktop-context";
import { DesktopRailUpdatePill } from "./desktop-update-pill";
import { resetDesktopAttentionReporterForTest } from "./use-desktop-unsaved-form";
import { setDesktopUserMenuOpen } from "./use-desktop-updater";
import { makeSnapshot } from "./desktop-updater-test-fixture";

describe("Desktop update capsule", () => {
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
});
