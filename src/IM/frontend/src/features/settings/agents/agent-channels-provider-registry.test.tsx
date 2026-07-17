import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@testing-library/react";
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

import {
  AgentChannelsPanel,
  CHANNEL_PROVIDERS,
  ChannelProviderDescriptor,
} from "./agent-channels-panel";
import type { AgentChannel } from "./im-agent-config-api";

const WEBHOOK_PROVIDER: ChannelProviderDescriptor = {
  id: "webhook",
  icon: "钩",
  label: { default: "Webhook" },
  description: { default: "Connect a generic webhook" },
  guide: {
    text: { default: "Create a webhook endpoint and issue an API token." },
    href: "https://example.test/webhooks",
    linkLabel: { default: "Webhook setup" },
  },
  fields: [
    {
      name: "workspace",
      wireKey: "workspace_slug",
      source: "config",
      label: { default: "Workspace" },
      validation: { default: "Enter a workspace" },
      resetsCredentials: true,
    },
    {
      name: "token",
      wireKey: "api_token",
      source: "credentials",
      label: { default: "API Token" },
      validation: { default: "Enter an API token" },
      inputType: "password",
    },
  ],
  summary: { field: "workspace", label: "Workspace", mask: false },
  removalSummary: { displayKey: "workspace_suffix", label: "Workspace" },
  diagnostics: {
    href: "https://example.test/webhooks/diagnostics",
    linkLabel: { default: "Webhook console" },
    scopeLabel: { default: "Webhook grants" },
    effectOverrides: {},
  },
  connectingDetail: { default: "Establishing webhook delivery" },
};

function resource(
  provider: "feishu" | "webhook",
  overrides: Partial<AgentChannel> = {},
): AgentChannel {
  return {
    channel_id: `channel-${provider}`,
    provider,
    enabled: true,
    config: provider === "feishu"
      ? { app_id: "cli_original_1234" }
      : { workspace_slug: "acme" },
    secret_configured: true,
    channel_revision: 2,
    sync_state: "applied",
    apply_error: null,
    observed: {
      observed_revision: 2,
      connection_state: "connected",
      status_updated_at: "2026-07-15T08:00:00Z",
    },
    updated_at: "2026-07-15T08:00:00Z",
    ...overrides,
  };
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentChannelsPanel
        agentId="agent-1"
        providers={[...CHANNEL_PROVIDERS, WEBHOOK_PROVIDER]}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  setLanguage("zh");
  for (const mock of Object.values(apiMocks)) mock.mockReset();
});

afterEach(() => setLanguage("en"));

describe("channel provider descriptor dispatch", () => {
  it("keeps uniqueness per provider and creates a second provider without Feishu fields", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([resource("feishu")]);
    apiMocks.createAgentChannel.mockResolvedValue(resource("webhook", {
      sync_state: "pending",
      observed: null,
    }));

    renderPanel();
    await screen.findByText("当前配置已应用");
    await user.click(screen.getByRole("button", { name: "添加通道" }));
    const dialog = screen.getByRole("dialog", { name: "添加通道" });
    expect(within(dialog).getByRole("button", { name: /飞书.*已添加/ })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: /Webhook/ }));

    expect(screen.queryByLabelText("App ID")).toBeNull();
    expect(screen.getByLabelText("Workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("API Token")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /飞书开放平台/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "保存并连接" }));
    expect(screen.getByText("Enter a workspace")).toBeInTheDocument();
    expect(screen.getByText("Enter an API token")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Workspace"), "acme");
    await user.type(screen.getByLabelText("API Token"), "token-value");
    await user.click(screen.getByRole("button", { name: "保存并连接" }));

    expect(apiMocks.createAgentChannel).toHaveBeenCalledWith("agent-1", {
      provider: "webhook",
      enabled: true,
      config: { workspace_slug: "acme" },
      credentials: { mode: "replace", api_token: "token-value" },
    });
    expect(await screen.findByText("Workspace · acme")).toBeInTheDocument();
    expect(screen.queryByText(/App ID · acme/)).toBeNull();
  });

  it("uses provider-owned card diagnostics without Feishu links or effects", async () => {
    apiMocks.listAgentChannels.mockResolvedValue([
      resource("webhook", {
        observed: {
          observed_revision: 2,
          connection_state: "connected",
          diagnostics_state: "limited",
          status_updated_at: "2026-07-15T08:00:00Z",
          checks: [{
            check_id: "webhook.delivery",
            state: "missing",
            required: {
              accepted_scope_sets: [["hook:write"]],
              recommended_scopes: ["hook:write"],
            },
            effect: "Delivery pauses",
            remediation: "Grant delivery access",
          }],
        },
      }),
    ]);

    renderPanel();

    expect(await screen.findByRole("link", { name: /Webhook console/ })).toHaveAttribute(
      "href",
      "https://example.test/webhooks/diagnostics",
    );
    expect(screen.getByLabelText("Webhook grants")).toBeInTheDocument();
    expect(screen.getByText(/Delivery pauses/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /开放平台/ })).toBeNull();
    expect(screen.queryByText(/群背景上下文/)).toBeNull();
  });

  it("serializes edits through the selected provider descriptor", async () => {
    const user = userEvent.setup();
    apiMocks.listAgentChannels.mockResolvedValue([resource("webhook")]);
    apiMocks.updateAgentChannel.mockResolvedValue(resource("webhook", {
      config: { workspace_slug: "new-space" },
      channel_revision: 3,
    }));

    renderPanel();
    await screen.findByText("Workspace · acme");
    await user.click(screen.getByRole("button", { name: "编辑" }));
    expect(screen.getByRole("radio", { name: /保留现有密钥/ })).toBeChecked();
    await user.clear(screen.getByLabelText("Workspace"));
    await user.type(screen.getByLabelText("Workspace"), "new-space");
    expect(screen.getByRole("radio", { name: /替换密钥/ })).toBeChecked();
    await user.type(screen.getByLabelText("API Token"), "replacement-token");
    await user.click(screen.getByRole("button", { name: "保存并连接" }));

    expect(apiMocks.updateAgentChannel).toHaveBeenCalledWith(
      "agent-1",
      "channel-webhook",
      {
        channel_revision: 2,
        enabled: true,
        config: { workspace_slug: "new-space" },
        credentials: { mode: "replace", api_token: "replacement-token" },
      },
    );
  });
});
