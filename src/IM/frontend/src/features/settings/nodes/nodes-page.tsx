import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { NodeSettingsProfile, listNodes, updateNode } from "../im-settings-api";

export function NodesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });

  const [drafts, setDrafts] = useState<Record<string, NodeSettingsProfile>>({});

  const rows = useMemo(() => {
    return (query.data ?? []).map((node) => drafts[node.node_id] ?? node);
  }, [drafts, query.data]);

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
    return <p className="text-sm text-slate-500">Loading nodes...</p>;
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <h2 className="im-title text-xl font-bold">Nodes</h2>
      {rows.map((row) => (
        <section key={row.node_id} className="rounded-xl border border-[var(--im-border)] bg-white p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
            <div>
              <p className="font-semibold">{row.node_id}</p>
              <p className="text-xs text-slate-500">live name: {row.node_name}</p>
            </div>
            <div className="text-right text-xs text-slate-500">
              <p>status: {row.status}</p>
              <p>agents: {row.agent_count}</p>
            </div>
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            <label className="grid gap-1 text-xs font-semibold text-slate-600" htmlFor={`alias-${row.node_id}`}>
              Alias {row.node_id}
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
              <span>Live Snapshot</span>
              <div className="rounded-lg border border-[var(--im-border)] bg-slate-50 px-3 py-2 text-xs font-normal text-slate-600">
                <p>Heartbeat: {row.last_heartbeat_at || "-"}</p>
                <p>Version: {row.version || "-"}</p>
                <p>Last Error: {row.last_error || "-"}</p>
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
              Relay Enabled
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
              Report Enabled
            </label>
          </div>

          <button
            type="button"
            className="im-btn im-btn-primary mt-3"
            onClick={() => mutation.mutate(row)}
            disabled={mutation.isPending}
          >
            Save {row.node_id}
          </button>
        </section>
      ))}
    </div>
  );
}
