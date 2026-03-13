import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { listAgentSummaries } from "./im-agent-config-api";

export function AgentsListPage() {
  const isMobile = useIsMobile();
  const query = useQuery({
    queryKey: ["settings", "agents"],
    queryFn: listAgentSummaries
  });

  if (query.isLoading) {
    return <p className="text-sm text-slate-500">Loading agents...</p>;
  }

  const agents = query.data ?? [];

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="im-title text-xl font-bold">Agents</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{agents.length} items</span>
          <Link className="im-btn im-btn-primary" to="/settings/agents/new">
            New Agent
          </Link>
        </div>
      </div>
      {isMobile ? (
        <div className="grid gap-3">
          {agents.map((agent) => (
            <article key={agent.agent_id} className="rounded-xl border border-[var(--im-border)] bg-white/70 p-3">
              <div className="flex items-start justify-between gap-3">
                <Link className="font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}`}>
                  {agent.display_name}
                </Link>
                <span className="rounded-full bg-[#dceef0] px-2 py-0.5 text-xs font-semibold text-slate-700">
                  {agent.profile_version}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-600">Bound nodes: {(agent.bound_nodes ?? []).join(", ") || "—"}</p>
              <p className="mt-1 text-xs text-slate-500">Updated: {agent.updated_at ? new Date(agent.updated_at).toLocaleString() : "—"}</p>
            </article>
          ))}
        </div>
      ) : (
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
              {agents.map((agent) => (
                <tr key={agent.agent_id} className="border-t border-[var(--im-border)]">
                  <td className="py-2">
                    <Link className="font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}`}>
                      {agent.display_name}
                    </Link>
                  </td>
                  <td className="py-2">{agent.profile_version}</td>
                  <td className="py-2">{(agent.bound_nodes ?? []).join(", ") || "—"}</td>
                  <td className="py-2 text-xs text-slate-500">{agent.updated_at ? new Date(agent.updated_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
