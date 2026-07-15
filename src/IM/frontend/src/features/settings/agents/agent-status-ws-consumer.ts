import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { subscribeUserStream, type UserStreamEvent } from "../../../realtime/user-stream";
import type { AgentSummary, AgentConfig } from "./im-agent-config-api";

type AgentStatus = "online" | "offline";

interface AgentDetailStateCacheShape {
  config: AgentConfig;
  capabilities: unknown;
  owningNode: unknown;
}

/**
 * 把 `agent.status_changed` WS 事件 patch 进 react-query 缓存。
 *
 * 列表 cache(`["settings","agents"]`):匹配到的 AgentSummary.node_status 直接覆盖。
 * 详情 cache(`["settings","agents",agentId,"detail-state"]`):配置内 node_status 覆盖。
 *
 * 暴露成纯函数是为了让单元测试不依赖真实 WS,直接喂事件断言 cache 变化。
 */
export function applyAgentStatusEvent(client: QueryClient, event: UserStreamEvent): void {
  if (event.eventType === "agent.channel.status_changed") {
    const agentId = typeof event.payload.agent_id === "string" ? event.payload.agent_id : null;
    const channelId = typeof event.payload.channel_id === "string" ? event.payload.channel_id : null;
    if (!agentId || !channelId) return;
    void client.invalidateQueries({
      queryKey: ["settings", "agents", agentId, "channels"],
      exact: true
    });
    return;
  }
  if (event.eventType !== "agent.status_changed") return;
  const payload = event.payload;
  const agentId = typeof payload.agent_id === "string" ? payload.agent_id : null;
  const rawStatus = typeof payload.status === "string" ? payload.status : null;
  if (!agentId || (rawStatus !== "online" && rawStatus !== "offline")) return;
  const status = rawStatus as AgentStatus;

  client.setQueryData<AgentSummary[] | undefined>(["settings", "agents"], (current) => {
    if (!current) return current;
    let changed = false;
    const next = current.map((agent) => {
      if (agent.agent_id !== agentId) return agent;
      if (agent.node_status === status) return agent;
      changed = true;
      return { ...agent, node_status: status };
    });
    return changed ? next : current;
  });

  client.setQueryData<AgentDetailStateCacheShape | undefined>(
    ["settings", "agents", agentId, "detail-state"],
    (current) => {
      if (!current) return current;
      if (current.config.node_status === status) return current;
      return {
        ...current,
        config: { ...current.config, node_status: status }
      };
    }
  );
}

/**
 * 在 Agents 列表/详情挂载时调用一次,订阅 WS hub 的 `agent.status_changed` 事件。
 *
 * 不依赖 M10 producer 真实推送 — 单测注入事件即可证明消费侧正确;M10 落地后由 reviewer 走 e2e。
 */
export function useAgentStatusBroadcastConsumer(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    const dispose = subscribeUserStream({
      onEvent: (event) => applyAgentStatusEvent(queryClient, event),
      onRecovery: async () => {
        await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      }
    });
    return dispose;
  }, [queryClient]);
}
