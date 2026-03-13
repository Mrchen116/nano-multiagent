import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { listAgentSummaries } from "./im-agent-config-api";

function formatUpdatedAt(value?: string | null) {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function formatBoundNodes(boundNodes?: string[]) {
  if (!boundNodes || boundNodes.length === 0) {
    return "Not bound yet";
  }

  return boundNodes.join(", ");
}

export function AgentsListPage() {
  const isMobile = useIsMobile();
  const query = useQuery({
    queryKey: ["settings", "agents"],
    queryFn: listAgentSummaries
  });

  const agents = query.data ?? [];
  const errorDetail =
    query.error instanceof Error ? query.error.message.split(" failed: ").at(-1) ?? query.error.message : "Unable to load agents right now.";

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="im-title text-xl font-bold">Agents</h2>
          <p className="text-sm text-slate-500">Review prompts, models, and node bindings before opening any detail page.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{query.isLoading ? "Loading…" : `${agents.length} agent${agents.length === 1 ? "" : "s"}`}</span>
          {query.isFetching && !query.isLoading ? (
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600">Refreshing…</span>
          ) : null}
          <Link className="im-btn im-btn-primary" to="/settings/agents/new">
            New Agent
          </Link>
        </div>
      </div>

      {query.isLoading ? (
        <section className="rounded-2xl border border-[var(--im-border)] bg-white/75 p-5 text-sm text-slate-500">
          Loading agents and the latest configuration snapshot...
        </section>
      ) : query.isError ? (
        <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-rose-700">Could not load agents.</p>
            <p className="text-sm text-rose-600">{errorDetail}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void query.refetch()}>
              Retry
            </button>
            <Link className="text-sm font-semibold text-teal-700 hover:underline" to="/settings/agents/new">
              Create an agent manually
            </Link>
          </div>
        </section>
      ) : agents.length === 0 ? (
        <section className="grid gap-3 rounded-2xl border border-dashed border-[var(--im-border)] bg-white/80 p-6">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-900">No agents yet</p>
            <p className="text-sm text-slate-500">Create your first runtime profile to verify prompts, default models, and node routing in one place.</p>
          </div>
          <div>
            <Link className="im-btn im-btn-primary inline-flex" to="/settings/agents/new">
              Create First Agent
            </Link>
          </div>
        </section>
      ) : isMobile ? (
        <div className="grid gap-3">
          {agents.map((agent) => (
            <article key={agent.agent_id} className="rounded-2xl border border-[var(--im-border)] bg-white/80 p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <Link className="font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}`}>
                    {agent.display_name}
                  </Link>
                  <p className="text-xs text-slate-500">{agent.agent_id}</p>
                </div>
                <span className="rounded-full bg-[#dceef0] px-2 py-0.5 text-xs font-semibold text-slate-700">v{agent.profile_version}</span>
              </div>
              <p className="mt-3 text-sm text-slate-600">{agent.description || "No description yet."}</p>
              <dl className="mt-3 grid gap-2 text-xs text-slate-500">
                <div className="flex items-center justify-between gap-3">
                  <dt>Default model</dt>
                  <dd className="text-right text-slate-700">{agent.default_model || "Auto"}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Bound nodes</dt>
                  <dd className="text-right text-slate-700">{formatBoundNodes(agent.bound_nodes)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Updated</dt>
                  <dd className="text-right text-slate-700">{formatUpdatedAt(agent.updated_at)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-[var(--im-border)] bg-white/80">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Agent</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Default Model</th>
                <th className="px-4 py-3">Bound Nodes</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.agent_id} className="border-t border-[var(--im-border)] align-top">
                  <td className="px-4 py-3">
                    <div className="space-y-1">
                      <Link className="font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}`}>
                        {agent.display_name}
                      </Link>
                      <p className="text-xs text-slate-500">{agent.agent_id}</p>
                      <p className="text-xs text-slate-600">{agent.description || "No description yet."}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">v{agent.profile_version}</td>
                  <td className="px-4 py-3">{agent.default_model || "Auto"}</td>
                  <td className="px-4 py-3">{formatBoundNodes(agent.bound_nodes)}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{formatUpdatedAt(agent.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
