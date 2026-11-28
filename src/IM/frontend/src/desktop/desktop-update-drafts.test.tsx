import "fake-indexeddb/auto";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../app/router";
import { AppShell } from "../app/shell/app-shell";
import { clearDesktopComposerDraftStorage, composerStoreFor, EMPTY_COMPOSER_SNAPSHOT, forgetComposerUser, resetComposerStores, threadDraftKey, writeComposerSnapshot } from "../features/chat/components/composer-draft-store";
import { setLanguage } from "../i18n";
import { renderRouter } from "../test/render-router";
import { setDesktopBootContextForTest } from "./desktop-context";
import { DesktopNarrowUpdateBanner, DesktopRailUpdatePill } from "./desktop-update-pill";
import { resetDesktopAttentionReporterForTest, useDesktopUnsavedForm } from "./use-desktop-unsaved-form";
import { buildReloadTargetUrl, setDesktopUserMenuOpen } from "./use-desktop-updater";
import { makeSnapshot } from "./desktop-updater-test-fixture";

describe("Desktop draft and unsaved-form preservation", () => {
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

  it("reports /onboarding route and has_unsaved_form=true outside AppShell and syncs reopen_capsule to host", async () => {
    const user = userEvent.setup();
    setDesktopBootContextForTest({
      imOrigin: "https://im.crewden.work",
      contextEpoch: 1,
      platform: "darwin-arm64",
    });

    const attentionPayloads: Array<Record<string, unknown>> = [];
    let currentSnap = makeSnapshot({
      phase: "ready_to_switch",
      mode: "hot_bundle",
      capsule_dismissed: true,
      target: { version: "1.4.0" },
    });
    const dismissKinds: string[] = [];

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
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/desktop/v1/updater/dismiss" && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as { kind: string };
        dismissKinds.push(body.kind);
        currentSnap = {
          ...currentSnap,
          capsule_dismissed: body.kind === "capsule",
        };
        return new Response(JSON.stringify(currentSnap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/im/v1/onboarding") {
        return new Response(
          JSON.stringify({
            nodes: [{ node_id: "node-1", node_name: "Mac", status: "online", alias: null }],
            install: { available: true, origin: "https://im.crewden.work", command: "curl" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/im/v1/nodes/node-1/setup")) {
        return new Response(
          JSON.stringify({
            default_model: "gpt-5",
            models: [{ model: "gpt-5", display_name: "GPT-5" }],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/im/v1/personal-agent") {
        return new Response(JSON.stringify({ binding: null, creation: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.startsWith("/desktop/v1/local-node/inspect")) {
        return new Response(JSON.stringify({ ownership: "managed_online", node_id: "node-1", node_name: "Mac" }), {
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

    const { unmount } = renderRouter({ routes: appRoutes, initialEntries: ["/onboarding"] });
    await screen.findByText("给你的个人助手起个名字");
    await waitFor(() =>
      expect(attentionPayloads).toContainEqual(
        expect.objectContaining({
          current_route: "/onboarding",
          has_unsaved_form: true,
        }),
      ),
    );
    unmount();

    // Reopening a dismissed capsule from the rail badge clears `capsule_dismissed` on the host so NarrowBanner also stays open!
    renderRouter({
      routes: [
        {
          path: "/chat",
          element: (
            <div>
              <DesktopRailUpdatePill />
              <DesktopNarrowUpdateBanner />
            </div>
          ),
        },
      ],
      initialEntries: ["/chat"],
    });
    const trigger = await screen.findByTestId("desktop-rail-update-trigger");
    expect(screen.queryByTestId("desktop-capsule-ready")).not.toBeInTheDocument();
    expect(screen.queryByTestId("desktop-narrow-ready")).not.toBeInTheDocument();

    await user.click(trigger);
    await waitFor(() => expect(dismissKinds).toContain("reopen_capsule"));
    expect(await screen.findByTestId("desktop-capsule-ready")).toBeInTheDocument();
    expect(await screen.findByTestId("desktop-narrow-ready")).toBeInTheDocument();
  });
});
