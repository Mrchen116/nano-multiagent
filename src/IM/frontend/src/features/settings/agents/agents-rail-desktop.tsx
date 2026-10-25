import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { AgentRow } from "./agent-row";
import { PersonalAgentEntry, configuredPersonalAgent, usePersonalAgentEntry } from "./personal-agent-entry";
import { listPublicAgents } from "./public-agents";
import { useAuthStore } from "../../auth/auth-store";

interface AgentsRailDesktopProps {
  activeId?: string;
  isCreatePage?: boolean;
  onSelectAgent?: (agentId: string) => void;
}

// Shared by agent detail and create pages so their wide-screen navigation stays identical.
export function AgentsRailDesktop({ activeId, isCreatePage = false, onSelectAgent }: AgentsRailDesktopProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const self = useAuthStore(s => s.user?.id);
  const query = useQuery({ queryKey: ["public-agents", self], queryFn: listPublicAgents, refetchInterval: 3000, staleTime: 30_000 });
  const [search, setSearch] = useState("");
  const agents = query.data ?? [];
  const personal = usePersonalAgentEntry();
  const personalBinding = configuredPersonalAgent(personal.data);
  const nodes: [] = [];

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
      className="im-agent-settings-rail hidden bg-[var(--im-sidebar)] lg:flex lg:flex-col lg:border-r lg:border-im-border"
      aria-label={t("agents.title")}
    >
      <header>
        <span className="text-[11px] font-bold tracking-[0.08em] uppercase text-[oklch(0.55_0.01_240)]">
          {t("agents.title")}
        </span>
        {isCreatePage ? (
          <span
            className="im-settings-create"
            aria-current="page"
          >
            {t("agents.newButton")}
          </span>
        ) : (
          <Link
            to="/settings/agents/new"
            className="im-settings-create"

          >
            {t("agents.newButton")}
          </Link>
        )}
      </header>
      <input type="search" className="chat-sidebar-search" aria-label={t("agents.search")} placeholder={t("agents.search")} value={search} onChange={e => setSearch(e.target.value)} />
      <nav className="flex-1 overflow-y-auto px-2 py-[6px]" aria-label={t("agents.title")}>
        <PersonalAgentEntry state={personal.data} failed={personal.isError} search={search} agent={agents.find(agent => agent.agent_id === personalBinding?.agent_id)} isMobile={false} isActive={activeId === personalBinding?.agent_id} onRetry={() => void personal.refetch()} onSelect={selectAgent} />
        {agents.filter(agent => agent.agent_id !== personalBinding?.agent_id).filter(agent => `${agent.display_name} ${agent.agent_id} ${agent.description}`.toLowerCase().includes(search.toLowerCase())).map((agent) => (
          <AgentRow
            key={agent.agent_id}
            agent={agent}
            nodes={nodes}
            nodesPending={false}
            isActive={agent.agent_id === activeId}
            isMobile={false}
            onSelect={selectAgent}
          />
        ))}
      </nav>
    </aside>
  );
}
