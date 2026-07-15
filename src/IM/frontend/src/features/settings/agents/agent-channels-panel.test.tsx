import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@testing-library/react";
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
import type { AgentChannel, AgentChannelRemoval } from "./im-agent-config-api";

function channel(overrides: Partial<AgentChannel> = {}): AgentChannel {
  return {
    channel_id: "channel-1",
    provider: "feishu",
    enabled: true,
    config: { app_id: "cli_original_1234" },
    secret_configured: true,
    channel_revision: 7,
    sync_state: "applied",
    observed: {
      observed_revision: 7,
      connection_state: "connected",
      status_message: null,
      status_updated_at: "2026-07-15T06:32:00Z",
    },
    updated_at: "2026-07-15T06:31:00Z",
    ...overrides,
  };
}

function removal(overrides: Partial<AgentChannelRemoval> = {}): AgentChannelRemoval {
  return {
    resource_type: "removal",
    channel_id: "channel-1",
    provider: "feishu",
    display_config: { app_id_suffix: "_1234" },
    deletion_manifest_revision: 8,
    apply_state: "pending",
    apply_error: null,
    created_at: "2026-07-15T06:40:00Z",
    ...overrides,
  };
}

function renderPanel(nodeStatus = "online") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentChannelsPanel agentId="agent-1" nodeStatus={nodeStatus} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  setLanguage("zh");
  apiMocks.listAgentChannels.mockReset();
  apiMocks.createAgentChannel.mockReset();
  apiMocks.deleteAgentChannel.mockReset();
  apiMocks.reconnectAgentChannel.mockReset();
  apiMocks.retryAgentChannelRemoval.mockReset();
  apiMocks.updateAgentChannel.mockReset();
});

afterEach(() => setLanguage("en"));

describe("AgentChannelsPanel", () => {
  it("renders the generic empty state and validates the short Feishu wizard", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([]);

    renderPanel();

    const emptyHeading = await screen.findByRole("heading", { name: "还没有外部通道" });
    expect(screen.queryByText(/Web IM/i)).toBeNull();
    await user.click(within(emptyHeading.closest("section")!).getByRole("button", { name: "添加通道" }));
    const picker = screen.getByRole("dialog", { name: "添加通道" });
    await user.click(within(picker).getByRole("button", { name: /飞书/ }));

    expect(screen.getByText("在飞书开放平台创建应用、开启机器人能力并选择长连接接收事件。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /打开飞书开放平台/ })).toHaveAttribute(
      "href",
      "https://open.feishu.cn/page/launcher?from=backend_oneclick",
    );
    await user.click(screen.getByRole("button", { name: "保存并连接" }));
    expect(screen.getByText("请输入 App ID")).toBeInTheDocument();
    expect(screen.getByText("请输入 App Secret")).toBeInTheDocument();
  });

  it("disables an already-added provider and makes App ID changes require secret replacement", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([channel()]);

    renderPanel();
    await screen.findByText("当前配置已应用");
    await user.click(screen.getByRole("button", { name: "添加通道" }));

    const provider = screen.getByRole("button", { name: /飞书.*已添加/ });
    expect(provider).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "关闭" }));
    await user.click(screen.getByRole("button", { name: "编辑" }));

    expect(screen.getByRole("radio", { name: /保留现有密钥/ })).toBeChecked();
    expect(screen.queryByLabelText("App Secret")).toBeNull();
    await user.clear(screen.getByLabelText("App ID"));
    await user.type(screen.getByLabelText("App ID"), "cli_replacement");
    expect(screen.getByRole("radio", { name: /替换密钥/ })).toBeChecked();
    expect(screen.getByLabelText("App Secret")).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "保存并连接" }));
    expect(screen.getByText("请输入 App Secret")).toBeInTheDocument();
  });

  it("projects a successful online save immediately as connecting", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([]);
    apiMocks.createAgentChannel.mockResolvedValue(
      channel({ channel_revision: 1, sync_state: "pending", observed: null }),
    );

    renderPanel();
    const emptyHeading = await screen.findByRole("heading", { name: "还没有外部通道" });
    await user.click(within(emptyHeading.closest("section")!).getByRole("button", { name: "添加通道" }));
    await user.click(screen.getByRole("button", { name: /飞书/ }));
    await user.type(screen.getByLabelText("App ID"), "cli_created");
    await user.type(screen.getByLabelText("App Secret"), "secret-value");
    await user.click(screen.getByRole("button", { name: "保存并连接" }));

    expect(await screen.findByText("正在连接")).toBeInTheDocument();
    expect(screen.getByText("配置与凭据已安全保存")).toBeInTheDocument();
    expect(apiMocks.createAgentChannel).toHaveBeenCalledWith("agent-1", {
      provider: "feishu",
      enabled: true,
      config: { app_id: "cli_created" },
      credentials: { mode: "replace", app_secret: "secret-value" },
    });
  });

  it("shows connected time without internal revision and exposes a concrete failure", async () => {
    apiMocks.listAgentChannels.mockResolvedValue([channel()]);
    const view = renderPanel();

    expect(await screen.findByText("当前配置已应用")).toBeInTheDocument();
    expect(screen.getByText(/状态更新于/)).toBeInTheDocument();
    expect(screen.queryByText(/revision|版本 7|v7/i)).toBeNull();

    apiMocks.listAgentChannels.mockResolvedValue([
      channel({
        sync_state: "failed",
        observed: {
          observed_revision: 7,
          connection_state: "failed",
          status_code: "invalid_credentials",
          status_message: "飞书拒绝了 App ID 或 App Secret",
          status_updated_at: "2026-07-15T06:35:00Z",
        },
      }),
    ]);
    view.rerender(
      <QueryClientProvider client={new QueryClient()}>
        <AgentChannelsPanel agentId="agent-2" />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getAllByText("连接失败")).toHaveLength(2));
    expect(screen.getByText("飞书拒绝了 App ID 或 App Secret")).toBeInTheDocument();
  });

  it("keeps offline desired changes pending and separates disabling from disabled", async () => {
    const user = userEvent.setup();
    const pending = channel({ sync_state: "pending", observed: null });
    apiMocks.listAgentChannels.mockResolvedValue([pending]);
    apiMocks.updateAgentChannel.mockResolvedValue({ ...pending, enabled: false });

    renderPanel("offline");

    expect(await screen.findByText("配置已保存")).toBeInTheDocument();
    expect(screen.getByText("节点上线后自动应用")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "节点离线" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "停用" }));
    await user.click(screen.getByRole("button", { name: "确认停用" }));
    expect(await screen.findByText("正在停用")).toBeInTheDocument();
    expect(apiMocks.updateAgentChannel).toHaveBeenCalledWith(
      "agent-1",
      "channel-1",
      expect.objectContaining({ enabled: false, credentials: { mode: "keep" } }),
    );

    apiMocks.listAgentChannels.mockResolvedValue([
      channel({
        enabled: false,
        observed: {
          observed_revision: 7,
          connection_state: "disabled",
          status_message: null,
          status_updated_at: "2026-07-15T06:42:00Z",
        },
      }),
    ]);
    renderPanel();
    expect(await screen.findByText("已停用")).toBeInTheDocument();
    expect(screen.getByText(/凭据已保留/)).toBeInTheDocument();
  });

  it("retains deleting receipts across reload and retries failed removal", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([
      removal({
        apply_state: "failed",
        apply_error: {
          code: "runtime_stop_failed",
          message: "worker 退出超时",
        },
      }),
    ]);
    apiMocks.retryAgentChannelRemoval.mockResolvedValue(removal());

    renderPanel();

    expect(await screen.findByText("删除未完成")).toBeInTheDocument();
    expect(screen.getByText("worker 退出超时")).toBeInTheDocument();
    expect(screen.queryByText("还没有外部通道")).toBeNull();
    await user.click(screen.getByRole("button", { name: "重新尝试应用" }));
    expect(await screen.findByText("删除待应用")).toBeInTheDocument();
    expect(apiMocks.retryAgentChannelRemoval).toHaveBeenCalledWith(
      "agent-1",
      "channel-1",
    );
  });

  it("confirms deletion and projects manual reconnect without changing credentials", async () => {
    const user = userEvent.setup();
    const connected = channel();
    apiMocks.listAgentChannels.mockResolvedValue([connected]);
    // The live command endpoint returns the pre-command channel snapshot. The
    // UI must not flash back to "connected" before the next observed report.
    apiMocks.reconnectAgentChannel.mockResolvedValue(connected);
    apiMocks.deleteAgentChannel.mockResolvedValue(removal());

    renderPanel();
    await screen.findByText("当前配置已应用");
    await user.click(screen.getByRole("button", { name: "重新连接" }));
    expect(await screen.findByText("正在重新连接")).toBeInTheDocument();
    expect(apiMocks.reconnectAgentChannel).toHaveBeenCalledWith(
      "agent-1",
      "channel-1",
    );
    await user.click(screen.getByRole("button", { name: "删除" }));
    await user.click(screen.getByRole("button", { name: "确认删除" }));
    expect(await screen.findByText("删除待应用")).toBeInTheDocument();
    expect(apiMocks.deleteAgentChannel).toHaveBeenCalledWith(
      "agent-1",
      "channel-1",
      7,
    );
  });
});
