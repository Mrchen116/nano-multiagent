import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "../../../i18n";
import { getAgentRole } from "../../settings/agents/im-agent-config-api";
import "./cooperation-guide.css";

export interface CooperationGuideAgent {
  id: string;
  name: string;
  personal: boolean;
  online: boolean;
}

/** Only mounted in a verified owner's direct chat; saved status comes from the workspace. */
export function CooperationGuide({ agent, messageCount, canStart, onStart }: {
  agent: CooperationGuideAgent;
  messageCount: number;
  canStart: boolean;
  onStart(text: string): void;
}) {
  const { t } = useTranslation();
  const [deferred, setDeferred] = useState(false);
  const [started, setStarted] = useState(false);
  const role = useQuery({
    queryKey: ["settings", "agents", agent.id, "role"],
    queryFn: ({ signal }) => getAgentRole(agent.id, signal),
    enabled: agent.online,
    retry: false,
    refetchOnMount: "always",
    refetchInterval: query => agent.online && !query.state.error && !query.state.data?.content && document.visibilityState === "visible" ? 5000 : false,
  });
  useEffect(() => { if (agent.online) void role.refetch(); }, [messageCount, agent.online, role.refetch]);
  const known = agent.online && role.isSuccess && role.isFetchedAfterMount;
  const saved = known && !!role.data.content.trim();
  const kind = agent.personal ? "personal" : "global";
  const label = (key: string) => t(`cooperation.${key}`);
  const start = (key: string) => { setStarted(true); setDeferred(false); onStart(label(`${kind}.${key}`)); };
  if (!known) return <section className="cooperation-guide cooperation-guide--compact" aria-label={label("label")}>
    <p role="status">{label(!agent.online ? "offline" : role.isError ? "unavailable" : "loading")}</p>
    {agent.online && role.isError && <button type="button" onClick={() => void role.refetch()}>{label("retry")}</button>}
  </section>;
  if (saved) return <section className="cooperation-guide cooperation-guide--saved" aria-label={label("label")}>
    <details><summary><span aria-hidden="true">✓</span> {label("saved")}<span className="cooperation-guide-meta">{label("view")}</span></summary>
      <p className="cooperation-guide-document">{role.data.content}</p>
      <p>{label("revise")}</p>
    </details>
    {messageCount === 0 && <p>{label("firstTask")}</p>}
  </section>;
  if (deferred || messageCount > 0) return <section className="cooperation-guide cooperation-guide--compact" aria-label={label("label")}>
    <div><strong>{label(started && !deferred ? "discussing" : "unset")}</strong><p>{label(deferred ? "deferred" : "confirmHint")}</p></div>
    <button type="button" disabled={!canStart} onClick={() => start("resume")}>{label("continue")}</button>
  </section>;
  return <section className="cooperation-guide" aria-label={label("label")}>
    <span className="cooperation-guide-eyebrow">{label("eyebrow")}</span>
    <h2>{t(`cooperation.${kind}.title`, { name: agent.name })}</h2>
    <p>{label(`${kind}.intro`)}</p>
    <ol className="cooperation-guide-steps"><li>{label("step1")}</li><li>{label("step2")}</li><li>{label("step3")}</li></ol>
    <div className="cooperation-guide-actions">
      <button type="button" disabled={!canStart} onClick={() => start("introduce")}>{label(`${kind}.introduceLabel`)} <span aria-hidden="true">↗</span></button>
      <button type="button" disabled={!canStart} onClick={() => start("responsibility")}>{label(`${kind}.responsibilityLabel`)} <span aria-hidden="true">↗</span></button>
    </div>
    <p className="cooperation-guide-note">{label("note")}</p>
    <button type="button" className="cooperation-guide-later" onClick={() => setDeferred(true)}>{label("later")}</button>
  </section>;
}
