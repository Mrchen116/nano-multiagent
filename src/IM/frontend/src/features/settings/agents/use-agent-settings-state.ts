import {useEffect, useRef, useState} from "react";
import {useQuery, useQueryClient} from "@tanstack/react-query";
import {subscribeUserStream} from "../../../realtime/user-stream";
import {applyAgentStatusEvent} from "./agent-status-ws-consumer";
import {getAgentDetailState, type AgentDetailState} from "./im-agent-config-api";

/** Keep the settings read generation separate from saved configuration and form drafts. */
export function useAgentSettingsState(agentId: string) {
  const client = useQueryClient();
  const generation = useRef(0);
  const streamAvailable = useRef(true);
  const [streamReady, setStreamReady] = useState(true);
  const prefix = ["settings", "agents", agentId];
  const key = [...prefix, "detail-state"];
  const query = useQuery({
    queryKey: key,
    queryFn: async ({signal}) => {
      const started = generation.current;
      const result = await getAgentDetailState(agentId, signal);
      if (signal.aborted || generation.current !== started) throw new DOMException("Superseded settings read", "AbortError");
      return result;
    },
    staleTime: 0,
    retry: false,
    refetchInterval: state => state.state.data?.pendingOperation ? 1000 : false,
  });
  useEffect(() => {
    const prefix = ["settings", "agents", agentId];
    const invalidate = async () => {
      generation.current += 1;
      await client.cancelQueries({queryKey: prefix});
      client.setQueryData<AgentDetailState>([...prefix, "detail-state"], current => current ? {...current, ready: false} : current);
      await client.invalidateQueries({queryKey: prefix});
    };
    return subscribeUserStream({
      onEvent: event => {
        if (event.eventType === "agent.status_changed" && event.payload.agent_id === agentId) generation.current += 1;
        applyAgentStatusEvent(client, event);
      },
      onRecovery: invalidate,
      onConnectionStatus: status => {
        const available = status === null;
        if (available === streamAvailable.current) return;
        streamAvailable.current = available;
        setStreamReady(available);
        generation.current += 1;
        void client.cancelQueries({queryKey: prefix});
        client.setQueryData<AgentDetailState>([...prefix, "detail-state"], current => current ? {...current, ready: false} : current);
        if (available) void client.invalidateQueries({queryKey: prefix});
      },
    });
  }, [agentId, client]);
  const nodeState = streamReady ? query.data?.config.node_status ?? "unknown" : "unknown";
  const connectionReadOnly = nodeState !== "online";
  const readOnly = connectionReadOnly || query.isFetching || query.isError || !query.data?.ready;
  const reason = nodeState === "offline" ? "offline" : nodeState !== "online" ? "unknown"
    : query.isFetching ? "refreshing" : query.data?.pendingOperation ? "pending"
    : readOnly ? "failed" : null;
  return {query, nodeState, connectionReadOnly, readOnly, reason};
}
