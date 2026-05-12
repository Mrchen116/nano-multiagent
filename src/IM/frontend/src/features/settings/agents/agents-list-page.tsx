import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { useAgentStatusBroadcastConsumer } from "./agent-status-ws-consumer";
import { listAgentSummaries, listNodes, type AgentSummary, type NodeSummary } from "./im-agent-config-api";

function initialsOf(displayName: string): string {
  const trimmed = displayName.trim();
  if (!trimmed) return "AG";
  return trimmed.slice(0, 2).toUpperCase();
}

function statusOf(agent: AgentSummary, nodes: NodeSummary[]): "online" | "offline" {
  if (agent.node_status === "online") return "online";
  if (agent.node_status === "offline") return "offline";
  if (!agent.node_id) return "offline";
  const node = nodes.find((n) => n.node_id === agent.node_id);
  return node?.status === "online" ? "online" : "offline";
}

function AgentRow(props: { agent: AgentSummary; status: "online" | "offline"; isMobile: boolean }) {
  const { agent, status, isMobile } = props;
  const initials = initialsOf(agent.display_name);
  return (
    <Link
      to={`/settings/agents/${agent.agent_id}`}
      className={`im-agent-row${isMobile ? " is-mobile" : ""}`}
      aria-label={agent.display_name}
    >
      <span className="im-agent-row-avatar" aria-hidden="true">
        {initials}
      </span>
      <span className="im-agent-row-text">
        <span className="im-agent-row-name">{agent.display_name}</span>
        <span className="im-agent-row-sub">{isMobile ? agent.description || agent.agent_id : agent.agent_id}</span>
      </span>
      <span
        className={`im-agent-row-status ${status}`}
        aria-label={`${agent.agent_id} ${status}`}
        role="status"
      />
      {isMobile ? (
        <span
          data-testid={`agent-row-chevron-${agent.agent_id}`}
          aria-hidden="true"
          className="ml-1 flex-shrink-0 text-[18px] font-light text-[oklch(0.70_0.01_240)]"
        >
          ›
        </span>
      ) : null}
    </Link>
  );
}

export function AgentsListPage() {
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  useAgentStatusBroadcastConsumer();
  const agentsQuery = useQuery({ queryKey: ["settings", "agents"], queryFn: listAgentSummaries });
  const nodesQuery = useQuery({ queryKey: ["settings", "agents", "nodes-status"], queryFn: listNodes });

  const agents = agentsQuery.data ?? [];
  const nodes = nodesQuery.data ?? [];
  const errorDetail =
    agentsQuery.error instanceof Error
      ? agentsQuery.error.message.split(" failed: ").at(-1) ?? agentsQuery.error.message
      : null;

  return (
    <div className={`im-agents-list${isMobile ? " is-mobile" : ""}`} data-testid="agents-list">
      {/* M20/R12-bis-7: mobile title centered with absolute-positioned + New button. */}
      {isMobile ? (
        <header className="relative flex h-12 items-center justify-center border-b border-[oklch(0.91_0.005_240)] px-3">
          <h2
            data-testid="agents-mobile-title-centered"
            className="m-0 text-[17px] font-bold tracking-tight text-[oklch(0.14_0.01_240)]"
          >
            {t("agents.title")}
          </h2>
          <Link
            className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center rounded-lg bg-[oklch(0.52_0.14_180)] px-3 py-1.5 text-[13px] font-semibold text-white"
            to="/settings/nodes"
          >
            {t("agents.newButton")}
          </Link>
        </header>
      ) : (
        <header className="im-agents-list-header">
          <h2 className="im-agents-list-title">{t("agents.title")}</h2>
          <Link className="im-btn im-btn-primary im-agents-new-btn" to="/settings/nodes">
            {t("agents.newButton")}
          </Link>
        </header>
      )}

      <div className="im-agents-list-body">
        {agentsQuery.isLoading ? (
          <p className="im-agents-list-status">{t("common.loading")}</p>
        ) : agentsQuery.isError ? (
          <section className="im-agents-list-error">
            <p className="im-agents-list-error-title">{t("agents.loadError")}</p>
            {errorDetail ? <p className="im-agents-list-error-detail">{errorDetail}</p> : null}
            <button className="im-btn im-btn-muted" type="button" onClick={() => void agentsQuery.refetch()}>
              {t("agents.retry")}
            </button>
          </section>
        ) : agents.length === 0 ? (
          <section className="im-agents-list-empty">
            <p className="im-agents-list-empty-title">{t("agents.empty.title")}</p>
            <p className="im-agents-list-empty-body">{t("agents.empty.body")}</p>
            <Link className="im-btn im-btn-primary" to="/settings/nodes">
              {t("agents.openNodes")}
            </Link>
          </section>
        ) : (
          <nav className="im-agents-list-nav" aria-label={t("agents.title")}>
            {agents.map((agent) => (
              <AgentRow
                key={agent.agent_id}
                agent={agent}
                status={statusOf(agent, nodes)}
                isMobile={isMobile}
              />
            ))}
          </nav>
        )}
      </div>
    </div>
  );
}
