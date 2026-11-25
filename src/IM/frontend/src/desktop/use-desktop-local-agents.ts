import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useMemo } from "react";
import { accountEnabled, useAuthStore } from "../features/auth/auth-store";
import { inspectDesktopLocalNode } from "./desktop-api";
import { isDesktopClient } from "./desktop-context";

/** Context carrying the `agent_id` whose workspace owns relative paths in the current subtree. */
export const WorkspaceAgentContext = createContext<string | null>(null);

export function useWorkspaceAgentId(): string | null {
  return useContext(WorkspaceAgentContext);
}

/** Return the set of `agent_id`s belonging to the currently authorized local node in Desktop mode. */
export function useDesktopLocalAgentMap(): ReadonlyMap<string, { display_name: string; workspace_root: string }> {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const enabled = isDesktopClient() && Boolean(user && accessToken && accountEnabled(user));

  const query = useQuery({
    queryKey: ["desktop", "local-node", user?.id],
    queryFn: () => inspectDesktopLocalNode(),
    enabled,
    staleTime: 10_000,
  });

  return useMemo(() => {
    const map = new Map<string, { display_name: string; workspace_root: string }>();
    const data = query.data;
    if (!data) return map;
    if (data.ownership !== "managed_online" && data.ownership !== "managed_stopped") return map;
    for (const agent of data.agents ?? []) {
      map.set(agent.agent_id, { display_name: agent.display_name, workspace_root: agent.workspace_root });
    }
    return map;
  }, [query.data]);
}
