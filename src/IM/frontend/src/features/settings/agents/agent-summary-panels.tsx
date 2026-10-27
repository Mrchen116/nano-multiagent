import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {Link} from "react-router-dom";
import {useTranslation} from "../../../i18n";
import {useAuthStore} from "../../auth/auth-store";
import {listConversations} from "../../chat/chat-api";
import {mentionNameMap, mentionPlainText} from "../../chat/components/mention-parser";
import type {AgentConfig} from "./im-agent-config-api";

/** Overview is saved configuration, never a claim that a disconnected runtime is current. */
export function AgentOverviewPanel({config, model, nodeName, nodeState, personal, onConfigure}: {
  config: AgentConfig; model: string | null; nodeName: string; nodeState: string; personal: boolean; onConfigure(): void;
}) {
  const {t} = useTranslation();
  return <section className="im-settings-overview" aria-label={t("agents.detail.sections.overview")}>
    {config.description && <p>{config.description}</p>}
    <dl className="im-settings-metadata">
      <div><dt>{t("agents.form.identity.agentId")}</dt><dd><code>{config.agent_id}</code></dd></div>
      <div><dt>{t("agents.mode")}</dt><dd>{t(personal ? "pa.label" : config.work_mode === "global" ? "agents.globalMode" : "agents.threadMode")}</dd></div>
      <div><dt>{t("agents.redesign.savedModel")}</dt><dd>{config.default_model || model || t("agents.form.access.modelPlatformDefaultPlain")}</dd></div>
      <div><dt>{t("agents.form.access.reasoning.label")}</dt><dd>{config.reasoning_effort || t("agents.redesign.modelDefault")}</dd></div>
    </dl>
    <h3>{t("agents.form.workspace.title")}</h3>
    <dl className="im-settings-metadata">
      <div><dt>{t("agents.device")}</dt><dd>{nodeName} · {t(nodeState === "online" ? "agents.redesign.online" : nodeState === "offline" ? "agents.redesign.offline" : "agents.redesign.unknown")}</dd></div>
      <div><dt>{t("agents.form.workspace.profileVersion")}</dt><dd>v{config.profile_version}</dd></div>
      <div><dt>{t("agents.form.workspace.workspaceRoot")}</dt><dd><code>{config.workspace_root || "—"}</code></dd></div>
      <div><dt>{t("agents.form.workspace.lastUpdated")}</dt><dd>{config.updated_at ? new Date(config.updated_at).toLocaleString() : "—"}</dd></div>
    </dl>
    <div className="im-settings-overview-links"><button type="button" className="im-settings-action" onClick={onConfigure}>{t("agents.redesign.editSettings")}</button></div>
  </section>;
}

/** Only conversations already visible to this user are eligible for the Agent's list. */
export function AgentSessionsPanel({agentId}: {agentId: string}) {
  const {t} = useTranslation();
  const userId = useAuthStore(state => state.user?.id);
  const [search, setSearch] = useState("");
  const query = useQuery({queryKey: ["chat", "conversations", userId], queryFn: listConversations});
  const sessions = (query.data ?? []).filter(chat => chat.source_agent_id === agentId || chat.participants.some(actor => actor.type === "agent" && actor.id === agentId));
  const visible = sessions.filter(chat => chat.title.toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a,b) => (b.last_message_at ?? b.created_at).localeCompare(a.last_message_at ?? a.created_at));
  return <section aria-label={t("agents.detail.sections.sessions")}>
    <header className="im-settings-list-header">
      <h3>{t("agents.redesign.conversations")}{query.isSuccess && <span className="im-settings-count">{sessions.length}</span>}</h3>
      <input type="search" className="im-input im-settings-search" aria-label={t("agents.redesign.searchSessions")} placeholder={t("agents.redesign.searchSessions")} value={search} onChange={event => setSearch(event.target.value)} />
    </header>
    {query.isPending && <p className="im-settings-empty" role="status">{t("common.loading")}</p>}
    {query.isError && <div className="im-settings-empty" role="alert">{t("agents.redesign.sessionsFailed")} <button type="button" className="im-settings-action" onClick={() => void query.refetch()}>{t("agents.retry")}</button></div>}
    {query.isSuccess && visible.length === 0 && <p className="im-settings-empty">{t(search ? "agents.redesign.noResults" : "agents.redesign.noSessions")}</p>}
    {visible.map(chat => <Link className="im-settings-conversation" to={`/chat/${encodeURIComponent(chat.id)}`} key={chat.id}>
      <strong>{chat.title}</strong>
      <time dateTime={chat.last_message_at ?? chat.created_at}>{new Date(chat.last_message_at ?? chat.created_at).toLocaleDateString()}</time>
      {chat.last_message_preview && <span>{mentionPlainText(chat.last_message_preview, mentionNameMap(chat.participants))}</span>}
    </Link>)}
  </section>;
}
