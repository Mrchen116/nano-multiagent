import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { AgentRow } from "./agent-row";
import { useAgentStatusBroadcastConsumer } from "./agent-status-ws-consumer";
import { listAgentSummaries, listNodes } from "./im-agent-config-api";

export function AgentsListPage() {
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  const navigate = useNavigate();
  useAgentStatusBroadcastConsumer();
  const agentsQuery = useQuery({ queryKey: ["settings", "agents"], queryFn: listAgentSummaries });
  const nodesQuery = useQuery({ queryKey: ["settings", "agents", "nodes-status"], queryFn: listNodes });

  const { agentId: activeAgentId } = useParams<{ agentId?: string }>();
  const agents = agentsQuery.data ?? [];
  const nodes = nodesQuery.data ?? [];
  const newAgentPath = "/settings/agents/new";
  const errorDetail =
    agentsQuery.error instanceof Error
      ? agentsQuery.error.message.split(" failed: ").at(-1) ?? agentsQuery.error.message
      : null;

  // Prototype: im-settings-page.jsx:12-75 AgentListView
  // Desktop: dark sidebar 240px; Mobile: light full-width
  const sidebarBg = isMobile ? "oklch(0.93 0.007 240)" : "oklch(0.24 0.012 240)";
  const borderColor = isMobile ? "oklch(0.87 0.006 240)" : "oklch(0.29 0.010 240)";

  return (
    <div
      className="flex flex-col flex-1 min-h-0"
      style={{
        width: isMobile ? "100%" : 240,
        flex: isMobile ? 1 : undefined,
        background: sidebarBg,
        borderRight: isMobile ? "none" : `1px solid ${borderColor}`,
      }}
      data-testid="agents-list"
    >
      {/* Header */}
      <div
        style={{
          padding: isMobile ? "10px 16px 12px" : "14px 12px 10px",
          borderBottom: `1px solid ${borderColor}`,
        }}
      >
        {isMobile ? (
          <div className="relative flex h-9 items-center justify-center">
            <h1
              className="m-0 text-[17px] font-bold tracking-tight text-[oklch(0.14_0.01_240)]"
            >
              {t("agents.title")}
            </h1>
            <Link
              to={newAgentPath}
              className="absolute right-0 top-0 inline-flex h-9 items-center rounded-[10px] border-none px-[14px] text-[13px] font-semibold text-white"
              style={{ background: "oklch(0.52 0.14 180)" }}
            >
              {t("agents.newButton")}
            </Link>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <span
              className="text-[11px] font-bold tracking-[0.08em] uppercase text-[oklch(0.55_0.01_240)]"
            >
              {t("agents.title")}
            </span>
            <Link
              to={newAgentPath}
              className="inline-flex h-9 items-center rounded-lg border-none px-3 text-[13px] font-semibold text-white"
              style={{ background: "oklch(0.30 0.012 240)" }}
            >
              {t("agents.newButton")}
            </Link>
          </div>
        )}
      </div>

      {/* Body */}
      <div
        className="flex-1 overflow-y-auto"
        style={{ padding: isMobile ? "8px 10px" : "6px 8px" }}
      >
        {agentsQuery.isLoading ? (
          <p className="p-2 text-[13px] text-[oklch(0.55_0.01_240)]">{t("common.loading")}</p>
        ) : agentsQuery.isError ? (
          <section className="m-2 p-4 rounded-xl border border-[oklch(0.29_0.010_240)] bg-[oklch(0.28_0.012_240)] flex flex-col gap-2 text-[13px]">
            <p className="font-bold m-0 text-white">{t("agents.loadError")}</p>
            {errorDetail ? <p className="m-0 text-[11px] text-[oklch(0.50_0.01_240)]">{errorDetail}</p> : null}
            <button
              type="button"
              onClick={() => void agentsQuery.refetch()}
              className="inline-flex items-center rounded-lg border-none px-3 py-1.5 text-[13px] font-semibold text-white"
              style={{ background: "oklch(0.30 0.012 240)" }}
            >
              {t("agents.retry")}
            </button>
          </section>
        ) : agents.length === 0 ? (
          <section className="m-2 p-4 rounded-xl border border-[oklch(0.87_0.006_240)] bg-white flex flex-col gap-2 text-[13px]">
            <p className="font-bold m-0 text-[oklch(0.21_0.012_240)]">{t("agents.empty.title")}</p>
            <p className="m-0 text-[11px] text-[oklch(0.50_0.01_240)]">{t("agents.empty.body")}</p>
            <Link
              to="/settings/nodes"
              className="inline-flex items-center rounded-lg border-none px-3 py-1.5 text-[13px] font-semibold text-white"
              style={{ background: "oklch(0.52 0.14 180)" }}
            >
              {t("agents.openNodes")}
            </Link>
          </section>
        ) : (
          <nav aria-label={t("agents.title")}>
            {agents.map((agent) => (
              <AgentRow
                key={agent.agent_id}
                agent={agent}
                nodes={nodes}
                isActive={agent.agent_id === activeAgentId}
                isMobile={isMobile}
                onSelect={(agentId) => navigate(`/settings/agents/${agentId}`)}
              />
            ))}
          </nav>
        )}
      </div>
    </div>
  );
}
