import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { getTaskRuntime, type TaskWait, type TaskWaitHealth } from "./task-graphs-api";

export function TaskWaitInfo({ wait, health, compact = false }: { wait?: TaskWait; health?: TaskWaitHealth; compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const state = health?.state ?? "unknown";
  return <div className={`tasks-wait${compact ? " tasks-wait--compact" : ""}`}>
    {!compact && <strong>{t("tasks.wait.reason")}</strong>}
    <span className="tasks-wait-reason">{wait?.reason || t("tasks.wait.reasonUnavailable")}</span>
    {state !== "valid" && (!compact || health) && <span className="tasks-wait-diagnostic">{t(`tasks.wait.${state}`)}</span>}
    <span>{state === "invalid" ? t("tasks.wait.noSchedule") : wait ? <>{t(state === "valid" ? "tasks.wait.nextCheck" : "tasks.wait.savedTime")} · {new Date(wait.next_check_at).toLocaleString(i18n.language)}</> : null}</span>
    {!compact && <small>{t("tasks.wait.notReceipt")}</small>}
  </div>;
}

/** Reports the Agent's observed execution state, independently of task progress. */
export function TaskAgentRuntime({ agentId, graphId, nodeId }: { agentId: string; graphId: string; nodeId: string }) {
  const { t } = useTranslation();
  const userId = useAuthStore(state => state.user?.id);
  const query = useQuery({ queryKey: ["task-agent-runtime", userId, graphId, nodeId, agentId],
    queryFn: () => getTaskRuntime(graphId, nodeId), retry: false,
    refetchInterval: () => document.visibilityState === "visible" ? 3000 : false });
  const state = query.isError ? "unknown" : query.data?.state;
  const known = ["running", "idle", "offline"].includes(state ?? "") ? state : "unknown";
  return <p className="tasks-detail-note">{t("tasks.runtime.label")} · {t(`tasks.runtime.${known}`)}</p>;
}
