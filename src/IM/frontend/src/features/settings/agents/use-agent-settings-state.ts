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
  const initialRead = useRef(true);
  const initialRecovery = useRef(true);
  const [streamReady, setStreamReady] = useState(true);
  const prefix = ["settings", "agents", agentId];
  const key = [...prefix, "detail-state"];
  const saved = useQuery({
    queryKey: [...prefix, "saved"],
    queryFn: ({signal}) => getAgentDetailState(agentId, signal, true),
    staleTime: 0,
    retry: false,
  });
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
      initialRead.current = false;
      generation.current += 1;
      await client.cancelQueries({queryKey: prefix});
      client.setQueryData<AgentDetailState>([...prefix, "detail-state"], current => current ? {...current, ready: false} : current);
      await client.invalidateQueries({queryKey: prefix});
    };
    return subscribeUserStream({
      onEvent: event => {
        if (event.eventType === "agent.status_changed" && event.payload.agent_id === agentId) {
          initialRead.current = false;
          generation.current += 1;
        }
        applyAgentStatusEvent(client, event);
      },
      onRecovery: async () => {
        const first = initialRecovery.current;
        initialRecovery.current = false;
        // Initial stream sync is not a node reconnect. The in-flight API read
        // already fences identity/version at completion; join it instead of
        // cancelling it and locking a freshly obtained draft a second time.
        if (first && streamAvailable.current && client.getQueryState(key)?.fetchStatus === 'fetching') {
          await client.invalidateQueries({queryKey:key},{cancelRefetch:false});
          return;
        }
        await invalidate();
      },
      onConnectionStatus: status => {
        const available = status === null;
        if (available === streamAvailable.current) return;
        initialRead.current = false;
        streamAvailable.current = available;
        setStreamReady(available);
        generation.current += 1;
        void client.cancelQueries({queryKey: prefix});
        client.setQueryData<AgentDetailState>([...prefix, "detail-state"], current => current ? {...current, ready: false} : current);
        if (available) void client.invalidateQueries({queryKey: prefix});
      },
    });
  }, [agentId, client]);
  const data = query.data ?? saved.data;
  const nodeState = streamReady ? data?.config.node_status ?? "unknown" : "unknown";
  const connectionReadOnly = nodeState !== "online";
  // Editing a draft does not submit it. Fresh capability/version confirmation
  // remains mandatory at the save boundary, including after reconnection.
  const savedDraftCurrent = !!saved.data && initialRead.current && saved.isFetchedAfterMount && !saved.isFetching &&
    !saved.data?.display.error && saved.data?.config.profile_version === data?.config.profile_version;
  const denied = [401,403,404].includes((query.error as {status?:number}|null)?.status ?? 0);
  const readOnly = denied || connectionReadOnly || !!data?.pendingOperation || (!data?.ready && !savedDraftCurrent);
  const reason = nodeState === "offline" ? "offline" : nodeState !== "online" ? "unknown"
    : query.isFetching ? (readOnly ? "refreshing" : "refreshingEditable") : query.data?.pendingOperation ? "pending"
    : readOnly ? "failed" : query.isError || !data?.ready ? 'failedEditable' : null;
  return {query: {...query, data, isLoading: query.isLoading && saved.isLoading}, nodeState, connectionReadOnly, readOnly, reason};
}
