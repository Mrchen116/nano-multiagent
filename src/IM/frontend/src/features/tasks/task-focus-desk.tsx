import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { listConversations } from "../chat/chat-api";
import type { Conversation } from "../chat/chat-types";
import { listContacts } from "../chat/contacts-api";
import {
  getTaskFocus,
  isTaskPrereqBlocked,
  taskGraphUrl,
  useTaskFocus,
  writeTaskGraph,
  type TaskFocusGoalItem,
  type TaskFocusScope,
  type TaskFocusSection,
  type TaskGraphSummary,
} from "./task-graphs-api";
import { actorName, plainTaskSnippet } from "./task-progress";
import { TaskStatusBadge, TaskStatusHelpDialog } from "./task-status-badge";
import { TaskAssigneeInline } from "./task-wait";
import type { TaskEditTarget } from "./task-editor";

function isPersonalConversation(chat: Conversation): boolean {
  return (
    chat.type === "direct" &&
    chat.participants.some(actor => actor.type === "agent" && actor.role === "personal")
  );
}

export function TaskFocusDesk({
  selectedKey,
  onSelectCard,
  onOpenEditor,
}: {
  selectedKey?: string | null;
  onSelectCard(item: TaskGraphSummary): void;
  onOpenEditor(target: TaskEditTarget): void;
}) {
  const { t, i18n } = useTranslation();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();

  const rawScope = params.get("scope") ?? (params.get("collection") === "assignee" ? "assignee" : "mine");
  const scope: TaskFocusScope =
    rawScope === "assignee" || rawScope === "all" ? rawScope : "mine";
  const lens: "actions" | "goals" = params.get("lens") === "goals" ? "goals" : "actions";
  const assigneeType = params.get("assignee_type") ?? "";
  const assigneeId = params.get("assignee_id") ?? "";
  const conversationFilter = params.get("conversation_id") ?? "";
  const queryText = params.get("query") ?? "";

  const [searchInput, setSearchInput] = useState(queryText);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(Boolean(queryText));
  const [inboxTab, setInboxTab] = useState<"needs_you" | "stashed">("needs_you");
  const [completedOpen, setCompletedOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [openMenu, setOpenMenu] = useState<"" | "scope" | "assignee" | "chatFilter" | "createTarget">("");
  const [quickTitle, setQuickTitle] = useState("");
  const [targetChatId, setTargetChatId] = useState(conversationFilter);
  const [busyCardKey, setBusyCardKey] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [appendedPages, setAppendedPages] = useState<Partial<Record<TaskFocusSection, TaskGraphSummary[]>>>({});
  const [sectionCursors, setSectionCursors] = useState<Partial<Record<TaskFocusSection, string | null>>>({});
  const toastTimer = useRef<number | null>(null);
  const menuWrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSearchInput(queryText);
  }, [queryText]);

  useEffect(() => {
    setAppendedPages({});
    setSectionCursors({});
  }, [scope, assigneeType, assigneeId, conversationFilter, queryText]);

  useEffect(() => {
    const onDocClick = (event: MouseEvent) => {
      if (openMenu && menuWrapRef.current && !menuWrapRef.current.contains(event.target as Node)) {
        setOpenMenu("");
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [openMenu]);

  useEffect(
    () => () => {
      if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    },
    [],
  );

  function showToast(message: string) {
    setToast(message);
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2600);
  }

  const conversationsQuery = useQuery({
    queryKey: ["task-write-conversations"],
    queryFn: listConversations,
  });
  const accessibleChats = conversationsQuery.data ?? [];
  const writableChats = useMemo(
    () =>
      accessibleChats
        .filter(chat => chat.can_write !== false && !chat.dissolved_at)
        .sort((a, b) => Number(isPersonalConversation(b)) - Number(isPersonalConversation(a))),
    [accessibleChats],
  );

  useEffect(() => {
    if (targetChatId && writableChats.some(c => c.id === targetChatId)) return;
    if (conversationFilter && writableChats.some(c => c.id === conversationFilter)) {
      setTargetChatId(conversationFilter);
      return;
    }
    if (writableChats.length > 0) setTargetChatId(writableChats[0]!.id);
  }, [writableChats, targetChatId, conversationFilter]);

  const contactsQuery = useQuery({
    queryKey: ["task-assignee-contacts"],
    queryFn: () => listContacts(),
    enabled: scope === "assignee",
  });

  const focusOptions = useMemo(
    () => ({
      scope,
      ...(scope === "assignee" ? { assignee_type: assigneeType, assignee_id: assigneeId } : {}),
      ...(conversationFilter ? { conversation_id: conversationFilter } : {}),
      ...(queryText ? { query: queryText } : {}),
    }),
    [scope, assigneeType, assigneeId, conversationFilter, queryText],
  );

  const focusQuery = useTaskFocus(focusOptions);
  const focus = focusQuery.data;

  const completedQuery = useTaskFocus(
    useMemo(() => ({ ...focusOptions, section: "completed" as const }), [focusOptions]),
    completedOpen,
  );

  function updateParams(mutator: (next: URLSearchParams) => void) {
    const next = new URLSearchParams(params);
    next.delete("collection");
    mutator(next);
    setParams(next);
  }

  const mergeItems = <T extends TaskGraphSummary>(base: T[], section: TaskFocusSection): T[] => {
    const extra = (appendedPages[section] ?? []) as T[];
    const byKey = new Map<string, T>();
    for (const item of [...base, ...extra]) {
      byKey.set(`${item.graph_id}:${item.node_id ?? item.root_node_id}`, item);
    }
    return [...byKey.values()];
  };

  const needsYou = mergeItems(focus?.needs_you ?? [], "needs_you");
  const stashed = mergeItems(focus?.stashed ?? [], "stashed");
  const active = mergeItems(focus?.active ?? [], "active");
  const goals = mergeItems(focus?.goals ?? [], "goals");
  const completedItems = mergeItems(completedQuery.data?.completed ?? [], "completed");

  const counts = focus?.counts ?? { needs_you: 0, stashed: 0, active: 0, goals: 0, completed: 0 };
  const actionCount = counts.needs_you + counts.active;
  const completedNextCursor =
    sectionCursors.completed !== undefined
      ? sectionCursors.completed
      : completedQuery.data?.next_cursors.completed ?? null;

  async function loadMoreSection(section: TaskFocusSection) {
    const baseCursor =
      section === "completed" ? completedQuery.data?.next_cursors.completed : focus?.next_cursors[section];
    const cursor = sectionCursors[section] !== undefined ? sectionCursors[section] : baseCursor;
    if (!cursor) return;
    const more = await getTaskFocus({ ...focusOptions, section, cursor });
    if (!more) return;
    setAppendedPages(prev => ({ ...prev, [section]: [...(prev[section] ?? []), ...(more[section] ?? [])] }));
    setSectionCursors(prev => ({ ...prev, [section]: more.next_cursors[section] }));
  }

  async function submitQuickCapture(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = quickTitle.trim();
    if (!trimmed || !targetChatId) return;
    setBusyCardKey("quick-capture");
    try {
      await writeTaskGraph("", {
        title: trimmed,
        conversation_id: targetChatId,
        mode: "none",
        status: "todo",
        request_key: crypto.randomUUID(),
      });
      setQuickTitle("");
      if (lens !== "actions") {
        updateParams(next => next.delete("lens"));
      }
      await client.invalidateQueries({ queryKey: ["task-graphs"] });
      showToast(t("tasks.focus.toastCaptured", { title: trimmed }));
    } catch (err) {
      showToast(err instanceof Error ? err.message : t("tasks.writeFailed"));
    } finally {
      setBusyCardKey(null);
    }
  }

  async function runCardAction(
    item: TaskGraphSummary,
    operations: Record<string, unknown>[],
    toastMsg: string,
    after?: () => void,
  ) {
    const key = `${item.graph_id}:${item.node_id ?? item.root_node_id}`;
    setBusyCardKey(key);
    try {
      await writeTaskGraph(`/${encodeURIComponent(item.graph_id)}/apply`, {
        base_revision: item.revision,
        request_key: crypto.randomUUID(),
        change_note: "",
        operations,
      });
      await client.invalidateQueries({ queryKey: ["task-graphs"] });
      showToast(toastMsg);
      after?.();
    } catch (err) {
      showToast(err instanceof Error ? err.message : t("tasks.writeFailed"));
    } finally {
      setBusyCardKey(null);
    }
  }

  function renderCrumb(item: TaskGraphSummary) {
    const nodeId = item.node_id ?? item.root_node_id;
    const isSubNode = nodeId !== item.root_node_id || (item.parent_path?.length ?? 0) > 0;
    if (isSubNode) {
      const goalTitle =
        (item.parent_path?.length ?? 0) > 1
          ? item.parent_path!.map(step => step.title).join(" / ")
          : item.root_title || item.parent_path?.[0]?.title || item.title;
      return (
        <button
          type="button"
          className="tasks-goal-crumb"
          onClick={e => {
            e.stopPropagation();
            navigate(taskGraphUrl(item.graph_id));
          }}
        >
          {t("tasks.focus.crumbGoal", { title: goalTitle })}
        </button>
      );
    }
    const chatTitle = item.conversation?.title ?? "";
    const isGroup = item.conversation?.visibility === "public";
    return (
      <span className={`tasks-goal-crumb ${isGroup ? "tasks-goal-crumb--team" : "tasks-goal-crumb--idea"}`}>
        {chatTitle
          ? t(isGroup ? "tasks.focus.crumbGroupSingle" : "tasks.focus.crumbSingle", { chat: chatTitle })
          : t("tasks.mode.none")}
      </span>
    );
  }

  function handleCardOpen(item: TaskGraphSummary) {
    if (scope === "assignee") {
      const nodeId = item.node_id ?? item.root_node_id;
      navigate(taskGraphUrl(item.graph_id, item.scope_id ?? nodeId, nodeId));
      return;
    }
    onSelectCard(item);
  }

  function renderActionCard(item: TaskGraphSummary) {
    const nodeId = item.node_id ?? item.root_node_id;
    const cardKey = `${item.graph_id}:${nodeId}`;
    const selected = selectedKey === cardKey;
    const isProposal = item.status === "proposed";
    const isStashed = item.status === "backlog" || item.status === "paused";
    const prereqBlocked = isTaskPrereqBlocked(item);
    const canEdit = item.can_edit !== false && item.conversation?.can_write !== false;
    const cardBusy = busyCardKey === cardKey;

    const descSnippet = plainTaskSnippet(
      item.status === "waiting"
        ? ""
        : (item.status === "in_review" || item.status === "done") && item.result?.trim()
          ? item.result
          : item.description,
    );

    return (
      <article
        key={cardKey}
        className={`tasks-focus-card${isProposal ? " tasks-focus-card--proposal" : ""}${
          isStashed ? " tasks-focus-card--stashed" : ""
        }${selected ? " is-selected" : ""}`}
        onClick={() => handleCardOpen(item)}
      >
        <div className="tasks-card-main">
          {renderCrumb(item)}
          <h3 className="tasks-card-title">
            <button
              type="button"
              className="tasks-card-title-btn"
              aria-label={t("tasks.viewNode", { title: item.title })}
              onClick={e => {
                e.stopPropagation();
                handleCardOpen(item);
              }}
            >
              {item.title}
            </button>
          </h3>
          {descSnippet && <p className="tasks-card-desc">{descSnippet}</p>}
          <div className="tasks-card-meta-row">
            <TaskStatusBadge status={item.status} />
            {item.status === "waiting" && item.wait?.reason && (
              <span className="tasks-wait-chip">{item.wait.reason}</span>
            )}
            {item.status === "waiting" && item.wait?.next_check_at && (
              <span className="tasks-meta-tag">
                {t("tasks.wait.nextCheck")} · {new Date(item.wait.next_check_at).toLocaleString(i18n.language)}
              </span>
            )}
            {item.status === "todo" && prereqBlocked && (
              <span className="tasks-wait-chip">{t("tasks.focus.prereqWaiting")}</span>
            )}
            <TaskAssigneeInline assignee={item.assignee} stashedMuted={isStashed} />
          </div>
        </div>

        <div className="tasks-card-actions" onClick={e => e.stopPropagation()}>
          {isProposal && canEdit && (
            <>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--primary"
                disabled={cardBusy}
                onClick={() =>
                  void runCardAction(
                    item,
                    [{ op: "approve_task", node_id: nodeId }],
                    t(
                      prereqBlocked
                        ? "tasks.focus.toastApprovedQueue"
                        : "tasks.focus.toastApprovedStart",
                      { title: item.title },
                    ),
                  )
                }
              >
                {t(prereqBlocked ? "tasks.focus.approveQueue" : "tasks.focus.approveStart")}
              </button>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--stash"
                disabled={cardBusy}
                onClick={() =>
                  void runCardAction(
                    item,
                    [{ op: "update_task", node_id: nodeId, patch: { status: "backlog" } }],
                    t("tasks.focus.toastStashed", { title: item.title }),
                  )
                }
              >
                {t("tasks.focus.stashAction")}
              </button>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--ghost"
                disabled={cardBusy}
                onClick={() =>
                  void runCardAction(
                    item,
                    [{ op: "update_task", node_id: nodeId, patch: { status: "closed" } }],
                    t("tasks.focus.toastClosed", { title: item.title }),
                  )
                }
              >
                {t("tasks.focus.closeAction")}
              </button>
            </>
          )}

          {item.status === "in_review" && canEdit && (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--primary"
              disabled={cardBusy}
              onClick={() =>
                void runCardAction(
                  item,
                  [{ op: "update_task", node_id: nodeId, patch: { status: "done" } }],
                  t("tasks.focus.toastDone", { title: item.title }),
                )
              }
            >
              {t("tasks.focus.confirmDone")}
            </button>
          )}

          {item.status === "waiting" && item.wait?.asked_user_id && item.conversation && (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--soft"
              onClick={() => navigate(`/chat/${encodeURIComponent(item.conversation!.id)}`)}
            >
              {t("tasks.focus.replyInChat")}
            </button>
          )}

          {isStashed && canEdit && (
            <>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--soft"
                disabled={cardBusy}
                onClick={() =>
                  void runCardAction(
                    item,
                    [{ op: "update_task", node_id: nodeId, patch: { status: "todo" } }],
                    t("tasks.focus.toastActivated", { title: item.title }),
                  )
                }
              >
                {t("tasks.focus.activateTodo")}
              </button>
              <button
                type="button"
                className="tasks-pill-btn"
                disabled={cardBusy}
                onClick={() => {
                  if (item.mode !== "none") {
                    navigate(taskGraphUrl(item.graph_id, nodeId === item.root_node_id ? undefined : nodeId));
                    return;
                  }
                  void runCardAction(
                    item,
                    [{ op: "update_task", node_id: nodeId, patch: { mode: "dag" } }],
                    item.title,
                    () =>
                      navigate(
                        taskGraphUrl(item.graph_id, nodeId === item.root_node_id ? undefined : nodeId),
                      ),
                  );
                }}
              >
                {t("tasks.focus.expandGoal")}
              </button>
              <button
                type="button"
                className="tasks-pill-btn tasks-pill-btn--ghost"
                disabled={cardBusy}
                onClick={() =>
                  void runCardAction(
                    item,
                    [{ op: "update_task", node_id: nodeId, patch: { status: "closed" } }],
                    t("tasks.focus.toastClosed", { title: item.title }),
                  )
                }
              >
                {t("tasks.focus.closeAction")}
              </button>
            </>
          )}

          {!isProposal && !isStashed && item.mode !== "none" && (
            <button
              type="button"
              className="tasks-pill-btn"
              aria-label={t("tasks.enterNode", { title: item.title })}
              onClick={() => navigate(taskGraphUrl(item.graph_id, nodeId === item.root_node_id ? undefined : nodeId))}
            >
              {t("tasks.focus.openGoal")}
            </button>
          )}
        </div>
      </article>
    );
  }

  function renderGoalCard(goal: TaskFocusGoalItem) {
    const stages = goal.stage_nodes ?? [];
    const total = Math.max(1, goal.progress?.total ?? (stages.length || 1));
    const doneCount = goal.progress?.done ?? stages.filter(s => s.status === "done").length;
    const activeStageCount = stages.filter(s => ["doing", "waiting", "in_review"].includes(s.status)).length;
    const proposedStageCount = stages.filter(s => s.status === "proposed").length;
    const donePct = Math.min(100, Math.round((doneCount / total) * 100));
    const doingPct = Math.min(100 - donePct, Math.round((activeStageCount / total) * 100));
    const propPct = Math.min(100 - donePct - doingPct, Math.round((proposedStageCount / total) * 100));
    const summaryText = goal.root_goal_summary || goal.description;

    return (
      <article
        key={goal.graph_id}
        className="tasks-goal-card"
        role="button"
        tabIndex={0}
        aria-label={t("tasks.enterNode", { title: goal.title })}
        onClick={() => navigate(taskGraphUrl(goal.graph_id))}
        onKeyDown={e => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            navigate(taskGraphUrl(goal.graph_id));
          }
        }}
      >
        <div className="tasks-goal-card-top">
          <div className="tasks-goal-card-tags">
            <TaskStatusBadge status={goal.status} />
            {goal.conversation && (
              <span className="tasks-meta-tag">
                {t("tasks.focus.crumbGroup", { chat: goal.conversation.title })}
              </span>
            )}
            <span className="tasks-goal-progress-text">
              {t("tasks.focus.stageProgress", { done: doneCount, total: goal.progress?.total ?? stages.length })}
            </span>
          </div>
          <span className="tasks-inline-link">{t("tasks.focus.openPanorama")}</span>
        </div>

        <div>
          <h3 className="tasks-goal-card-title">{goal.title}</h3>
          {summaryText && (
            <p className="tasks-card-desc">
              {t("tasks.focus.northStarPrefix", { summary: summaryText })}
            </p>
          )}
        </div>

        <div className="tasks-goal-bar" aria-hidden>
          <div className="tasks-goal-bar-done" style={{ width: `${donePct}%` }} />
          <div className="tasks-goal-bar-doing" style={{ width: `${doingPct}%` }} />
          <div className="tasks-goal-bar-prop" style={{ width: `${propPct}%` }} />
        </div>

        {stages.length > 0 && (
          <div className="tasks-goal-stage-strip">
            {stages.map((stage, idx) => {
              const activeStep = ["doing", "waiting", "in_review"].includes(stage.status);
              const prefix = stage.status === "done" ? "✓" : activeStep ? "●" : "◌";
              return (
                <span key={stage.id} className="tasks-goal-stage-wrap">
                  {idx > 0 && (
                    <span className="tasks-goal-stage-sep">
                      {stage.status === "proposed" ? "⇢" : "→"}
                    </span>
                  )}
                  <span className={`tasks-goal-stage-step${activeStep ? " is-active" : ""}`}>
                    {prefix} {stage.title}
                  </span>
                </span>
              );
            })}
          </div>
        )}
      </article>
    );
  }

  const selectedTargetChat = writableChats.find(c => c.id === targetChatId);
  const targetIsPersonal = selectedTargetChat ? isPersonalConversation(selectedTargetChat) : true;
  const selectedAssigneeContact = contactsQuery.data?.find(
    c => `${c.kind === "human" ? "user" : "agent"}:${c.agent_id ?? c.user_id}` === `${assigneeType}:${assigneeId}`,
  );
  const selectedFilterChat = accessibleChats.find(c => c.id === conversationFilter);

  const scopeLabel =
    scope === "assignee"
      ? t("tasks.focus.scopeAssignee")
      : scope === "all"
        ? t("tasks.focus.scopeAll")
        : t("tasks.focus.scopeMine");

  return (
    <div className="tasks-focus-workspace" ref={menuWrapRef}>
      <div className="tasks-focus-topbar">
        <div className="tasks-topbar-title-group">
          <h1 className="tasks-topbar-title">{t("tasks.focus.heading")}</h1>
          <div className="tasks-scope-tabs" role="tablist" aria-label={t("tasks.focus.lensLabel")}>
            <button
              type="button"
              role="tab"
              aria-selected={lens === "actions"}
              className={`tasks-scope-tab${lens === "actions" ? " is-active" : ""}`}
              onClick={() => updateParams(next => next.delete("lens"))}
            >
              <span>{t("tasks.focus.actionsLens")}</span>
              <span className="tasks-scope-tab-count">{actionCount}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={lens === "goals"}
              className={`tasks-scope-tab${lens === "goals" ? " is-active" : ""}`}
              onClick={() => updateParams(next => next.set("lens", "goals"))}
            >
              <span>{t("tasks.focus.goalsLens")}</span>
              <span className="tasks-scope-tab-count">{counts.goals}</span>
            </button>
          </div>
        </div>

        <div className="tasks-topbar-controls">
          {/* Scope pill popover */}
          <div className="tasks-menu-anchor">
            <button
              type="button"
              className="tasks-pill-select"
              aria-expanded={openMenu === "scope"}
              onClick={() => setOpenMenu(current => (current === "scope" ? "" : "scope"))}
            >
              <span className="tasks-pill-dot" aria-hidden />
              <span>{scopeLabel}</span>
              <span aria-hidden>▾</span>
            </button>
            {openMenu === "scope" && (
              <div className="tasks-popover-menu tasks-popover-menu--right" role="menu">
                {(
                  [
                    ["mine", t("tasks.focus.scopeMine"), t("tasks.focus.scopeMineDesc")],
                    ["assignee", t("tasks.focus.scopeAssignee"), t("tasks.focus.scopeAssigneeDesc")],
                    ["all", t("tasks.focus.scopeAll"), t("tasks.focus.scopeAllDesc")],
                  ] as const
                ).map(([val, label, desc]) => (
                  <button
                    key={val}
                    type="button"
                    role="menuitemradio"
                    aria-checked={scope === val}
                    className={`tasks-popover-option${scope === val ? " is-selected" : ""}`}
                    onClick={() => {
                      setOpenMenu("");
                      updateParams(next => {
                        val === "mine" ? next.delete("scope") : next.set("scope", val);
                        if (val !== "assignee") {
                          next.delete("assignee_type");
                          next.delete("assignee_id");
                        }
                      });
                    }}
                  >
                    <div>
                      {label}
                      <small>{desc}</small>
                    </div>
                    {scope === val && <span aria-hidden>✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Assignee pill popover when scope === 'assignee' */}
          {scope === "assignee" && (
            <div className="tasks-menu-anchor">
              <button
                type="button"
                className="tasks-pill-select"
                aria-label={t("tasks.assignee")}
                aria-expanded={openMenu === "assignee"}
                onClick={() => setOpenMenu(current => (current === "assignee" ? "" : "assignee"))}
              >
                <span>{selectedAssigneeContact?.display_name || assigneeId || t("tasks.chooseAssignee")}</span>
                <span aria-hidden>▾</span>
              </button>
              {openMenu === "assignee" && (
                <div className="tasks-popover-menu tasks-popover-menu--right" role="menu">
                  {(contactsQuery.data ?? []).map(contact => {
                    const cType = contact.kind === "human" ? "user" : "agent";
                    const cId = contact.agent_id ?? contact.user_id;
                    const activeAssignee = assigneeType === cType && assigneeId === cId;
                    return (
                      <button
                        key={contact.user_id}
                        type="button"
                        role="menuitemradio"
                        aria-checked={activeAssignee}
                        className={`tasks-popover-option${activeAssignee ? " is-selected" : ""}`}
                        onClick={() => {
                          setOpenMenu("");
                          updateParams(next => {
                            next.set("scope", "assignee");
                            next.set("assignee_type", cType);
                            next.set("assignee_id", cId);
                          });
                        }}
                      >
                        <div>{contact.display_name}</div>
                        {activeAssignee && <span aria-hidden>✓</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Conversation filter pill popover */}
          {accessibleChats.length > 0 && (
            <div className="tasks-menu-anchor">
              <button
                type="button"
                className="tasks-pill-select"
                aria-label={t("tasks.focus.conversationFilter")}
                aria-expanded={openMenu === "chatFilter"}
                onClick={() => setOpenMenu(current => (current === "chatFilter" ? "" : "chatFilter"))}
              >
                <span>{selectedFilterChat?.title ?? t("tasks.focus.allConversations")}</span>
                <span aria-hidden>▾</span>
              </button>
              {openMenu === "chatFilter" && (
                <div className="tasks-popover-menu tasks-popover-menu--right" role="menu">
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={!conversationFilter}
                    className={`tasks-popover-option${!conversationFilter ? " is-selected" : ""}`}
                    onClick={() => {
                      setOpenMenu("");
                      updateParams(next => next.delete("conversation_id"));
                    }}
                  >
                    <div>{t("tasks.focus.allConversations")}</div>
                    {!conversationFilter && <span aria-hidden>✓</span>}
                  </button>
                  {accessibleChats.map(chat => (
                    <button
                      key={chat.id}
                      type="button"
                      role="menuitemradio"
                      aria-checked={conversationFilter === chat.id}
                      className={`tasks-popover-option${conversationFilter === chat.id ? " is-selected" : ""}`}
                      onClick={() => {
                        setOpenMenu("");
                        updateParams(next => next.set("conversation_id", chat.id));
                      }}
                    >
                      <div>{chat.title}</div>
                      {conversationFilter === chat.id && <span aria-hidden>✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Search */}
          {isMobile && !mobileSearchOpen ? (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--ghost"
              aria-label={t("tasks.search")}
              onClick={() => setMobileSearchOpen(true)}
            >
              🔍 {t("tasks.focus.searchMobile")}
            </button>
          ) : (
            <form
              className="tasks-search-shell"
              onSubmit={e => {
                e.preventDefault();
                updateParams(next => {
                  const q = searchInput.trim();
                  q ? next.set("query", q) : next.delete("query");
                });
              }}
            >
              <span className="tasks-search-icon" aria-hidden>
                🔍
              </span>
              <input
                className="tasks-search-input"
                aria-label={t("tasks.search")}
                value={searchInput}
                placeholder={t("tasks.focus.searchPlaceholder")}
                onChange={e => setSearchInput(e.target.value)}
              />
            </form>
          )}

          {isMobile && (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--soft"
              onClick={() =>
                onOpenEditor({
                  conversationId: targetChatId || undefined,
                  initialTitle: quickTitle.trim() || undefined,
                  defaultMode: "dag",
                })
              }
            >
              {t("tasks.focus.splitGoalMobile")}
            </button>
          )}

          <button
            type="button"
            className="tasks-help-btn"
            aria-label={t("tasks.focus.helpAria")}
            onClick={() => setHelpOpen(true)}
          >
            <span className="tasks-help-qmark" aria-hidden>
              ?
            </span>
            <span>{t("tasks.focus.helpButton")}</span>
          </button>
        </div>
      </div>

      <div className="tasks-focus-body">
        {/* Quick-capture rounded bar */}
        <form className="tasks-quick-create" onSubmit={e => void submitQuickCapture(e)}>
          <div className="tasks-menu-anchor">
            <button
              type="button"
              className={`tasks-pill-select ${
                targetIsPersonal ? "tasks-pill-select--butter" : "tasks-pill-select--mint"
              }`}
              disabled={writableChats.length === 0}
              aria-expanded={openMenu === "createTarget"}
              onClick={() => setOpenMenu(current => (current === "createTarget" ? "" : "createTarget"))}
            >
              <span aria-hidden>{targetIsPersonal ? "✦" : "◎"}</span>
              <span>{selectedTargetChat?.title ?? t("tasks.focus.noWritableChat")}</span>
              <span aria-hidden>▾</span>
            </button>
            {openMenu === "createTarget" && writableChats.length > 0 && (
              <div className="tasks-popover-menu" role="menu">
                {writableChats.map(chat => {
                  const personal = isPersonalConversation(chat);
                  const selected = chat.id === targetChatId;
                  return (
                    <button
                      key={chat.id}
                      type="button"
                      role="menuitemradio"
                      aria-checked={selected}
                      className={`tasks-popover-option${selected ? " is-selected" : ""}`}
                      onClick={() => {
                        setTargetChatId(chat.id);
                        setOpenMenu("");
                      }}
                    >
                      <div>
                        {chat.title}
                        <small>
                          {t(personal ? "tasks.focus.targetPersonalHint" : "tasks.focus.targetGroupHint")}
                        </small>
                      </div>
                      {selected && <span aria-hidden>✓</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <input
            value={quickTitle}
            onChange={e => setQuickTitle(e.target.value)}
            placeholder={t(isMobile ? "tasks.focus.quickCaptureMobile" : "tasks.focus.quickCapturePlaceholder")}
            aria-label={t("tasks.focus.quickCaptureAria")}
          />

          {!isMobile && (
            <button
              type="button"
              className="tasks-pill-btn tasks-pill-btn--soft"
              onClick={() =>
                onOpenEditor({
                  conversationId: targetChatId || undefined,
                  initialTitle: quickTitle.trim() || undefined,
                  defaultMode: "dag",
                })
              }
            >
              {t("tasks.focus.splitGoal")}
            </button>
          )}

          <button
            type="submit"
            className="tasks-pill-btn tasks-pill-btn--primary"
            disabled={!quickTitle.trim() || !targetChatId || busyCardKey === "quick-capture"}
          >
            {t("tasks.focus.quickCaptureAdd")}
          </button>
        </form>

        {scope === "assignee" && (!assigneeType || !assigneeId) ? (
          <div className="tasks-calm-zero">{t("tasks.chooseAssignee")}</div>
        ) : focusQuery.isPending ? (
          <div className="tasks-calm-zero" role="status">
            {t("tasks.loading")}
          </div>
        ) : focusQuery.isError ? (
          <div className="tasks-notice" role="alert">
            <span>{t("tasks.readFailed")}</span>
            <button type="button" className="tasks-pill-btn" onClick={() => void focusQuery.refetch()}>
              {t("tasks.refresh")}
            </button>
          </div>
        ) : focus === null ? (
          <div className="tasks-calm-zero" role="alert">
            {t("tasks.unavailable")}
          </div>
        ) : lens === "goals" ? (
          <section aria-label={t("tasks.focus.goalsTitle")}>
            <div className="tasks-section-head">
              <h2 className="tasks-section-title">
                {t("tasks.focus.goalsTitle")} <span className="tasks-count-pill">{counts.goals}</span>
              </h2>
            </div>
            {goals.length === 0 ? (
              <div className="tasks-calm-zero">{t("tasks.focus.goalsEmpty")}</div>
            ) : (
              <div className="tasks-goal-stack">{goals.map(renderGoalCard)}</div>
            )}
            {(sectionCursors.goals !== undefined ? sectionCursors.goals : focus?.next_cursors.goals) && (
              <button
                type="button"
                className="tasks-pill-btn"
                onClick={() => void loadMoreSection("goals")}
              >
                {t("tasks.next")}
              </button>
            )}
          </section>
        ) : (
          <>
            {/* Candidate switcher: Needs your call ⇄ Stashed */}
            <section aria-label={t("tasks.focus.candidateRegion")}>
              {counts.needs_you === 0 && counts.stashed === 0 ? (
                <div className="tasks-calm-zero">{t("tasks.focus.calmBothZero")}</div>
              ) : (
                <>
                  <div className="tasks-section-head">
                    <div
                      className="tasks-scope-tabs"
                      role="tablist"
                      aria-label={t("tasks.focus.candidateTabs")}
                    >
                      <button
                        type="button"
                        role="tab"
                        aria-selected={inboxTab === "needs_you"}
                        className={`tasks-scope-tab${inboxTab === "needs_you" ? " is-active" : ""}`}
                        onClick={() => setInboxTab("needs_you")}
                      >
                        <span>{t("tasks.focus.needsYouTab")}</span>
                        <span
                          className={`tasks-scope-tab-count${
                            counts.needs_you > 0 ? " tasks-scope-tab-count--butter" : ""
                          }`}
                        >
                          {counts.needs_you}
                        </span>
                      </button>
                      <button
                        type="button"
                        role="tab"
                        aria-selected={inboxTab === "stashed"}
                        className={`tasks-scope-tab${inboxTab === "stashed" ? " is-active" : ""}`}
                        onClick={() => setInboxTab("stashed")}
                      >
                        <span>{t("tasks.focus.stashedTab")}</span>
                        <span className="tasks-scope-tab-count">{counts.stashed}</span>
                      </button>
                    </div>
                  </div>

                  {inboxTab === "needs_you" ? (
                    needsYou.length === 0 ? (
                      <div className="tasks-calm-zero">
                        {t("tasks.focus.calmNeedsYouZero", { count: counts.stashed })}
                      </div>
                    ) : (
                      <div className="tasks-stack-list">{needsYou.map(renderActionCard)}</div>
                    )
                  ) : stashed.length === 0 ? (
                    <div className="tasks-calm-zero">{t("tasks.focus.calmStashedZero")}</div>
                  ) : (
                    <div className="tasks-stack-list">{stashed.map(renderActionCard)}</div>
                  )}

                  {inboxTab === "needs_you" &&
                    (sectionCursors.needs_you !== undefined
                      ? sectionCursors.needs_you
                      : focus?.next_cursors.needs_you) && (
                      <button
                        type="button"
                        className="tasks-pill-btn"
                        onClick={() => void loadMoreSection("needs_you")}
                      >
                        {t("tasks.next")}
                      </button>
                    )}
                  {inboxTab === "stashed" &&
                    (sectionCursors.stashed !== undefined
                      ? sectionCursors.stashed
                      : focus?.next_cursors.stashed) && (
                      <button
                        type="button"
                        className="tasks-pill-btn"
                        onClick={() => void loadMoreSection("stashed")}
                      >
                        {t("tasks.next")}
                      </button>
                    )}
                </>
              )}
            </section>

            {/* Active In-progress stream */}
            <section aria-label={t("tasks.focus.activeSection")}>
              <div className="tasks-section-head">
                <h2 className="tasks-section-title">
                  {t("tasks.focus.activeSection")}{" "}
                  <span className="tasks-count-pill">{counts.active}</span>
                </h2>
              </div>
              {active.length === 0 ? (
                <div className="tasks-calm-zero">{t("tasks.focus.activeEmpty")}</div>
              ) : (
                <div className="tasks-stack-list">{active.map(renderActionCard)}</div>
              )}
              {(sectionCursors.active !== undefined ? sectionCursors.active : focus?.next_cursors.active) && (
                <button
                  type="button"
                  className="tasks-pill-btn"
                  onClick={() => void loadMoreSection("active")}
                >
                  {t("tasks.next")}
                </button>
              )}
            </section>

            {/* Folded Completed drawer */}
            {!completedOpen ? (
              <section aria-label={t("tasks.focus.completedRegion")}>
                <button
                  type="button"
                  className="tasks-pill-btn tasks-pill-btn--ghost"
                  onClick={() => setCompletedOpen(true)}
                >
                  {t("tasks.focus.completedFolded", { count: counts.completed })}
                </button>
              </section>
            ) : (
              <section className="tasks-stash-drawer" aria-label={t("tasks.focus.completedRegion")}>
                <div className="tasks-stash-drawer-head">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <strong>
                      {t("tasks.focus.completedTitle", {
                        count: completedItems.length || counts.completed,
                      })}
                    </strong>
                  </div>
                  <button
                    type="button"
                    className="tasks-pill-btn tasks-pill-btn--ghost"
                    onClick={() => setCompletedOpen(false)}
                  >
                    {t("tasks.focus.collapse")}
                  </button>
                </div>
                {completedQuery.isPending ? (
                  <div className="tasks-calm-zero" role="status">
                    {t("tasks.loading")}
                  </div>
                ) : completedItems.length === 0 ? (
                  <div className="tasks-calm-zero">{t("tasks.noTasks")}</div>
                ) : (
                  <div className="tasks-stack-list">{completedItems.map(renderActionCard)}</div>
                )}
                {completedNextCursor && (
                  <button
                    type="button"
                    className="tasks-pill-btn"
                    onClick={() => void loadMoreSection("completed")}
                  >
                    {t("tasks.next")}
                  </button>
                )}
              </section>
            )}
          </>
        )}
      </div>

      <TaskStatusHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
      {toast && (
        <div className="tasks-floating-toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
