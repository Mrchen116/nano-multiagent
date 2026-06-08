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


describe("promptPreview reflects features for heartbeat/cron", () => {
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

describe("cadence input shows actual backend value", () => {
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

