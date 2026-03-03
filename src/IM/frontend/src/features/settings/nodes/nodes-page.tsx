import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { NodeProfile, listNodes, updateNode } from "../mock-settings-api";

export function NodesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });

  const [drafts, setDrafts] = useState<Record<string, NodeProfile>>({});

  const rows = useMemo(() => {
    return (query.data ?? []).map((node) => drafts[node.node_id] ?? node);
  }, [drafts, query.data]);

  const mutation = useMutation({
    mutationFn: (row: NodeProfile) => updateNode(row.node_id, row),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
    }
  });

  if (query.isLoading) {
    return <p className="text-sm text-slate-500">Loading nodes...</p>;
  }

  return (
    <div className="grid gap-3">
      <h2 className="im-title text-xl font-bold">Nodes</h2>
      {rows.map((row) => (
        <section key={row.node_id} className="rounded-xl border border-[var(--im-border)] bg-white p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
            <p className="font-semibold">{row.node_id}</p>
            <p className="text-xs text-slate-500">status: {row.status}</p>
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            <label className="grid gap-1 text-xs font-semibold text-slate-600" htmlFor={`alias-${row.node_id}`}>
              Alias {row.node_id}
              <input
                id={`alias-${row.node_id}`}
                className="im-input"
                value={row.node_name}
                onChange={(event) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.node_id]: { ...row, node_name: event.target.value }
                  }))
                }
              />
            </label>

            <label className="grid gap-1 text-xs font-semibold text-slate-600" htmlFor={`cfg-${row.node_id}`}>
              Desired Config Version
              <input
                id={`cfg-${row.node_id}`}
                className="im-input"
                value={row.desired_config_version}
                onChange={(event) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.node_id]: { ...row, desired_config_version: event.target.value }
                  }))
                }
              />
            </label>
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
                checked={row.report_enabled}
                onChange={(event) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.node_id]: { ...row, report_enabled: event.target.checked }
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
