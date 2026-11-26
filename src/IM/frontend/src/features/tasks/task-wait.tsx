import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useInRouterContext } from "react-router-dom";
import { useTranslation } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import {
  AgentActivityPopover,
  type AgentActivityAnchor,
} from "../chat/components/agent-activity-popover";
import {
  Avatar,
  colorForAgent,
  colorForAgentSeed,
  initialsOf,
} from "../chat/components/avatar";
import {
  getTaskRuntime,
  type TaskActor,
  type TaskWait,
  type TaskWaitHealth,
} from "./task-graphs-api";
import { actorName } from "./task-progress";

export function TaskWaitInfo({
  wait,
  health,
  compact = false,
}: {
  wait?: TaskWait;
  health?: TaskWaitHealth;
  compact?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const hasSchedule = Boolean(wait?.schedule_id || wait?.next_check_at || health);
  const state = health?.state ?? "unknown";
  return (
    <div className={`tasks-wait${compact ? " tasks-wait--compact" : ""}`}>
      {!compact && <strong>{t("tasks.wait.reason")}</strong>}
      <span className="tasks-wait-reason">{wait?.reason || t("tasks.wait.reasonUnavailable")}</span>
      {wait?.question && (
        <span className="tasks-wait-question">
          {t("tasks.wait.questionLabel")} · {wait.question}
        </span>
      )}
      {hasSchedule && state !== "valid" && (!compact || health) && (
        <span className="tasks-wait-diagnostic">{t(`tasks.wait.${state}`)}</span>
      )}
      {hasSchedule && (
        <span>
          {state === "invalid" ? (
            t("tasks.wait.noSchedule")
          ) : wait?.next_check_at ? (
            <>
              {t(state === "valid" ? "tasks.wait.nextCheck" : "tasks.wait.savedTime")} ·{" "}
              {new Date(wait.next_check_at).toLocaleString(i18n.language)}
            </>
          ) : null}
        </span>
      )}
      {hasSchedule && !compact && <small>{t("tasks.wait.notReceipt")}</small>}
    </div>
  );
}

export function useTaskAgentRuntimeState(
  agentId: string | undefined,
  graphId: string,
  nodeId: string,
): "running" | "idle" | "offline" | "unknown" {
  const userId = useAuthStore(state => state.user?.id);
  const query = useQuery({
    queryKey: ["task-agent-runtime", userId, graphId, nodeId, agentId],
    queryFn: () => getTaskRuntime(graphId, nodeId),
    enabled: Boolean(agentId),
    retry: false,
    refetchInterval: () => (document.visibilityState === "visible" ? 3000 : false),
  });
  if (!agentId || query.isError) return "unknown";
  const state = query.data?.state;
  return state === "running" || state === "idle" || state === "offline" ? state : "unknown";
}

/** Reports the Agent's observed execution state, independently of task progress. */
export function TaskAgentRuntime({
  agentId,
  graphId,
  nodeId,
}: {
  agentId: string;
  graphId: string;
  nodeId: string;
}) {
  const { t } = useTranslation();
  const inRouter = useInRouterContext();
  const known = useTaskAgentRuntimeState(agentId, graphId, nodeId);
  return (
    <p className="tasks-detail-note tasks-runtime-row">
      <span>
        {t("tasks.runtime.label")} · {t(`tasks.runtime.${known}`)}
      </span>
      {inRouter && (
        <Link className="tasks-inline-link" to={`/settings/agents/${encodeURIComponent(agentId)}?view=work`}>
          {t("tasks.runtime.openWork")}
        </Link>
      )}
    </p>
  );
}

/** Compact inline avatar + display name for task list and spine cards. */
export function TaskAssigneeInline({
  assignee,
  stashedMuted = false,
}: {
  assignee?: TaskActor | null;
  stashedMuted?: boolean;
}) {
  const { t } = useTranslation();
  const name = actorName(assignee);
  if (!assignee || !name) {
    return (
      <span className="tasks-assignee-inline tasks-assignee-inline--empty">
        {stashedMuted
          ? t("tasks.focus.stashedMutedHint", { assignee: t("tasks.unassigned") })
          : t("tasks.unassigned")}
      </span>
    );
  }
  const isAgent = assignee.type === "agent";
  const isPersonal = isAgent && assignee.id.startsWith("pa_");
  return (
    <span className="tasks-assignee-inline">
      <Avatar
        size={17}
        personal={isPersonal}
        agentId={isAgent ? assignee.id : undefined}
        initials={initialsOf(name)}
        color={isAgent ? colorForAgent({ display_name: name, agent_id: assignee.id }) : colorForAgentSeed(name)}
      />
      <span>{name}</span>
    </span>
  );
}

/**
 * Interactive assignee chip for the task detail header: displays the person's or Agent's
 * avatar and name cleanly, and opens the Chat-consistent AgentActivityPopover on click
 * when assigned to an Agent so live status and Work stay one tap away without cluttering the page.
 */
export function TaskAssigneePill({
  assignee,
  graphId,
  nodeId,
  canConfigureAgent = false,
  canEdit = false,
  onAssignClick,
}: {
  assignee?: TaskActor | null;
  graphId: string;
  nodeId: string;
  canConfigureAgent?: boolean;
  canEdit?: boolean;
  onAssignClick?(): void;
}) {
  const { t } = useTranslation();
  const inRouter = useInRouterContext();
  const [anchor, setAnchor] = useState<AgentActivityAnchor | null>(null);
  const isAgent = assignee?.type === "agent";
  const runtimeState = useTaskAgentRuntimeState(isAgent ? assignee.id : undefined, graphId, nodeId);

  useEffect(() => {
    setAnchor(null);
  }, [graphId, nodeId, assignee?.id]);

  const name = actorName(assignee);
  if (!assignee || !name) {
    return canEdit && onAssignClick ? (
      <button type="button" className="tasks-assignee-pill tasks-assignee-pill--empty" onClick={onAssignClick}>
        {t("tasks.unassigned")}
      </button>
    ) : (
      <span className="tasks-assignee-pill tasks-assignee-pill--empty">{t("tasks.unassigned")}</span>
    );
  }

  if (!isAgent) {
    return (
      <span className="tasks-assignee-pill" title={`${t("tasks.assignee")}: ${name}`}>
        <Avatar size={20} initials={initialsOf(name)} color={colorForAgentSeed(name)} />
        <span>{name}</span>
      </span>
    );
  }

  const isPersonal = assignee.id.startsWith("pa_");
  const avatarStatus =
    runtimeState === "running"
      ? "running"
      : runtimeState === "idle"
        ? "online"
        : runtimeState === "offline"
          ? "offline"
          : null;

  return (
    <>
      <button
        type="button"
        className="tasks-assignee-pill tasks-assignee-pill--agent"
        aria-label={t("chat.agentActivity.trigger", { name })}
        aria-expanded={Boolean(anchor)}
        title={t("chat.agentActivity.trigger", { name })}
        onClick={event => {
          const element = event.currentTarget;
          setAnchor(current => (current ? null : { agentId: assignee.id, name, element }));
        }}
      >
        <Avatar
          size={20}
          personal={isPersonal}
          agentId={assignee.id}
          initials={initialsOf(name)}
          color={colorForAgent({ display_name: name, agent_id: assignee.id })}
          status={avatarStatus}
        />
        <span>{name}</span>
        {runtimeState === "running" && (
          <span className="tasks-assignee-live-tag">{t("tasks.runtime.running")}</span>
        )}
      </button>
      {anchor && inRouter && (
        <AgentActivityPopover
          anchor={anchor}
          canConfigure={canConfigureAgent}
          fallbackRuntimeState={runtimeState}
          onClose={() => setAnchor(null)}
        />
      )}
    </>
  );
}
