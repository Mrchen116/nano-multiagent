import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLanguage } from "../../../i18n";

const apiMocks = vi.hoisted(() => ({
  createAgentChannel: vi.fn(),
  deleteAgentChannel: vi.fn(),
  listAgentChannels: vi.fn(),
  reconnectAgentChannel: vi.fn(),
  retryAgentChannelRemoval: vi.fn(),
  updateAgentChannel: vi.fn(),
}));

vi.mock("./im-agent-config-api", () => apiMocks);

import { AgentChannelsPanel } from "./agent-channels-panel";
import type { AgentChannel, ChannelDiagnosticCheck } from "./im-agent-config-api";

function check(
  overrides: Partial<ChannelDiagnosticCheck> = {},
): ChannelDiagnosticCheck {
  return {
    check_id: "feishu.receive_group_message",
    state: "missing",
    required: {
      accepted_scope_sets: [
        ["im:message.group_msg"],
        ["im:message.group_msg:readonly"],
      ],
      recommended_scopes: ["im:message.group_msg"],
    },
    effect: "Messages without an @Bot mention do not enter group background context.",
    remediation: "Grant the recommended scope and publish the app.",
    ...overrides,
  };
}

function channel(overrides: Partial<AgentChannel> = {}): AgentChannel {
  return {
    channel_id: "channel-1",
    provider: "feishu",
    enabled: true,
    config: { app_id: "cli_original_1234" },
    secret_configured: true,
    channel_revision: 7,
    sync_state: "applied",
    apply_error: null,
    observed: {
      observed_revision: 7,
      connection_state: "connected",
      diagnostics_state: "limited",
      status_message: null,
      status_updated_at: "2026-07-15T06:32:00Z",
      checks: [
        check(),
        check({
          check_id: "feishu.message_history",
          state: "unknown",
          required: {
            accepted_scope_sets: [["im:message:readonly"]],
            recommended_scopes: ["im:message:readonly"],
          },
          effect: "Message history cannot be recovered after an interruption.",
        }),
      ],
    },
    updated_at: "2026-07-15T06:31:00Z",
    ...overrides,
  };
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentChannelsPanel agentId="agent-1" nodeStatus="online" />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  setLanguage("zh");
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
  window.dispatchEvent(new Event("resize"));
});

afterEach(() => setLanguage("en"));

describe("AgentChannelsPanel diagnostics", () => {
  it("keeps the connection usable while showing actionable limited and unknown checks", async () => {
    apiMocks.listAgentChannels.mockResolvedValue([channel()]);

    renderPanel();

    expect(await screen.findByText("连接受限")).toBeInTheDocument();
    expect(screen.getByText("已连接")).toBeInTheDocument();
    expect(screen.getByText("im:message.group_msg")).toBeInTheDocument();
    expect(screen.getByText(/群背景上下文不完整/)).toBeInTheDocument();
    expect(screen.getAllByText("影响")).not.toHaveLength(0);
    expect(screen.getAllByText("修复方向")).not.toHaveLength(0);
    expect(screen.getByText("该项权限暂时无法确认")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /前往开放平台检查/ })).toHaveAttribute(
      "href",
      "https://open.feishu.cn/app/cli_original_1234/auth",
    );
  });

  it("does not fabricate missing permissions when diagnostics are unknown", async () => {
    apiMocks.listAgentChannels.mockResolvedValue([
      channel({
        sync_state: "failed",
        observed: {
          observed_revision: 7,
          connection_state: "failed",
          diagnostics_state: "unknown",
          status_message: "Long connection interrupted",
          status_updated_at: "2026-07-15T06:35:00Z",
          checks: [check({ state: "unknown" })],
        },
      }),
    ]);

    renderPanel();

    expect(await screen.findByText("权限状态暂时无法确认")).toBeInTheDocument();
    expect(screen.getAllByText("连接失败")).not.toHaveLength(0);
    expect(screen.queryByText("权限缺失")).toBeNull();
  });

  it("renders a retryable list error instead of an empty state", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels
      .mockRejectedValueOnce(new Error("GET failed: service unavailable"))
      .mockResolvedValueOnce([channel()]);

    renderPanel();

    expect(await screen.findByRole("heading", { name: "无法加载通道配置" })).toBeInTheDocument();
    expect(screen.queryByText("还没有外部通道")).toBeNull();
    await user.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(apiMocks.listAgentChannels).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("连接受限")).toBeInTheDocument();
  });
});
