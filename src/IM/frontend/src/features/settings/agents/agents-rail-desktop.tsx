import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { AgentRow } from "./agent-row";
import { listAgentSummaries, listNodes } from "./im-agent-config-api";

interface AgentsRailDesktopProps {
  activeId?: string;
  isCreatePage?: boolean;
  onSelectAgent?: (agentId: string) => void;
}

// Shared by agent detail and create pages so their wide-screen navigation stays identical.
export function AgentsRailDesktop({ activeId, isCreatePage = false, onSelectAgent }: AgentsRailDesktopProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["settings", "agents"], queryFn: listAgentSummaries, staleTime: 30_000 });
  const nodesQuery = useQuery({ queryKey: ["settings", "agents", "nodes-status"], queryFn: listNodes, staleTime: 30_000 });
  const agents = query.data ?? [];
  const nodes = nodesQuery.data ?? [];

  function selectAgent(agentId: string) {
    if (onSelectAgent) {
      onSelectAgent(agentId);
      return;
    }
    navigate(`/settings/agents/${agentId}`);
  }

  return (
    <aside
      data-testid="agents-rail-desktop"
      className="hidden bg-[oklch(0.24_0.012_240)] lg:flex lg:w-[240px] lg:flex-col lg:border-r lg:border-[oklch(0.29_0.010_240)]"
      aria-label={t("agents.title")}
    >
      <div className="flex items-center justify-between px-3 py-[10px] border-b border-[oklch(0.29_0.010_240)]">
        <span className="text-[11px] font-bold tracking-[0.08em] uppercase text-[oklch(0.55_0.01_240)]">
          {t("agents.title")}
        </span>
        {isCreatePage ? (
          <button
            className="inline-flex h-9 items-center rounded-lg border-0 px-3 text-[13px] font-semibold text-white"
            style={{ background: "oklch(0.30 0.012 240)", cursor: "default" }}
            type="button"
            disabled
            aria-current="page"
          >
            {t("agents.newButton")}
          </button>
        ) : (
          <Link
            to="/settings/agents/new"
            className="inline-flex h-9 items-center rounded-lg px-3 text-[13px] font-semibold text-white"
            style={{ background: "oklch(0.30 0.012 240)" }}
          >
            {t("agents.newButton")}
          </Link>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-[6px]" aria-label={t("agents.title")}>
        {agents.map((agent) => (
          <AgentRow
            key={agent.agent_id}
            agent={agent}
            nodes={nodes}
            nodesPending={nodesQuery.isPending}
            isActive={agent.agent_id === activeId}
            isMobile={false}
            onSelect={selectAgent}
          />
        ))}
      </nav>
    </aside>
  );
}
