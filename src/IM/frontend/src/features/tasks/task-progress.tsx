import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../i18n";
import { TaskWaitInfo } from "./task-wait";
import { listContacts } from "../chat/contacts-api";
import { taskGraphUrl, useTaskGraphColumn, type DirectCounts, type TaskActor, type TaskGraphSummary, type TaskNode, type TaskStatus, type TaskListOptions } from "./task-graphs-api";

export const taskStatuses: TaskStatus[] = ["todo", "doing", "waiting", "in_review", "done", "paused", "closed"];
export const editableTaskStatuses = (current?: TaskStatus) => taskStatuses.filter(status => status !== "waiting" || current === "waiting");
const columns: TaskStatus[] = ["todo", "doing", "in_review", "done", "closed"];
export const actorName = (actor?: TaskActor | null) => actor?.display_name || actor?.id;
export function TaskCounts({ counts }: { counts?: DirectCounts }) {
  const { t } = useTranslation();
  return <small>{t("tasks.directCount", { done: counts?.done ?? 0, total: counts?.total ?? 0 })}</small>;
}
type Card = Pick<TaskNode, "id" | "title" | "status" | "mode" | "assignee" | "direct_counts" | "wait" | "wait_health"> & { context?: string; selected?: boolean };
type CardActions = { onSelect(node: Card): void; onEnter(node: Card): void };
function TaskColumn({ status, nodes, total, pending = false, bodyRef, children, onSelect, onEnter }: CardActions & {
  status: TaskStatus; nodes: Card[]; total?: number; pending?: boolean;
  bodyRef?: RefObject<HTMLDivElement | null>; children?: ReactNode;
}) {
  const { t } = useTranslation();
  return <section className={`tasks-column tasks-column--${status}`} data-testid="task-status-column" aria-label={t(status === "doing" ? "tasks.ongoing" : `tasks.status.${status}`)}>
    <header><h2>{t(status === "doing" ? "tasks.ongoing" : `tasks.status.${status}`)}</h2><span>{total ?? "—"}</span></header>
    <div className="tasks-column-body" ref={bodyRef} aria-busy={pending}>
      {nodes.map(node => <article className="tasks-progress-card" key={node.id}>
        <button className="tasks-progress-card-main" data-node-id={node.id} aria-label={t("tasks.viewNode", { title: node.title })} onClick={() => onSelect(node)}>
          <h3>{node.title}</h3>{["paused", "doing", "waiting"].includes(node.status) && <span className={`tasks-status tasks-status--${node.status}`}>{t(`tasks.status.${node.status}`)}</span>}
          {node.selected && <span className="tasks-picked">{t("tasks.picked")}</span>}
          <span>{actorName(node.assignee) || t("tasks.unassigned")}</span>{node.context && <small>{node.context}</small>}
          <TaskCounts counts={node.direct_counts} />
          {node.status === "waiting" && <TaskWaitInfo wait={node.wait} health={node.wait_health} compact />}
        </button>
        <button className="tasks-child-entry" onClick={() => onEnter(node)} aria-label={t("tasks.enterNode", { title: node.title })}>{t("tasks.children")} →</button>
      </article>)}
      {!pending && total === 0 && <p className="tasks-column-empty">{t("tasks.noTasks")}</p>}
      {children}
    </div>
  </section>;
}
export function TaskBoard({ nodes, onSelect, onEnter }: CardActions & { nodes: Card[] }) {
  return <div className="tasks-board">{columns.map(status => {
    const group = nodes.filter(node => node.status === status || status === "todo" && node.status === "paused" || status === "doing" && node.status === "waiting");
    return <TaskColumn key={status} status={status} nodes={group} total={group.length} onSelect={onSelect} onEnter={onEnter} />;
  })}</div>;
}
function TaskOverviewColumn({ status, options, byOwner, onSelect }: {
  status: TaskStatus; options: TaskListOptions; byOwner: boolean; onSelect(item: TaskGraphSummary): void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useTaskGraphColumn({ ...options, statuses: status === "todo" ? ["todo", "paused"] : status === "doing" ? ["doing", "waiting"] : [status] });
  const body = useRef<HTMLDivElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const pages = query.data?.pages ?? [];
  const items = [...new Map(pages.flatMap(page => page?.items ?? []).map(item => [`${item.graph_id}:${item.node_id ?? item.root_node_id}`, item])).values()];
  const total = pages[0]?.total;
  const unavailable = pages.some(page => page === null);
  useEffect(() => {
    if (!query.hasNextPage || query.isFetching || query.isError || !end.current) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) void query.fetchNextPage();
    }, { root: body.current, rootMargin: "0px 0px 160px 0px" });
    observer.observe(end.current);
    return () => observer.disconnect();
  }, [query.hasNextPage, query.isFetching, query.isError, query.fetchNextPage]);
  const itemFor = (node: Card) => items.find(item => `${item.graph_id}:${item.node_id ?? item.root_node_id}` === node.id)!;
  return <TaskColumn status={status} total={unavailable ? undefined : total} pending={query.isPending} bodyRef={body}
    nodes={unavailable ? [] : items.map(item => ({ ...item, id: `${item.graph_id}:${item.node_id ?? item.root_node_id}`, context: [item.conversation?.title, ...(item.parent_path?.map(node => node.title) ?? [])].filter(Boolean).join(" / ") }))}
    onSelect={node => { const item = itemFor(node); if (byOwner) navigate(taskGraphUrl(item.graph_id, item.scope_id ?? item.node_id ?? item.root_node_id, item.node_id ?? item.root_node_id)); else onSelect(item); }}
    onEnter={node => { const item = itemFor(node); navigate(taskGraphUrl(item.graph_id, item.node_id ?? item.root_node_id)); }}>
    {query.isPending && <p className="tasks-column-empty" role="status">{t("tasks.loading")}</p>}
    {query.isError && <div className="tasks-column-notice" role="alert">{t(query.isFetchNextPageError ? "tasks.appendFailed" : items.length ? "tasks.columnRefreshFailed" : "tasks.readFailed")}<button className="tasks-button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>{t(query.isFetchNextPageError ? "common.retry" : "tasks.refresh")}</button></div>}
    {unavailable && <p role="alert" className="tasks-column-empty">{t("tasks.unavailable")}</p>}
    {!unavailable && total !== undefined && total > 0 && <div ref={end} className="tasks-column-end" role="status">
      {query.isFetchingNextPage ? t("tasks.loadingMore") : query.hasNextPage ? t("tasks.loadedCount", { count: items.length, total }) : t("tasks.allLoaded", { count: items.length })}
    </div>}
  </TaskColumn>;
}
export function TaskOverview({ onCreate, onSelect }: { onCreate(): void; onSelect(item: TaskGraphSummary): void }) {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const queryText = params.get("query") ?? "";
  const [search, setSearch] = useState(queryText);
  const byOwner = params.get("collection") === "assignee";
  const contacts = useQuery({ queryKey: ["task-assignee-contacts"], queryFn: () => listContacts(), enabled: byOwner });
  const assigneeType = params.get("assignee_type") ?? "";
  const assigneeId = params.get("assignee_id") ?? "";
  const options = { query: queryText, assignee_type: byOwner ? assigneeType : undefined, assignee_id: byOwner ? assigneeId : undefined };
  function setFilter(key: string, value: string) { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); setParams(next); }
  return <>
    <div className="tasks-toolbar">
      <button className="tasks-button" aria-pressed={!byOwner} onClick={() => setFilter("collection", "")}>{t("tasks.overview")}</button>
      <button className="tasks-button" aria-pressed={byOwner} onClick={() => setFilter("collection", "assignee")}>{t("tasks.byAssignee")}</button>
      {byOwner && <select aria-label={t("tasks.assignee")} value={`${assigneeType}:${assigneeId}`} onChange={event => { const [type, id] = event.target.value.split(":"); const next = new URLSearchParams(params); next.set("assignee_type", type); next.set("assignee_id", id); setParams(next); }}>
        <option value=":">{t("tasks.chooseAssignee")}</option>{contacts.data?.map(contact => <option key={contact.user_id} value={`${contact.kind === "human" ? "user" : "agent"}:${contact.agent_id ?? contact.user_id}`}>{contact.display_name}</option>)}
      </select>}
      <form className="tasks-search" onSubmit={event => { event.preventDefault(); setFilter("query", search.trim()); }}><input aria-label={t("tasks.search")} value={search} placeholder={t("tasks.search")} onChange={event => setSearch(event.target.value)} /><button className="tasks-button">{t("tasks.searchButton")}</button></form>
      <button className="tasks-button tasks-button--primary" onClick={onCreate}>{t("tasks.createRoot")}</button>
    </div>
    <p className="tasks-range">{t(byOwner ? "tasks.allLevels" : "tasks.rootsOnly")}</p>
    {byOwner && !assigneeId ? <p className="tasks-range">{t("tasks.chooseAssignee")}</p> :
      <div className="tasks-board" key={JSON.stringify(options)}>{columns.map(status => <TaskOverviewColumn key={status} status={status} options={options} byOwner={byOwner} onSelect={onSelect} />)}</div>}
  </>;
}
