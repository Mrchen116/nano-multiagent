import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setLanguage } from "../../../i18n";

const api = vi.hoisted(() => ({
  listAgentChannels: vi.fn(), createAgentChannel: vi.fn(), updateAgentChannel: vi.fn(),
  deleteAgentChannel: vi.fn(), reconnectAgentChannel: vi.fn(), retryAgentChannelRemoval: vi.fn(),
}));
vi.mock("./im-agent-config-api", () => api);
import { AgentChannelsPanel } from "./agent-channels-panel";
import type { AgentChannel, AgentChannelResource } from "./im-agent-config-api";
const channel: AgentChannel = {
  channel_id: "channel-1", provider: "feishu", enabled: true,
  config: { app_id: "cli_original" }, secret_configured: true,
  channel_revision: 7, sync_state: "applied", apply_error: null,
  observed: { observed_revision: 7, connection_state: "connected", status_message: null,
    status_updated_at: "2026-07-15T06:32:00Z" },
  updated_at: "2026-07-15T06:31:00Z",
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
function panel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const tree = (status: string, readOnly = false) => (
    <QueryClientProvider client={queryClient}>
      <AgentChannelsPanel agentId="agent-1" nodeStatus={status} readOnly={readOnly} />
    </QueryClientProvider>
  );
  const view = render(tree("online"));
  return { queryClient, rerender: (status: string, readOnly = false) => view.rerender(tree(status, readOnly)) };
}
beforeEach(() => {
  setLanguage("zh");
  Object.values(api).forEach((mock) => mock.mockReset());
  api.listAgentChannels.mockResolvedValue([channel]);
});
afterEach(() => setLanguage("en"));

describe("Channel drafts and connectivity", () => {
  it("retains App ID and secret through offline, delayed refresh and revision conflict", async () => {
    const user = userEvent.setup();
    const view = panel();
    await user.click(await screen.findByRole("button", { name: "编辑" }));
    await user.clear(screen.getByLabelText("App ID"));
    await user.type(screen.getByLabelText("App ID"), "cli_draft");
    await user.type(screen.getByLabelText("App Secret"), "unsaved-test-secret");
    view.rerender("offline");
    expect(screen.getByLabelText("App ID")).toHaveValue("cli_draft");
    expect(screen.getByLabelText("App Secret")).toHaveValue("unsaved-test-secret");
    expect(screen.getByLabelText("App Secret")).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "保存并连接" }));
    expect(api.updateAgentChannel).not.toHaveBeenCalled();
    const refresh = deferred<AgentChannelResource[]>();
    api.listAgentChannels.mockReturnValue(refresh.promise);
    view.rerender("online");
    expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled();
    await act(async () => refresh.resolve([{ ...channel, channel_revision: 8, config: { app_id: "cli_elsewhere" } }]));
    expect(await screen.findByText(/通道已在其他地方更新/)).toBeInTheDocument();
    expect(screen.getByLabelText("App ID")).toHaveValue("cli_draft");
    expect(screen.getByLabelText("App Secret")).toHaveValue("unsaved-test-secret");
    expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "取消" }));
    await user.click(screen.getByRole("button", { name: "编辑" }));
    expect(screen.getByLabelText("App ID")).toHaveValue("cli_elsewhere");
  });

  it("keeps an open confirmation read-only while connection is unknown and refreshing", async () => {
    const user = userEvent.setup();
    const view = panel();
    await user.click(await screen.findByRole("button", { name: "删除" }));
    view.rerender("unknown");
    expect(screen.getByRole("button", { name: "确认删除" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消" })).toBeEnabled();
    const refresh = deferred<AgentChannelResource[]>();
    api.listAgentChannels.mockReturnValue(refresh.promise);
    view.rerender("online");
    expect(screen.getByRole("button", { name: "确认删除" })).toBeDisabled();
    await act(async () => refresh.resolve([channel]));
    await waitFor(() => expect(screen.getByRole("button", { name: "确认删除" })).toBeEnabled());
    expect(api.deleteAgentChannel).not.toHaveBeenCalled();
  });

  it("retains a draft on refresh failure and unlocks only after a successful retry", async () => {
    const user = userEvent.setup();
    const view = panel();
    await user.click(await screen.findByRole("button", { name: "编辑" }));
    view.rerender("online", true);
    expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled();
    api.listAgentChannels.mockRejectedValue(new Error("refresh failed"));
    view.rerender("online", false);
    await waitFor(() => expect(screen.getAllByText(/通道读取失败/).length).toBeGreaterThan(0));
    expect(screen.getByLabelText("App ID")).toHaveValue("cli_original");
    expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled();
    api.listAgentChannels.mockResolvedValue([channel]);
    await user.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "保存并连接" })).toBeEnabled());
    expect(api.updateAgentChannel).not.toHaveBeenCalled();
  });

  it("does not resend a lost create response when the provider now exists", async () => {
    const user = userEvent.setup();
    api.listAgentChannels.mockResolvedValue([]);
    api.createAgentChannel.mockRejectedValue(new Error("network response lost"));
    const view = panel();
    await user.click((await screen.findAllByRole("button", { name: "添加通道" }))[0]);
    await user.click(screen.getByRole("button", { name: /飞书/ }));
    await user.type(screen.getByLabelText("App ID"), "cli_draft");
    await user.type(screen.getByLabelText("App Secret"), "unsaved-test-secret");
    await user.click(screen.getByRole("button", { name: "保存并连接" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled());
    expect(screen.getByLabelText("App Secret")).toHaveValue("unsaved-test-secret");
    await user.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "保存并连接" })).toBeEnabled());
    expect(screen.getByText(/此前操作结果无法确认/)).toBeInTheDocument();
    expect(api.createAgentChannel).toHaveBeenCalledTimes(1);
    api.listAgentChannels.mockResolvedValue([channel]);
    await act(() => view.queryClient.invalidateQueries({ queryKey: ["settings", "agents", "agent-1", "channels"] }));
    await user.click(screen.getByRole("button", { name: "保存并连接" }));
    expect(api.createAgentChannel).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "保存并连接" })).toBeDisabled();
    expect(screen.getByLabelText("App ID")).toHaveValue("cli_draft");
  });

  it("does not confirm reconnect from an old connected observation", async () => {
    const user = userEvent.setup();
    api.reconnectAgentChannel.mockResolvedValue(channel);
    const view = panel();
    await user.click(await screen.findByRole("button", { name: "重新连接" }));
    await act(() => view.queryClient.invalidateQueries({ queryKey: ["settings", "agents", "agent-1", "channels"] }));
    expect(screen.getByRole("button", { name: "重新连接" })).toBeDisabled();
    expect(screen.getByText("正在重新连接")).toBeInTheDocument();
    api.listAgentChannels.mockResolvedValue([{ ...channel, observed: {
      ...channel.observed!, status_updated_at: new Date(Date.now() + 1000).toISOString(),
    } }]);
    await act(() => view.queryClient.invalidateQueries({ queryKey: ["settings", "agents", "agent-1", "channels"] }));
    await waitFor(() => expect(screen.getByRole("button", { name: "重新连接" })).toBeEnabled());
    expect(screen.getByText("当前配置已应用")).toBeInTheDocument();
  });
});
