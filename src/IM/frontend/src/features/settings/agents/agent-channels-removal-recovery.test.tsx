import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { act, render, screen, waitFor } from "@testing-library/react";
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
import type { AgentChannelRemoval } from "./im-agent-config-api";

function failedRemoval(): AgentChannelRemoval {
  return {
    resource_type: "removal",
    channel_id: "channel-1",
    provider: "feishu",
    display_config: { app_id_suffix: "_1234" },
    deletion_manifest_revision: 8,
    apply_state: "failed",
    apply_error: {
      code: "runtime_stop_failed",
      message: "worker 退出超时",
    },
    created_at: "2026-07-15T06:40:00Z",
  };
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AgentChannelsPanel agentId="agent-1" nodeStatus="online" />
    </QueryClientProvider>,
  );
  return queryClient;
}

beforeEach(() => {
  setLanguage("zh");
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
});

afterEach(() => setLanguage("en"));

describe("AgentChannelsPanel removal recovery", () => {
  it("clears a lost retry response once polling confirms the receipt disappeared", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([failedRemoval()]);
    apiMocks.retryAgentChannelRemoval.mockRejectedValue(
      new Error("temporary gateway failure: response lost"),
    );
    const queryClient = renderPanel();

    await screen.findByText("删除未完成");
    await user.click(screen.getByRole("button", { name: "重新尝试应用" }));

    expect(
      await screen.findByText("temporary gateway failure: response lost"),
    ).toHaveAttribute("role", "alert");
    act(() => {
      queryClient.setQueryData(
        ["settings", "agents", "agent-1", "channels"],
        [],
      );
    });

    expect(await screen.findByText("还没有外部通道")).toBeInTheDocument();
    await waitFor(() => expect(
      screen.queryByText("temporary gateway failure: response lost"),
    ).toBeNull());
    expect(screen.queryByText("等待节点上线后继续删除")).toBeNull();
  });

  it("clears the offline waiting notice before an online retry reports an error", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([failedRemoval()]);
    apiMocks.retryAgentChannelRemoval.mockRejectedValue(
      new Error("temporary gateway failure"),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const view = render(
      <QueryClientProvider client={queryClient}>
        <AgentChannelsPanel agentId="agent-1" nodeStatus="offline" />
      </QueryClientProvider>,
    );

    await screen.findByText("删除未完成");
    await user.click(screen.getByRole("button", { name: "重新尝试应用" }));
    expect(screen.getByText("等待节点上线后继续删除")).toHaveAttribute(
      "role",
      "status",
    );
    expect(apiMocks.retryAgentChannelRemoval).not.toHaveBeenCalled();

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <AgentChannelsPanel agentId="agent-1" nodeStatus="online" />
      </QueryClientProvider>,
    );
    await user.click(screen.getByRole("button", { name: "重新尝试应用" }));

    expect(await screen.findByText("temporary gateway failure")).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.queryByText("等待节点上线后继续删除")).toBeNull();
  });
});
