import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { listAgents, type AgentSummary } from "../agents/im-agent-config-api";
import { NodeSettingsProfile, listNodes, updateNode } from "../im-settings-api";

const STATUS_DOT_CLASS: Record<string, string> = {
  online: "bg-emerald-500",
  offline: "bg-red-500",
  degraded: "bg-amber-500"
};

const STATUS_PILL_CLASS: Record<string, string> = {
  online: "bg-emerald-50 text-emerald-700 border-emerald-200",
  offline: "bg-red-50 text-red-700 border-red-200",
  degraded: "bg-amber-50 text-amber-700 border-amber-200"
};

function statusLabelKey(status: string): string {
  if (status === "online") return "settings.nodes.statusOnline";
  if (status === "offline") return "settings.nodes.statusOffline";
  if (status === "degraded") return "settings.nodes.statusDegraded";
  return "settings.nodes.statusOffline";
}

export function NodesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });
  const agentsQuery = useQuery({
    queryKey: ["settings", "nodes", "agents"],
    queryFn: listAgents
  });

  const [drafts, setDrafts] = useState<Record<string, NodeSettingsProfile>>({});

  const rows = useMemo(() => {
    return (query.data ?? []).map((node) => drafts[node.node_id] ?? node);
  }, [drafts, query.data]);

  const agentsByNode = useMemo(() => {
    const grouped = new Map<string, AgentSummary[]>();
    for (const agent of agentsQuery.data ?? []) {
      const key = agent.node_id ?? "";
      if (!key) continue;
      const arr = grouped.get(key) ?? [];
      arr.push(agent);
      grouped.set(key, arr);
    }
    return grouped;
  }, [agentsQuery.data]);

  const mutation = useMutation({
    mutationFn: (row: NodeSettingsProfile) =>
      updateNode(row.node_id, {
        alias: row.alias,
        relay_enabled: row.relay_enabled,
        reporting_enabled: row.reporting_enabled
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
    }
  });

  if (query.isLoading) {
    return <p className="text-sm text-slate-500">{t("settings.nodes.loading")}</p>;
  }

  if (rows.length === 0) {
    return (
      <div className="flex h-full flex-col gap-3">
        <h2 className="im-title text-xl font-bold">{t("settings.nodes.title")}</h2>
        <p data-testid="nodes-empty" className="text-sm text-slate-500">
          {t("settings.nodes.empty")}
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <h2 className="im-title text-xl font-bold">{t("settings.nodes.title")}</h2>
      {rows.map((row) => {
        const dotClass = STATUS_DOT_CLASS[row.status] ?? STATUS_DOT_CLASS.offline;
        const pillClass = STATUS_PILL_CLASS[row.status] ?? STATUS_PILL_CLASS.offline;
        const statusText = t(statusLabelKey(row.status));
        const nodeAgents = agentsByNode.get(row.node_id) ?? [];

        return (
          <section key={row.node_id} className="rounded-xl border border-[var(--im-border)] bg-white p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
              <div>
                <p className="font-semibold">{row.node_id}</p>
                <p className="text-xs text-slate-500">{t("settings.nodes.liveName", { name: row.node_name })}</p>
              </div>
              <div className="flex flex-col items-end gap-1 text-right text-xs text-slate-500">
                <span
                  data-testid={`node-status-pill-${row.node_id}`}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${pillClass}`}
                >
                  <span
                    data-status-dot={row.status}
                    className={`inline-block h-2 w-2 rounded-full ${dotClass}`}
                  />
                  {statusText}
                </span>
                <span>{t("settings.nodes.agentsCount", { count: row.agent_count })}</span>
              </div>
            </div>

            <div className="grid gap-2 md:grid-cols-2">
              <label
                className="grid gap-1 text-xs font-semibold text-slate-600"
                htmlFor={`alias-${row.node_id}`}
              >
                {t("settings.nodes.aliasLabel", { nodeId: row.node_id })}
                <input
                  id={`alias-${row.node_id}`}
                  className="im-input"
                  value={row.alias ?? row.node_name}
                  onChange={(event) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [row.node_id]: { ...row, alias: event.target.value }
                    }))
                  }
                />
              </label>

              <div className="grid gap-1 text-xs font-semibold text-slate-600">
                <span>{t("settings.nodes.liveSnapshot")}</span>
                <div className="rounded-lg border border-[var(--im-border)] bg-slate-50 px-3 py-2 text-xs font-normal text-slate-600">
                  <p>
                    {t("settings.nodes.heartbeat")}: {row.last_heartbeat_at || "-"}
                  </p>
                  <p>
                    {t("settings.nodes.version")}: {row.version || "-"}
                  </p>
                  <p>
                    {t("settings.nodes.lastError")}:{" "}
                    {row.last_error ? (
                      <span
                        data-testid={`node-last-error-${row.node_id}`}
                        className="font-medium text-red-600"
                      >
                        {row.last_error}
                      </span>
                    ) : (
                      "-"
                    )}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-2 flex items-center gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.relay_enabled}
                  onChange={(event) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [row.node_id]: { ...row, relay_enabled: event.target.checked }
                    }))
                  }
                />
                {t("settings.nodes.relayEnabled")}
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.reporting_enabled}
                  onChange={(event) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [row.node_id]: { ...row, reporting_enabled: event.target.checked }
                    }))
                  }
                />
                {t("settings.nodes.reportingEnabled")}
              </label>
            </div>

            <div className="mt-3" data-testid={`node-agents-${row.node_id}`}>
              <p className="mb-1 text-xs font-semibold text-slate-600">{t("settings.nodes.agentsOnNode")}</p>
              {nodeAgents.length === 0 ? (
                <p className="text-xs text-slate-400">{t("settings.nodes.agentsOnNodeEmpty")}</p>
              ) : (
                <ul className="flex flex-col gap-1 text-xs">
                  {nodeAgents.map((agent) => (
                    <li key={agent.agent_id}>
                      <Link
                        to={`/settings/agents/${agent.agent_id}`}
                        className="text-slate-700 underline-offset-2 hover:underline"
                      >
                        {agent.display_name || agent.agent_id}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              {row.status === "online" ? (
                <Link className="im-btn im-btn-muted" to={`/settings/nodes/${row.node_id}/agents/new`}>
                  {t("settings.nodes.createAgentOn", { nodeId: row.node_id })}
                </Link>
              ) : null}
              <button
                type="button"
                className="im-btn im-btn-primary"
                onClick={() => mutation.mutate(row)}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? t("settings.nodes.saving") : t("settings.nodes.save", { nodeId: row.node_id })}
              </button>
            </div>
          </section>
        );
      })}
    </div>
  );
}
