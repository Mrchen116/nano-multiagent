import { AgentExecutionDeletedError, workBase, workRequest } from "./agent-work-api";
import { AgentDeletionStatus, useAgentDeletion } from "./agent-deletion";
import { AgentLifecycleAction, AgentLifecycleStatus, useAgentLifecycle } from './agent-lifecycle';
import "./agent-settings.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "../../auth/auth-store";
import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { listContacts, contactActor } from "../../chat/contacts-api";
import { createConversation } from "../../chat/chat-api";
import { Avatar, colorForAgent, initialsOf } from "../../chat/components/avatar";
import { AgentDetailPage } from "./agent-detail-page";
import { AgentsRailDesktop } from "./agents-rail-desktop";
import { AgentWorkPanel } from "./agent-work-panel";
import type { listPublicAgents } from "./public-agents";

/** Public profile and Work never load another person's writable configuration. */
export function AgentProfilePage() {
  const { agentId } = useParams();
  const lifecycle = useAgentLifecycle(agentId ?? "");
  const self = useAuthStore(s => s.user?.id);
  const { t, i18n } = useTranslation();
  const l = (zh: string, en: string) => i18n.language.startsWith("zh") ? zh : en;
  const isMobile = useIsMobile();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const workRequested = params.get("view") === "work";
  const [detailsOpened, setDetailsOpened] = useState(!workRequested);
  useEffect(() => { if (!workRequested) setDetailsOpened(true); }, [workRequested]);
  const query = useQuery({ queryKey: ["contacts", self, "agents"], queryFn: () => listContacts("", "agent"), refetchInterval: 3000 });
  const agent = query.data?.find(a => a.agent_id === agentId);
  const scope = params.get("execution");
  const messageId = params.get("message_id");
  const historical = useQuery({
    queryKey: ["agent-work", agentId, "historical", scope, messageId],
    enabled: query.isSuccess && !agent && !!agentId && workRequested,
    retry: false,
    queryFn: ({signal}) => workRequest(
      scope
        ? `${workBase(agentId!)}/sessions/${encodeURIComponent(scope)}/turns?view=summary`
        : `${workBase(agentId!)}?view=summary${messageId ? `&message_id=${encodeURIComponent(messageId)}` : ""}`,
      signal
    ),
  });
  const stopped = lifecycle.query.data;
  const deletion = useAgentDeletion(agentId ?? "", query.isSuccess && (!!agent
    ? agent.owner_id === self && agent.role !== "personal" && workRequested && stopped?.desired === "disabled" && stopped.observed === "disabled" && stopped.applied_revision === stopped.revision
    : !workRequested && !!self), !workRequested);
  const deletionState = deletion.query.data?.operation?.state;
  const managing = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (agent && agent.owner_id === self && !workRequested) managing.current = agentId;
  }, [agent, agentId, self, workRequested]);
  const returnToList = !!agentId && !workRequested && deletionState === "deleted"
    && (managing.current === agentId || !!agent && agent.owner_id === self);
  useEffect(() => {
    if (!returnToList) return;
    client.setQueryData<Awaited<ReturnType<typeof listPublicAgents>>>(["public-agents", self],
      agents => agents?.filter(item => item.agent_id !== agentId));
    for (const key of [["settings", "agents"], ["contacts"], ["public-agents"], ["chat", "agents"], ["chat", "conversations"], ["agent-work", agentId]]) {
      void client.invalidateQueries({ queryKey: key });
    }
    navigate("/settings/agents", { replace: true });
  }, [returnToList, agentId, client, navigate, self]);
  const send = useMutation({ mutationFn: () => createConversation({ type: "direct", title: agent!.display_name, participants: [contactActor(agent!)] }), onSuccess: async chat => { await client.invalidateQueries({ queryKey: ["chat", "conversations"] }); navigate(`/chat/${chat.id}`); } });
  // Once accepted, the receipt is authoritative even if the profile reads start failing.
  if (returnToList || (!workRequested && deletionState && deletionState !== "deleted")) {
    return <section className="im-agent-panel im-agent-settings im-create-state">
      <AgentDeletionStatus deletion={deletion} online={agent?.status === "online"} />
    </section>;
  }
  if (historical.error instanceof AgentExecutionDeletedError || (!agent && !workRequested && deletionState === "deleted")) {
    return <section className="im-agent-panel im-agent-settings im-create-state">
      <p role="status">{workRequested ? l("执行记录已删除", "Execution record deleted") : l("Agent 已删除", "Agent deleted")}</p>
      <Link className="im-settings-action" to="/settings/agents">{t("agents.title")}</Link>
    </section>;
  }
  if (query.isPending || (query.isSuccess && !agent && (historical.isFetching || deletion.query.isFetching))) return <section className="im-agent-panel im-agent-settings im-create-state"><p>{t("common.loading")}</p></section>;
  if (query.isError || !agent) return <section className="im-agent-panel im-agent-settings im-create-state"><p role="alert">{t("agents.loadError")}</p><button className="im-settings-action" onClick={() => void query.refetch()}>{t("agents.retry")}</button></section>;
  const work = agent.work_mode === "global" && workRequested;
  return <>
    {agent.owner_id === self && <div hidden={work} style={{display:work ? 'none' : 'contents'}}>
      {(!work || detailsOpened) && <AgentDetailPage key={agentId} personal={agent.role === "personal"} inactive={work} />}
    </div>}
    {(agent.owner_id !== self || work) && <div className="agents-overview">
    <AgentsRailDesktop activeId={agentId} />
    <section className="im-agent-panel im-agent-settings min-w-0">
      <header className="im-agent-panel-header">
        <div className="im-agent-panel-header-row">
          {isMobile && (
            <Link
              to="/settings/agents"
              aria-label={t("agents.title")}
              className="im-settings-back"
            >
              <span aria-hidden="true">‹</span>
            </Link>
          )}
          <Avatar
            initials={initialsOf(agent.display_name)}
            color={colorForAgent(agent)}
            status={agent.status}
            size={32}
          />
          <div className="min-w-0 flex-1">
            <h2 className="im-agent-panel-title">{agent.display_name}</h2>
            <p className="im-agent-panel-subtitle im-agent-panel-node-line">
              <span className="im-agent-panel-agent-id">{agent.agent_id}</span>
              <span className={`im-agent-panel-node ${agent.status === "online" ? "online" : ""}`}>
                <span className="dot" /> {agent.node_name}
              </span>
            </p>
          </div>
          <div className="im-agent-header-actions shrink-0">
            <AgentLifecycleAction lifecycle={lifecycle} canManage={agent.owner_id === self && !deletionState} online={agent.status === "online"} />
            <button
              type="button"
              className="im-settings-action"
              disabled={send.isPending}
              onClick={() => send.mutate()}
            >
              {t(agent.owner_id === self ? "agents.detail.openChat" : "chat.contacts.message")}
            </button>
          </div>
        </div>
        <AgentLifecycleStatus lifecycle={lifecycle} online={agent.status === "online"} />
        {send.isError && <p role="alert" className="im-agent-footer-status error">{t("chat.contacts.failed")}</p>}
        <nav
          className="im-agent-settings-tabs"
          aria-label={t("agents.detail.sections.navLabel")}
        >
          {[
            ...(agent.work_mode === "global" ? [{ id: "work", label: t("agents.detail.sections.work") }] : []),
            ...(agent.owner_id === self ? [
              {id: "overview", label: t("agents.detail.sections.overview")},
              {id: "config", label: t("agents.detail.sections.config")},
              {id: "channels", label: t("agents.detail.sections.channels")},
              {id: "skills", label: t("agents.detail.sections.skills")},
              {id: "plugins", label: t("agents.detail.sections.plugins")},
              {id: "sessions", label: t("agents.detail.sections.sessions")},
            ] : [{ id: "profile", label: t("agents.publicProfile") }])
          ].map(section => (
            <button
              key={section.id}
              type="button"

              aria-pressed={(work ? "work" : "profile") === section.id}
              onClick={() => setParams(section.id === "work" || agent.owner_id === self ? { view: section.id } : {})}
            >
              {section.label}
            </button>
          ))}
        </nav>
      </header>
      <div className={`im-agent-panel-body im-agent-detail-body ${work ? "im-agent-work-body" : ""}`}>
        {work ? <AgentWorkPanel agentId={agent.agent_id!} agentName={agent.display_name} /> : (
          <section className="im-settings-overview" aria-label={t("agents.publicProfile")}>
            <dl className="im-settings-metadata">
              <div><dt>{t("agents.mode")}</dt><dd>{t(agent.role === "personal" ? "pa.label" : agent.work_mode === "global" ? "agents.globalMode" : "agents.threadMode")}</dd></div>
              <div><dt>{t("agents.managedBy")}</dt><dd>{agent.owner_display_name}</dd></div>
              <div><dt>{t("agents.device")}</dt><dd>{agent.node_name}</dd></div>
            </dl>
          </section>
        )}
      </div>
    </section>
  </div>}
  </>;
}
