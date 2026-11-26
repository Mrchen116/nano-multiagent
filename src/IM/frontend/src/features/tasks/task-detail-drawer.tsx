import * as Dialog from "@radix-ui/react-dialog";
import { Link2, MoreHorizontal, Pencil, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
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
import { TaskAssigneePill, TaskWaitInfo } from "./task-wait";
import type { TaskEditTarget } from "./task-editor";

export interface TaskDetailDrawerProps {
  graph: TaskGraph;
  node: TaskNode;
  docked?: boolean;
  busy: boolean;
  error: string;
  returnChatId?: string | null;
  returnMessageId?: string | null;
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

function isAgentPopoverEvent(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(target.closest(".chat-agent-activity"));
}

function formatCompactTime(iso: string, lang: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(lang, {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function stripRawActorId(label: string): string {
  return label.replace(/\s*\([a-z0-9_-]{4,}\)\s*$/i, "").trim();
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
          onEscapeKeyDown={event => {
            if (document.querySelector(".chat-agent-activity, .tasks-more-dropdown")) {
              event.preventDefault();
            }
          }}
          onPointerDownOutside={event => {
            if (isAgentPopoverEvent(event.target)) event.preventDefault();
          }}
          onInteractOutside={event => {
            if (isAgentPopoverEvent(event.target)) event.preventDefault();
          }}
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
  returnMessageId,
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
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setDeleting(false);
    setMoreOpen(false);
  }, [graph.graph_id, node.id]);

  useEffect(() => {
    if (!moreOpen) return;
    const closeOutside = (event: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(event.target as Node)) {
        setMoreOpen(false);
      }
    };
    const closeEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeEsc, true);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeEsc, true);
    };
  }, [moreOpen]);

  const root = graph.nodes.find(candidate => candidate.id === graph.root_node_id);
  const parent = graph.nodes.find(candidate => candidate.id === node.container_id);
  const children = graph.nodes.filter(candidate => candidate.container_id === node.id);
  const isChildOfGoal = Boolean(root && node.id !== root.id);
  const prereqBlocked = isTaskPrereqBlocked(node, graph, node.id);
  const isProposal = node.status === "proposed";
  const isStashed = node.status === "backlog" || node.status === "paused";
  const hasProposal = isProposal && Boolean(node.proposal?.rationale || node.proposal?.on_approve);
  const hasDescription = Boolean(node.description?.trim());
  const hasResult = Boolean(node.result?.trim());

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
  const assigneeDisplayName = actorName(node.assignee);
  const showConversationCrumb =
    !isChildOfGoal &&
    Boolean(
      conversation &&
        (conversation.visibility === "public" || conversation.title !== assigneeDisplayName),
    );
  const canConfigureAgent = Boolean(
    node.assignee?.type === "agent" &&
      node.assignee.id.startsWith("pa_") &&
      conversation?.visibility === "private" &&
      conversation?.can_write,
  );
  const creatorLabel = stripRawActorId(actorName(node.created_by) || node.updated_by || "");
  const timeLabel = formatCompactTime(node.updated_at, i18n.language);
  const fallbackChatTarget = returnChatId || conversation?.id || null;

  return (
    <div className="tasks-drawer-inner">
      <div className="tasks-drawer-head">
        <div className="tasks-drawer-head-top">
          <div className="tasks-drawer-crumb-slot">
            {isChildOfGoal && root ? (
              <button
                type="button"
                className="tasks-goal-crumb"
                onClick={() => (onOpenGoal ? onOpenGoal(graph.graph_id) : onEnter(root))}
              >
                {t("tasks.focus.crumbGoal", { title: root.title })}
              </button>
            ) : !docked && returnChatId ? (
              <Link
                className="tasks-goal-crumb"
                to={`/chat/${encodeURIComponent(returnChatId)}`}
                state={returnMessageId ? { returnAnchorMessageId: returnMessageId } : undefined}
              >
                {t("tasks.panorama.backToChat")}
              </Link>
            ) : showConversationCrumb && conversation ? (
              <span className="tasks-goal-crumb tasks-goal-crumb--idea">
                {conversation.title}
              </span>
            ) : null}
          </div>

          <div className="tasks-drawer-head-tools">
            {node.can_edit && (
              <button
                type="button"
                className="tasks-icon-btn"
                aria-label={t("tasks.edit")}
                title={t("tasks.edit")}
                onClick={() => onEdit({ graph, node })}
              >
                <Pencil size={15} />
              </button>
            )}
            <button
              type="button"
              className="tasks-icon-btn"
              aria-label={t("tasks.copyReference")}
              title={t("tasks.copyReference")}
              onClick={() => onCopy(node)}
            >
              <Link2 size={15} />
            </button>
            {node.can_delete && (
              <div className="tasks-menu-anchor" ref={moreRef}>
                <button
                  type="button"
                  className="tasks-icon-btn"
                  aria-label={t("tasks.more")}
                  title={t("tasks.more")}
                  aria-expanded={moreOpen}
                  onClick={() => setMoreOpen(current => !current)}
                >
                  <MoreHorizontal size={16} />
                </button>
                {moreOpen && (
                  <div className="tasks-popover-menu tasks-popover-menu--right tasks-more-dropdown" role="menu">
                    <button
                      type="button"
                      role="menuitem"
                      className="tasks-popover-option tasks-popover-option--danger"
                      onClick={() => {
                        setMoreOpen(false);
                        setDeleting(true);
                      }}
                    >
                      <span className="tasks-popover-danger-label">
                        <Trash2 size={14} aria-hidden />
                        <span>{t("tasks.delete")}</span>
                      </span>
                    </button>
                  </div>
                )}
              </div>
            )}
            <button
              type="button"
              className="tasks-icon-btn"
              aria-label={t("tasks.close")}
              title={t("tasks.close")}
              onClick={onClose}
            >
              <X size={17} />
            </button>
          </div>
        </div>

        <h2 className="tasks-drawer-title">{node.title}</h2>

        <div className="tasks-drawer-meta">
          <TaskStatusBadge status={node.status} />
          <TaskAssigneePill
            assignee={node.assignee}
            graphId={graph.graph_id}
            nodeId={node.id}
            canConfigureAgent={canConfigureAgent}
            canEdit={node.can_edit}
            onAssignClick={() => onEdit({ graph, node })}
          />
          {node.mode !== "none" && <span className="tasks-mode">{t(`tasks.mode.${node.mode}`)}</span>}
        </div>
      </div>

      <div className="tasks-drawer-body">
        {error && (
          <p className="tasks-notice" role="alert">
            {error}
          </p>
        )}

        {deleting && (
          <section className="tasks-conflict">
            <h3>{t("tasks.deleteSubtree")}</h3>
            <p>{t("tasks.deleteScope", { title: node.title, count: deletionIds.size })}</p>
            <div className="tasks-drawer-action-row">
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--danger"
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

        {node.status === "waiting" && (
          <section className="tasks-drawer-section tasks-drawer-section--wait">
            <TaskWaitInfo wait={node.wait} health={node.wait_health} />
          </section>
        )}

        {hasProposal && (
          <section className="tasks-proposal-callout">
            <h3 className="tasks-drawer-heading tasks-drawer-heading--proposal">
              {t("tasks.panorama.whyProposed")}
            </h3>
            {node.proposal?.rationale && (
              <p className="tasks-proposal-rationale">{node.proposal.rationale}</p>
            )}
            {node.proposal?.on_approve && (
              <p className="tasks-proposal-plan">
                <strong>{t("tasks.panorama.onApproveShort")}</strong>
                {node.proposal.on_approve}
              </p>
            )}
          </section>
        )}

        {(hasDescription || (!hasProposal && node.status !== "waiting" && !hasResult)) && (
          <section className="tasks-drawer-block">
            <h3 className="tasks-drawer-heading">{t("tasks.panorama.backgroundReq")}</h3>
            <div className={`tasks-prose tasks-drawer-prose${!hasDescription ? " is-empty" : ""}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: TaskGraphLink }}>
                {hasDescription ? node.description : t("tasks.noDescription")}
              </ReactMarkdown>
            </div>
          </section>
        )}

        {hasResult && (
          <section className="tasks-result-block">
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
                {node.result}
              </ReactMarkdown>
            </div>
          </section>
        )}

        {node.change_note && (
          <section className="tasks-drawer-group">
            <h3>{t("tasks.changeNote")}</h3>
            <p className="tasks-prose">{node.change_note}</p>
          </section>
        )}

        {parent?.mode === "dag" && (predecessors.length > 0 || successors.length > 0) && (
          <section className="tasks-drawer-group">
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
          <section className="tasks-drawer-group">
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
          <section className="tasks-drawer-group">
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
            {node.selection_reason && <p>{node.selection_reason}</p>}
          </section>
        )}

        {node.links.length > 0 && (
          <section className="tasks-drawer-group">
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
          <section className="tasks-drawer-group">
            <div className="tasks-drawer-section-label">
              <span>{t("tasks.structure")}</span>
              <span>{t("tasks.nodeCount", { count: children.length })}</span>
            </div>
            <TaskCounts counts={node.direct_counts} />
          </section>
        )}

        {(creatorLabel || timeLabel) && (
          <p className="tasks-drawer-byline">
            {creatorLabel ? t("tasks.bylineCreated", { creator: creatorLabel }) : ""}
            {creatorLabel && timeLabel ? " · " : ""}
            {timeLabel}
          </p>
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
                {t("tasks.focus.dismissProposal")}
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
        </div>

        {node.last_chat_id ? (
          <button
            type="button"
            className="tasks-pill-btn tasks-pill-btn--soft"
            onClick={() => onDiscuss(node)}
          >
            {t("tasks.discussNode")}
          </button>
        ) : !docked && fallbackChatTarget ? (
          <Link
            className="tasks-pill-btn tasks-pill-btn--soft"
            to={`/chat/${encodeURIComponent(fallbackChatTarget)}`}
          >
            {t("tasks.goChat")}
          </Link>
        ) : null}
      </div>
    </div>
  );
}
