import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useId, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { useTranslation } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { composerStoreFor, EMPTY_COMPOSER_SNAPSHOT, writeComposerSnapshot } from "../chat/components/composer-draft-store";
import { layoutTaskScope } from "./task-graph-layout";
import { taskGraphUrl, useTaskGraph, useTaskGraphList, type TaskGraph, type TaskNode, type TaskStatus } from "./task-graphs-api";
import "./task-graphs.css";

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = useTranslation();
  return <span className={`tasks-status tasks-status--${status}`}><i aria-hidden />{t(`tasks.status.${status}`)}</span>;
}

export function ConversationTasksLink({ conversationId }: { conversationId: string }) {
  const { t } = useTranslation();
  const query = useTaskGraphList({ conversationId, limit: 1 });
  return <Link className="chat-pane-tasks" to={`/tasks?conversation_id=${encodeURIComponent(conversationId)}`}>
    {t("shell.tabs.tasks")} <span>{query.data?.total ?? "—"}</span>
  </Link>;
}

function ReadNotice({ stale, onRefresh }: { stale: boolean; onRefresh: () => void }) {
  const { t } = useTranslation();
  return <div className="tasks-notice" role="alert"><span>{t(stale ? "tasks.stale" : "tasks.readFailed")}</span>
    <button className="tasks-button" onClick={onRefresh}>{t("tasks.refresh")}</button>
  </div>;
}

function TaskGraphListPanel({ graphId, onChoose }: { graphId?: string; onChoose?: () => void }) {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const conversationId = params.get("conversation_id") ?? undefined;
  const queryText = params.get("query") ?? "";
  const [search, setSearch] = useState(queryText);
  const [cursors, setCursors] = useState<string[]>([]);
  const query = useTaskGraphList({ conversationId, query: queryText, cursor: cursors.at(-1) });
  useEffect(() => { setSearch(queryText); setCursors([]); }, [queryText, conversationId]);
  return <section className="tasks-list" aria-label={t("tasks.targets")}>
    <div className="tasks-list-heading"><h2>{t("tasks.targets")}</h2><span>{query.data?.total ?? ""}</span></div>
    <form className="tasks-search" onSubmit={event => {
      event.preventDefault();
      const next = new URLSearchParams(params);
      if (search.trim()) next.set("query", search.trim()); else next.delete("query");
      setParams(next);
    }}>
      <input aria-label={t("tasks.search")} placeholder={t("tasks.search")} value={search} onChange={event => setSearch(event.target.value)} />
      <button type="submit" className="tasks-button">{t("tasks.searchButton")}</button>
    </form>
    {conversationId && <Link className="tasks-all" to="/tasks" onClick={onChoose}>{t("tasks.allTargets")}</Link>}
    <div className="tasks-list-items">
      {query.isPending && <p className="tasks-list-message" role="status">{t("tasks.loading")}</p>}
      {query.isError && <ReadNotice stale={Boolean(query.data)} onRefresh={() => void query.refetch()} />}
      {query.data === null && <p className="tasks-list-message" role="alert">{t("tasks.unavailable")}</p>}
      {query.data?.items.map(graph => {
        const to = new URLSearchParams();
        if (conversationId) to.set("conversation_id", conversationId);
        if (queryText) to.set("query", queryText);
        return <Link key={graph.graph_id} className={`tasks-list-item${graphId === graph.graph_id ? " is-active" : ""}`}
          to={`${taskGraphUrl(graph.graph_id)}${to.size ? `?${to}` : ""}`} onClick={onChoose}>
          <strong>{graph.title}</strong>
          <span>{t(`tasks.mode.${graph.mode}`)} · <TaskStatusBadge status={graph.status} /></span>
          <small>{graph.home_conversation_title}</small>
        </Link>;
      })}
      {query.data?.items.length === 0 && <p className="tasks-list-message">{t(queryText ? "tasks.noMatches" : "tasks.noGraphsHint")}</p>}
    </div>
    {(cursors.length > 0 || query.data?.next_cursor) && <div className="tasks-pagination">
      <button className="tasks-button" disabled={!cursors.length} onClick={() => setCursors(value => value.slice(0, -1))}>{t("tasks.previous")}</button>
      <button className="tasks-button" disabled={!query.data?.next_cursor} onClick={() => setCursors(value => [...value, query.data!.next_cursor!])}>{t("tasks.next")}</button>
    </div>}
    <p className="tasks-list-footnote">{t("tasks.listHint")}</p>
  </section>;
}

type GraphActions = { onSelect: (node: TaskNode) => void; onEnter: (node: TaskNode) => void; onDiscuss: (node: TaskNode) => void };

function TaskGraphCanvas({ graph, scope, selectedId, onSelect, onEnter, onDiscuss }: {
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
          <svg width={layout.width} height={layout.height} aria-label={t(derive ? "tasks.derivation" : "tasks.dependencies")} role="img">
            <defs><marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill={derive ? "#5a9c8e" : "#97aab5"} /></marker></defs>
            {layout.routes.map(edge => <g key={`${edge.from}:${edge.to}`}>
              <path data-edge={`${edge.from}:${edge.to}`} d={edge.path} fill="none" stroke={derive ? "#5a9c8e" : "#97aab5"} strokeWidth="1.5" strokeDasharray={derive ? "5 4" : undefined} markerEnd={`url(#${marker})`}>
                <title>{graph.nodes.find(node => node.id === edge.from)?.title} → {graph.nodes.find(node => node.id === edge.to)?.title}</title>
              </path>
              {derive && <text x={edge.labelX} y={edge.labelY} textAnchor="middle" className="tasks-edge-label">{t("tasks.derived")}</text>}
            </g>)}
          </svg>
          {layout.nodes.map(node => <article key={node.id} data-node={node.id}
            className={`tasks-node${selectedId === node.id ? " is-selected" : ""}${scope.selected_candidate_id === node.id ? " is-picked" : ""}${node.status === "dropped" ? " is-dropped" : ""}`}
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
    </div> : <div className="tasks-empty"><h2>{t("tasks.emptyScope")}</h2><p>{t("tasks.emptyScopeHint")}</p><button className="tasks-button" onClick={() => onDiscuss(scope)}>{t("tasks.discuss")}</button></div>}
    {selectedCandidate && <div className="tasks-selection"><strong>{t("tasks.currentChoice")} {selectedCandidate.title}</strong><p>{scope.selection_reason || t("tasks.noReason")}</p><span>{t("tasks.selectionHint")}</span></div>}
    <div className="tasks-legend"><span><i className={derive ? "is-derived" : ""} />{t(derive ? "tasks.derivation" : "tasks.dependencies")}</span><span>{t(derive ? "tasks.droppedHint" : "tasks.statusHint")}</span><span>{t("tasks.canvasHint")}</span></div>
  </div>;
}

function TaskNodeDetail({ graph, node, onSelect, onEnter, onDiscuss }: { graph: TaskGraph; node: TaskNode } & GraphActions) {
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
    <section><h3>{t("tasks.description")}</h3><div className="tasks-prose"><ReactMarkdown remarkPlugins={[remarkGfm]}>{node.description || t("tasks.noDescription")}</ReactMarkdown></div></section>
    <section><h3>{t("tasks.result")}</h3><div className="tasks-prose"><ReactMarkdown remarkPlugins={[remarkGfm]}>{node.result || t("tasks.noResult")}</ReactMarkdown></div></section>
    {parent?.mode === "dag" && <><section><h3>{t("tasks.predecessors")}</h3>{relationList(graph.dependencies.filter(edge => edge.to === node.id).map(edge => edge.from))}</section>
      <section><h3>{t("tasks.successors")}</h3>{relationList(graph.dependencies.filter(edge => edge.from === node.id).map(edge => edge.to))}</section></>}
    {node.derived_from_id && <section><h3>{t("tasks.derivedFrom")}</h3>{relationList([node.derived_from_id])}</section>}
    {node.selected_candidate_id && <section><h3>{t("tasks.currentChoice")}</h3>{relationList([node.selected_candidate_id])}<p>{node.selection_reason || t("tasks.noReason")}</p></section>}
    {node.links.length > 0 && <section><h3>{t("tasks.links")}</h3><ul>{node.links.map((link, index) => <li key={index}><ReactMarkdown>{`[${link.replace(/[\[\]]/g, "\\$&")}](${link})`}</ReactMarkdown></li>)}</ul></section>}
    <section className="tasks-detail-facts"><dl><div><dt>{t("tasks.structure")}</dt><dd>{children.length ? t("tasks.nodeCount", { count: children.length }) : t("tasks.mode.none")}</dd></div>
      <div><dt>{t("tasks.updatedBy")}</dt><dd>{node.updated_by}</dd></div><div><dt>{t("tasks.updatedAt")}</dt><dd>{new Date(node.updated_at).toLocaleString(i18n.language)}</dd></div>
      <div><dt>{t("tasks.revision")}</dt><dd>{graph.revision}</dd></div></dl><p className="tasks-detail-note">{t("tasks.recordedHint")}</p></section>
    <div className="tasks-detail-actions">{node.mode !== "none" && <button className="tasks-button tasks-button--primary" onClick={() => onEnter(node)}>{t("tasks.enter")} · {t(`tasks.mode.${node.mode}`)} →</button>}
      <button className="tasks-button" onClick={() => onDiscuss(node)}>{t("tasks.discussNode")}</button></div>
  </>;
}

export function TaskGraphsPage() {
  const { t } = useTranslation();
  const { graphId } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [listOpen, setListOpen] = useState(false);
  const query = useTaskGraph(graphId);
  const graph = query.data;
  const root = graph?.nodes.find(node => node.id === graph.root_node_id);
  const selected = graph?.nodes.find(node => node.id === params.get("node"));
  const scopeId = params.get("scope") ?? selected?.container_id ?? graph?.root_node_id;
  const scope = graph?.nodes.find(node => node.id === scopeId);
  const invalidLocation = Boolean(graph && (!root || !scope || (params.has("node") && (!selected || (selected.id !== scope.id && selected.container_id !== scope.id)))));
  const breadcrumbs: TaskNode[] = [];
  for (let current = scope; current; current = graph?.nodes.find(node => node.id === current?.container_id)) breadcrumbs.unshift(current);

  function enter(node: TaskNode) {
    const next = new URLSearchParams(params);
    next.set("scope", node.id);
    next.delete("node");
    setParams(next);
  }
  function select(node: TaskNode) {
    const next = new URLSearchParams(params);
    if (node.id !== scope?.id && node.container_id !== scope?.id) next.set("scope", node.container_id ?? node.id);
    next.set("node", node.id);
    setParams(next);
  }
  function closeDetail() {
    const next = new URLSearchParams(params);
    next.delete("node");
    setParams(next, { replace: true });
  }
  function discuss(node: TaskNode) {
    if (!graph) return;
    const store = composerStoreFor(useAuthStore.getState().user?.id ?? null);
    const current = store.get(graph.home_conversation_id) ?? EMPTY_COMPOSER_SNAPSHOT;
    const title = node.title.replace(/([\\[\]])/g, "\\$1");
    const reference = `[${t("tasks.taskReference")}: ${title}](${taskGraphUrl(graph.graph_id, node.container_id ?? node.id, node.id)})`;
    writeComposerSnapshot(store, graph.home_conversation_id, { ...current, draft: `${current.draft}${current.draft ? "\n\n" : ""}${reference}\n` });
    navigate(`/chat/${encodeURIComponent(graph.home_conversation_id)}`);
  }
  const actions = { onSelect: select, onEnter: enter, onDiscuss: discuss };
  return <div className="tasks-workspace">
    <aside className={`tasks-sidebar${!graphId ? " tasks-sidebar--index" : ""}`}><TaskGraphListPanel graphId={graphId} /></aside>
    <main className={`tasks-main${!graphId ? " tasks-main--index" : ""}`}>
      <header className="tasks-header"><div><h1>{root?.title ?? t("shell.tabs.tasks")}</h1>
        <p>{graph ? `${graph.home_conversation_title} · ${t("tasks.revision")} ${graph.revision}` : t("tasks.subtitle")}</p></div>
        <div className="tasks-header-actions"><button className="tasks-button tasks-targets-button" onClick={() => setListOpen(true)}>{t("tasks.targets")}</button>
          {graphId && <button className="tasks-button" aria-label={t("tasks.refresh")} disabled={query.isFetching} onClick={() => void query.refetch()}>↻ <span className="tasks-refresh-label">{t("tasks.refresh")}</span></button>}
          {graph && root && <button className="tasks-button tasks-return" onClick={() => discuss(selected ?? scope ?? root)}>{t("tasks.discuss")}</button>}</div>
      </header>
      {!graphId ? <div className="tasks-empty"><h2>{t("tasks.chooseGraph")}</h2><p>{t("tasks.listHint")}</p><Link className="tasks-button" to="/chat">{t("tasks.goChat")}</Link></div>
        : query.isPending ? <div className="tasks-empty" role="status">{t("tasks.loading")}</div>
        : graph === null ? <div className="tasks-empty" role="alert"><h2>{t("tasks.unavailable")}</h2><Link className="tasks-button" to="/tasks">{t("tasks.allTargets")}</Link></div>
        : <>{query.isError && <ReadNotice stale={Boolean(graph)} onRefresh={() => void query.refetch()} />}
          {invalidLocation ? <div className="tasks-empty" role="alert"><h2>{t("tasks.invalidLocation")}</h2>{root && <button className="tasks-button" onClick={() => enter(root)}>{t("tasks.backRoot")}</button>}</div>
            : graph && scope && <><nav className="tasks-breadcrumbs" aria-label={t("tasks.breadcrumbs")}><Link to="/tasks">{t("shell.tabs.tasks")}</Link>
              {breadcrumbs.map((node, index) => <span key={node.id}><i aria-hidden>›</i><button aria-current={index === breadcrumbs.length - 1 ? "page" : undefined} onClick={() => enter(node)}>{node.title}</button></span>)}</nav>
              <div className="tasks-content"><TaskGraphCanvas key={`${graph.graph_id}:${scope.id}`} graph={graph} scope={scope} selectedId={selected?.id} {...actions} />
                {!isMobile && <aside className="tasks-detail" aria-label={t("tasks.nodeDetails")}><TaskNodeDetail graph={graph} node={selected ?? scope} {...actions} /></aside>}
              </div>
              {isMobile && <Dialog.Root open={Boolean(selected)} onOpenChange={open => { if (!open) closeDetail(); }}><Dialog.Portal>
                <Dialog.Overlay className="tasks-dialog-overlay" /><Dialog.Content className="tasks-detail tasks-detail--mobile" aria-describedby={undefined} onCloseAutoFocus={event => {
                  event.preventDefault();
                  const button = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-node-id]")).find(element => element.dataset.nodeId === selected?.id);
                  button?.focus();
                }}>
                  <div className="tasks-dialog-heading"><Dialog.Title>{t("tasks.nodeDetails")}</Dialog.Title><Dialog.Close className="tasks-button">{t("tasks.close")}</Dialog.Close></div>
                  {selected && <TaskNodeDetail graph={graph} node={selected} {...actions} />}
                </Dialog.Content>
              </Dialog.Portal></Dialog.Root>}
            </>}
        </>}
    </main>
    <Dialog.Root open={listOpen} onOpenChange={setListOpen}><Dialog.Portal><Dialog.Overlay className="tasks-dialog-overlay" /><Dialog.Content className="tasks-targets-dialog" aria-describedby={undefined}>
      <div className="tasks-dialog-heading"><Dialog.Title>{t("tasks.targets")}</Dialog.Title><Dialog.Close className="tasks-button">{t("tasks.close")}</Dialog.Close></div>
      <TaskGraphListPanel graphId={graphId} onChoose={() => setListOpen(false)} />
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}
