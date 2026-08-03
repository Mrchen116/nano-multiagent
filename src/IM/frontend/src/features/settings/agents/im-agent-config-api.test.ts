import { describe, it, expect, vi, beforeEach } from "vitest";

import { authFetch } from "../../auth/auth-fetch";
import {
  createAgentChannel,
  deleteAgentChannel,
  getAgentConfig,
  getAgentSkillsUsage,
  listAgentChannels,
  reconnectAgentChannel,
  retryAgentChannelRemoval,
  normalizeAgentConfigResponse,
  updateAgentChannel,
} from "./im-agent-config-api";

vi.mock("../../auth/auth-fetch", () => ({
  authFetch: vi.fn(),
}));

const BASE_RAW = {
  agent_id: "a1",
  owner_id: "o1",
  node_id: null,
  display_name: "Test",
  description: "",
  system_prompt: "",
  skills: [],
  tool_allowlist: [],
  group_reply_policy: "MENTION",
  default_model: null,
  workspace_root: "/tmp/ws",
  workspace_is_default: true,
  profile_version: 1,
  updated_at: null,
  features: {},
  custom_prompt: null,
  heartbeat_json: null,
};

describe("normalizeAgentConfigResponse heartbeat cadence", () => {
  it.each([
    [{ every: "10m" }, { every: "10m" }],
    [
      { every: "1h", active_hours: { start: "09:00", end: "22:00" } },
      { every: "1h", active_hours: { start: "09:00", end: "22:00" } },
    ],
    [{ enabled: true, every: "30m" }, { every: "30m" }],
  ])("normalizes stored %o to cadence %o", (stored, expected) => {
    const result = normalizeAgentConfigResponse({
      ...BASE_RAW,
      heartbeat_json: JSON.stringify(stored),
    });

    expect(result.heartbeat).toEqual(expected);
  });

  it.each([
    ["null", BASE_RAW],
    ["absent", (({ heartbeat_json: _, ...raw }) => raw)(BASE_RAW)],
    ["enable-only", { ...BASE_RAW, heartbeat_json: JSON.stringify({ enabled: true }) }],
  ])("leaves heartbeat undefined when cadence is %s", (_case, raw) => {
    expect(normalizeAgentConfigResponse(raw).heartbeat).toBeUndefined();
  });
});

describe("getAgentConfig source selection", () => {
  const mockedFetch = vi.mocked(authFetch);

  beforeEach(() => {
    mockedFetch.mockReset();
    mockedFetch.mockResolvedValue(
      new Response(JSON.stringify(BASE_RAW), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("defaults to the mirror source", async () => {
    await getAgentConfig("a1");
    expect(mockedFetch).toHaveBeenCalledWith(
      "/im/v1/agents/a1/config?source=mirror",
      expect.anything(),
    );
  });

  it("requests the live source when asked", async () => {
    await getAgentConfig("a1", "live");
    expect(mockedFetch).toHaveBeenCalledWith(
      "/im/v1/agents/a1/config?source=live",
      expect.anything(),
    );
  });
});

describe("getAgentSkillsUsage", () => {
  const mockedFetch = vi.mocked(authFetch);

  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("requests the agent skills usage endpoint and preserves dashboard fields", async () => {
    mockedFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          agent_id: "a1",
          node_id: "node-1",
          node_online: true,
          skills: [
            {
              skill_id: "deploy-check",
              name: "deploy-check",
              source: "F3",
              state: "active",
              use_count: 3,
              last_used_at: "2026-07-02T10:00:00Z",
              recent_call_keys: ["s1:tc1"],
              trend_buckets: [0, 0, 1],
            },
          ],
          heatmap_data: [0, 1, 2],
          health: {
            created_auto_total: 2,
            active_auto_total: 1,
            used_auto_total: 1,
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const usage = await getAgentSkillsUsage("a1");

    expect(mockedFetch).toHaveBeenCalledWith(
      "/im/v1/agents/a1/skills/usage",
      expect.anything(),
    );
    expect(usage.skills[0].name).toBe("deploy-check");
    expect(usage.skills[0].use_count).toBe(3);
    expect(usage.heatmap_data).toEqual([0, 1, 2]);
    expect(usage.health.created_auto_total).toBe(2);
  });
});

describe("agent channel API", () => {
  const mockedFetch = vi.mocked(authFetch);

  beforeEach(() => mockedFetch.mockReset());

  it("uses authenticated channel lifecycle resources", async () => {
    const responseBody = {
      channel_id: "channel-1",
      provider: "feishu",
      enabled: true,
      config: { app_id: "cli_test" },
      secret_configured: true,
      channel_revision: 1,
      sync_state: "pending",
      observed: null,
      updated_at: "2026-07-15T06:31:00Z",
    };
    mockedFetch
      .mockResolvedValueOnce(new Response(JSON.stringify([responseBody]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(responseBody), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(responseBody), { status: 200 }))
      .mockImplementation(() => Promise.resolve(
        new Response(JSON.stringify(responseBody), { status: 200 }),
      ));

    await expect(listAgentChannels("agent/a")).resolves.toEqual([responseBody]);
    const createPayload = {
      provider: "feishu",
      enabled: true,
      config: { app_id: "cli_test" },
      credentials: { mode: "replace" as const, app_secret: "new-secret" },
    };
    await createAgentChannel("agent/a", createPayload);
    const updatePayload = {
      channel_revision: 1,
      enabled: true,
      config: { app_id: "cli_test" },
      credentials: { mode: "keep" as const },
    };
    await updateAgentChannel("agent/a", "channel/1", updatePayload);
    await reconnectAgentChannel("agent/a", "channel/1");
    await deleteAgentChannel("agent/a", "channel/1", 1);
    await retryAgentChannelRemoval("agent/a", "channel/1");

    expect(mockedFetch).toHaveBeenNthCalledWith(1, "/im/v1/agents/agent%2Fa/channels", expect.anything());
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      "/im/v1/agents/agent%2Fa/channels",
      expect.objectContaining({ method: "POST", body: JSON.stringify(createPayload) }),
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      3,
      "/im/v1/agents/agent%2Fa/channels/channel%2F1",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify(updatePayload) }),
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      4,
      "/im/v1/agents/agent%2Fa/channels/channel%2F1/actions/reconnect",
      expect.objectContaining({ method: "POST" }),
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      5,
      "/im/v1/agents/agent%2Fa/channels/channel%2F1?channel_revision=1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      6,
      "/im/v1/agents/agent%2Fa/channel-removals/channel%2F1/actions/retry",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
