import type { ReactNode, RefObject } from "react";
import { useTranslation } from "../../i18n";
import { TaskWaitInfo } from "./task-wait";
import { TaskStatusBadge, useTaskStatusLabel } from "./task-status-badge";
import { TASK_STATUSES, type DirectCounts, type TaskActor, type TaskNode, type TaskStatus } from "./task-graphs-api";

export const taskStatuses: TaskStatus[] = [...TASK_STATUSES];
export const editableTaskStatuses = (current?: TaskStatus) =>
  taskStatuses.filter(status => status !== "waiting" || current === "waiting");

const columns: TaskStatus[] = ["todo", "doing", "in_review", "done", "closed"];

export const actorName = (actor?: TaskActor | null) => actor?.display_name || actor?.id;

/** Strip inline Markdown markers so 1-2 line card previews read cleanly without raw `**` or `#`. */
export function plainTaskSnippet(raw?: string | null): string {
  if (!raw) return "";
  return raw
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/(\*\*|__|~~|`)/g, "")
    .replace(/\s*\n+\s*/g, " · ")
    .trim();
}

export function TaskCounts({ counts }: { counts?: DirectCounts }) {
  const { t } = useTranslation();
  return <small>{t("tasks.directCount", { done: counts?.done ?? 0, total: counts?.total ?? 0 })}</small>;
}

type Card = Pick<
  TaskNode,
  "id" | "title" | "status" | "mode" | "assignee" | "direct_counts" | "wait" | "wait_health"
> & { context?: string; selected?: boolean };

type CardActions = { onSelect(node: Card): void; onEnter(node: Card): void };

function TaskColumn({
  status,
  nodes,
  total,
  pending = false,
  bodyRef,
  children,
  onSelect,
  onEnter,
}: CardActions & {
  status: TaskStatus;
  nodes: Card[];
  total?: number;
  pending?: boolean;
  bodyRef?: RefObject<HTMLDivElement | null>;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const statusLabel = useTaskStatusLabel();
  const heading = status === "doing" ? t("tasks.ongoing") : statusLabel(status);
  return (
    <section
      className={`tasks-column tasks-column--${status}`}
      data-testid="task-status-column"
      aria-label={heading}
    >
      <header>
        <h2>{heading}</h2>
        <span>{total ?? "—"}</span>
      </header>
      <div className="tasks-column-body" ref={bodyRef} aria-busy={pending}>
        {nodes.map(node => (
          <article className="tasks-progress-card" key={node.id}>
            <button
              className="tasks-progress-card-main"
              data-node-id={node.id}
              aria-label={t("tasks.viewNode", { title: node.title })}
              onClick={() => onSelect(node)}
            >
              <h3>{node.title}</h3>
              <TaskStatusBadge status={node.status} />
              {node.selected && <span className="tasks-picked">{t("tasks.picked")}</span>}
              <span>{actorName(node.assignee) || t("tasks.unassigned")}</span>
              {node.context && <small>{node.context}</small>}
              <TaskCounts counts={node.direct_counts} />
              {node.status === "waiting" && <TaskWaitInfo wait={node.wait} health={node.wait_health} compact />}
            </button>
            <button
              className="tasks-child-entry"
              onClick={() => onEnter(node)}
              aria-label={t("tasks.enterNode", { title: node.title })}
            >
              {t("tasks.children")} →
            </button>
          </article>
        ))}
        {!pending && total === 0 && <p className="tasks-column-empty">{t("tasks.noTasks")}</p>}
        {children}
      </div>
    </section>
  );
}

export function TaskBoard({ nodes, onSelect, onEnter }: CardActions & { nodes: Card[] }) {
  return (
    <div className="tasks-board">
      {columns.map(status => {
        const group = nodes.filter(
          node =>
            node.status === status ||
            (status === "todo" && ["paused", "proposed", "backlog"].includes(node.status)) ||
            (status === "doing" && node.status === "waiting"),
        );
        return (
          <TaskColumn
            key={status}
            status={status}
            nodes={group}
            total={group.length}
            onSelect={onSelect}
            onEnter={onEnter}
          />
        );
      })}
    </div>
  );
}
