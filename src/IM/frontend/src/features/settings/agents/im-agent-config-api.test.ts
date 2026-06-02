/**
 * Tests for feat-394 / feat-394-M2 round-trip: heartbeat_json / cron_json
 * (raw JSON strings from backend) must be parsed back to HeartbeatConfig / CronConfig objects
 * so that HeartbeatCard / CronCard render the correct initial checked state.
 *
 * These tests call normalizeAgentConfigResponse directly (no HTTP mock needed).
 */
import { describe, it, expect } from "vitest";
import { normalizeAgentConfigResponse } from "./im-agent-config-api";

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
  cron_json: null,
};

describe("normalizeAgentConfigResponse — heartbeat_json round-trip", () => {
  it("parses heartbeat_json string into heartbeat object", () => {
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify({ enabled: true, every: "10m" }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat).toEqual({ enabled: true, every: "10m" });
  });

  it("heartbeat.enabled=true survives round-trip", () => {
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify({ enabled: true, every: "30m" }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat?.enabled).toBe(true);
  });

  it("heartbeat.enabled=false survives round-trip", () => {
    const raw = { ...BASE_RAW, heartbeat_json: JSON.stringify({ enabled: false, every: "30m" }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.heartbeat?.enabled).toBe(false);
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
});

describe("normalizeAgentConfigResponse — cron_json round-trip", () => {
  it("parses cron_json string into cron object", () => {
    const raw = { ...BASE_RAW, cron_json: JSON.stringify({ enabled: true }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.cron).toEqual({ enabled: true });
  });

  it("cron.enabled=true survives round-trip", () => {
    const raw = { ...BASE_RAW, cron_json: JSON.stringify({ enabled: true }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.cron?.enabled).toBe(true);
  });

  it("cron.enabled=false survives round-trip", () => {
    const raw = { ...BASE_RAW, cron_json: JSON.stringify({ enabled: false }) };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.cron?.enabled).toBe(false);
  });

  it("null cron_json produces undefined cron", () => {
    const raw = { ...BASE_RAW, cron_json: null };
    const result = normalizeAgentConfigResponse(raw);
    expect(result.cron).toBeUndefined();
  });

  it("absent cron_json key produces undefined cron", () => {
    const { cron_json: _, ...rawWithout } = BASE_RAW;
    const result = normalizeAgentConfigResponse(rawWithout);
    expect(result.cron).toBeUndefined();
  });
});
