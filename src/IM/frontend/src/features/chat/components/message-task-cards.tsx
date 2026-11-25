import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import {
  isTaskPrereqBlocked,
  taskGraphUrl,
  useTaskCardNodes,
  writeTaskGraph,
  type TaskCardRef,
  type TaskGraphSummary,
} from "../../tasks/task-graphs-api";
import { TaskStatusBadge } from "../../tasks/task-status-badge";
import "../../tasks/task-graphs.css";

/** Live-synced task cards embedded inside a chat message bubble via `message.task_cards`. */
export function MessageTaskCards({
  refs,
  conversationId,
  messageId,
  canWrite,
}: {
  refs: TaskCardRef[];
  conversationId: string;
  messageId?: string;
  canWrite: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useTaskCardNodes(refs);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const uniqueRefs = refs.filter(
    (ref, index, list) =>
      Boolean(ref.graph_id && ref.node_id) &&
      list.findIndex(item => item.graph_id === ref.graph_id && item.node_id === ref.node_id) === index,
  );
  if (!uniqueRefs.length) return null;

  async function applyCardOperation(card: TaskGraphSummary, operation: Record<string, unknown>, key: string) {
    setPendingKey(key);
    setErrorMessage(null);
    try {
      await writeTaskGraph(`/${encodeURIComponent(card.graph_id)}/apply`, {
        base_revision: card.revision,
        request_key: crypto.randomUUID(),
        change_note: "",
        operations: [operation],
      });
      await queryClient.invalidateQueries({ queryKey: ["task-graphs"] });
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : t("tasks.writeFailed"));
    } finally {
      setPendingKey(null);
    }
  }

  return (
    <div className="chat-embed-task-list" data-testid="message-task-cards">
      {uniqueRefs.map(ref => {
        const refKey = `${ref.graph_id}:${ref.node_id}`;
        if (query.isPending) {
          return (
            <div key={refKey} className="chat-embed-task chat-embed-task--unavailable">
              {t("common.loading")}
            </div>
          );
        }
        if (query.isError) {
          return (
            <div key={refKey} className="chat-embed-task chat-embed-task--unavailable" role="status">
              {t("tasks.readFailed")}
            </div>
          );
        }
        const card = query.data?.items.find(
          item => item.graph_id === ref.graph_id && (item.node_id ?? item.root_node_id) === ref.node_id,
        );
        if (!card) {
          return (
            <div
              key={refKey}
              className="chat-embed-task chat-embed-task--unavailable"
              data-testid="chat-task-card-unavailable"
            >
              {t("tasks.cards.unavailable")}
            </div>
          );
        }

        const nodeId = card.node_id ?? card.root_node_id;
        const isChild = Boolean(card.node_id && card.node_id !== card.root_node_id && card.root_title);
        const prereqBlocked = isTaskPrereqBlocked(card);
        const editable = canWrite && card.can_edit !== false && (card.conversation?.can_write ?? true);
        const targetUrl = taskGraphUrl(
          card.graph_id,
          card.scope_id ?? card.root_node_id,
          nodeId,
          conversationId,
          messageId,
        );
        const snippet =
          card.status === "proposed"
            ? [
                card.proposal?.rationale,
                card.proposal?.on_approve ? `${t("tasks.panorama.onApproveLabel")}${card.proposal.on_approve}` : "",
              ]
                .filter(Boolean)
                .join(" · ") || card.description
            : card.status === "waiting"
              ? [card.wait?.question, card.wait?.reason].filter(Boolean).join(" · ") || card.description
              : card.result || card.description;
        const statusNote =
          card.status === "doing"
            ? t("tasks.cards.approvedDoing")
            : card.status === "todo"
              ? t("tasks.cards.approvedTodo")
              : card.status === "backlog"
                ? t("tasks.cards.stashedNote")
                : card.assignee
                  ? t("tasks.focus.assigneeLabel", { assignee: card.assignee.display_name || card.assignee.id })
                  : "";

        return (
          <div
            key={refKey}
            role="link"
            tabIndex={0}
            data-testid={`chat-task-card-${card.graph_id}-${nodeId}`}
            className={`chat-embed-task${card.status === "proposed" ? " chat-embed-task--proposed" : ""}`}
            onClick={() => navigate(targetUrl)}
            onKeyDown={event => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                navigate(targetUrl);
              }
            }}
          >
            <div className="chat-embed-task-top">
              <span className={`tasks-card-crumb${isChild ? "" : " tasks-card-crumb--single"}`}>
                {isChild
                  ? t("tasks.focus.crumbGoal", { title: card.root_title })
                  : card.conversation?.title
                    ? t("tasks.focus.crumbSingle", { chat: card.conversation.title })
                    : t("tasks.taskReference")}
              </span>
              <TaskStatusBadge status={card.status} />
            </div>
            <div className="chat-embed-task-title">{card.title}</div>
            {snippet ? <p className="chat-embed-task-desc">{snippet}</p> : null}
            <div className="chat-embed-task-actions">
              {card.status === "proposed" && editable ? (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="tasks-pill-btn tasks-pill-btn--primary tasks-pill-btn--sm"
                    disabled={pendingKey !== null}
                    onClick={event => {
                      event.stopPropagation();
                      void applyCardOperation(card, { op: "approve_task", node_id: nodeId }, `${refKey}:approve`);
                    }}
                  >
                    {prereqBlocked ? t("tasks.focus.approveQueue") : t("tasks.focus.approveStart")}
                  </button>
                  <button
                    type="button"
                    className="tasks-pill-btn tasks-pill-btn--sm"
                    disabled={pendingKey !== null}
                    onClick={event => {
                      event.stopPropagation();
                      void applyCardOperation(
                        card,
                        { op: "update_task", node_id: nodeId, patch: { status: "backlog" } },
                        `${refKey}:stash`,
                      );
                    }}
                  >
                    {t("tasks.focus.stashAction")}
                  </button>
                  <button
                    type="button"
                    className="tasks-pill-btn tasks-pill-btn--ghost tasks-pill-btn--sm"
                    disabled={pendingKey !== null}
                    onClick={event => {
                      event.stopPropagation();
                      void applyCardOperation(
                        card,
                        { op: "update_task", node_id: nodeId, patch: { status: "closed" } },
                        `${refKey}:close`,
                      );
                    }}
                  >
                    {t("tasks.focus.closeAction")}
                  </button>
                </div>
              ) : (
                <span style={{ fontSize: 11.5, color: "var(--im-text-muted)" }}>{statusNote}</span>
              )}
              <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--im-accent)" }}>
                {t("tasks.cards.openTask")}
              </span>
            </div>
          </div>
        );
      })}
      {errorMessage ? (
        <p role="alert" style={{ margin: 0, fontSize: 11.5, color: "var(--im-danger)" }}>
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
