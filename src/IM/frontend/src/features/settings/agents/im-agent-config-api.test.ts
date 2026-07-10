/**
 * Tests for feat-394 round-trip: heartbeat_json (raw JSON string from backend) must be
 * parsed back to a HeartbeatConfig cadence object so HeartbeatCard renders correct cadence.
 *
 * feat-394 M9-E: heartbeat enable lives in features["heartbeat"]; heartbeat_json only
 * carries cadence (every / active_hours). cron_json and CronConfig are retired.
 *
 * These tests call normalizeAgentConfigResponse directly (no HTTP mock needed).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import { authFetch } from "../../auth/auth-fetch";
import {
  getAgentConfig,
  getAgentSkillsUsage,
  normalizeAgentConfigResponse,
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

describe("normalizeAgentConfigResponse — heartbeat_json cadence round-trip", () => {
  it("parses heartbeat_json string into cadence-only heartbeat object", () => {
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify({ every: "10m" }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat).toEqual({ every: "10m" });
  });

  it("extracts only cadence fields — drops legacy enabled field from stored JSON", () => {
    // Legacy heartbeat_json may contain "enabled"; M9-E: only cadence fields are kept.
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify({ enabled: true, every: "30m" }) };
    const result = normalizeAgentConfigResponse(raw);
    // "enabled" must NOT appear on heartbeat — it lives in features["heartbeat"].
    expect(result.heartbeat).toEqual({ every: "30m" });
    expect((result.heartbeat as Record<string, unknown>)?.enabled).toBeUndefined();
  });

  it("extracts active_hours cadence from heartbeat_json", () => {
    const hb = { every: "1h", active_hours: { start: "09:00", end: "22:00" } };
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify(hb) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat).toEqual(hb);
  });

  it("null heartbeat_json produces undefined heartbeat", () => {
    const raw = { ...BASE_RAW, heartbeat_json: null };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat).toBeUndefined();
  });

  it("absent heartbeat_json key produces undefined heartbeat", () => {
    const { heartbeat_json: _, ...rawWithout } = BASE_RAW;
    const result = normalizeAgentConfigResponse(rawWithout);
    expect(result.heartbeat).toBeUndefined();
  });

  it("heartbeat_json with only enabled and no cadence produces undefined heartbeat", () => {
    // Pure-enable JSON with no cadence fields → nothing useful to keep.
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify({ enabled: true }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat).toBeUndefined();
  });
});

// feat-394 M9-E: cron_json round-trip tests removed — cron enable lives in
// features["cron_scheduling"]; cron_json parsing path deleted from normalizeAgentConfigResponse.
// feat-394 M9-E: heartbeat.enabled round-trip tests removed — enable lives in features["heartbeat"].

// feat-430 fix-r2 (P0): getAgentConfig must let the caller pick the data source so the
// slash picker can fetch the agent's真实已启用 skills (live Gateway) instead of the empty
// mirror whitelist that triggers the "empty→all" fallback.
describe("getAgentConfig — source selection", () => {
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

  it("requests the live source when asked (slash picker path)", async () => {
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
