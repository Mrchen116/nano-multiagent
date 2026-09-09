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

  // Desktop and mobile share the navigation palette.
  const sidebarBg = "var(--im-sidebar)";
  const borderColor = "var(--im-border)";

  return (
    <div className="agents-overview">
      <div
        className="flex flex-col flex-1 min-h-0"
        style={{
          width: isMobile ? "100%" : 240,
          flex: isMobile ? 1 : "0 0 240px",
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
                style={{ background: "var(--im-accent)" }}
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
                style={{ background: "var(--im-accent)" }}
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
            <section className="m-2 p-4 rounded-xl border border-im-border bg-im-surface flex flex-col gap-2 text-[13px]">
              <p className="font-bold m-0 text-im-text">{t("agents.loadError")}</p>
              {errorDetail ? <p className="m-0 text-[11px] text-[oklch(0.50_0.01_240)]">{errorDetail}</p> : null}
              <button
                type="button"
                onClick={() => void agentsQuery.refetch()}
                className="inline-flex items-center rounded-lg border-none px-3 py-1.5 text-[13px] font-semibold text-white"
                style={{ background: "var(--im-accent)" }}
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
                style={{ background: "var(--im-accent)" }}
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
                  nodesPending={nodesQuery.isPending}
                  isActive={agent.agent_id === activeAgentId}
                  isMobile={isMobile}
                  onSelect={(agentId) => navigate(`/settings/agents/${agentId}`)}
                />
              ))}
            </nav>
          )}
        </div>
      </div>
      {!isMobile && (
        <section className="agents-selection-empty">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="4" y="6" width="16" height="14" rx="4" /><path d="M12 3v3M8 12h.01M16 12h.01M9 16h6" />
          </svg>
          <h1>{t("agents.selectTitle")}</h1>
          <p>{t("agents.selectBody")}</p>
        </section>
      )}
    </div>
  );
}
