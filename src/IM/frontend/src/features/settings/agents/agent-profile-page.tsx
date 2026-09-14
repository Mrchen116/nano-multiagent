import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuthStore } from "../../auth/auth-store";
import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { listContacts, contactActor } from "../../chat/contacts-api";
import { createConversation } from "../../chat/chat-api";
import { Avatar, colorForAgent, initialsOf } from "../../chat/components/avatar";
import { AgentDetailPage } from "./agent-detail-page";
import { AgentsRailDesktop } from "./agents-rail-desktop";
import { AgentWorkPanel } from "./agent-work-panel";

/** Public profile and Work never load another person's writable configuration. */
export function AgentProfilePage() {
  const { agentId } = useParams();
  const self = useAuthStore(s => s.user?.id);
  const { t } = useTranslation();
  const isMobile = useIsMobile();
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
    <section className="im-agent-panel min-w-0">
      <header className="im-agent-panel-header">
        <div className="im-agent-panel-header-row">
          {isMobile && (
            <Link
              to="/settings/agents"
              aria-label={t("agents.title")}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[oklch(0.91_0.006_240)] text-[16px] text-[oklch(0.40_0.01_240)]"
            >
              <span aria-hidden="true">‹</span>
            </Link>
          )}
          <Avatar
            initials={initialsOf(agent.display_name)}
            color={colorForAgent(agent)}
            status={agent.status}
            size={isMobile ? 38 : 42}
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
            <button
              type="button"
              className="rounded-lg border border-[var(--im-accent)] bg-[var(--im-accent)] px-3 py-[5px] text-[0.75rem] font-semibold text-[var(--im-accent-fg)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={send.isPending}
              onClick={() => send.mutate()}
            >
              {t("chat.contacts.message")}
            </button>
          </div>
        </div>
        {send.isError && <p role="alert" className="im-agent-footer-status error">{t("chat.contacts.failed")}</p>}
        <nav
          className="-mx-5 mt-3 flex flex-wrap gap-0 border-t border-[var(--im-border)] px-5"
          aria-label={t("agents.detail.sections.navLabel")}
        >
          {[
            ...(agent.work_mode === "global" ? [{ id: "work", label: t("agents.detail.sections.work") }] : []),
            { id: "profile", label: t("agents.publicProfile") }
          ].map(section => (
            <button
              key={section.id}
              type="button"
              className={`border-0 border-b-2 bg-transparent px-4 py-3 text-[13px] font-semibold ${
                (work ? "work" : "profile") === section.id
                  ? "border-[var(--im-accent)] text-[var(--im-accent)]"
                  : "border-transparent text-slate-500 hover:text-slate-900"
              }`}
              aria-pressed={(work ? "work" : "profile") === section.id}
              onClick={() => setParams(section.id === "work" ? { view: "work" } : {})}
            >
              {section.label}
            </button>
          ))}
        </nav>
      </header>
      <div className={`im-agent-panel-body im-agent-detail-body ${work ? "im-agent-work-body" : ""}`}>
        {work ? <AgentWorkPanel agentId={agent.agent_id!} /> : (
          <section className="im-agent-card">
            <div>
              <h3 className="im-agent-card-title">{t("agents.publicProfile")}</h3>
              <p className="im-agent-card-sub">
                {t("agents.mode")}: {t(agent.work_mode === "global" ? "agents.globalMode" : "agents.threadMode")}
              </p>
            </div>
            <dl className="im-agent-card-grid-2 im-agent-profile-details">
              <div><dt>{t("agents.managedBy")}</dt><dd>{agent.owner_display_name}</dd></div>
              <div><dt>{t("agents.device")}</dt><dd>{agent.node_name}</dd></div>
            </dl>
          </section>
        )}
      </div>
    </section>
  </div>;
}
