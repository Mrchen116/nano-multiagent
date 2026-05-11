import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { applyAgentStatusEvent } from "./agent-status-ws-consumer";
import type { AgentConfig, AgentSummary } from "./im-agent-config-api";

function makeSummary(overrides: Partial<AgentSummary> = {}): AgentSummary {
  return {
    agent_id: "agent-a",
    owner_id: "owner-1",
    display_name: "Agent A",
    description: "",
    profile_version: 1,
    default_model: null,
    workspace_root: "/tmp/agent-a",
    workspace_is_default: true,
    node_id: "node-1",
    node_name: "MacBook",
    node_status: "offline",
    updated_at: null,
    ...overrides
  };
}

function makeConfig(overrides: Partial<AgentConfig> = {}): AgentConfig {
  return {
    agent_id: "agent-a",
    owner_id: "owner-1",
    display_name: "Agent A",
    description: "",
    system_prompt: "You are A.",
    skills: [],
    tool_allowlist: [],
    group_reply_policy: "MENTION",
    default_model: null,
    workspace_root: "/tmp/agent-a",
    workspace_is_default: true,
    profile_version: 1,
    node_id: "node-1",
    node_name: "MacBook",
    node_status: "offline",
    updated_at: "2026-03-13T10:00:00Z",
    ...overrides
  };
}

describe("applyAgentStatusEvent — agent.status_changed WS consumer", () => {
  it("patches the list cache so the matching AgentSummary.node_status flips offline → online", () => {
    const client = new QueryClient();
    const initial = [makeSummary({ agent_id: "agent-a", node_status: "offline" }), makeSummary({ agent_id: "agent-b", node_status: "offline" })];
    client.setQueryData(["settings", "agents"], initial);

    applyAgentStatusEvent(client, {
      eventType: "agent.status_changed",
      payload: { agent_id: "agent-a", status: "online", seq: 1 }
    });

    const after = client.getQueryData<AgentSummary[]>(["settings", "agents"]);
    expect(after).toBeDefined();
    expect(after![0]).toMatchObject({ agent_id: "agent-a", node_status: "online" });
    expect(after![1]).toMatchObject({ agent_id: "agent-b", node_status: "offline" });
  });

  it("patches the detail-state cache so AgentConfig.node_status flips on the event", () => {
    const client = new QueryClient();
    client.setQueryData(["settings", "agents", "agent-a", "detail-state"], {
      config: makeConfig({ node_status: "offline" }),
      capabilities: { foo: "bar" },
      owningNode: { node_id: "node-1" }
    });

    applyAgentStatusEvent(client, {
      eventType: "agent.status_changed",
      payload: { agent_id: "agent-a", status: "online", seq: 2 }
    });

    const after = client.getQueryData<{ config: AgentConfig }>(["settings", "agents", "agent-a", "detail-state"]);
    expect(after?.config.node_status).toBe("online");
  });

  it("ignores unrelated event types and unknown agent_ids", () => {
    const client = new QueryClient();
    const initial = [makeSummary({ agent_id: "agent-a", node_status: "offline" })];
    client.setQueryData(["settings", "agents"], initial);

    applyAgentStatusEvent(client, {
      eventType: "node.status_changed",
      payload: { node_id: "node-1", status: "online", seq: 3 }
    });
    applyAgentStatusEvent(client, {
      eventType: "agent.status_changed",
      payload: { agent_id: "agent-not-in-cache", status: "online", seq: 4 }
    });

    const after = client.getQueryData<AgentSummary[]>(["settings", "agents"]);
    expect(after![0].node_status).toBe("offline");
  });

  it("rejects malformed payloads without throwing", () => {
    const client = new QueryClient();
    const initial = [makeSummary({ agent_id: "agent-a", node_status: "offline" })];
    client.setQueryData(["settings", "agents"], initial);

    applyAgentStatusEvent(client, {
      eventType: "agent.status_changed",
      payload: { agent_id: "agent-a" }
    });
    applyAgentStatusEvent(client, {
      eventType: "agent.status_changed",
      payload: { agent_id: "agent-a", status: "bogus-status" }
    });

    const after = client.getQueryData<AgentSummary[]>(["settings", "agents"]);
    expect(after![0].node_status).toBe("offline");
  });
});
