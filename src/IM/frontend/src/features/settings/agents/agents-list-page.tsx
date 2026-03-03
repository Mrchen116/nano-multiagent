import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listAgents } from "../mock-settings-api";

export function AgentsListPage() {
  const query = useQuery({
    queryKey: ["settings", "agents"],
    queryFn: listAgents
  });

  if (query.isLoading) {
    return <p className="text-sm text-slate-500">Loading agents...</p>;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="im-title text-xl font-bold">Agents</h2>
        <span className="text-xs text-slate-500">{query.data?.length ?? 0} items</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2">Agent</th>
              <th className="pb-2">Version</th>
              <th className="pb-2">Bound Nodes</th>
              <th className="pb-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {(query.data ?? []).map((agent) => (
              <tr key={agent.agent_id} className="border-t border-[var(--im-border)]">
                <td className="py-2">
                  <Link className="font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}`}>
                    {agent.display_name}
                  </Link>
                </td>
                <td className="py-2">{agent.profile_version}</td>
                <td className="py-2">{agent.bound_nodes.join(", ")}</td>
                <td className="py-2 text-xs text-slate-500">{new Date(agent.updated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
