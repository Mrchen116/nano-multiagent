/**
 * Tool pills render the stored tool_allowlist truthfully.
 *
 * Empty tool_allowlist → no pills are selected. Non-empty allowlist → only the
 * listed tools appear selected. Pills can be toggled in/out of the allowlist.
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
  createConversationMock: vi.fn(),
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
  createConversation: apiMocks.createConversationMock,
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

const TOOL_DEFAULT = { name: "read", description: "Read files", default_on: true };
const TOOL_OPTIONAL = { name: "cron", description: "Cron scheduling", default_on: false };

function makeAgentState(toolAllowlist: string[]) {
  return {
    config: {
      agent_id: "agent-m9c-1",
      owner_id: "owner-1",
      display_name: "M9C Agent",
      description: "",
      system_prompt: "",
      custom_prompt: "",
      features: {},
      skills: [],
      tool_allowlist: toolAllowlist,
      group_reply_policy: "MENTION" as const,
      default_model: null,
      workspace_root: "/tmp",
      workspace_is_default: false,
      profile_version: 1,
      node_id: "node-1",
      node_name: "MacBook",
      node_status: "online",
      updated_at: "2026-03-13T10:00:00Z",
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
      features: [],
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

function pill(name: string) {
  return document.querySelector<HTMLButtonElement>(`[data-pill-name="${name}"]`);
}

describe("tool pills render stored allowlist", () => {
  it("empty tool_allowlist renders all pills unselected", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeAgentState([]));

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("false");
    });
    expect(pill("cron")?.getAttribute("aria-pressed")).toBe("false");
  });

  it("non-empty tool_allowlist renders only listed pills selected", async () => {
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeAgentState(["read"]));

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("true");
    });
    expect(pill("cron")?.getAttribute("aria-pressed")).toBe("false");
  });

  it("toggling a pill updates its selected state", async () => {
    const user = userEvent.setup();
    apiMocks.getAgentDetailStateMock.mockResolvedValue(makeAgentState([]));

    renderDetailPage();
    await screen.findByRole("heading", { name: "M9C Agent" });

    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("false");
    });

    await user.click(pill("read")!);
    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("true");
    });

    await user.click(pill("read")!);
    await waitFor(() => {
      expect(pill("read")?.getAttribute("aria-pressed")).toBe("false");
    });
  });
});
