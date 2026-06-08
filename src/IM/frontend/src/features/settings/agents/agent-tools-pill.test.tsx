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


describe("tool pills render default_on state", () => {
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

