/**
 * feat-394 M9-C: vitest tests for features-driven heartbeat/cron panel behavior.
 *
 * When capabilities.features includes "heartbeat" or "cron_scheduling", the agent
 * detail page must:
 *   1. Remove the independent enable toggle from HeartbeatCard / CronCard.
 *   2. Show/hide the config panels based on draft.features (controlled by the
 *      Features checkbox list).
 *   3. Render tool pills with default_on state (empty allowlist → default tools
 *      appear selected).
 *
 * These tests are RED until M9-C implementation is verified end-to-end.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getAgentDetailStateMock: vi.fn(),
  updateAgentConfigMock: vi.fn(),
  listAgentSummariesMock: vi.fn(),
  listAgentsMock: vi.fn(),
  navigateMock: vi.fn(),
  promptPreviewMock: vi.fn(),
  createDirectChatByAgentUserIdMock: vi.fn(),
  createDirectConversationMock: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ agentId: "agent-m9c-1" }),
    useNavigate: () => apiMocks.navigateMock,
  };
});

vi.mock("../../chat/chat-api", () => ({
  createDirectConversation: apiMocks.createDirectConversationMock,
  createDirectChatByAgentUserId: apiMocks.createDirectChatByAgentUserIdMock,
  listAgents: apiMocks.listAgentsMock,
}));

vi.mock("../../../hooks/use-is-mobile", () => ({
  useIsMobile: () => false,
}));

vi.mock("./im-agent-config-api", () => ({
  getAgentDetailState: apiMocks.getAgentDetailStateMock,
  updateAgentConfig: apiMocks.updateAgentConfigMock,
  listAgentSummaries: apiMocks.listAgentSummariesMock,
  promptPreview: apiMocks.promptPreviewMock,
}));

import { AgentDetailPage } from "./agent-detail-page";

function renderDetailPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentDetailPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// Capability features that include heartbeat + cron_scheduling (M9-C Gateway).
const HB_CAP_FEATURE = {
  key: "heartbeat",
  label_i18n: "agents.features.heartbeat.label",
  help_i18n: "agents.features.heartbeat.help",
  default_on: false,
  available: true,
  requires_tool: null,
};

const CRON_CAP_FEATURE = {
  key: "cron_scheduling",
  label_i18n: "agents.features.cron_scheduling.label",
  help_i18n: "agents.features.cron_scheduling.help",
  default_on: false,
  available: true,
  requires_tool: "cron",
};

const TOOL_DEFAULT = { name: "read", description: "Read files", default_on: true };
const TOOL_OPTIONAL = { name: "cron", description: "Cron scheduling", default_on: false };

function makeM9CState(opts: {
  configFeatures?: Record<string, boolean>;
  capFeatures?: object[];
  heartbeat?: object;
  // feat-394 M9-E: cron field removed from AgentConfig; enable in features["cron_scheduling"].
} = {}) {
  return {
    config: {
      agent_id: "agent-m9c-1",
      owner_id: "owner-1",
      display_name: "M9C Agent",
      description: "",
      system_prompt: "",
      custom_prompt: "",
      features: opts.configFeatures ?? {},
      skills: [],
      tool_allowlist: [] as string[],
      group_reply_policy: "MENTION" as const,
      default_model: null,
      workspace_root: "/tmp",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-03-13T10:00:00Z",
      ...(opts.heartbeat !== undefined ? { heartbeat: opts.heartbeat } : {}),
      // feat-394 M9-E: no cron config field; enable in features["cron_scheduling"].
    },
    capabilities: {
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      capabilities_updated_at: "2026-03-13T10:00:00Z",
      skills: [],
      tools: [TOOL_DEFAULT, TOOL_OPTIONAL],
      model_options: [],
      platform_default_model: null,
      default_system_prompt: "",
      features: opts.capFeatures ?? [HB_CAP_FEATURE, CRON_CAP_FEATURE],
    },
    owningNode: null,
  };
}

beforeEach(() => {
  apiMocks.listAgentSummariesMock.mockResolvedValue([
    {
      agent_id: "agent-m9c-1",
      display_name: "M9C Agent",
      owner_id: "owner-1",
      description: "",
      profile_version: 1,
      default_model: null,
      workspace_root: "",
      workspace_is_default: false,
    },
  ]);
  apiMocks.listAgentsMock.mockResolvedValue([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Part A: HeartbeatCard independent toggle hidden when heartbeat in cap features
// ---------------------------------------------------------------------------

describe("M9-C: heartbeat controlled by Features list", () => {
  it("heartbeat-enabled-toggle is hidden when heartbeat is in capabilities.features", async () => {
    // heartbeat is a registered capability feature → toggle moves to Features list
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({ capFeatures: [HB_CAP_FEATURE, CRON_CAP_FEATURE] })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    const toggle = document.querySelector<HTMLInputElement>(
      '[data-testid="heartbeat-enabled-toggle"]'
    );
    expect(toggle, "heartbeat-enabled-toggle must be hidden when heartbeat is in cap features").toBeNull();
  });

  it("HeartbeatCard is not rendered when features.heartbeat is false/absent", async () => {
    // heartbeat in cap features but not in draft.features → card hidden
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: {}, // heartbeat not enabled
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // HeartbeatCard title must not appear
    expect(screen.queryByRole("heading", { name: /Heartbeat/i })).toBeNull();
  });

  it("HeartbeatCard appears when features.heartbeat is toggled on via Features list", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: {}, // initially off
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // Before toggle: card absent
    expect(screen.queryByRole("heading", { name: /Heartbeat/i })).toBeNull();

    // Find the heartbeat checkbox in the Features list
    const hbCheckbox = document.querySelector<HTMLInputElement>(
      '[data-feature-key="heartbeat"]'
    );
    expect(hbCheckbox, "heartbeat feature checkbox must exist in Features list").not.toBeNull();

    // Toggle it on
    if (hbCheckbox) await user.click(hbCheckbox);

    // After toggle: HeartbeatCard (with cadence config) appears
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /Heartbeat/i })).not.toBeNull();
    });
  });

  it("HeartbeatCard shows cadence config (every input) when enabled via features", async () => {
    // heartbeat on via features → cadence panel always visible (no separate enable toggle)
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: { heartbeat: true }, // pre-enabled
        heartbeat: { enabled: true, every: "1h" },
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // Cadence input must be visible (not gated behind a separate enable toggle)
    const everyInput = document.querySelector<HTMLInputElement>("#heartbeat-every");
    expect(everyInput, "'every' interval input must be visible when heartbeat feature is on").not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Part B: CronCard independent toggle hidden when cron_scheduling in cap features
// ---------------------------------------------------------------------------

describe("M9-C: cron controlled by Features list", () => {
  it("cron-enabled-toggle is hidden when cron_scheduling is in capabilities.features", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({ capFeatures: [HB_CAP_FEATURE, CRON_CAP_FEATURE] })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    const toggle = document.querySelector<HTMLInputElement>(
      '[data-testid="cron-enabled-toggle"]'
    );
    expect(toggle, "cron-enabled-toggle must be hidden when cron_scheduling is in cap features").toBeNull();
  });

  it("CronCard is not rendered when features.cron_scheduling is false/absent", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [CRON_CAP_FEATURE],
        configFeatures: {}, // cron not enabled
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    expect(screen.queryByRole("heading", { name: /Cron Jobs/i })).toBeNull();
  });

  it("CronCard appears when features.cron_scheduling toggled on via Features list", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [CRON_CAP_FEATURE],
        configFeatures: {},
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    expect(screen.queryByRole("heading", { name: /Cron Jobs/i })).toBeNull();

    const cronCheckbox = document.querySelector<HTMLInputElement>(
      '[data-feature-key="cron_scheduling"]'
    );
    expect(cronCheckbox, "cron_scheduling feature checkbox must exist").not.toBeNull();

    if (cronCheckbox) await user.click(cronCheckbox);

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /Cron Jobs/i })).not.toBeNull();
    });
  });
});

// ---------------------------------------------------------------------------
// Part C: Tool pills render with default_on state
// ---------------------------------------------------------------------------

describe("M9-C: tool pills render default_on state", () => {
  it("default tools appear selected when tool_allowlist is empty", async () => {
    // empty tool_allowlist → pills show 'read' (default_on=true) as selected,
    // 'cron' (default_on=false) as unselected
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({ configFeatures: {} })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // 'read' pill (default_on=true) must appear pressed
    await waitFor(() => {
      const readPill = document.querySelector<HTMLButtonElement>(
        '[data-pill-name="read"]'
      );
      expect(readPill, "'read' pill must exist").not.toBeNull();
      expect(readPill?.getAttribute("aria-pressed"), "read pill should be 'pressed' when tool_allowlist is empty (default_on=true)").toBe("true");
    });

    // 'cron' pill (default_on=false) must appear not pressed
    const cronPill = document.querySelector<HTMLButtonElement>('[data-pill-name="cron"]');
    if (cronPill) {
      expect(cronPill.getAttribute("aria-pressed"), "cron pill should be 'false' (default_on=false)").toBe("false");
    }
  });

  it("default tool can be deselected (true whitelist semantics)", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({ configFeatures: {} })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // 'read' appears selected (default_on=true, empty allowlist)
    await waitFor(() => {
      const readPill = document.querySelector<HTMLButtonElement>('[data-pill-name="read"]');
      expect(readPill?.getAttribute("aria-pressed")).toBe("true");
    });

    // Click to deselect
    const readPill = document.querySelector<HTMLButtonElement>('[data-pill-name="read"]');
    if (readPill) await user.click(readPill);

    // After deselect: 'read' is no longer selected
    await waitFor(() => {
      const readPill2 = document.querySelector<HTMLButtonElement>('[data-pill-name="read"]');
      expect(readPill2?.getAttribute("aria-pressed"), "read pill should be deselected after click").toBe("false");
    });
  });
});

// ---------------------------------------------------------------------------
// Part D: promptPreview sends features (heartbeat/cron_scheduling via features dict)
// ---------------------------------------------------------------------------

describe("M9-C: promptPreview reflects features for heartbeat/cron", () => {
  it("preview body includes heartbeat=true when toggled on in Features list", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: { heartbeat: true },
        heartbeat: { enabled: true, every: "30m" },
      })
    );
    apiMocks.promptPreviewMock.mockResolvedValue("## Heartbeat\nCadence...");

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // Open preview
    const previewBtn = screen.getByRole("button", { name: /Preview full system prompt/i });
    await user.click(previewBtn);

    await waitFor(() => {
      expect(apiMocks.promptPreviewMock).toHaveBeenCalled();
    });

    const lastCall = apiMocks.promptPreviewMock.mock.calls.at(-1);
    const body = lastCall?.[1] as { features?: Record<string, boolean> };
    expect(body?.features?.heartbeat, "preview body must contain features.heartbeat=true").toBe(true);
  });
});

// ---------------------------------------------------------------------------
// feat-394-M11 decision E: cadence input binds to backend config value (no 30m hardcode)
// ---------------------------------------------------------------------------

describe("M11: cadence input binds to config value, no hardcoded 30m fallback", () => {
  it("cadence input shows empty string (not '30m') when heartbeat.every is not configured", async () => {
    // When the backend does not configure heartbeat.every, the frontend must NOT
    // silently fill in "30m" as a hardcoded fallback — the input must reflect the
    // actual backend state (empty/undefined).  The "30m" default should appear only
    // as placeholder text, not as an actual input value.
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: { heartbeat: true },
        // heartbeat.every intentionally absent — simulates "no cadence configured"
        heartbeat: { enabled: true },
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    const everyInput = document.querySelector<HTMLInputElement>("#heartbeat-every");
    expect(everyInput, "cadence input must be rendered when heartbeat is on").not.toBeNull();
    expect(
      everyInput!.value,
      "cadence input value must be empty (not hardcoded '30m') when heartbeat.every is unset"
    ).toBe("");
    expect(everyInput!.placeholder, "placeholder should be '30m' as the default hint").toBe("30m");
  });

  it("cadence input shows the configured every value from backend", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: { heartbeat: true },
        heartbeat: { enabled: true, every: "45m" },
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    const everyInput = document.querySelector<HTMLInputElement>("#heartbeat-every");
    expect(everyInput, "cadence input must render").not.toBeNull();
    expect(everyInput!.value, "cadence input must display backend value '45m'").toBe("45m");
  });
});

// ---------------------------------------------------------------------------
// feat-394-M11 decision E: HEARTBEAT.md read-only preview panel
// ---------------------------------------------------------------------------

describe("M11: HEARTBEAT.md read-only preview in HeartbeatCard", () => {
  it("shows a collapsible HEARTBEAT.md preview when heartbeat feature is on", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(
      makeM9CState({
        capFeatures: [HB_CAP_FEATURE],
        configFeatures: { heartbeat: true },
        heartbeat: { enabled: true, every: "30m" },
      })
    );

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    // A button/details element labelled around "HEARTBEAT.md" must be present
    // to expand the read-only preview.
    const previewTrigger = document.querySelector<HTMLElement>("[data-testid='heartbeat-md-preview-toggle']");
    expect(
      previewTrigger,
      "HEARTBEAT.md collapsible preview toggle must be present when heartbeat is on"
    ).not.toBeNull();
  });
});
