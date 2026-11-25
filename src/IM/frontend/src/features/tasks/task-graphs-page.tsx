import { useEffect, useId, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { joinConversation } from "../chat/chat-api";
import {
  composerStoreFor,
  EMPTY_COMPOSER_SNAPSHOT,
  writeComposerSnapshot,
} from "../chat/components/composer-draft-store";
import { TaskDetailDrawer } from "./task-detail-drawer";
import { TaskEditor, type TaskEditTarget } from "./task-editor";
import { TaskFocusDesk } from "./task-focus-desk";
import { layoutTaskScope } from "./task-graph-layout";
import {
  isTaskPrereqBlocked,
  taskGraphUrl,
  useTaskGraph,
  writeTaskGraph,
  type TaskGraph,
  type TaskGraphSummary,
  type TaskNode,
} from "./task-graphs-api";
import { actorName, TaskBoard, TaskCounts } from "./task-progress";
import { TaskStageSpine } from "./task-stage-spine";
import { TaskStatusBadge, TaskStatusHelpDialog } from "./task-status-badge";
import "./task-graphs.css";

function ReadNotice({ stale, onRefresh }: { stale: boolean; onRefresh: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="tasks-notice" role="alert">
      <span>{t(stale ? "tasks.stale" : "tasks.readFailed")}</span>
      <button className="tasks-button" onClick={onRefresh}>
        {t("tasks.refresh")}
      </button>
    </div>
  );
}

type GraphActions = {
  onSelect: (node: TaskNode) => void;
  onEnter: (node: TaskNode) => void;
  onDiscuss: (node: TaskNode) => void;
  onCopy: (node: TaskNode) => void;
};

function TaskGraphCanvas({
  graph,
  scope,
  selectedId,
  busy,
  onAct,
  onSelect,
  onEnter,
  onDiscuss,
  onCopy,
}: {
  graph: TaskGraph;
  scope: TaskNode;
  selectedId?: string;
  busy: boolean;
  onAct: (fn: () => Promise<unknown>) => Promise<void>;
} & GraphActions) {
  const { t } = useTranslation();
  const [zoom, setZoom] = useState(1);
  const marker = useId().replace(/:/g, "");
  const layout = useMemo(() => layoutTaskScope(graph, scope), [graph, scope]);
  const derive = scope.mode === "explore";
  const selectedCandidate = graph.nodes.find(node => node.id === scope.selected_candidate_id);

  const applySproutOp = (operations: Record<string, unknown>[]) =>
    onAct(() =>
      writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}/apply`, {
        base_revision: graph.revision,
        request_key: crypto.randomUUID(),
        change_note: "",
        operations,
      }),
    );

  return (
    <div className="tasks-canvas-panel">
      <div className="tasks-canvas-heading">
        <div>
          <button className="tasks-scope-title" onClick={() => onSelect(scope)}>
            {scope.title}
          </button>
          <p>{t(derive ? "tasks.exploreHint" : "tasks.dagHint")}</p>
        </div>
        <div className="tasks-zoom" aria-label={t("tasks.zoom")}>
          <button
            onClick={() => setZoom(value => Math.max(0.6, value - 0.1))}
            disabled={zoom <= 0.6}
            aria-label={t("tasks.zoomOut")}
          >
            −
          </button>
          <output>{Math.round(zoom * 100)}%</output>
          <button
            onClick={() => setZoom(value => Math.min(1.4, value + 0.1))}
            disabled={zoom >= 1.4}
            aria-label={t("tasks.zoomIn")}
          >
            ＋
          </button>
        </div>
      </div>

      {layout.nodes.length > 0 ? (
        <div className="tasks-graph-scroll" tabIndex={0} aria-label={t("tasks.graphCanvas")}>
          <div
            className="tasks-graph-viewport"
            style={{ width: layout.width * zoom, height: layout.height * zoom }}
          >
            <div
              className="tasks-graph"
              style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}
            >
              {!derive &&
                layout.columns.map((column, index) => (
                  <div
                    key={column.x}
                    className="tasks-stage"
                    style={{ left: column.x - 8, width: 244, height: layout.height - 16 }}
                  >
                    <span>{t("tasks.dependencyLayer", { count: index + 1 })}</span>
                    {column.count > 1 && <span>{t("tasks.parallel")}</span>}
                  </div>
                ))}
              <svg
                width={layout.width}
                height={layout.height}
                aria-label={t(derive ? "tasks.derivation" : "tasks.dependencies")}
                role="img"
              >
                <defs>
                  <marker
                    id={marker}
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="5"
                    markerHeight="5"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill={derive ? "#5a9c8e" : "#97aab5"} />
                  </marker>
                </defs>
                {layout.routes.map(edge => (
                  <g key={`${edge.from}:${edge.to}`}>
                    <path
                      data-edge={`${edge.from}:${edge.to}`}
                      d={edge.path}
                      fill="none"
                      stroke={derive ? "#5a9c8e" : "#97aab5"}
                      strokeWidth="1.7"
                      strokeLinejoin="round"
                      strokeDasharray={derive ? "5 4" : undefined}
                      markerEnd={`url(#${marker})`}
                    >
                      <title>
                        {graph.nodes.find(node => node.id === edge.from)?.title} →{" "}
                        {graph.nodes.find(node => node.id === edge.to)?.title}
                      </title>
                    </path>
                    {derive && (
                      <text x={edge.labelX} y={edge.labelY} textAnchor="middle" className="tasks-edge-label">
                        {t("tasks.derived")}
                      </text>
                    )}
                  </g>
                ))}
              </svg>

              {layout.nodes.map(node => {
                const isSprout = node.status === "proposed";
                const prereqBlocked = isTaskPrereqBlocked(node, graph, node.id);
                return (
                  <article
                    key={node.id}
                    data-node={node.id}
                    className={`tasks-node${selectedId === node.id ? " is-selected" : ""}${
                      scope.selected_candidate_id === node.id ? " is-picked" : ""
                    }${node.status === "closed" ? " is-dropped" : ""}${
                      isSprout ? " tasks-node--sprout" : ""
                    }`}
                    style={{
                      left: layout.positions.get(node.id)!.x,
                      top: layout.positions.get(node.id)!.y,
                    }}
                  >
                    <button
                      className="tasks-node-main"
                      data-node-id={node.id}
                      onClick={() => onSelect(node)}
                      aria-label={t("tasks.viewNode", { title: node.title })}
                    >
                      <span className="tasks-node-top">
                        <span className="tasks-node-id" title={node.id}>
                          {node.id}
                        </span>
                        <TaskStatusBadge status={node.status} />
                      </span>
                      <h3>{node.title}</h3>
                      {!isSprout && (
                        <small className="tasks-node-assignee">
                          {actorName(node.assignee) || t("tasks.unassigned")}
                        </small>
                      )}
                    </button>

                    {isSprout && node.can_edit ? (
                      <div className="tasks-node-sprout-actions">
                        <button
                          type="button"
                          className="tasks-sprout-btn tasks-sprout-btn--primary"
                          disabled={busy}
                          onClick={() => void applySproutOp([{ op: "approve_task", node_id: node.id }])}
                        >
                          {t(prereqBlocked ? "tasks.focus.approveQueue" : "tasks.focus.approveStart")}
                        </button>
                        <button
                          type="button"
                          className="tasks-sprout-btn"
                          disabled={busy}
                          onClick={() =>
                            void applySproutOp([
                              { op: "update_task", node_id: node.id, patch: { status: "backlog" } },
                            ])
                          }
                        >
                          {t("tasks.focus.stashAction")}
                        </button>
                        <button
                          type="button"
                          className="tasks-sprout-btn"
                          disabled={busy}
                          onClick={() =>
                            void applySproutOp([
                              { op: "update_task", node_id: node.id, patch: { status: "closed" } },
                            ])
                          }
                        >
                          {t("tasks.focus.closeAction")}
                        </button>
                      </div>
                    ) : (
                      <div className="tasks-node-footer">
                        <span className={scope.selected_candidate_id === node.id ? "tasks-picked" : ""}>
                          {scope.selected_candidate_id === node.id
                            ? t("tasks.picked")
                            : t(`tasks.mode.${node.mode}`)}
                        </span>
                        {node.mode !== "none" && (
                          <button
                            onClick={() => onEnter(node)}
                            aria-label={t("tasks.enterNode", { title: node.title })}
                          >
                            {t("tasks.enter")} →
                          </button>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="tasks-empty">
          <h2>{t("tasks.emptyScope")}</h2>
          <p>{t("tasks.emptyScopeHint")}</p>
          {scope.last_chat_id && (
            <button className="tasks-button" onClick={() => onDiscuss(scope)}>
              {t("tasks.discuss")}
            </button>
          )}
          <button className="tasks-button" onClick={() => onCopy(scope)}>
            {t("tasks.copyReference")}
          </button>
        </div>
      )}
      {selectedCandidate && (
        <div className="tasks-selection">
          <strong>
            {t("tasks.currentChoice")} {selectedCandidate.title}
          </strong>
          <p>{scope.selection_reason || t("tasks.noReason")}</p>
          <span>{t("tasks.selectionHint")}</span>
        </div>
      )}
      <div className="tasks-legend">
        <span>
          <i className={derive ? "is-derived" : ""} />
          {t(derive ? "tasks.derivation" : "tasks.dependencies")}
        </span>
        <span>{t(derive ? "tasks.droppedHint" : "tasks.statusHint")}</span>
        <span>{t("tasks.canvasHint")}</span>
      </div>
    </div>
  );
}

export function TaskGraphsPage() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const { graphId } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();

  const [overviewSelection, setOverviewSelection] = useState<TaskGraphSummary | null>(null);
  const [editor, setEditor] = useState<TaskEditTarget | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [viewOverride, setViewOverride] = useState<"graph" | "spine" | "progress" | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [copyStatus, setCopyStatus] = useState<"copied" | "copyFailed" | null>(null);

  const activeView: "graph" | "spine" | "progress" =
    viewOverride ?? (isMobile ? "spine" : "graph");

  useEffect(() => {
    if (params.get("create") !== "root") return;
    setEditor({ conversationId: params.get("conversation_id") ?? undefined });
    const next = new URLSearchParams(params);
    next.delete("create");
    setParams(next, { replace: true });
  }, [params, setParams]);

  const query = useTaskGraph(graphId ?? overviewSelection?.graph_id);
  const graph = query.data;
  const root = graph?.nodes.find(node => node.id === graph.root_node_id);
  const selectedId = graphId
    ? params.get("node")
    : overviewSelection?.node_id ?? overviewSelection?.root_node_id;
  const selected = graph?.nodes.find(node => node.id === selectedId);
  const scopeId = params.get("scope") ?? selected?.container_id ?? graph?.root_node_id;
  const scope = graph?.nodes.find(node => node.id === scopeId);

  useEffect(() => {
    setCopyStatus(null);
    setError("");
  }, [graphId, selectedId]);

  const invalidLocation = Boolean(
    graphId &&
      graph &&
      (!root ||
        !scope ||
        (params.has("node") && (!selected || (selected.id !== scope.id && selected.container_id !== scope.id)))),
  );

  const breadcrumbs: TaskNode[] = [];
  for (let current = scope; current; current = graph?.nodes.find(node => node.id === current?.container_id)) {
    breadcrumbs.unshift(current);
  }

  function enter(node: TaskNode) {
    if (!graphId) {
      navigate(taskGraphUrl(graph!.graph_id, node.id === graph!.root_node_id ? undefined : node.id));
      setOverviewSelection(null);
      return;
    }
    const next = new URLSearchParams(params);
    next.set("scope", node.id);
    next.delete("node");
    setParams(next);
  }

  function select(node: TaskNode) {
    if (!graphId && overviewSelection) {
      setOverviewSelection({ ...overviewSelection, node_id: node.id });
      return;
    }
    const next = new URLSearchParams(params);
    next.set("scope", node.container_id ?? node.id);
    next.set("node", node.id);
    setParams(next);
  }

  function closeDetail() {
    setOverviewSelection(null);
    const next = new URLSearchParams(params);
    next.delete("node");
    setParams(next, { replace: true });
  }

  function discuss(node: TaskNode) {
    if (!graph || !node.last_chat_id) return;
    const store = composerStoreFor(useAuthStore.getState().user?.id ?? null);
    const current = store.get(node.last_chat_id) ?? EMPTY_COMPOSER_SNAPSHOT;
    const title = node.title.replace(/([\\[\]])/g, "\\$1");
    const reference = `[${t("tasks.taskReference")}: ${title}](${taskGraphUrl(
      graph.graph_id,
      node.container_id ?? node.id,
      node.id,
    )})`;
    writeComposerSnapshot(store, node.last_chat_id, {
      ...current,
      draft: `${current.draft}${current.draft ? "\n\n" : ""}${reference}\n`,
    });
    navigate(`/chat/${encodeURIComponent(node.last_chat_id)}`);
  }

  async function copyReference(node: TaskNode) {
    const title = node.title.replace(/([\\[\]])/g, "\\$1");
    try {
      await navigator.clipboard.writeText(
        `[${t("tasks.taskReference")}: ${title}](${taskGraphUrl(
          graph!.graph_id,
          node.container_id ?? node.id,
          node.id,
        )})`,
      );
      setCopyStatus("copied");
    } catch {
      setCopyStatus("copyFailed");
    }
  }

  async function refresh() {
    await client.invalidateQueries({ queryKey: ["task-graphs"] });
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("tasks.writeFailed"));
    } finally {
      setBusy(false);
    }
  }

  const actions = { onSelect: select, onEnter: enter, onDiscuss: discuss, onCopy: copyReference };
  const children =
    graph?.nodes
      .filter(node => node.container_id === scope?.id)
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id)) ?? [];
  const conversation = graph?.conversation;
  const selectedFocusKey = overviewSelection
    ? `${overviewSelection.graph_id}:${overviewSelection.node_id ?? overviewSelection.root_node_id}`
    : null;

  return (
    <div className="tasks-workspace">
      <main className="tasks-main">
        {graphId && (
          <header className="tasks-header tasks-header--compact">
            <nav className="tasks-breadcrumbs" aria-label={t("tasks.breadcrumbs")}>
              <Link to="/tasks" onClick={() => setOverviewSelection(null)}>
                {t("tasks.panorama.backFocus")}
              </Link>
              {breadcrumbs.map((node, index) => (
                <span key={node.id}>
                  <i aria-hidden>›</i>
                  <button
                    aria-current={index === breadcrumbs.length - 1 ? "page" : undefined}
                    onClick={() => enter(node)}
                  >
                    {node.title}
                  </button>
                </span>
              ))}
            </nav>
            <div className="tasks-panorama-header-actions">
              {conversation && (
                <Link className="tasks-context" to={`/chat/${encodeURIComponent(conversation.id)}`}>
                  {t(
                    conversation.dissolved_at
                      ? "tasks.history"
                      : conversation.visibility === "public"
                        ? "tasks.public"
                        : "tasks.private",
                  )}{" "}
                  · {conversation.title}
                </Link>
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
              <button
                className="tasks-button"
                aria-label={t("tasks.refresh")}
                disabled={query.isFetching}
                onClick={() => void query.refetch()}
              >
                ↻
              </button>
              {params.get("return_chat") && (
                <Link
                  className="tasks-button"
                  to={`/chat/${encodeURIComponent(params.get("return_chat")!)}`}
                >
                  {t("tasks.goChat")}
                </Link>
              )}
            </div>
          </header>
        )}

        {copyStatus && (
          <p className="tasks-notice" role={copyStatus === "copied" ? "status" : "alert"}>
            {t(`tasks.${copyStatus}`)}
          </p>
        )}
        {error && (
          <p className="tasks-notice" role="alert">
            {error}
          </p>
        )}
        {!graphId && overviewSelection && graph === null && (
          <p className="tasks-notice" role="alert">
            {t("tasks.unavailable")}
          </p>
        )}

        {!graphId ? (
          <TaskFocusDesk
            selectedKey={selectedFocusKey}
            onSelectCard={setOverviewSelection}
            onOpenEditor={target => setEditor(target)}
          />
        ) : query.isPending ? (
          <div className="tasks-empty" role="status">
            {t("tasks.loading")}
          </div>
        ) : graph === null ? (
          <div className="tasks-empty" role="alert">
            <h2>{t("tasks.unavailable")}</h2>
            <Link to="/tasks">{t("tasks.allTargets")}</Link>
          </div>
        ) : (
          <>
            {query.isError && <ReadNotice stale={Boolean(graph)} onRefresh={() => void query.refetch()} />}
            {invalidLocation ? (
              <div className="tasks-empty" role="alert">
                <h2>{t("tasks.invalidLocation")}</h2>
                {root && (
                  <button className="tasks-button" onClick={() => enter(root)}>
                    {t("tasks.backRoot")}
                  </button>
                )}
              </div>
            ) : (
              graph &&
              root &&
              scope && (
                <>
                  {/* North-Star Goal Banner */}
                  <section className="tasks-north-star-banner" aria-label={t("tasks.panorama.northStarLabel")}>
                    <div className="tasks-north-star-main">
                      <div className="tasks-north-star-top">
                        <TaskStatusBadge status={root.status} />
                        <span className="tasks-north-star-label">
                          {t("tasks.panorama.northStarLabel")}
                          {scope.id !== root.id ? ` · ${root.title}` : ""}
                        </span>
                      </div>
                      <p className="tasks-north-star-goal">
                        {root.description || t("tasks.panorama.northStarEmpty")}
                      </p>
                    </div>
                    <div className="tasks-north-star-counts">
                      <TaskCounts counts={scope.direct_counts} />
                    </div>
                  </section>

                  <div className="tasks-toolbar">
                    <div className="tasks-scope-actions">
                      <button className="tasks-button" onClick={() => select(scope)}>
                        {t("tasks.nodeDetails")}
                      </button>
                      {scope.can_edit && (
                        <button
                          className="tasks-button tasks-button--primary"
                          onClick={() => setEditor({ graph, parent: scope })}
                        >
                          {t("tasks.createChild")}
                        </button>
                      )}
                      {scope.last_chat_id && !params.get("return_chat") && (
                        <button className="tasks-button" onClick={() => discuss(scope)}>
                          {t("tasks.discuss")}
                        </button>
                      )}
                      {conversation && !conversation.can_write && (
                        <span>{t(conversation.dissolved_at ? "tasks.history" : "tasks.readOnly")}</span>
                      )}
                      {conversation?.visibility === "public" &&
                        !conversation.is_member &&
                        !conversation.dissolved_at && (
                          <button
                            className="tasks-button"
                            disabled={busy}
                            onClick={() => void act(() => joinConversation(conversation.id))}
                          >
                            {t("tasks.join")}
                          </button>
                        )}
                    </div>

                    <div className="tasks-view-switch" role="group" aria-label={t("tasks.view")}>
                      {isMobile && (
                        <button
                          type="button"
                          aria-pressed={activeView === "spine"}
                          onClick={() => setViewOverride("spine")}
                        >
                          {t("tasks.panorama.spineView")}
                        </button>
                      )}
                      <button
                        type="button"
                        aria-pressed={activeView === "progress"}
                        onClick={() => setViewOverride("progress")}
                      >
                        {t("tasks.progress")}
                      </button>
                      <button
                        type="button"
                        aria-pressed={activeView === "graph"}
                        onClick={() => setViewOverride("graph")}
                      >
                        {t("tasks.structure")}
                      </button>
                    </div>
                  </div>

                  <div className={`tasks-panorama-split${!isMobile && selected ? " has-docked-detail" : ""}`}>
                    <div className="tasks-panorama-main">
                      {activeView === "graph" ? (
                        <div className="tasks-content">
                          <TaskGraphCanvas
                            key={`${graph.graph_id}:${scope.id}`}
                            graph={graph}
                            scope={scope}
                            selectedId={selected?.id}
                            busy={busy}
                            onAct={act}
                            {...actions}
                          />
                        </div>
                      ) : activeView === "spine" ? (
                        <TaskStageSpine
                          graph={graph}
                          scope={scope}
                          selectedId={selected?.id}
                          busy={busy}
                          onSelect={select}
                          onEnter={enter}
                          onAct={act}
                        />
                      ) : (
                        <TaskBoard
                          nodes={children.map(node => ({
                            ...node,
                            selected: scope.selected_candidate_id === node.id,
                          }))}
                          onSelect={card => select(graph.nodes.find(node => node.id === card.id)!)}
                          onEnter={card => enter(graph.nodes.find(node => node.id === card.id)!)}
                        />
                      )}
                      {activeView !== "graph" && scope.selected_candidate_id && (
                        <div className="tasks-selection">
                          {t("tasks.currentChoice")}{" "}
                          {graph.nodes.find(node => node.id === scope.selected_candidate_id)?.title} ·{" "}
                          {scope.selection_reason}
                        </div>
                      )}
                    </div>

                    {!isMobile && selected && (
                      <TaskDetailDrawer
                        docked
                        graph={graph}
                        node={selected}
                        busy={busy}
                        error={error}
                        returnChatId={params.get("return_chat")}
                        onClose={closeDetail}
                        onSelect={select}
                        onEnter={enter}
                        onDiscuss={discuss}
                        onCopy={copyReference}
                        onEdit={setEditor}
                        onAct={act}
                        onDeletedRoot={() => navigate("/tasks")}
                      />
                    )}
                  </div>
                </>
              )
            )}
          </>
        )}

        {/* Overlay detail drawer: used on /tasks focus desk OR on mobile /tasks/:graphId */}
        {graph && selected && !invalidLocation && (!graphId || isMobile) && (
          <TaskDetailDrawer
            graph={graph}
            node={selected}
            busy={busy}
            error={error}
            returnChatId={params.get("return_chat")}
            onClose={closeDetail}
            onSelect={select}
            onEnter={enter}
            onDiscuss={discuss}
            onCopy={copyReference}
            onEdit={setEditor}
            onOpenGoal={id => {
              setOverviewSelection(null);
              navigate(taskGraphUrl(id));
            }}
            onAct={act}
            onDeletedRoot={() => navigate("/tasks")}
          />
        )}

        <TaskStatusHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />

        {editor && (
          <TaskEditor
            target={editor}
            onClose={() => setEditor(null)}
            onSaved={id => {
              setEditor(null);
              void refresh();
              if (!editor.graph) {
                navigate(taskGraphUrl(id));
                setOverviewSelection(null);
              }
            }}
          />
        )}
      </main>
    </div>
  );
}
