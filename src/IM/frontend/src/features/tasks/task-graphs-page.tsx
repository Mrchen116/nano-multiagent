import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useId, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useQueryClient } from "@tanstack/react-query";
import { joinConversation } from "../chat/chat-api";
import { TaskBoard, TaskCounts, TaskOverview, actorName, taskStatuses } from "./task-progress";
import { TaskEditor, type TaskEditTarget } from "./task-editor";
import { useTranslation } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { composerStoreFor, EMPTY_COMPOSER_SNAPSHOT, writeComposerSnapshot } from "../chat/components/composer-draft-store";
import { layoutTaskScope } from "./task-graph-layout";
import { TaskGraphLink } from "./task-graph-link";
import { taskGraphUrl, useTaskGraph, writeTaskGraph, type TaskGraph, type TaskNode, type TaskStatus, type TaskGraphSummary } from "./task-graphs-api";
import "./task-graphs.css";

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = useTranslation();
  return <span className={`tasks-status tasks-status--${status}`}><i aria-hidden />{t(`tasks.status.${status}`)}</span>;
}

function ReadNotice({ stale, onRefresh }: { stale: boolean; onRefresh: () => void }) {
  const { t } = useTranslation();
  return <div className="tasks-notice" role="alert"><span>{t(stale ? "tasks.stale" : "tasks.readFailed")}</span>
    <button className="tasks-button" onClick={onRefresh}>{t("tasks.refresh")}</button>
  </div>;
}

type GraphActions = { onSelect: (node: TaskNode) => void; onEnter: (node: TaskNode) => void; onDiscuss: (node: TaskNode) => void; onCopy: (node: TaskNode) => void };

function TaskGraphCanvas({ graph, scope, selectedId, onSelect, onEnter, onDiscuss, onCopy }: {
  graph: TaskGraph; scope: TaskNode; selectedId?: string;
} & GraphActions) {
  const { t } = useTranslation();
  const [zoom, setZoom] = useState(1);
  const marker = useId().replace(/:/g, "");
  const layout = useMemo(() => layoutTaskScope(graph, scope), [graph, scope]);
  const derive = scope.mode === "explore";
  const selectedCandidate = graph.nodes.find(node => node.id === scope.selected_candidate_id);
  return <div className="tasks-canvas-panel">
    <div className="tasks-canvas-heading">
      <div><button className="tasks-scope-title" onClick={() => onSelect(scope)}>{scope.title}</button>
        <p>{t(derive ? "tasks.exploreHint" : "tasks.dagHint")}</p></div>
      <div className="tasks-zoom" aria-label={t("tasks.zoom")}>
        <button onClick={() => setZoom(value => Math.max(.6, value - .1))} disabled={zoom <= .6} aria-label={t("tasks.zoomOut")}>−</button>
        <output>{Math.round(zoom * 100)}%</output>
        <button onClick={() => setZoom(value => Math.min(1.4, value + .1))} disabled={zoom >= 1.4} aria-label={t("tasks.zoomIn")}>＋</button>
      </div>
    </div>
    {layout.nodes.length > 0 ? <div className="tasks-graph-scroll" tabIndex={0} aria-label={t("tasks.graphCanvas")}>
      <div className="tasks-graph-viewport" style={{ width: layout.width * zoom, height: layout.height * zoom }}>
        <div className="tasks-graph" style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}>
          {!derive && layout.columns.map((column, index) => <div key={column.x} className="tasks-stage"
            style={{ left: column.x - 8, width: 220, height: layout.height - 16 }}>
            <span>{t("tasks.dependencyLayer", { count: index + 1 })}</span>
            {column.count > 1 && <span>{t("tasks.parallel")}</span>}
          </div>)}
          <svg width={layout.width} height={layout.height} aria-label={t(derive ? "tasks.derivation" : "tasks.dependencies")} role="img">
            <defs><marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill={derive ? "#5a9c8e" : "#97aab5"} /></marker></defs>
            {layout.routes.map(edge => <g key={`${edge.from}:${edge.to}`}>
              <path data-edge={`${edge.from}:${edge.to}`} d={edge.path} fill="none" stroke={derive ? "#5a9c8e" : "#97aab5"} strokeWidth="1.7" strokeLinejoin="round" strokeDasharray={derive ? "5 4" : undefined} markerEnd={`url(#${marker})`}>
                <title>{graph.nodes.find(node => node.id === edge.from)?.title} → {graph.nodes.find(node => node.id === edge.to)?.title}</title>
              </path>
              {derive && <text x={edge.labelX} y={edge.labelY} textAnchor="middle" className="tasks-edge-label">{t("tasks.derived")}</text>}
            </g>)}
          </svg>
          {layout.nodes.map(node => <article key={node.id} data-node={node.id}
            className={`tasks-node${selectedId === node.id ? " is-selected" : ""}${scope.selected_candidate_id === node.id ? " is-picked" : ""}${node.status === "closed" ? " is-dropped" : ""}`}
            style={{ left: layout.positions.get(node.id)!.x, top: layout.positions.get(node.id)!.y }}>
            <button className="tasks-node-main" data-node-id={node.id} onClick={() => onSelect(node)} aria-label={t("tasks.viewNode", { title: node.title })}>
              <span className="tasks-node-top"><span className="tasks-node-id" title={node.id}>{node.id}</span><TaskStatusBadge status={node.status} /></span>
              <h3>{node.title}</h3>
            </button>
            <div className="tasks-node-footer"><span className={scope.selected_candidate_id === node.id ? "tasks-picked" : ""}>
              {scope.selected_candidate_id === node.id ? t("tasks.picked") : t(`tasks.mode.${node.mode}`)}</span>
              {node.mode !== "none" && <button onClick={() => onEnter(node)} aria-label={t("tasks.enterNode", { title: node.title })}>{t("tasks.enter")} →</button>}
            </div>
          </article>)}
        </div>
      </div>
    </div> : <div className="tasks-empty"><h2>{t("tasks.emptyScope")}</h2><p>{t("tasks.emptyScopeHint")}</p>
      {scope.last_chat_id && <button className="tasks-button" onClick={() => onDiscuss(scope)}>{t("tasks.discuss")}</button>}
      <button className="tasks-button" onClick={() => onCopy(scope)}>{t("tasks.copyReference")}</button></div>}
    {selectedCandidate && <div className="tasks-selection"><strong>{t("tasks.currentChoice")} {selectedCandidate.title}</strong><p>{scope.selection_reason || t("tasks.noReason")}</p><span>{t("tasks.selectionHint")}</span></div>}
    <div className="tasks-legend"><span><i className={derive ? "is-derived" : ""} />{t(derive ? "tasks.derivation" : "tasks.dependencies")}</span><span>{t(derive ? "tasks.droppedHint" : "tasks.statusHint")}</span><span>{t("tasks.canvasHint")}</span></div>
  </div>;
}

function TaskNodeDetail({ graph, node, onSelect, onEnter, onDiscuss, onCopy }: { graph: TaskGraph; node: TaskNode } & GraphActions) {
  const { t, i18n } = useTranslation();
  const parent = graph.nodes.find(candidate => candidate.id === node.container_id);
  const children = graph.nodes.filter(candidate => candidate.container_id === node.id);
  const relationList = (ids: string[]) => ids.length ? <ul className="tasks-relations">{ids.map(id => {
    const related = graph.nodes.find(candidate => candidate.id === id)!;
    return <li key={id}><button onClick={() => onSelect(related)}>{related.title}</button></li>;
  })}</ul> : <p>{t("tasks.none")}</p>;
  return <>
    <div className="tasks-detail-id">{t("tasks.nodeDetails")} · <span>{node.id}</span></div>
    <section><h2>{node.title}</h2><div className="tasks-tags"><span className="tasks-mode">{t(`tasks.mode.${node.mode}`)}</span><TaskStatusBadge status={node.status} /></div></section>
    <section className="tasks-detail-facts"><dl><div><dt>{t("tasks.creator")}</dt><dd>{actorName(node.created_by)}</dd></div><div><dt>{t("tasks.assignee")}</dt><dd>{actorName(node.assignee) || t("tasks.unassigned")}</dd></div></dl><TaskCounts counts={node.direct_counts} /><p>{taskStatuses.map(status => `${t(`tasks.status.${status}`)} ${node.direct_counts?.[status] ?? 0}`).join(" · ")}</p></section>
    <section><h3>{t("tasks.description")}</h3><div className="tasks-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: TaskGraphLink }}>{node.description || t("tasks.noDescription")}</ReactMarkdown></div></section>
    <section><h3>{t("tasks.result")}</h3><div className="tasks-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: TaskGraphLink }}>{node.result || t("tasks.noResult")}</ReactMarkdown></div></section>
    {node.change_note && <section><h3>{t("tasks.changeNote")}</h3><p className="tasks-prose">{node.change_note}</p></section>}
    {parent?.mode === "dag" && <><section><h3>{t("tasks.predecessors")}</h3>{relationList(graph.dependencies.filter(edge => edge.to === node.id).map(edge => edge.from))}</section>
      <section><h3>{t("tasks.successors")}</h3>{relationList(graph.dependencies.filter(edge => edge.from === node.id).map(edge => edge.to))}</section></>}
    {node.derived_from_id && <section><h3>{t("tasks.derivedFrom")}</h3>{relationList([node.derived_from_id])}</section>}
    {node.selected_candidate_id && <section><h3>{t("tasks.currentChoice")}</h3>{relationList([node.selected_candidate_id])}<p>{node.selection_reason || t("tasks.noReason")}</p></section>}
    {node.links.length > 0 && <section><h3>{t("tasks.links")}</h3><ul>{node.links.map((link, index) => <li key={index}><ReactMarkdown components={{ a: TaskGraphLink }}>{`[${link.replace(/[\[\]]/g, "\\$&")}](${link})`}</ReactMarkdown></li>)}</ul></section>}
    <section className="tasks-detail-facts"><dl><div><dt>{t("tasks.structure")}</dt><dd>{children.length ? t("tasks.nodeCount", { count: children.length }) : t("tasks.mode.none")}</dd></div>
      <div><dt>{t("tasks.updatedBy")}</dt><dd>{node.updated_by}</dd></div><div><dt>{t("tasks.updatedAt")}</dt><dd>{new Date(node.updated_at).toLocaleString(i18n.language)}</dd></div>
      {node.last_chat_title && <div><dt>{t("tasks.updateChat")}</dt><dd>{node.last_chat_title}</dd></div>}
      <div><dt>{t("tasks.revision")}</dt><dd>{graph.revision}</dd></div></dl><p className="tasks-detail-note">{t("tasks.recordedHint")}</p></section>
    <div className="tasks-detail-actions">{node.mode !== "none" && <button className="tasks-button tasks-button--primary" onClick={() => onEnter(node)}>{t("tasks.enter")} · {t(`tasks.mode.${node.mode}`)} →</button>}
      {node.last_chat_id && <button className="tasks-button" onClick={() => onDiscuss(node)}>{t("tasks.discussNode")}</button>}
      <button className="tasks-button" onClick={() => onCopy(node)}>{t("tasks.copyReference")}</button></div>
  </>;
}

export function TaskGraphsPage() {
  const { t } = useTranslation();
  const { graphId } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [overviewSelection, setOverviewSelection] = useState<TaskGraphSummary | null>(null);
  const [editor, setEditor] = useState<TaskEditTarget | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState("progress");
  const [copyStatus, setCopyStatus] = useState<"copied" | "copyFailed" | null>(null);
  useEffect(() => {
    if (params.get("create") !== "root") return;
    setEditor({ conversationId: params.get("conversation_id") ?? undefined });
    const next = new URLSearchParams(params); next.delete("create"); setParams(next, { replace: true });
  }, [params, setParams]);
  const query = useTaskGraph(graphId ?? overviewSelection?.graph_id);
  const graph = query.data;
  const root = graph?.nodes.find(node => node.id === graph.root_node_id);
  const selectedId = graphId ? params.get("node") : overviewSelection?.node_id ?? overviewSelection?.root_node_id;
  const selected = graph?.nodes.find(node => node.id === selectedId);
  const scopeId = params.get("scope") ?? selected?.container_id ?? graph?.root_node_id;
  const scope = graph?.nodes.find(node => node.id === scopeId);
  useEffect(() => { setCopyStatus(null); setError(""); setDeleting(false); }, [graphId, selectedId]);
  const invalidLocation = Boolean(graphId && graph && (!root || !scope || (params.has("node") && (!selected || (selected.id !== scope.id && selected.container_id !== scope.id)))));
  const breadcrumbs: TaskNode[] = [];
  for (let current = scope; current; current = graph?.nodes.find(node => node.id === current?.container_id)) breadcrumbs.unshift(current);
  function enter(node: TaskNode) {
    if (!graphId) { navigate(taskGraphUrl(graph!.graph_id, node.id)); setOverviewSelection(null); return; }
    const next = new URLSearchParams(params); next.set("scope", node.id); next.delete("node"); setParams(next);
  }
  function select(node: TaskNode) { if (!graphId && overviewSelection) { setOverviewSelection({ ...overviewSelection, node_id: node.id }); return; } const next = new URLSearchParams(params); next.set("scope", node.container_id ?? node.id); next.set("node", node.id); setParams(next); }
  function closeDetail() { setDeleting(false); setOverviewSelection(null); const next = new URLSearchParams(params); next.delete("node"); setParams(next, { replace: true }); }
  function discuss(node: TaskNode) {
    if (!graph || !node.last_chat_id) return;
    const store = composerStoreFor(useAuthStore.getState().user?.id ?? null);
    const current = store.get(node.last_chat_id) ?? EMPTY_COMPOSER_SNAPSHOT;
    const title = node.title.replace(/([\\[\]])/g, "\\$1");
    const reference = `[${t("tasks.taskReference")}: ${title}](${taskGraphUrl(graph.graph_id, node.container_id ?? node.id, node.id)})`;
    writeComposerSnapshot(store, node.last_chat_id, { ...current, draft: `${current.draft}${current.draft ? "\n\n" : ""}${reference}\n` });
    navigate(`/chat/${encodeURIComponent(node.last_chat_id)}`);
  }
  async function copyReference(node: TaskNode) {
    const title = node.title.replace(/([\\[\]])/g, "\\$1");
    try { await navigator.clipboard.writeText(`[${t("tasks.taskReference")}: ${title}](${taskGraphUrl(graph!.graph_id, node.container_id ?? node.id, node.id)})`); setCopyStatus("copied"); }
    catch { setCopyStatus("copyFailed"); }
  }
  async function refresh() { await client.invalidateQueries({ queryKey: ["task-graphs"] }); }
  async function act(fn: () => Promise<unknown>) { setBusy(true); setError(""); try { await fn(); await refresh(); } catch (err) { setError(err instanceof Error ? err.message : t("tasks.writeFailed")); } finally { setBusy(false); } }
  const actions = { onSelect: select, onEnter: enter, onDiscuss: discuss, onCopy: copyReference };
  const children = graph?.nodes.filter(node => node.container_id === scope?.id).sort((a,b) => a.order - b.order || a.id.localeCompare(b.id)) ?? [];
  const deletionIds = new Set(selected ? [selected.id] : []);
  for (let depth = 0; depth < 8; depth++) graph?.nodes.forEach(node => { if (node.container_id && deletionIds.has(node.container_id)) deletionIds.add(node.id); });
  const conversation = graph?.conversation;
  return <div className="tasks-workspace"><main className="tasks-main">
    <header className="tasks-header tasks-header--compact"><nav className="tasks-breadcrumbs" aria-label={t("tasks.breadcrumbs")}><Link to="/tasks" onClick={() => setOverviewSelection(null)}>{t("tasks.overview")}</Link>{graphId && breadcrumbs.map((node, index) => <span key={node.id}><i aria-hidden>›</i><button aria-current={index === breadcrumbs.length - 1 ? "page" : undefined} onClick={() => enter(node)}>{node.title}</button></span>)}</nav>
      {graphId && conversation && <Link className="tasks-context" to={`/chat/${encodeURIComponent(conversation.id)}`}>{t(conversation.dissolved_at ? "tasks.history" : conversation.visibility === "public" ? "tasks.public" : "tasks.private")} · {conversation.title}</Link>}
      {graphId && <button className="tasks-button" aria-label={t("tasks.refresh")} disabled={query.isFetching} onClick={() => void query.refetch()}>↻</button>}
      {params.get("return_chat") && <Link className="tasks-button" to={`/chat/${encodeURIComponent(params.get("return_chat")!)}`}>{t("tasks.goChat")}</Link>}
    </header>
    {copyStatus && <p className="tasks-notice" role={copyStatus === "copied" ? "status" : "alert"}>{t(`tasks.${copyStatus}`)}</p>}
    {error && <p className="tasks-notice" role="alert">{error}</p>}
    {!graphId && overviewSelection && graph === null && <p className="tasks-notice" role="alert">{t("tasks.unavailable")}</p>}
    {!graphId ? <TaskOverview onCreate={() => setEditor({ conversationId: params.get("conversation_id") ?? undefined })} onSelect={setOverviewSelection} />
      : query.isPending ? <div className="tasks-empty" role="status">{t("tasks.loading")}</div>
      : graph === null ? <div className="tasks-empty" role="alert"><h2>{t("tasks.unavailable")}</h2><Link to="/tasks">{t("tasks.allTargets")}</Link></div>
      : <>{query.isError && <ReadNotice stale={Boolean(graph)} onRefresh={() => void query.refetch()} />}
        {invalidLocation ? <div className="tasks-empty" role="alert"><h2>{t("tasks.invalidLocation")}</h2>{root && <button className="tasks-button" onClick={() => enter(root)}>{t("tasks.backRoot")}</button>}</div>
          : graph && scope && <><div className="tasks-toolbar">
            <div className="tasks-scope-actions"><button className="tasks-button" onClick={() => select(scope)}>{t("tasks.nodeDetails")}</button>
            {scope.can_edit && <button className="tasks-button tasks-button--primary" onClick={() => setEditor({ graph, parent: scope })}>{t("tasks.createChild")}</button>}
            {conversation && !conversation.can_write && <span>{t(conversation.dissolved_at ? "tasks.history" : "tasks.readOnly")}</span>}
            {conversation?.visibility === "public" && !conversation.is_member && !conversation.dissolved_at && <button className="tasks-button" disabled={busy} onClick={() => void act(() => joinConversation(conversation.id))}>{t("tasks.join")}</button>}
            </div>
            <div className="tasks-view-switch" role="group" aria-label={t("tasks.view")}>
              <button type="button" aria-pressed={view === "progress"} onClick={() => setView("progress")}>
                <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3" width="4" height="10" rx="1" /><rect x="10" y="3" width="4" height="6" rx="1" /></svg>
                {t("tasks.progress")}
              </button>
              <button type="button" aria-pressed={view === "graph"} onClick={() => setView("graph")}>
                <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1" y="6" width="4" height="4" rx="1" /><rect x="11" y="1" width="4" height="4" rx="1" /><rect x="11" y="11" width="4" height="4" rx="1" /><path d="M5 8h3V3h3M8 8v5h3" /></svg>
                {t("tasks.structure")}
              </button>
            </div>
          </div><p className="tasks-range">{t("tasks.directOnly")} · <TaskCounts counts={scope.direct_counts} /></p>
          {view === "graph" ? <div className="tasks-content"><TaskGraphCanvas key={`${graph.graph_id}:${scope.id}`} graph={graph} scope={scope} selectedId={selected?.id} {...actions} /></div>
            : <TaskBoard nodes={children.map(node => ({ ...node, selected: scope.selected_candidate_id === node.id }))} onSelect={card => select(graph.nodes.find(node => node.id === card.id)!)} onEnter={card => enter(graph.nodes.find(node => node.id === card.id)!)} />}
          {view !== "graph" && scope.selected_candidate_id && <div className="tasks-selection">{t("tasks.currentChoice")} {graph.nodes.find(node => node.id === scope.selected_candidate_id)?.title} · {scope.selection_reason}</div>}
          </>}
        </>}
    <Dialog.Root open={Boolean(selected && !invalidLocation)} onOpenChange={open => { if (!open) closeDetail(); }}><Dialog.Portal><Dialog.Overlay className="tasks-dialog-overlay" /><Dialog.Content className="tasks-detail tasks-detail--overlay" aria-describedby={undefined}>
      <div className="tasks-dialog-heading"><Dialog.Title>{t("tasks.nodeDetails")}</Dialog.Title><Dialog.Close className="tasks-button">{t("tasks.close")}</Dialog.Close></div>
      {graph && selected && <><div className="tasks-detail-actions">{selected.can_edit && <button className="tasks-button tasks-button--primary" onClick={() => setEditor({ graph, node: selected })}>{t("tasks.edit")}</button>}{selected.can_claim && <button className="tasks-button" disabled={busy} onClick={() => selected.status === "done" ? setEditor({ graph, node: selected, claim: true }) : void act(() => writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}/apply`, { base_revision: graph.revision, request_key: crypto.randomUUID(), change_note: "", operations: [{ op: "claim_task", node_id: selected.id }] }))}>{t("tasks.claim")}</button>}{selected.can_delete && <details><summary>{t("tasks.more")}</summary><button className="tasks-button" onClick={() => setDeleting(true)}>{t("tasks.delete")}</button></details>}</div>
        {deleting && <section className="tasks-conflict"><h3>{t("tasks.deleteSubtree")}</h3><p>{t("tasks.deleteScope", { title: selected.title, count: deletionIds.size })}</p><button className="tasks-button" disabled={busy} onClick={() => void act(async () => { await writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}`, { base_revision: graph.revision, request_key: crypto.randomUUID(), node_id: selected.id }, "DELETE"); closeDetail(); if (selected.id === graph.root_node_id) navigate("/tasks"); })}>{t("tasks.confirmDelete", { count: deletionIds.size })}</button><button className="tasks-button" onClick={() => setDeleting(false)}>{t("tasks.cancel")}</button></section>}
        {error && <p role="alert">{error}</p>}
        <TaskNodeDetail graph={graph} node={selected} {...actions} />
        {params.get("return_chat") && <Link className="tasks-button" to={`/chat/${encodeURIComponent(params.get("return_chat")!)}`}>{t("tasks.goChat")}</Link>}
        {conversation && <Link className="tasks-button" to={`/chat/${encodeURIComponent(conversation.id)}`}>{t(conversation.dissolved_at ? "tasks.history" : "tasks.conversation")} · {conversation.title}</Link>}
      </>}
    </Dialog.Content></Dialog.Portal></Dialog.Root>
    {editor && <TaskEditor target={editor} onClose={() => setEditor(null)} onSaved={id => { setEditor(null); void refresh(); if (!editor.graph) { navigate(taskGraphUrl(id)); setOverviewSelection(null); } }} />}
  </main></div>;
}
