import { useState } from "react";
import "./agent-settings.css";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { AgentLifecycleRow as AgentRow } from "./agent-lifecycle";
import { PersonalAgentEntry, configuredPersonalAgent, usePersonalAgentEntry } from "./personal-agent-entry";
import { useAgentStatusBroadcastConsumer } from "./agent-status-ws-consumer";
import { listPublicAgents } from "./public-agents";
import { useAuthStore } from "../../auth/auth-store";

export function AgentsListPage() {
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  const self = useAuthStore(s => s.user?.id);
  const navigate = useNavigate();
  useAgentStatusBroadcastConsumer();
  const agentsQuery = useQuery({ queryKey: ["public-agents", self], queryFn: listPublicAgents, refetchInterval: 3000 });

  const { agentId: activeAgentId } = useParams<{ agentId?: string }>();
  const [search, setSearch] = useState("");
  const agents = agentsQuery.data ?? [];
  const personal = usePersonalAgentEntry();
  const personalBinding = configuredPersonalAgent(personal.data);
  const nodes: [] = [];
  const newAgentPath = "/settings/agents/new";
  const errorDetail =
    agentsQuery.error instanceof Error
      ? agentsQuery.error.message.split(" failed: ").at(-1) ?? agentsQuery.error.message
      : null;

  const queryText = search.trim().toLowerCase();
  const visibleAgents = agents.filter(agent => agent.agent_id !== personalBinding?.agent_id)
    .filter(agent => `${agent.display_name} ${agent.agent_id} ${agent.description}`.toLowerCase().includes(queryText));
  const personalMatches = personalBinding && `${personalBinding.display_name} ${personalBinding.agent_id} ${t("pa.label")} ${agents.find(agent => agent.agent_id === personalBinding.agent_id)?.description ?? ""}`.toLowerCase().includes(queryText);

  return (
    <section className="im-agent-panel im-agent-settings im-agent-directory" data-testid="agents-list">
      <header className="im-settings-list-header">
        <h1>{t("agents.title")}{agentsQuery.isSuccess && <span className="im-settings-count">{agents.length}</span>}</h1>
        <Link className="im-settings-action" to={newAgentPath}>{t("agents.newButton")}</Link>
      </header>
      <input type="search" className="im-input im-settings-search" aria-label={t("agents.search")} placeholder={t("agents.search")} value={search} onChange={e => setSearch(e.target.value)} />
      <div className="im-directory-content">
        <PersonalAgentEntry state={personal.data} failed={personal.isError} search={search} agent={agents.find(agent => agent.agent_id === personalBinding?.agent_id)} isMobile={isMobile} isActive={activeAgentId === personalBinding?.agent_id} onRetry={() => void personal.refetch()} onSelect={id => navigate(`/settings/agents/${encodeURIComponent(id)}`)} />
        {agentsQuery.isLoading ? <p className="im-settings-empty">{t("common.loading")}</p>
          : agentsQuery.isError ? <div className="im-settings-empty" role="alert">
            <p>{t("agents.loadError")}</p>
            {errorDetail && <p className="im-agent-field-help">{errorDetail}</p>}
            <button type="button" className="im-settings-action" onClick={() => void agentsQuery.refetch()}>{t("agents.retry")}</button>
          </div>
          : agents.length === 0 ? <div className="im-settings-empty">
            <p>{t("agents.empty.title")}</p>
            <Link className="im-settings-action" to="/settings/nodes">{t("agents.openNodes")}</Link>
          </div>
          : <>
            {queryText && !visibleAgents.length && !personalMatches && <p className="im-settings-empty">{t("agents.redesign.noAgents")}</p>}
            <nav className="im-directory-agents" aria-label={t("agents.title")}>
              {visibleAgents.map(agent => <AgentRow key={agent.agent_id} agent={agent} nodes={nodes} nodesPending={false}
                isActive={agent.agent_id === activeAgentId} isMobile={isMobile} onSelect={id => navigate(`/settings/agents/${id}`)} />)}
            </nav>
          </>}
      </div>
    </section>
  );
}
