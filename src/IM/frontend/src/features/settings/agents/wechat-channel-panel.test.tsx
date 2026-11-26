import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
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

const wechatSetupMocks = vi.hoisted(() => ({
  setupWeChatChannel: vi.fn(),
}));

vi.mock("./im-agent-config-api", () => apiMocks);
vi.mock("./wechat-channel-setup-api", () => wechatSetupMocks);

import { AgentChannelsPanel } from "./agent-channels-panel";
import type { AgentChannel } from "./im-agent-config-api";

function feishuChannel(overrides: Partial<AgentChannel> = {}): AgentChannel {
  return {
    channel_id: "ch_feishu",
    provider: "feishu",
    enabled: true,
    config: { app_id: "cli_original_8a91f" },
    secret_configured: true,
    channel_revision: 3,
    sync_state: "applied",
    apply_error: null,
    observed: {
      observed_revision: 3,
      connection_state: "connected",
      status_message: null,
      status_updated_at: "2026-07-15T06:32:00Z",
    },
    updated_at: "2026-07-15T06:31:00Z",
    ...overrides,
  };
}

function wechatChannel(overrides: Partial<AgentChannel> = {}): AgentChannel {
  return {
    channel_id: "ch_wechat",
    provider: "wechat",
    enabled: true,
    config: {
      bot_id: "bot_wx_9001",
      owner_user_id: "wxid_owner_3k92",
      base_url: "https://ilinkai.weixin.qq.com",
    },
    secret_configured: true,
    channel_revision: 2,
    sync_state: "applied",
    apply_error: null,
    observed: {
      observed_revision: 2,
      connection_state: "connected",
      status_message: null,
      status_updated_at: "2026-07-15T06:40:00Z",
    },
    updated_at: "2026-07-15T06:39:00Z",
    ...overrides,
  };
}

function renderPanel(nodeStatus = "online") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <AgentChannelsPanel agentId="agent-1" nodeStatus={nodeStatus} />
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

beforeEach(() => {
  setLanguage("zh");
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  wechatSetupMocks.setupWeChatChannel.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  setLanguage("en");
});

describe("AgentChannelsPanel WeChat channel flow", () => {
  it("walks through WeChat QR scan, PIN error retry, and confirmation alongside an existing Feishu channel", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([feishuChannel()]);

    let statusPollCount = 0;
    wechatSetupMocks.setupWeChatChannel.mockImplementation(async (_agentId: string, payload: Record<string, unknown>) => {
      if (payload.action === "start") {
        return {
          setup_id: "setup_1",
          state: "waiting_scan",
          qr_svg: '<svg viewBox="0 0 10 10"><path d="M0,0h10v10h-10z"/></svg>',
        };
      }
      if (payload.action === "status") {
        statusPollCount += 1;
        if (statusPollCount === 1) {
          return {
            setup_id: "setup_1",
            state: "scanned",
            qr_svg: '<svg viewBox="0 0 10 10"><path d="M0,0h10v10h-10z"/></svg>',
          };
        }
        return {
          setup_id: "setup_1",
          state: "need_verify_code",
        };
      }
      if (payload.action === "verify_code") {
        if (payload.code === "000000") {
          return {
            setup_id: "setup_1",
            state: "need_verify_code",
            error_code: "wrong_verify_code",
            error_message: "验证码不正确，请核对手机微信界面显示的数字后重试",
          };
        }
        return {
          setup_id: "setup_1",
          state: "confirmed",
          channel: wechatChannel({ sync_state: "applied" }),
        };
      }
      return { setup_id: "setup_1", state: "cancelled" };
    });

    renderPanel();
    await screen.findByText("当前配置已应用");

    const addButton = screen.getByRole("button", { name: "连接通道" });
    expect(addButton).toBeEnabled();
    await user.click(addButton);

    const dialog = screen.getByRole("dialog", { name: "添加通道" });
    expect(within(dialog).getByRole("button", { name: /飞书.*已添加/ })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: /微信/ }));

    expect(await screen.findByText("请使用本人手机微信扫描二维码")).toBeInTheDocument();
    expect(wechatSetupMocks.setupWeChatChannel).toHaveBeenCalledWith("agent-1", { action: "start" });

    expect(await screen.findByText(/已扫码，请在手机微信上点击确认/)).toBeInTheDocument();
    const pinInput = await screen.findByLabelText("输入手机微信显示的数字验证码", {}, { timeout: 4000 });
    const submitPin = screen.getByRole("button", { name: "确认绑定" });
    expect(submitPin).toBeDisabled();

    await user.type(pinInput, "000000");
    expect(submitPin).toBeEnabled();
    await user.click(submitPin);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("验证码不正确");
    expect(pinInput).toHaveAttribute("aria-invalid", "true");

    await user.clear(pinInput);
    await user.type(pinInput, "482916");
    await user.click(submitPin);

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByText(/wxid_o••••3k92/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "连接通道" })).toBeDisabled();
  });

  it("refreshes an expired QR code and cancels active setup on modal close", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([]);
    let startCount = 0;
    wechatSetupMocks.setupWeChatChannel.mockImplementation(async (_agentId: string, payload: Record<string, unknown>) => {
      if (payload.action === "start") {
        startCount += 1;
        return startCount === 1
          ? {
            setup_id: "setup_exp",
            state: "expired",
            qr_svg: '<svg viewBox="0 0 10 10"><path d="M0,0h5v5h-5z"/></svg>',
          }
          : {
            setup_id: "setup_fresh",
            state: "waiting_scan",
            qr_svg: '<svg viewBox="0 0 10 10"><path d="M0,0h8v8h-8z"/></svg>',
          };
      }
      return { setup_id: String(payload.setup_id), state: "cancelled" };
    });

    renderPanel();
    await screen.findByText("还没有外部通道");
    await user.click(screen.getByRole("button", { name: "连接通道" }));
    await user.click(screen.getByRole("button", { name: /微信/ }));

    expect(await screen.findByText("二维码已过期")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "刷新二维码" }));
    expect(await screen.findByText("请使用本人手机微信扫描二维码")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(wechatSetupMocks.setupWeChatChannel).toHaveBeenCalledWith("agent-1", {
      action: "cancel",
      setup_id: "setup_fresh",
    });
  });

  it("hides useless Reconnect and promotes Re-scan QR when WeChat token is revoked", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([
      feishuChannel(),
      wechatChannel({
        observed: {
          observed_revision: 2,
          connection_state: "failed",
          status_code: "wechat_token_revoked",
          status_message: "微信侧已解除授权或在别处重新扫码，请点击「重新扫码」恢复绑定",
          status_updated_at: "2026-07-15T06:50:00Z",
        },
      }),
    ]);
    wechatSetupMocks.setupWeChatChannel.mockResolvedValue({
      setup_id: "setup_rebind",
      state: "waiting_scan",
      qr_svg: '<svg viewBox="0 0 10 10"><path d="M0,0h10v10h-10z"/></svg>',
    });

    renderPanel();
    expect(await screen.findByText("登录已失效")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "连接通道" })).toBeDisabled();

    // Feishu keeps Reconnect, while WeChat revoked card hides Reconnect and promotes Re-scan QR.
    expect(screen.getAllByRole("button", { name: "重新连接" })).toHaveLength(1);
    const rescanBtn = screen.getByRole("button", { name: "重新扫码" });
    expect(rescanBtn.className).toContain("im-btn-primary");

    await user.click(rescanBtn);
    expect(await screen.findByText("请使用本人手机微信扫描二维码")).toBeInTheDocument();
    expect(wechatSetupMocks.setupWeChatChannel).toHaveBeenCalledWith("agent-1", {
      action: "start",
      editing_channel_id: "ch_wechat",
      channel_revision: 2,
    });
  });
});
