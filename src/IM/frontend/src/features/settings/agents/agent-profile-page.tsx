import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuthStore } from "../../auth/auth-store";
import { useTranslation } from "../../../i18n";
import { listContacts, contactActor } from "../../chat/contacts-api";
import { createConversation } from "../../chat/chat-api";
import { Avatar, colorForAgentSeed } from "../../chat/components/avatar";
import { AgentDetailPage } from "./agent-detail-page";
import { AgentsRailDesktop } from "./agents-rail-desktop";
import { AgentWorkPanel } from "./agent-work-panel";

/** Public profile and Work never load another person's writable configuration. */
export function AgentProfilePage() {
  const { agentId } = useParams();
  const self = useAuthStore(s => s.user?.id);
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["contacts", self, "agents"], queryFn: () => listContacts("", "agent"), refetchInterval: 3000 });
  const agent = query.data?.find(a => a.agent_id === agentId);
  const send = useMutation({ mutationFn: () => createConversation({ type: "direct", title: agent!.display_name, participants: [contactActor(agent!)] }), onSuccess: async chat => { await client.invalidateQueries({ queryKey: ["chat", "conversations"] }); navigate(`/chat/${chat.id}`); } });
  if (query.isPending) return <p>{t("common.loading")}</p>;
  if (query.isError || !agent) return <section className="im-agent-panel"><p role="alert">{t("agents.loadError")}</p><button onClick={() => void query.refetch()}>{t("agents.retry")}</button></section>;
  if (agent.owner_id === self) return <AgentDetailPage />;
  const work = agent.work_mode === "global" && params.get("view") === "work";
  return <div className="agents-overview">
    <AgentsRailDesktop activeId={agentId} />
    <section className="im-agent-panel public-agent-profile">
      <Link to="/settings/agents">‹ {t("agents.title")}</Link>
      <header className="public-agent-header"><Avatar initials={agent.display_name.slice(0, 2)} color={colorForAgentSeed(agent.display_name)} status={agent.status} size={48} /><div><h1>{agent.display_name}</h1><p>{[agent.owner_display_name, agent.node_name].filter(Boolean).join(" · ")}</p></div><button className="chat-modal-btn-primary" disabled={send.isPending} onClick={() => send.mutate()}>{t("chat.contacts.message")}</button></header>
      {send.isError && <p role="alert">{t("chat.contacts.failed")}</p>}
      <nav className="public-agent-tabs"><button aria-current={!work ? "page" : undefined} onClick={() => setParams({})}>{t("agents.publicProfile")}</button>{agent.work_mode === "global" && <button aria-current={work ? "page" : undefined} onClick={() => setParams({ view: "work" })}>{t("chat.viewWork")}</button>}</nav>
      {work ? <AgentWorkPanel agentId={agent.agent_id!} /> : <dl><dt>{t("agents.managedBy")}</dt><dd>{agent.owner_display_name}</dd><dt>{t("agents.device")}</dt><dd>{agent.node_name}</dd><dt>{t("agents.mode")}</dt><dd>{t(agent.work_mode === "global" ? "agents.globalMode" : "agents.threadMode")}</dd></dl>}
    </section>
  </div>;
}
