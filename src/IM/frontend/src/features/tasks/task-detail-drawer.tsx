import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useTranslation } from "../../i18n";
import { TaskGraphLink } from "./task-graph-link";
import {
  isTaskPrereqBlocked,
  writeTaskGraph,
  type TaskGraph,
  type TaskNode,
  type TaskStatus,
} from "./task-graphs-api";
import { actorName, TaskCounts } from "./task-progress";
import { TaskStatusBadge } from "./task-status-badge";
import { TaskAgentRuntime, TaskWaitInfo } from "./task-wait";
import type { TaskEditTarget } from "./task-editor";

export interface TaskDetailDrawerProps {
  graph: TaskGraph;
  node: TaskNode;
  docked?: boolean;
  busy: boolean;
  error: string;
  returnChatId?: string | null;
  onClose(): void;
  onSelect(node: TaskNode): void;
  onEnter(node: TaskNode): void;
  onDiscuss(node: TaskNode): void;
  onCopy(node: TaskNode): void;
  onEdit(target: TaskEditTarget): void;
  onOpenGoal?(graphId: string): void;
  onAct(fn: () => Promise<unknown>): Promise<void>;
  onDeletedRoot?(): void;
}

export function TaskDetailDrawer(props: TaskDetailDrawerProps) {
  const { t } = useTranslation();
  if (props.docked) {
    return (
      <aside
        className="tasks-detail-docked"
        role="dialog"
        aria-modal="false"
        aria-label={t("tasks.nodeDetails")}
      >
        <TaskDetailDrawerContent {...props} />
      </aside>
    );
  }
  return (
    <Dialog.Root
      open
      onOpenChange={open => {
        if (!open) props.onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="tasks-dialog-overlay tasks-drawer-overlay" />
        <Dialog.Content
          className="tasks-drawer-sheet"
          aria-label={t("tasks.nodeDetails")}
          aria-describedby={undefined}
        >
          <Dialog.Title className="sr-only">{t("tasks.nodeDetails")}</Dialog.Title>
          <TaskDetailDrawerContent {...props} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function TaskDetailDrawerContent({
  graph,
  node,
  docked,
  busy,
  error,
  returnChatId,
  onClose,
  onSelect,
  onEnter,
  onDiscuss,
  onCopy,
  onEdit,
  onOpenGoal,
  onAct,
  onDeletedRoot,
}: TaskDetailDrawerProps) {
  const { t, i18n } = useTranslation();
  const [deleting, setDeleting] = useState(false);

  const root = graph.nodes.find(candidate => candidate.id === graph.root_node_id);
  const parent = graph.nodes.find(candidate => candidate.id === node.container_id);
  const children = graph.nodes.filter(candidate => candidate.container_id === node.id);
  const isChildOfGoal = Boolean(root && node.id !== root.id);
  const prereqBlocked = isTaskPrereqBlocked(node, graph, node.id);
  const isProposal = node.status === "proposed";
  const isStashed = node.status === "backlog" || node.status === "paused";
  const showProgressBlock =
    Boolean(node.result?.trim()) ||
    ["doing", "waiting", "in_review", "done", "closed"].includes(node.status);

  const deletionIds = new Set([node.id]);
  for (let depth = 0; depth < 8; depth++) {
    graph.nodes.forEach(item => {
      if (item.container_id && deletionIds.has(item.container_id)) deletionIds.add(item.id);
    });
  }

  const predecessors =
    parent?.mode === "dag"
      ? graph.dependencies
          .filter(edge => edge.to === node.id)
          .map(edge => graph.nodes.find(candidate => candidate.id === edge.from))
          .filter((item): item is TaskNode => Boolean(item))
      : [];
  const successors =
    parent?.mode === "dag"
      ? graph.dependencies
          .filter(edge => edge.from === node.id)
          .map(edge => graph.nodes.find(candidate => candidate.id === edge.to))
          .filter((item): item is TaskNode => Boolean(item))
      : [];
  const derivedSource = node.derived_from_id
    ? graph.nodes.find(candidate => candidate.id === node.derived_from_id)
    : undefined;
  const currentChoice = node.selected_candidate_id
    ? graph.nodes.find(candidate => candidate.id === node.selected_candidate_id)
    : undefined;

  const applyOp = (operations: Record<string, unknown>[]) =>
    onAct(() =>
      writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}/apply`, {
        base_revision: graph.revision,
        request_key: crypto.randomUUID(),
        change_note: "",
        operations,
      }),
    );

  const conversation = graph.conversation;

  return (
    <div className="tasks-drawer-inner">
      <div className="tasks-drawer-head">
        <div className="tasks-drawer-head-top">
          {isChildOfGoal && root ? (
            <button
              type="button"
              className="tasks-goal-crumb"
              onClick={() => (onOpenGoal ? onOpenGoal(graph.graph_id) : onEnter(root))}
            >
              {t("tasks.focus.crumbGoal", { title: root.title })}
            </button>
          ) : (
            <span className="tasks-goal-crumb tasks-goal-crumb--idea">
              {conversation
                ? t("tasks.focus.crumbSingle", { chat: conversation.title })
                : `${t("tasks.nodeDetails")} · ${node.id}`}
            </span>
          )}
          <button type="button" className="tasks-pill-btn tasks-pill-btn--ghost" onClick={onClose}>
            {t("tasks.close")}
          </button>
        </div>

        <h2 className="tasks-drawer-title">{node.title}</h2>
        <div className="tasks-drawer-meta">
          <TaskStatusBadge status={node.status} />
          {node.mode !== "none" && <span className="tasks-mode">{t(`tasks.mode.${node.mode}`)}</span>}
          <span>
            {t("tasks.focus.assigneeLabel", {
              assignee: actorName(node.assignee) || t("tasks.unassigned"),
            })}
          </span>
        </div>
      </div>

      <div className="tasks-drawer-body">
        {error && (
          <p className="tasks-notice" role="alert">
            {error}
          </p>
        )}

        {node.assignee?.type === "agent" && (
          <TaskAgentRuntime agentId={node.assignee.id} graphId={graph.graph_id} nodeId={node.id} />
        )}

        {node.status === "waiting" && (
          <section className="tasks-drawer-section tasks-drawer-section--wait">
            <TaskWaitInfo wait={node.wait} health={node.wait_health} />
          </section>
        )}

        {isProposal && (node.proposal?.rationale || node.proposal?.on_approve) && (
          <section className="tasks-drawer-section tasks-drawer-section--butter">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.panorama.whyProposed")}</span>
            </div>
            {node.proposal?.rationale && <p>{node.proposal.rationale}</p>}
            {node.proposal?.on_approve && (
              <p>
                <strong>{t("tasks.panorama.onApproveLabel")}</strong> {node.proposal.on_approve}
              </p>
            )}
          </section>
        )}

        <section className={`tasks-drawer-section${isProposal && !node.proposal ? " tasks-drawer-section--butter" : ""}`}>
          <div className="tasks-drawer-section-label">
            <span>{t(isProposal && !node.proposal ? "tasks.panorama.whyProposed" : "tasks.panorama.backgroundReq")}</span>
            {node.can_edit && (
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--ghost tasks-pill-btn--xs"
                onClick={() => onEdit({ graph, node })}
              >
                {t("tasks.edit")}
              </button>
            )}
          </div>
          <div className="tasks-prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: TaskGraphLink }}>
              {node.description || t("tasks.noDescription")}
            </ReactMarkdown>
          </div>
        </section>

        {showProgressBlock && (
          <section className="tasks-drawer-section">
            <div className="tasks-drawer-section-label">
              <span>
                {t(
                  node.status === "done" || node.status === "closed"
                    ? "tasks.panorama.finalResult"
                    : "tasks.panorama.currentProgress",
                )}
              </span>
            </div>
            <div className="tasks-prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: TaskGraphLink }}>
                {node.result || t("tasks.noResult")}
              </ReactMarkdown>
            </div>
          </section>
        )}

        {node.change_note && (
          <section className="tasks-drawer-section">
            <h3>{t("tasks.changeNote")}</h3>
            <p className="tasks-prose">{node.change_note}</p>
          </section>
        )}

        {parent?.mode === "dag" && (predecessors.length > 0 || successors.length > 0) && (
          <section className="tasks-drawer-section">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.panorama.stageRelations")}</span>
            </div>
            {predecessors.length > 0 && (
              <div>
                <strong>{t("tasks.predecessors")}: </strong>
                <ul className="tasks-relations">
                  {predecessors.map(rel => (
                    <li key={rel.id}>
                      <button type="button" onClick={() => onSelect(rel)}>
                        {rel.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {successors.length > 0 && (
              <div>
                <strong>{t("tasks.successors")}: </strong>
                <ul className="tasks-relations">
                  {successors.map(rel => (
                    <li key={rel.id}>
                      <button type="button" onClick={() => onSelect(rel)}>
                        {rel.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {derivedSource && (
          <section className="tasks-drawer-section">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.derivedFrom")}</span>
            </div>
            <ul className="tasks-relations">
              <li>
                <button type="button" onClick={() => onSelect(derivedSource)}>
                  {derivedSource.title}
                </button>
              </li>
            </ul>
          </section>
        )}

        {currentChoice && (
          <section className="tasks-drawer-section">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.currentChoice")}</span>
            </div>
            <ul className="tasks-relations">
              <li>
                <button type="button" onClick={() => onSelect(currentChoice)}>
                  {currentChoice.title}
                </button>
              </li>
            </ul>
            <p>{node.selection_reason || t("tasks.noReason")}</p>
          </section>
        )}

        {node.links.length > 0 && (
          <section className="tasks-drawer-section">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.links")}</span>
            </div>
            <ul>
              {node.links.map((link, index) => (
                <li key={index}>
                  <ReactMarkdown components={{ a: TaskGraphLink }}>
                    {`[${link.replace(/[\[\]]/g, "\\$&")}](${link})`}
                  </ReactMarkdown>
                </li>
              ))}
            </ul>
          </section>
        )}

        {children.length > 0 && (
          <section className="tasks-drawer-section">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.structure")}</span>
              <span>{t("tasks.nodeCount", { count: children.length })}</span>
            </div>
            <TaskCounts counts={node.direct_counts} />
          </section>
        )}

        {deleting && (
          <section className="tasks-conflict">
            <h3>{t("tasks.deleteSubtree")}</h3>
            <p>{t("tasks.deleteScope", { title: node.title, count: deletionIds.size })}</p>
            <div className="tasks-drawer-action-row">
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--primary"
                disabled={busy}
                onClick={() =>
                  void onAct(async () => {
                    await writeTaskGraph(
                      `/${encodeURIComponent(graph.graph_id)}`,
                      {
                        base_revision: graph.revision,
                        request_key: crypto.randomUUID(),
                        node_id: node.id,
                      },
                      "DELETE",
                    );
                    onClose();
                    if (node.id === graph.root_node_id) onDeletedRoot?.();
                  })
                }
              >
                {t("tasks.confirmDelete", { count: deletionIds.size })}
              </button>
              <button type="button" className="tasks-pill-btn" onClick={() => setDeleting(false)}>
                {t("tasks.cancel")}
              </button>
            </div>
          </section>
        )}
      </div>

      <div className="tasks-drawer-foot">
        <div className="tasks-drawer-action-row">
          {isProposal && node.can_edit && (
            <>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--primary"
                disabled={busy}
                onClick={() => void applyOp([{ op: "approve_task", node_id: node.id }])}
              >
                {t(prereqBlocked ? "tasks.focus.approveQueue" : "tasks.focus.approveStart")}
              </button>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--stash"
                disabled={busy}
                onClick={() =>
                  void applyOp([{ op: "update_task", node_id: node.id, patch: { status: "backlog" } }])
                }
              >
                {t("tasks.focus.stashAction")}
              </button>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--ghost"
                disabled={busy}
                onClick={() =>
                  void applyOp([{ op: "update_task", node_id: node.id, patch: { status: "closed" } }])
                }
              >
                {t("tasks.focus.closeAction")}
              </button>
            </>
          )}

          {isStashed && node.can_edit && (
            <>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--soft"
                disabled={busy}
                onClick={() =>
                  void applyOp([{ op: "update_task", node_id: node.id, patch: { status: "todo" } }])
                }
              >
                {t("tasks.focus.activateTodo")}
              </button>
              {node.status === "paused" && (
                <button
                  type="button"
                  className="tasks-pill-btn"
                  disabled={busy}
                  onClick={() =>
                    void applyOp([{ op: "update_task", node_id: node.id, patch: { status: "doing" } }])
                  }
                >
                  {t("tasks.resume")}
                </button>
              )}
              {node.mode === "none" && (
                <button
                  type="button"
                  className="tasks-pill-btn"
                  disabled={busy}
                  onClick={() =>
                    void onAct(async () => {
                      await writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}/apply`, {
                        base_revision: graph.revision,
                        request_key: crypto.randomUUID(),
                        change_note: "",
                        operations: [{ op: "update_task", node_id: node.id, patch: { mode: "dag" } }],
                      });
                      onEnter(node);
                    })
                  }
                >
                  {t("tasks.focus.expandGoal")}
                </button>
              )}
            </>
          )}

          {node.status === "in_review" && node.can_edit && (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--primary"
              disabled={busy}
              onClick={() =>
                void applyOp([{ op: "update_task", node_id: node.id, patch: { status: "done" } }])
              }
            >
              {t("tasks.focus.confirmDone")}
            </button>
          )}

          {node.status === "waiting" && node.can_edit && (
            <>
              {(["doing", "paused", "backlog"] as TaskStatus[]).map(nextStatus => (
                <button
                  type="button"
                  className="tasks-pill-btn"
                  disabled={busy}
                  key={nextStatus}
                  onClick={() =>
                    void applyOp([{ op: "update_task", node_id: node.id, patch: { status: nextStatus } }])
                  }
                >
                  {t(
                    nextStatus === "doing"
                      ? "tasks.resume"
                      : nextStatus === "backlog"
                        ? "tasks.focus.stashAction"
                        : "tasks.status.paused",
                  )}
                </button>
              ))}
            </>
          )}

          {node.can_claim && node.status !== "doing" && (
            <button
              type="button"
              className="tasks-pill-btn"
              disabled={busy}
              onClick={() =>
                node.status === "done"
                  ? onEdit({ graph, node, claim: true })
                  : void applyOp([{ op: "claim_task", node_id: node.id }])
              }
            >
              {t("tasks.claim")}
            </button>
          )}

          {node.mode !== "none" && (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--soft"
              onClick={() => onEnter(node)}
            >
              {t("tasks.enter")} · {t(`tasks.mode.${node.mode}`)} →
            </button>
          )}

          {node.mode === "none" && node.can_edit && !isProposal && !isStashed && (
            <button
              type="button"
              className="tasks-pill-btn"
              onClick={() => onEdit({ graph, parent: node })}
            >
              {t("tasks.panorama.splitSingleCard")}
            </button>
          )}

          {node.last_chat_id && (
            <button type="button" className="tasks-pill-btn" onClick={() => onDiscuss(node)}>
              {t("tasks.discussNode")}
            </button>
          )}

          <button type="button" className="tasks-pill-btn" onClick={() => onCopy(node)}>
            {t("tasks.copyReference")}
          </button>

          {node.can_delete && (
            <details className="tasks-more-menu">
              <summary className="tasks-pill-btn tasks-pill-btn--ghost">{t("tasks.more")}</summary>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--danger"
                onClick={() => setDeleting(true)}
              >
                {t("tasks.delete")}
              </button>
            </details>
          )}
        </div>

        <div className="tasks-drawer-foot-meta">
          <span>
            {t("tasks.creator")}: {actorName(node.created_by) || "—"} · {t("tasks.updatedBy")}:{" "}
            {node.updated_by} · {new Date(node.updated_at).toLocaleString(i18n.language)} · v{graph.revision}
          </span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {!docked && returnChatId && (
              <Link className="tasks-inline-link" to={`/chat/${encodeURIComponent(returnChatId)}`}>
                {t("tasks.goChat")}
              </Link>
            )}
            {conversation && (
              <Link className="tasks-inline-link" to={`/chat/${encodeURIComponent(conversation.id)}`}>
                {t(conversation.dissolved_at ? "tasks.history" : "tasks.conversation")} · {conversation.title}
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
