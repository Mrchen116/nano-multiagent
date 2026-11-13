import { useInfiniteQuery } from "@tanstack/react-query";
import { Archive, LoaderCircle } from "lucide-react";
import { useId, useLayoutEffect, useRef, useState, type RefObject } from "react";

import { i18n } from "../../../i18n";
import { workAccessLost, workBase, workRequest, type WorkDelegationNode, type WorkDelegationPage } from "./agent-work-api";
import { formatWorkTokens, tr } from "./agent-work-text";

type Window = WorkDelegationPage["window"];

const states: Record<string, string> = {
  running: "运行中", waiting_permission: "等待授权", completed: "已完成", failed: "失败",
  interrupted: "已中断", unknown: "状态未知", idle: "空闲",
};

function DelegationEdges({diagram, parents, visible}: {
  diagram: RefObject<HTMLDivElement | null>;
  parents: Map<string, string>;
  visible: boolean;
}) {
  const marker = useId();
  const [paths, setPaths] = useState<string[]>([]);
  useLayoutEffect(() => {
    const element = diagram.current;
    if (!element || !visible) return;
    const nodes = [...element.querySelectorAll<HTMLElement>("[data-work-node]")];
    const draw = () => {
      const {left, top} = element.getBoundingClientRect();
      const bounds = new Map(nodes.map(node => [node.dataset.workNode, node.getBoundingClientRect()]));
      setPaths([...parents].flatMap(([child, parent]) => {
        const from = bounds.get(parent), to = bounds.get(child);
        if (!from || !to) return [];
        const x1 = from.right - left, x2 = to.left - left;
        const y1 = from.top + from.height / 2 - top, y2 = to.top + to.height / 2 - top;
        const middle = (x1 + x2) / 2;
        return [`M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2 - 1} ${y2}`];
      }));
    };
    draw();
    if (typeof ResizeObserver === "undefined") return;
    const resize = new ResizeObserver(draw);
    resize.observe(element);
    nodes.forEach(node => resize.observe(node));
    return () => resize.disconnect();
  }, [diagram, parents, visible]);

  return <svg className="im-work-graph-edges" aria-hidden="true">
    <defs><marker id={marker} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M 1 1 L 7 4 L 1 7" />
    </marker></defs>
    {paths.map((path, i) => <path key={i} d={path} markerEnd={`url(#${marker})`} />)}
  </svg>;
}

export function WorkDelegation({agentId, agentName, visible, openSession}: {
  agentId: string; agentName?: string; visible: boolean; openSession(sessionId: string | null): void;
}) {
  const [window, setWindow] = useState<Window>("3d");
  const [selected, setSelected] = useState<string>();
  const diagram = useRef<HTMLDivElement>(null);
  const pages = useInfiniteQuery({
    queryKey: ["agent-work-delegation", agentId, window],
    enabled: visible,
    staleTime: 30_000,
    initialPageParam: null as {after: string; until: string} | null,
    queryFn: ({signal, pageParam}) => {
      const query = new URLSearchParams({window, limit: "8"});
      if (pageParam) { query.set("after_session", pageParam.after); query.set("until", pageParam.until); }
      return workRequest<WorkDelegationPage>(`${workBase(agentId)}/delegation?${query}`, signal);
    },
    getNextPageParam: page => page.next_cursor ? {after: page.next_cursor, until: page.until} : undefined,
  });
  const head = workAccessLost(pages.error) ? undefined : pages.data?.pages[0];
  const catchingUp = head?.record_sync_state === "catching_up";
  const byId = new Map<string, WorkDelegationNode>();
  for (const page of (head && pages.data?.pages) || []) for (const node of page.nodes) {
    if (!byId.has(node.session_id) || !node.ancestor_only) byId.set(node.session_id, node);
  }
  const byParent = new Map<string | null, WorkDelegationNode[]>();
  const parentsById = new Map<string, string>();
  const sameTitle = new Map<string, number>();
  for (const node of byId.values()) {
    if (node.title) sameTitle.set(node.title, (sameTitle.get(node.title) ?? 0) + 1);
    const parent = node.parent_session_id && byId.has(node.parent_session_id) ? node.parent_session_id : null;
    if (parent) parentsById.set(node.session_id, parent);
    const children = byParent.get(parent) ?? [];
    children.push(node);
    byParent.set(parent, children);
  }
  for (const siblings of byParent.values()) {
    siblings.sort((a, b) => Number(b.session_id === head?.main_session_id) - Number(a.session_id === head?.main_session_id) ||
      (b.last_active_at ?? "").localeCompare(a.last_active_at ?? ""));
  }
  const timestamp = (iso: string) => new Date(iso).toLocaleString(i18n.language, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

  const renderNode = (node: WorkDelegationNode, parents: ReadonlySet<string>) => {
    const {session_id: id, usage} = node;
    if (parents.has(id)) return null;
    const isRoot = id === head?.main_session_id;
    const children = byParent.get(id) ?? [];
    const path = new Set(parents).add(id);
    const label = isRoot ? agentName || tr("主 Agent") : node.title || id;
    const ambiguous = node.title && (sameTitle.get(node.title) ?? 0) > 1;
    const totalTurns = usage.reported_turns + usage.missing_turns;
    return <li key={id} className="im-work-graph-branch">
      <button type="button" className="im-work-graph-node" title={id} data-work-node={id}
        data-root={isRoot} data-selected={selected === id}
        onClick={() => { setSelected(id); openSession(isRoot ? null : id); }}>
        <strong>{label}</strong>
        <span className={`im-work-graph-node-meta ${node.status}`}>
          {isRoot ? agentName && tr("主 Agent") : <>
            {node.last_active_at && <time dateTime={node.last_active_at}>{timestamp(node.last_active_at)} · </time>}
            {tr(states[node.status] ?? node.status)}
            {ambiguous && ` · ${id.slice(-8)}`}
          </>}
        </span>
        <span className="im-work-graph-node-metrics">
          {usage.total_tokens === null ? tr("Token 未报告") : <>
            {isRoot ? `${tr("自身累计")} · ` : totalTurns > 1 ? `${totalTurns} ${tr("轮累计")} · ` : ""}
            <span title={`${usage.total_tokens.toLocaleString(i18n.language)} tok`}>{formatWorkTokens(usage.total_tokens)} tok</span>
          </>}
        </span>
        {(isRoot && totalTurns > 0 || usage.missing_turns > 0 || node.ancestor_only) && <small>{node.ancestor_only
          ? tr("仅显示派工路径") : `${usage.reported_turns}/${totalTurns} ${tr("轮次已报告")}`}</small>}
      </button>
      {children.length > 0 && <ul>{children.map(child => renderNode(child, path))}</ul>}
    </li>;
  };

  return <section className="im-work-graph" hidden={!visible} aria-label={tr("派工关系")}>
    <header className="im-work-graph-toolbar">
      <div className="im-work-graph-period">
        {head?.from && head.until && <time dateTime={head.until}>{timestamp(head.from)} – {timestamp(head.until)}</time>}
        {head && head.record_sync_state !== "current" && <span className="im-work-graph-sync" role="status"
          title={tr(catchingUp ? "工作记录正在补齐，当前显示已保存内容。" : "当前显示已保存记录，最新进度尚未确认。")}>
          {catchingUp ? <LoaderCircle aria-hidden="true" size={13} className="motion-safe:animate-spin" /> : <Archive aria-hidden="true" size={13} />}
          {tr(catchingUp ? "记录同步中" : "已保存记录")}
        </span>}
      </div>
      <label className="im-work-graph-range">
        <span>{tr("活动范围")}</span>
        <select value={window} onChange={event => setWindow(event.currentTarget.value === "2h" ? "2h" : "3d")}>
          <option value="3d">{tr("最近 3 天")}</option>
          <option value="2h">{tr("最近 2 小时")}</option>
        </select>
      </label>
    </header>
    {pages.isLoading && <p role="status" className="im-work-state">{tr("正在加载工作记录…")}</p>}
    {pages.isError && <p role="alert" className="im-work-callout">{pages.error.message} <button type="button"
      onClick={() => pages.isFetchNextPageError ? void pages.fetchNextPage() : void pages.refetch()}>{tr("重试")}</button></p>}
    {head && <div className="im-work-graph-canvas">
      {byParent.get(null)?.length ? <>
        <div className="im-work-graph-columns" aria-hidden="true">
          <span>{tr("主 Agent")}</span><span>{tr("直接派工")}</span><span>{tr("继续派工")}</span>
        </div>
        <div ref={diagram} className="im-work-graph-diagram">
          <DelegationEdges diagram={diagram} parents={parentsById} visible={visible} />
          <ul className="im-work-graph-tree">{byParent.get(null)?.map(node => renderNode(node, new Set()))}</ul>
        </div>
      </> : <p className="im-work-state">{tr("这个时间范围内没有派工记录。")}</p>}
    </div>}
    {pages.hasNextPage && <button type="button" className="im-work-child-link" disabled={pages.isFetching}
      onClick={() => void pages.fetchNextPage()}>{tr("加载更多")}</button>}
  </section>;
}
