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

function workspaceSourceLabel(isDefault: boolean | undefined) {
  return isDefault ? "Managed default" : "Custom path";
}

function AgentSummaryCard(props: {
  agent: {
    agent_id: string;
    display_name: string;
    description?: string | null;
    profile_version: number;
    default_model?: string | null;
    workspace_root: string;
    workspace_is_default?: boolean;
    bound_nodes?: string[];
    updated_at?: string | null;
  };
  compact?: boolean;
}) {
  const { agent, compact = false } = props;

  return (
    <article className={`rounded-[1.35rem] border border-[var(--im-border)] bg-white/85 shadow-sm ${compact ? "p-4" : "p-5"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link className="font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}`}>
              {agent.display_name}
            </Link>
            <span className="rounded-full bg-[#dceef0] px-2 py-0.5 text-xs font-semibold text-slate-700">v{agent.profile_version}</span>
          </div>
          <p className="text-xs text-slate-500">{agent.agent_id}</p>
        </div>
        <span className="im-badge">Stable direct chat</span>
      </div>

      <p className={`mt-3 text-slate-600 ${compact ? "text-sm" : "text-sm leading-6"}`}>{agent.description || "No description yet."}</p>

      {compact ? (
        <>
          <dl className="mt-3 grid gap-2 text-xs text-slate-500">
            <div className="flex items-center justify-between gap-3">
              <dt>Default model</dt>
              <dd className="text-right text-slate-700">{agent.default_model || "Auto"}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt>Runtime mode</dt>
              <dd className="text-right text-slate-700">{workspaceSourceLabel(agent.workspace_is_default)}</dd>
            </div>
            <div className="grid gap-1">
              <dt>Current runtime directory</dt>
              <dd className="break-all font-mono text-[11px] text-slate-700">{agent.workspace_root}</dd>
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
          <div className="mt-3">
            <Link className="text-sm font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}#workspace-settings`}>
              Workspace settings
            </Link>
          </div>
        </>
      ) : (
        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-start">
          <section className="im-subtle-card grid gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Runtime</p>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-900">{workspaceSourceLabel(agent.workspace_is_default)}</p>
              <p className="text-xs text-slate-500">Current runtime directory</p>
              <p className="break-all font-mono text-[11px] text-slate-700">{agent.workspace_root}</p>
            </div>
          </section>
          <section className="im-subtle-card grid gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Access</p>
            <div className="space-y-1 text-sm text-slate-700">
              <p>Default model: {agent.default_model || "Auto"}</p>
              <p>Bound nodes: {formatBoundNodes(agent.bound_nodes)}</p>
              <p className="text-xs text-slate-500">Updated {formatUpdatedAt(agent.updated_at)}</p>
            </div>
          </section>
          <div className="flex lg:justify-end">
            <Link className="text-sm font-semibold text-teal-700 hover:underline" to={`/settings/agents/${agent.agent_id}#workspace-settings`}>
              Workspace settings
            </Link>
          </div>
        </div>
      )}
    </article>
  );
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
        <div className="max-w-2xl space-y-1">
          <h2 className="im-title text-xl font-bold">Agents</h2>
          <p className="text-sm text-slate-500">Review each agent's role, access, and runtime placement before opening settings.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
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
            <AgentSummaryCard key={agent.agent_id} agent={agent} compact />
          ))}
        </div>
      ) : (
        <section className="grid gap-4 rounded-[1.35rem] border border-[var(--im-border)] bg-white/75 p-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Active agents</p>
              <p className="text-sm text-slate-600">{agents.length} profiles</p>
            </div>
          </div>
          <div className="grid gap-4">
            {agents.map((agent) => (
              <AgentSummaryCard key={agent.agent_id} agent={agent} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
