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
import { listContacts, contactActor, type Contact } from "../../chat/contacts-api";
import { createConversation } from "../../chat/chat-api";
import { Avatar } from "../../chat/components/avatar";
import { AgentDetailPage } from "./agent-detail-page";
import { AgentsRailDesktop } from "./agents-rail-desktop";
import { AgentWorkPanel } from "./agent-work-panel";
import type { listPublicAgents } from "./public-agents";
import "../../people/people-directory.css";

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
  const isOwner = Boolean(agent && (agent.owner_user_id ?? agent.owner_id) === self);
  const humansQuery = useQuery({
    queryKey: ["contacts", self, "humans"],
    queryFn: () => listContacts("", "human"),
    enabled: Boolean(self && agent && !isOwner),
    staleTime: 10_000
  });
  const ownerContact = !isOwner && agent
    ? humansQuery.data?.find(h => h.user_id !== self && h.user_id === (agent.owner_user_id ?? agent.owner_id))
    : undefined;
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
    ? isOwner && agent.role !== "personal" && workRequested && stopped?.desired === "disabled" && stopped.observed === "disabled" && stopped.applied_revision === stopped.revision
    : !workRequested && !!self), !workRequested);
  const deletionState = deletion.query.data?.operation?.state;
  const managing = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (agent && isOwner && !workRequested) managing.current = agentId;
  }, [agent, isOwner, agentId, self, workRequested]);
  const returnToList = !!agentId && !workRequested && deletionState === "deleted"
    && (managing.current === agentId || !!agent && isOwner);
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
  const messageOwner = useMutation({
    mutationFn: (owner: Contact) => createConversation({ type: "direct", title: owner.display_name, participants: [contactActor(owner)] }),
    onSuccess: async chat => { await client.invalidateQueries({ queryKey: ["chat", "conversations"] }); navigate(`/chat/${chat.id}`); }
  });
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
  if (query.isError) return <section className="im-agent-panel im-agent-settings im-create-state"><p role="alert">{t("agents.loadError")}</p><button className="im-settings-action" onClick={() => void query.refetch()}>{t("agents.retry")}</button></section>;
  if (!agent) return <section className="im-agent-panel im-agent-settings im-create-state"><p role="status">{t("agents.unavailablePrivate")}</p><Link className="im-settings-action" to="/settings/agents">{t("agents.title")}</Link></section>;
  const canViewWork = agent.work_mode === "global" && (agent.role !== "personal" || isOwner);
  const work = canViewWork && workRequested;
  return <>
    {isOwner && <div hidden={work} style={{display:work ? 'none' : 'contents'}}>
      {(!work || detailsOpened) && <AgentDetailPage key={agentId} personal={agent.role === "personal"} inactive={work} />}
    </div>}
    {(!isOwner || work) && <div className="agents-overview">
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
          <Avatar id={agent.user_id} size={32} status={agent.status} />
          <div className="min-w-0 flex-1">
            <h2 className="im-agent-panel-title">{agent.display_name}</h2>
            <p className="im-agent-panel-subtitle im-agent-panel-node-line">
              <span className="im-agent-panel-agent-id">{agent.agent_id}</span>
              {agent.node_name && (
                <span className={`im-agent-panel-node ${agent.status === "online" ? "online" : ""}`}>
                  <span className="dot" /> {agent.node_name}
                </span>
              )}
            </p>
          </div>
          <div className="im-agent-header-actions shrink-0">
            <AgentLifecycleAction lifecycle={lifecycle} canManage={isOwner && !deletionState} online={agent.status === "online"} />
            <button
              type="button"
              className="im-settings-action"
              disabled={send.isPending}
              onClick={() => send.mutate()}
            >
              {t(isOwner ? "agents.detail.openChat" : "chat.contacts.message")}
            </button>
          </div>
        </div>
        <AgentLifecycleStatus lifecycle={lifecycle} online={agent.status === "online"} />
        {(send.isError || messageOwner.isError) && <p role="alert" className="im-agent-footer-status error">{t("chat.contacts.failed")}</p>}
        <nav
          className="im-agent-settings-tabs"
          aria-label={t("agents.detail.sections.navLabel")}
        >
          {[
            ...(canViewWork ? [{ id: "work", label: t("agents.detail.sections.work") }] : []),
            ...(isOwner ? [
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
              onClick={() => setParams(section.id === "work" || isOwner ? { view: section.id } : {})}
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
              <div>
                <dt>{t("agents.managedBy")}</dt>
                <dd className="im-agent-owner-field">
                  <span>{agent.owner_display_name}{ownerContact?.username ? ` (@${ownerContact.username})` : ""}</span>
                  {ownerContact && (
                    <button
                      type="button"
                      className="im-settings-action"
                      disabled={messageOwner.isPending}
                      onClick={() => messageOwner.mutate(ownerContact)}
                    >
                      {t("agents.messageOwner", { name: ownerContact.display_name })}
                    </button>
                  )}
                </dd>
              </div>
              {agent.node_name && <div><dt>{t("agents.device")}</dt><dd>{agent.node_name}</dd></div>}
            </dl>
          </section>
        )}
      </div>
    </section>
  </div>}
  </>;
}
