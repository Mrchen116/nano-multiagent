import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { AgentRow } from "./agent-row";
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
      className="hidden bg-[var(--im-sidebar)] lg:flex lg:w-[240px] lg:flex-col lg:border-r lg:border-im-border"
      aria-label={t("agents.title")}
    >
      <div className="flex items-center justify-between px-3 py-[10px] border-b border-im-border">
        <span className="text-[11px] font-bold tracking-[0.08em] uppercase text-[oklch(0.55_0.01_240)]">
          {t("agents.title")}
        </span>
        {isCreatePage ? (
          <button
            className="inline-flex h-9 items-center rounded-lg border-0 px-3 text-[13px] font-semibold text-white"
            style={{ background: "var(--im-accent)", cursor: "default" }}
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
            style={{ background: "var(--im-accent)" }}
          >
            {t("agents.newButton")}
          </Link>
        )}
      </div>
      <input type="search" className="chat-sidebar-search" aria-label={t("agents.search")} placeholder={t("agents.search")} value={search} onChange={e => setSearch(e.target.value)} />
      <nav className="flex-1 overflow-y-auto px-2 py-[6px]" aria-label={t("agents.title")}>
        {agents.filter(agent => `${agent.display_name} ${agent.agent_id} ${agent.description}`.toLowerCase().includes(search.toLowerCase())).map((agent) => (
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
