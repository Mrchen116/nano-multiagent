import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { attachUserConversationStream } from "../../chat/im-chat-api";
import { listAgentSummaries, type AgentSummary } from "../agents/im-agent-config-api";
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
    queryFn: listAgentSummaries
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

  const selfUserId = useAuthStore((state) => state.user?.id ?? null);
  const accessToken = useAuthStore((state) => state.accessToken ?? "");

  // node.status_changed is emitted by M10 (owner-scoped) and patched into React
  // Query cache so the status pill / last_heartbeat / last_error reflect heartbeat
  // state in real time without forcing a refetch round trip.
  useEffect(() => {
    if (!selfUserId || !accessToken) return;
    const detach = attachUserConversationStream({
      selfUserId,
      token: accessToken,
      onEvent: (event) => {
        if (event.eventType !== "node.status_changed") return;
        const payload = event.payload as {
          node_id?: unknown;
          status?: unknown;
          last_heartbeat_at?: unknown;
          last_error?: unknown;
        };
        const nodeId = typeof payload.node_id === "string" ? payload.node_id : null;
        const status = typeof payload.status === "string" ? payload.status : null;
        if (!nodeId || !status) return;
        queryClient.setQueryData<NodeSettingsProfile[] | undefined>(["settings", "nodes"], (prev) => {
          if (!prev) return prev;
          let changed = false;
          const next = prev.map((node) => {
            if (node.node_id !== nodeId) return node;
            changed = true;
            return {
              ...node,
              status,
              last_heartbeat_at:
                typeof payload.last_heartbeat_at === "string" ? payload.last_heartbeat_at : node.last_heartbeat_at,
              last_error:
                payload.last_error === null
                  ? null
                  : typeof payload.last_error === "string"
                    ? payload.last_error
                    : node.last_error
            } satisfies NodeSettingsProfile;
          });
          return changed ? next : prev;
        });
        // Live status fields override the draft's read-only snapshot without dropping
        // user-in-progress alias / toggle edits.
        setDrafts((prev) => {
          const draft = prev[nodeId];
          if (!draft) return prev;
          return {
            ...prev,
            [nodeId]: {
              ...draft,
              status,
              last_heartbeat_at:
                typeof payload.last_heartbeat_at === "string" ? payload.last_heartbeat_at : draft.last_heartbeat_at,
              last_error:
                payload.last_error === null
                  ? null
                  : typeof payload.last_error === "string"
                    ? payload.last_error
                    : draft.last_error
            }
          };
        });
      }
    });
    return detach;
  }, [selfUserId, accessToken, queryClient]);

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

  // M19/R11-5: prototype `im-extra-pages.jsx::NodesPage` 顶部 4 KPI 卡 — 视觉契约
  // 用 Tailwind utility 直接落 (white card / oklch border / 24px bold 数字 / 12px 灰 label)。
  const totalNodes = rows.length;
  const onlineCount = rows.filter((r) => r.status === "online").length;
  const offlineCount = rows.filter((r) => r.status === "offline").length;
  const totalAgents = rows.reduce((s, r) => s + (r.agent_count ?? 0), 0);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto bg-[oklch(0.95_0.005_240)] p-[24px_28px]">
      <div>
        <h1 className="m-0 text-[22px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">{t("settings.nodes.title")}</h1>
        <p className="mt-1 text-[13px] text-[oklch(0.55_0.01_240)]">{t("settings.nodes.subtitle")}</p>
      </div>
      <div
        data-testid="nodes-kpi-grid"
        className="grid grid-cols-2 gap-[10px] md:grid-cols-4"
      >
        <div data-testid="nodes-kpi-total" className="rounded-[10px] border border-[oklch(0.87_0.006_240)] bg-white px-[14px] py-[12px]">
          <p className="m-0 text-[24px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">{totalNodes}</p>
          <p className="mt-[3px] text-[12px] text-[oklch(0.55_0.01_240)]">{t("settings.nodes.kpiTotal")}</p>
        </div>
        <div data-testid="nodes-kpi-online" className="rounded-[10px] border border-[oklch(0.87_0.006_240)] bg-white px-[14px] py-[12px]">
          <p className="m-0 text-[24px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">{onlineCount}</p>
          <p className="mt-[3px] text-[12px] text-[oklch(0.55_0.01_240)]">{t("settings.nodes.kpiOnline")}</p>
        </div>
        <div data-testid="nodes-kpi-offline" className="rounded-[10px] border border-[oklch(0.87_0.006_240)] bg-white px-[14px] py-[12px]">
          <p className="m-0 text-[24px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">{offlineCount}</p>
          <p className="mt-[3px] text-[12px] text-[oklch(0.55_0.01_240)]">{t("settings.nodes.kpiOffline")}</p>
        </div>
        <div data-testid="nodes-kpi-agents" className="rounded-[10px] border border-[oklch(0.87_0.006_240)] bg-white px-[14px] py-[12px]">
          <p className="m-0 text-[24px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">{totalAgents}</p>
          <p className="mt-[3px] text-[12px] text-[oklch(0.55_0.01_240)]">{t("settings.nodes.kpiAgents")}</p>
        </div>
      </div>
      {rows.map((row) => {
        const dotClass = STATUS_DOT_CLASS[row.status] ?? STATUS_DOT_CLASS.offline;
        const pillClass = STATUS_PILL_CLASS[row.status] ?? STATUS_PILL_CLASS.offline;
        const statusText = t(statusLabelKey(row.status));
        const nodeAgents = agentsByNode.get(row.node_id) ?? [];
        const isOnline = row.status === "online";

        return (
          <section
            key={row.node_id}
            className="rounded-[14px] border border-[oklch(0.87_0.006_240)] bg-white overflow-hidden"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[oklch(0.87_0.006_240)] px-[18px] py-[14px]">
              <div className="flex items-center gap-3">
                <span
                  data-testid={`node-icon-${row.node_id}`}
                  className={
                    "flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[10px] text-[16px] " +
                    (isOnline ? "bg-[oklch(0.92_0.08_145)]" : "bg-[oklch(0.92_0.005_240)]")
                  }
                  aria-hidden="true"
                >
                  {isOnline ? "🖥" : "💤"}
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="m-0 text-[14px] font-extrabold text-[oklch(0.14_0.01_240)]">{row.alias ?? row.node_name}</h3>
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
                  </div>
                  <p className="m-0 mt-[2px] font-mono text-[11.5px] text-[oklch(0.55_0.01_240)]">{row.node_id}</p>
                </div>
              </div>
              <div className="flex shrink-0 gap-[14px] text-right text-[12px] text-[oklch(0.55_0.01_240)]">
                <span>
                  <b data-testid={`node-agent-count-${row.node_id}`} className="text-[15px] text-[oklch(0.25_0.01_240)]">{row.agent_count}</b><br />
                  {t("settings.nodes.agentsShort")}
                </span>
                <span>
                  <b data-testid={`node-version-${row.node_id}`} className="text-[15px] text-[oklch(0.25_0.01_240)]">v{row.version}</b><br />
                  {t("settings.nodes.versionShort")}
                </span>
              </div>
            </div>

            <div className="grid gap-[14px] px-[18px] py-[14px]">
              <div className="grid items-start gap-[14px] md:grid-cols-2">
                <label
                  className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]"
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

                <div className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
                  <span>{t("settings.nodes.liveSnapshot")}</span>
                  <div className="rounded-[8px] border border-[oklch(0.87_0.006_240)] bg-[oklch(0.95_0.005_240)] px-3 py-2 font-mono text-[12px] font-normal text-[oklch(0.25_0.01_240)]">
                    <div className="flex justify-between">
                      <span className="text-[oklch(0.55_0.01_240)]">{t("settings.nodes.heartbeat")}</span>
                      <span>{row.last_heartbeat_at ? new Date(row.last_heartbeat_at).toLocaleTimeString() : "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[oklch(0.55_0.01_240)]">{t("settings.nodes.version")}</span>
                      <span>{row.version || "—"}</span>
                    </div>
                    {row.last_error ? (
                      <div
                        data-testid={`node-last-error-${row.node_id}`}
                        className="mt-1 rounded-[6px] bg-[oklch(0.96_0.06_25)] px-2 py-1 text-[11px] leading-snug text-[oklch(0.45_0.14_25)]"
                      >
                        ⚠ {row.last_error}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              <div data-testid={`node-agents-${row.node_id}`}>
                <p className="mb-1 text-[12px] font-semibold text-[oklch(0.30_0.01_240)]">{t("settings.nodes.agentsOnNode")}</p>
                {nodeAgents.length === 0 ? (
                  <p className="text-[12px] text-[oklch(0.65_0.01_240)]">{t("settings.nodes.agentsOnNodeEmpty")}</p>
                ) : (
                  <ul className="flex flex-col gap-1 text-[12px]">
                    {nodeAgents.map((agent) => (
                      <li key={agent.agent_id}>
                        <Link
                          to={`/settings/agents/${agent.agent_id}`}
                          className="text-[oklch(0.30_0.01_240)] underline-offset-2 hover:underline"
                        >
                          {agent.display_name || agent.agent_id}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3 border-t border-[oklch(0.91_0.005_240)] pt-2">
                {isOnline ? (
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
            </div>
          </section>
        );
      })}
    </div>
  );
}
