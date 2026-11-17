import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "../../../i18n";
import { getAgentRole } from "../../settings/agents/im-agent-config-api";
import "./cooperation-guide.css";

export interface CooperationGuideAgent {
  id: string;
  name: string;
  personal: boolean;
  online: boolean;
}

/** First-conversation prompts for the verified owner; never render the role document. */
export function CooperationGuide({ agent, canStart, onStart }: {
  agent: CooperationGuideAgent;
  canStart: boolean;
  onStart(text: string): void;
}) {
  const { t } = useTranslation();
  const [deferred, setDeferred] = useState(false);
  const role = useQuery({
    queryKey: ["settings", "agents", agent.id, "role"],
    queryFn: ({ signal }) => getAgentRole(agent.id, signal),
    enabled: agent.online,
    retry: false,
    refetchOnMount: "always",
  });
  const known = agent.online && role.isSuccess && role.isFetchedAfterMount;
  const saved = known && !!role.data.content.trim();
  const kind = agent.personal ? "personal" : "global";
  const label = (key: string) => t(`cooperation.${key}`);
  const start = (key: string) => onStart(label(`${kind}.${key}`));
  if (!known || saved || deferred) return null;
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
