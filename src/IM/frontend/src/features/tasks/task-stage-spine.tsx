import { useMemo, useState } from "react";
import { useTranslation } from "../../i18n";
import { layoutTaskScope } from "./task-graph-layout";
import { isTaskPrereqBlocked, writeTaskGraph, type TaskGraph, type TaskNode } from "./task-graphs-api";
import { actorName } from "./task-progress";
import { plainTaskSnippet } from "./task-progress";
import { TaskStatusBadge } from "./task-status-badge";
import { TaskAssigneeInline } from "./task-wait";

export function TaskStageSpine({
  graph,
  scope,
  selectedId,
  busy,
  onSelect,
  onEnter,
  onAct,
}: {
  graph: TaskGraph;
  scope: TaskNode;
  selectedId?: string;
  busy: boolean;
  onSelect(node: TaskNode): void;
  onEnter(node: TaskNode): void;
  onAct(fn: () => Promise<unknown>): Promise<void>;
}) {
  const { t } = useTranslation();
  const [earlierExpanded, setEarlierExpanded] = useState(false);
  const layout = useMemo(() => layoutTaskScope(graph, scope), [graph, scope]);

  const stages = useMemo(() => {
    const byX = new Map<number, TaskNode[]>();
    for (const node of layout.nodes) {
      const x = layout.positions.get(node.id)?.x ?? 0;
      byX.set(x, [...(byX.get(x) ?? []), node]);
    }
    return [...byX.entries()]
      .sort(([a], [b]) => a - b)
      .map(([, nodes], idx) => ({ index: idx + 1, nodes }));
  }, [layout]);

  const { earlierDoneStages, remainingStages } = useMemo(() => {
    let splitAt = 0;
    while (
      splitAt < stages.length - 1 &&
      stages[splitAt]!.nodes.every(n => n.status === "done" || n.status === "closed")
    ) {
      splitAt += 1;
    }
    return {
      earlierDoneStages: stages.slice(0, splitAt),
      remainingStages: stages.slice(splitAt),
    };
  }, [stages]);

  const childCountFor = (nodeId: string) =>
    graph.nodes.filter(candidate => candidate.container_id === nodeId).length;

  const applyNodeOp = (operations: Record<string, unknown>[]) =>
    onAct(() =>
      writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}/apply`, {
        base_revision: graph.revision,
        request_key: crypto.randomUUID(),
        change_note: "",
        operations,
      }),
    );

  if (layout.nodes.length === 0) {
    return (
      <div className="tasks-empty">
        <h2>{t("tasks.emptyScope")}</h2>
        <p>{t("tasks.emptyScopeHint")}</p>
      </div>
    );
  }

  return (
    <div className="tasks-spine-stream" aria-label={t("tasks.panorama.mobileSpine")}>
      {earlierDoneStages.length > 0 && (
        <div className="tasks-spine-item">
          <span className="tasks-spine-dot tasks-spine-dot--done" aria-hidden />
          <div className="tasks-spine-card tasks-spine-card--earlier">
            <button
              type="button"
              className="tasks-spine-earlier-toggle"
              aria-expanded={earlierExpanded}
              onClick={() => setEarlierExpanded(value => !value)}
            >
              <span className="tasks-spine-earlier-head">
                <TaskStatusBadge status="done" />
                <strong>{t("tasks.panorama.earlierStages", { count: earlierDoneStages.length })}</strong>
              </span>
              <span className="tasks-inline-link">
                {t(earlierExpanded ? "tasks.panorama.collapseEarlier" : "tasks.panorama.expandEarlier")}
              </span>
            </button>
            {earlierExpanded && (
              <div className="tasks-spine-earlier-list">
                {earlierDoneStages.flatMap(stage =>
                  stage.nodes.map(node => {
                    const count = childCountFor(node.id);
                    return (
                      <div key={node.id} className="tasks-spine-earlier-row">
                        <button
                          type="button"
                          className="tasks-spine-node-link"
                          aria-label={t("tasks.viewNode", { title: node.title })}
                          onClick={() => onSelect(node)}
                        >
                          <TaskStatusBadge status={node.status} />
                          <span>
                            {t("tasks.panorama.stageLabel", { index: stage.index })} · {node.title}
                          </span>
                        </button>
                        {node.mode !== "none" && (
                          <button
                            type="button"
                            className="tasks-inline-link"
                            aria-label={t("tasks.enterNode", { title: node.title })}
                            onClick={() => onEnter(node)}
                          >
                            {t("tasks.panorama.enterSubscopeCount", { count })}
                          </button>
                        )}
                      </div>
                    );
                  }),
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {remainingStages.map(stage =>
        stage.nodes.map(node => {
          const isSprout = node.status === "proposed";
          const isDone = node.status === "done";
          const prereqBlocked = isTaskPrereqBlocked(node, graph, node.id);
          const subCount = childCountFor(node.id);
          return (
            <div key={node.id} className="tasks-spine-item">
              <span
                className={`tasks-spine-dot${
                  isDone ? " tasks-spine-dot--done" : isSprout ? " tasks-spine-dot--sprout" : ""
                }`}
                aria-hidden
              />
              <article
                className={`tasks-spine-card${isSprout ? " tasks-spine-card--sprout" : ""}${
                  selectedId === node.id ? " is-selected" : ""
                }`}
              >
                <div className="tasks-spine-card-head">
                  <div className="tasks-spine-card-badges">
                    <TaskStatusBadge status={node.status} />
                    <span className="tasks-spine-stage-tag">
                      {t("tasks.panorama.stageLabel", { index: stage.index })}
                      {isSprout ? ` · ${t("tasks.panorama.sproutStage")}` : ""}
                      {node.status === "doing" ? ` · ${t("tasks.panorama.frontierBadge")}` : ""}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="tasks-pill-btn tasks-pill-btn--ghost tasks-pill-btn--xs"
                    aria-label={t("tasks.viewNode", { title: node.title })}
                    onClick={() => onSelect(node)}
                  >
                    {t("tasks.panorama.detailEdit")}
                  </button>
                </div>

                <h3 className="tasks-spine-title">{node.title}</h3>
                {(node.wait?.reason || node.result || node.description) && (
                  <p className="tasks-spine-desc">
                    {plainTaskSnippet(
                      node.status === "waiting"
                        ? node.wait?.reason || node.description
                        : (node.status === "in_review" || node.status === "done") && node.result?.trim()
                          ? node.result
                          : node.description || node.result,
                    )}
                  </p>
                )}

                <div className="tasks-spine-meta">
                  <TaskAssigneeInline assignee={node.assignee} />
                  {scope.selected_candidate_id === node.id && (
                    <span className="tasks-picked">{t("tasks.picked")}</span>
                  )}
                  {node.mode !== "none" && (
                    <button
                      type="button"
                      className="tasks-inline-link"
                      aria-label={t("tasks.enterNode", { title: node.title })}
                      onClick={() => onEnter(node)}
                    >
                      {t("tasks.panorama.enterSubscopeCount", { count: subCount })}
                    </button>
                  )}
                </div>

                {isSprout && node.can_edit && (
                  <div className="tasks-spine-actions">
                    <button
                      type="button"
                      className="tasks-pill-btn tasks-pill-btn--primary"
                      disabled={busy}
                      onClick={() => void applyNodeOp([{ op: "approve_task", node_id: node.id }])}
                    >
                      {t(prereqBlocked ? "tasks.focus.approveQueue" : "tasks.focus.approveStart")}
                    </button>
                    <button
                      type="button"
                      className="tasks-pill-btn tasks-pill-btn--stash"
                      disabled={busy}
                      onClick={() =>
                        void applyNodeOp([
                          { op: "update_task", node_id: node.id, patch: { status: "backlog" } },
                        ])
                      }
                    >
                      {t("tasks.focus.stashAction")}
                    </button>
                    <button
                      type="button"
                      className="tasks-pill-btn tasks-pill-btn--ghost"
                      disabled={busy}
                      onClick={() =>
                        void applyNodeOp([
                          { op: "update_task", node_id: node.id, patch: { status: "closed" } },
                        ])
                      }
                    >
                      {t("tasks.focus.closeAction")}
                    </button>
                  </div>
                )}

                {node.status === "backlog" && node.can_edit && (
                  <div className="tasks-spine-actions">
                    <button
                      type="button"
                      className="tasks-pill-btn tasks-pill-btn--soft"
                      disabled={busy}
                      onClick={() =>
                        void applyNodeOp([{ op: "update_task", node_id: node.id, patch: { status: "todo" } }])
                      }
                    >
                      {t("tasks.focus.activateTodo")}
                    </button>
                  </div>
                )}
              </article>
            </div>
          );
        }),
      )}
    </div>
  );
}
