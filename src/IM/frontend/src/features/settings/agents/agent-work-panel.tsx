import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { TaskGraphLink } from "../../tasks/task-graph-link";

import { subscribeUserStream } from "../../../realtime/user-stream";
import type { BackgroundReturn, PermissionRequest, TokenUsage, ToolCall } from "../../chat/chat-types";
import { formatDuration } from "../../chat/components/tool-calls-panel";
import { WorkTool, WorkBackground, WorkUsage, withVisibleReasoning } from "./agent-work-presenters";
import { tr } from "./agent-work-text";
import { i18n, useTranslation } from "../../../i18n";
import { PermissionCard } from "../../chat/components/permission-card";
import { WorkNavigationContext, WorkThreadLink } from "../../chat/components/work-thread-link";
import { AgentExecutionDeletedError, workBase, workCatalogPath, workRequest, workSessionPath, type WorkCatalogPage, type WorkItemsPage, type WorkFocus, type WorkItem, type WorkSession, type WorkTurn, type WorkTurnPage, type WorkView } from "./agent-work-api";
import "./agent-work.css";
import { useWorkHistory } from './agent-work-history';
import { LegacyWorkLinks, WorkLink } from './agent-work-links';
import { WorkOriginals } from "./agent-work-originals";
import { AgentTrajectory } from './agent-trajectory';

type SavedView = { selected: string | null; expanded: Record<string, boolean>; scroll: number; mainScroll?: number; focus?: string };
const str = (value: unknown) => typeof value === "string" ? value : "";
const obj = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const turnElementId = (session: string, turn: string) => `work-turn-${encodeURIComponent(session)}-${encodeURIComponent(turn)}`;
const statusLabel = (status: string) => tr({ running: "运行中", waiting_permission: "等待授权", completed: "已完成", failed: "失败", interrupted: "已中断", unknown: "状态未知", idle: "空闲" }[status] ?? status);

function readSaved(key: string): SavedView {
  try { return JSON.parse(sessionStorage.getItem(key) ?? "null") ?? { selected: null, expanded: {}, scroll: 0 }; }
  catch { return { selected: null, expanded: {}, scroll: 0 }; }
}

function WorkTurnList({ turns, anchors, renderTurn, nextTurnId, earlier, history }: {
  turns: WorkTurn[];
  anchors: WorkFocus[];
  renderTurn(turn: WorkTurn): ReactNode;
  nextTurnId?: string | null;
  earlier?: {loading: boolean; load(): void};
  history?: ReturnType<typeof useWorkHistory>;
}) {
  const ordinary = new Set(turns.map(turn => turn.turn_id));
  const extra = new Map(anchors.filter(anchor => !ordinary.has(anchor.turn.turn_id)).map(anchor => [anchor.turn.turn_id, anchor]));
  const merged = extra.size ? [...turns, ...[...extra.values()].map(anchor => anchor.turn)].sort((a, b) => b.seq - a.seq) : turns;
  const olderByTurn = new Map(turns.map((turn, i) => [turn.turn_id, turns[i + 1]?.turn_id ?? nextTurnId]));
  const neighbor = (turn: WorkTurn) => {
    const anchor = extra.get(turn.turn_id);
    return anchor ? anchor.older_turn_id : history ? history.history.older[turn.turn_id] : olderByTurn.get(turn.turn_id);
  };
  const gaps = merged.map((turn, i) => {
    if (history) return i > 0 && neighbor(merged[i - 1]) !== turn.turn_id;
    const anchor = extra.get(turn.turn_id);
    if (!anchor) return false;
    const previous = merged[i - 1];
    // An inactive anchor may have been newest when cached. The preceding
    // card's older neighbor still identifies the boundary after newer turns arrive.
    const precedingAnchor = previous && extra.get(previous.turn_id);
    const older = precedingAnchor ? precedingAnchor.older_turn_id : previous && olderByTurn.get(previous.turn_id);
    return older !== undefined ? older !== turn.turn_id : anchor.newer_turn_id !== (previous?.turn_id ?? null);
  });
  const firstGap = gaps.indexOf(true);
  const tail = merged.at(-1);
  const before = history && (firstGap >= 1 ? merged[firstGap - 1].turn_id : tail && neighbor(tail) ? tail.turn_id : undefined);
  const paging = history ? before && {loading: history.loading, load: () => history.load(before)} : earlier;
  const more = paging && <button className="im-work-earlier" type="button" disabled={paging.loading} onClick={paging.load}>{tr("更早轮次")}</button>;
  return <>
    {merged.map((turn, i) => <Fragment key={turn.turn_id}>
      {firstGap === i && more}
      {gaps[i] && <p className="im-work-gap">{tr("中间轮次尚未加载")}</p>}
      {renderTurn(turn)}
    </Fragment>)}
    {firstGap === -1 && more}
    {history?.error && <p role="alert">{history.error.message}</p>}
  </>;
}

const Usage = WorkUsage;

function turnTitle(turn: WorkTurn) {
  const trigger = turn.trigger ?? {};
  const origin = typeof turn.origin === "string" ? turn.origin : str(turn.origin?.kind);
  const type = str(trigger.kind) || origin;
  if (type === "inbox") return "Inbox 唤醒";
  if (type === "inbox-background") return "近况同步";
  if (type === "heartbeat") return "Heartbeat";
  if (turn.scope === "cron" || type === "cron") return cronTitle(trigger.source, turn.job_id);
  if (turn.scope === "workflow") return "Workflow 执行";
  if (type === "background_task") {
    const returns = turn.items.flatMap(item => Array.isArray(item.payload.background_returns) ? item.payload.background_returns.map(obj) : item.kind === "background_return" ? [item.payload] : []);
    if (turn.scope === "subagent" && returns.length === 0 && !turn.has_background_returns && !trigger.task_type) return turn.description || "子 Agent 执行";
    const taskType = str(trigger.task_type) || str(returns[0]?.task_type) || str(turn.background_task_type);
    return ({ agent: "收到子 Agent 结果", subagent: "收到子 Agent 结果", bash: "收到后台 Bash 结果", workflow: "收到 Workflow 结果" }[taskType] ?? "收到后台结果");
  }
  return ({ human: "人工输入", user: "输入触发" }[type] ?? "执行轮次");
}

function cronTitle(trigger: unknown, jobId?: string) {
  const title = trigger === "manual" ? "Cron · 手动执行" : trigger === "scheduled" ? "Cron · 定时执行" : "Cron";
  return jobId ? `${tr(title)} · ${jobId}` : tr(title);
}

function sessionTitle(session?: WorkSession) {
  if (session?.scope === "cron") return cronTitle(session.trigger, session.job_id);
  if (session?.scope === "workflow") return "Workflow 执行";
  return session?.description || session?.title || "关联执行";
}

function SessionFacts({ items, title = "执行记录" }: { items?: WorkItem[]; title?: string }) {
  const visibleItems = items?.filter(item => !(item.kind === "control_result" && item.payload.command === "new"));
  if (!visibleItems?.length) return null;
  return <details className="im-work-other"><summary>{tr(title)}</summary>{visibleItems.map(item => {
    const p = item.payload;
    return <div key={item.item_id}>
      <strong>{item.kind === "cron_delivery" ? "Cron 实际投递" : item.kind === "cron_trigger" ? cronTitle(p.trigger, str(p.job_id)) : str(p.command) || item.kind}</strong>
      {item.observed_at && <small className="im-work-muted"> · {new Date(item.observed_at).toLocaleString()}</small>}
      {item.kind === "cron_delivery" && str(p.conversation_id) && <div><WorkThreadLink conversationId={str(p.conversation_id)} messageId={str(p.message_id)}>{tr("投递聊天 · 原消息")}</WorkThreadLink><small className="im-work-muted"> · {str(p.conversation_id)}</small></div>}
      <pre className="chat-tool-call-pre">{str(p.text) || str(p.error) || str(p.model) || JSON.stringify(p, null, 2)}</pre>
    </div>;
  })}</details>;
}

function SessionControls({agentId, sessionId, title}: {agentId: string; sessionId: string; title: string}) {
  const [open, setOpen] = useState(false);
  const pages = useInfiniteQuery({
    queryKey: ["work-controls", agentId, sessionId], enabled: open, staleTime: Infinity, initialPageParam: "0",
    queryFn: ({pageParam, signal}) => workRequest<WorkItemsPage>(`${workSessionPath(agentId, sessionId)}/controls?after_seq=${pageParam}`, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  return <details className="im-work-other" onToggle={event => {if (event.target === event.currentTarget) setOpen(event.currentTarget.open);}}>
    <summary>{tr(title)}</summary>
    {pages.isLoading && <p role="status">{tr("正在加载工作记录…")}</p>}
    {pages.isError && <p role="alert">{pages.error.message}<button onClick={() => void pages.refetch()}>{tr("重试")}</button></p>}
    {pages.data?.pages.flatMap(page => page.items).filter(item => item.kind !== "control_result" || item.payload.command !== "new").map(item =>
      <SessionFacts key={item.item_id} items={[item]} title={str(item.payload.command) || item.kind} />)}
    {pages.hasNextPage && <button type="button" disabled={pages.isFetching} onClick={() => void pages.fetchNextPage()}>{tr("加载更多")}</button>}
  </details>;
}

/** Durable main/child timeline. Visual state survives a real Chat navigation. */
export function AgentWorkPanel({ agentId }: { agentId: string }) {
  useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const search = new URLSearchParams(location.search);
  const nativeMode = search.get('work_view') === 'trajectory';
  const messageId = search.get('message_id');
  const replyNavigation = useRef({agentId, messageId, token: location.key});
  // Internal record/trajectory switches replace the URL too, but must not apply
  // the same reply anchor again over the reader's folding and scroll position.
  if (replyNavigation.current.agentId !== agentId || replyNavigation.current.messageId !== messageId) replyNavigation.current = {agentId, messageId, token: location.key};
  const replyFocusToken = replyNavigation.current.token;
  const focusedNavigation = useRef<string | null>(null);
  const recordScroll = useRef(0);
  const nativePositions = useRef<Record<string, { top: number; firstSeq?: number; rowKey?: string; detailTab?: string }>>({});
  const client = useQueryClient();
  const namesQuery = useQuery({ queryKey: ["work-conversation-names"], queryFn: () => workRequest<{items: {id: string; title: string; participants?: {id: string; user_id?: string; display_name?: string}[]}[]}>("/im/v1/conversations") });
  const people = Object.fromEntries((namesQuery.data?.items ?? []).flatMap(c => (c.participants ?? []).flatMap(p => p.display_name ? [[p.id, p.display_name], ...(p.user_id ? [[p.user_id, p.display_name]] : [])] : [])));
  const names = Object.fromEntries((namesQuery.data?.items ?? []).map(c => [c.id, c.title]));
  const storageKey = `agent-work:${agentId}`;
  const [saved, setSaved] = useState(() => readSaved(storageKey));
  const root = useRef<HTMLDivElement>(null);
  const restored = useRef(false);
  const viewQuery = useInfiniteQuery({ queryKey: ["agent-work", agentId, "main"], initialPageParam: "", staleTime: 1000, queryFn: ({ pageParam, signal }) => workRequest<WorkView>(`${workBase(agentId)}?view=summary&catalog=separate${pageParam ? `&before_turn=${encodeURIComponent(pageParam)}` : ""}`, signal), getNextPageParam: page => page.catalog === "separate" ? undefined : page.next_cursor ?? undefined });
  const view = viewQuery.data?.pages[0];
  const separate = view?.catalog === "separate";
  const focusPrefix = ["agent-work", agentId, "focus"];
  const focusQuery = useQuery({
    queryKey: [...focusPrefix, messageId], enabled: Boolean(messageId && view), staleTime: 1000, retry: false,
    refetchOnWindowFocus: !separate, refetchOnReconnect: !separate,
    queryFn: async ({signal}) => (await workRequest<{focus: WorkFocus | null}>(`${workBase(agentId)}/focus?message_id=${encodeURIComponent(messageId!)}${separate ? "&catalog=separate" : ""}`, signal)).focus,
  });
  const focus = focusQuery.isSuccess ? focusQuery.data?.turn : undefined;
  // The ordinary pages own their cursors. Visited reply summaries share the
  // account's query cache and supplement those pages until pagination reaches them.
  const anchors = (viewQuery.isSuccess ? client.getQueriesData<WorkFocus | null>({queryKey: focusPrefix}) : []).flatMap(([key, data]) =>
    data && client.getQueryState(key)?.status === "success" ? [data] : []);
  const nativeSession = search.get('execution') || focus?.session_id || view?.main_session_id || null;
  const [nativeSelectionVersion, setNativeSelectionVersion] = useState(0);
  const [activeNative, setActiveNative] = useState<{base: string | null; sessionId: string; label?: string} | null>(null);
  const onActiveNative = useCallback((sessionId: string, label?: string) => setActiveNative({base:nativeSession,sessionId,label}), [nativeSession]);
  const shownNative = activeNative?.base === nativeSession ? activeNative.sessionId : nativeSession;
  const showNative = (sessionId?: string | null) => {
    setNativeSelectionVersion(value => value + 1);
    setActiveNative(null);
    if (!nativeMode) recordScroll.current = root.current?.closest('.im-agent-panel')?.scrollTop ?? 0;
    setSaved(current => ({ ...current, selected: sessionId && sessionId !== view?.main_session_id ? sessionId : null }));
    const next = new URLSearchParams(location.search); next.set('work_view', 'trajectory');
    if (sessionId) next.set('execution', sessionId); else next.delete('execution');
    navigate({ search: next.toString() }, { replace: true });
    root.current?.closest('.im-agent-panel')?.scrollTo({ top: 0 });
  };
  const showRecords = () => {
    const next = new URLSearchParams(location.search); next.delete('work_view'); next.delete('execution');
    navigate({ search: next.toString() }, { replace: true });
    requestAnimationFrame(() => root.current?.closest('.im-agent-panel')?.scrollTo({ top: recordScroll.current }));
  };
  const childPath = saved.selected ? workSessionPath(agentId, saved.selected) : "";
  const childQuery = useInfiniteQuery({
    queryKey: ["agent-work", agentId, "session", saved.selected, separate], initialPageParam: "",
    enabled: Boolean(view && saved.selected) && !nativeMode,
    queryFn: ({pageParam, signal}) => workRequest<WorkTurnPage>(`${childPath}/turns?view=summary${separate ? "&catalog=separate" : ""}${pageParam ? `&before_turn=${encodeURIComponent(pageParam)}` : ""}`, signal),
    getNextPageParam: page => separate ? undefined : page.next_cursor ?? undefined,
  });
  const metadataId = nativeMode ? shownNative : saved.selected;
  const metadata = useQuery({
    queryKey: ["work-session-metadata", agentId, metadataId], enabled: separate && Boolean(metadataId && metadataId !== view?.main_session_id),
    queryFn: ({signal}) => workRequest<WorkSession>(workSessionPath(agentId, metadataId!), signal), staleTime: Infinity, retry: false,
  });
  const [catalogOpen, setCatalogOpen] = useState(false);
  const catalogKey = ["work-catalog", agentId];
  const catalog = useInfiniteQuery({
    queryKey: catalogKey, enabled: separate && (catalogOpen || nativeMode), initialPageParam: "", staleTime: Infinity,
    queryFn: ({pageParam, signal}) => workRequest<WorkCatalogPage>(workCatalogPath(agentId, pageParam ? {after_session: pageParam} : {}), signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  const sessions = separate ? catalog.data?.pages.flatMap(page => page.sessions) ?? [] : view?.other_executions ?? [];
  const selected = separate ? metadata.data : sessions.find(s => s.session_id === saved.selected);
  const online = view?.node_connection_state === "online";
  const mainHistory = useWorkHistory(agentId, separate ? view?.main_session_id : null, separate ? view : undefined,
    view?.main_session_id ? workSessionPath(agentId, view.main_session_id) : "");
  const childHistory = useWorkHistory(agentId, separate ? saved.selected : null, separate ? childQuery.data?.pages[0] : undefined, childPath);
  const mainTurns = separate ? mainHistory.history.turns : viewQuery.data?.pages.flatMap(p => p.turns) ?? [];
  const childTurns = separate ? childHistory.history.turns : childQuery.data?.pages.flatMap(p => p.turns) ?? [];
  const mainAnchors = anchors.filter(anchor => anchor.turn.session_id === view?.main_session_id);
  const childAnchors = anchors.filter(anchor => anchor.turn.session_id === saved.selected);
  const save = () => {
    const scroll = root.current?.closest(".im-agent-panel")?.scrollTop ?? 0;
    sessionStorage.setItem(storageKey, JSON.stringify({ ...saved, scroll, focus: document.activeElement?.id }));
  };
  useEffect(() => { sessionStorage.setItem(storageKey, JSON.stringify(saved)); }, [saved, storageKey]);
  const refreshCurrent = useRef<() => void>(() => {});
  refreshCurrent.current = () => {
    if (!separate) {
      void client.invalidateQueries({queryKey: ["agent-work", agentId]}, {cancelRefetch: false});
      return;
    }
    void viewQuery.refetch({cancelRefetch: false});
    if (saved.selected && !nativeMode) void childQuery.refetch({cancelRefetch: false});
    if (messageId && !focus && !(focusQuery.error instanceof AgentExecutionDeletedError)) void focusQuery.refetch({cancelRefetch: false});
  };
  useEffect(() => {
    let timer: number | undefined;
    const schedule = () => {
      if (timer !== undefined) return;
      timer = window.setTimeout(() => { timer = undefined; refreshCurrent.current(); }, 500);
    };
    const unsubscribe = subscribeUserStream({onEvent: event => {
      if ((event.eventType === "agent.work.updated" || event.eventType === "agent.status_changed") && event.payload.agent_id === agentId) schedule();
    }, onRecovery: schedule});
    const refreshVisible = () => { if (document.visibilityState !== "hidden") refreshCurrent.current(); };
    const poll = window.setInterval(refreshVisible, 15_000);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      unsubscribe(); window.clearTimeout(timer); window.clearInterval(poll);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [agentId]);
  useEffect(() => {
    if (!view || restored.current || (focus && !nativeMode)) return;
    restored.current = true;
    const frame = requestAnimationFrame(() => {
      const scroller = root.current?.closest(".im-agent-panel");
      if (scroller) scroller.scrollTop = saved.scroll;
      if (saved.focus) document.getElementById(saved.focus)?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [view, saved, focus, nativeMode]);
  useEffect(() => {
    if (!view || !focus || nativeMode || focusedNavigation.current === replyFocusToken) return;
    focusedNavigation.current = replyFocusToken;
    restored.current = true;
    const key = `${focus.session_id}:${focus.turn_id}`;
    setSaved(current => ({...current, selected: focus.session_id === view.main_session_id ? null : focus.session_id, expanded: {...current.expanded, [key]: true}}));
  }, [focus, view, nativeMode, replyFocusToken]);
  const expand = (key: string, open: boolean) => setSaved(current => ({ ...current, expanded: { ...current.expanded, [key]: open } }));
  const refresh = () => refreshCurrent.current();
  const selectChild = (id: string | null) => {
    const scroller = root.current?.closest(".im-agent-panel");
    const mainScroll = saved.selected ? saved.mainScroll ?? 0 : scroller?.scrollTop ?? 0;
    setSaved(current => ({ ...current, selected: id, mainScroll }));
    if (window.matchMedia("(max-width:700px)").matches) requestAnimationFrame(() => {
      if (scroller) scroller.scrollTop = id ? 0 : mainScroll;
    });
  };
  const renderTurn = (turn: WorkTurn) => {
    const main = turn.session_id === view?.main_session_id;
    const head = main ? view : childQuery.data?.pages[0];
    const active = !nativeMode && head?.turns.some(item => item.turn_id === turn.turn_id) && ["running", "waiting_permission", "unknown"].includes(turn.status);
    return <Turn key={`${turn.session_id}:${turn.turn_id}`} turn={turn} agentId={agentId} online={online} separate={separate}
      sessions={sessions} expanded={saved.expanded} expand={expand} onChild={selectChild} refresh={refresh}
      activity={active} headUpdate={nativeMode ? 0 : main ? viewQuery.dataUpdatedAt : childQuery.dataUpdatedAt}
      focusToken={!nativeMode && focus?.session_id === turn.session_id && focus?.turn_id === turn.turn_id ? replyFocusToken : undefined} />;
  };
  const catalogMore = separate && <>
    {catalog.isLoading && <small role="status">{tr("正在加载工作记录…")}</small>}
    {catalog.isError && <p role="alert">{catalog.error.message}<button type="button" onClick={() => void catalog.refetch()}>{tr("重试")}</button></p>}
    {catalog.data && <button type="button" disabled={catalog.isFetching} onClick={() => void client.resetQueries({queryKey: catalogKey, exact: true})}>{tr("刷新目录")}</button>}
    {catalog.hasNextPage && <button type="button" disabled={catalog.isFetching} onClick={() => void catalog.fetchNextPage()}>{tr("加载更多")}</button>}
  </>;
  return <WorkNavigationContext.Provider value={{ returnUrl: `${location.pathname}?view=work`, beforeLeave: save, names, people }}>
    <div ref={root} className="im-work" data-testid="agent-work-panel">
      {viewQuery.isLoading ? <p role="status" className="im-work-state">{tr("正在加载工作记录…")}</p> : viewQuery.isError ? <div role="alert" className="im-work-state">{viewQuery.error.message}{!(viewQuery.error instanceof AgentExecutionDeletedError) && <button type="button" onClick={() => void viewQuery.refetch()}>{tr("重试")}</button>}</div> : view && <>
        <div className="im-work-toolbar">
          <div className="im-work-view-switch" role="tablist" aria-label="工作查看方式"><button role="tab" aria-selected={!nativeMode} onClick={showRecords}>{tr('工作记录')}</button><button role="tab" aria-selected={nativeMode} onClick={() => showNative(saved.selected || focus?.session_id || view.main_session_id)}>{tr('原生轨迹')}</button></div>
          {nativeMode && <label className="im-native-execution"><span>{tr('当前执行')}</span><select aria-label="当前执行" value={shownNative ?? ''} onChange={event => showNative(event.target.value)}>{view.main_session_id && <option value={view.main_session_id}>{tr('主 Agent')}</option>}{sessions.map(session => <option key={session.session_id} value={session.session_id}>{session.session_id === shownNative && activeNative?.base === nativeSession && activeNative.label ? activeNative.label : tr(sessionTitle(session))}</option>)}{shownNative && shownNative !== view.main_session_id && !sessions.some(session => session.session_id === shownNative) && <option value={shownNative}>{activeNative?.label || tr(sessionTitle(selected))}</option>}</select>{catalogMore}</label>}
          <div className="im-work-toolbar-status">{!nativeMode && <span>{tr("主 Agent")} · {statusLabel(online ? view.main_execution : "unknown")}</span>}{!online && <span className="im-work-error">{tr("节点离线")}</span>}</div>
        </div>
        {nativeMode && <AgentTrajectory key={nativeSelectionVersion} onActiveSessionChange={onActiveNative} rootSessionId={view.main_session_id} initialTitle={nativeSession === view.main_session_id ? tr('主 Agent') : tr(sessionTitle(sessions.find(item => item.session_id === nativeSession) ?? selected))} agentId={agentId} sessionId={nativeSession === view.main_session_id && !mainTurns.length ? null : nativeSession} positions={nativePositions.current} onBack={showRecords} />}
        <div hidden={nativeMode}>
        {messageId && (focusQuery.isError || focusQuery.data === null) && <p className="im-work-callout" role="status">{focusQuery.error instanceof AgentExecutionDeletedError ? focusQuery.error.message : tr("该回复的工作记录尚未同步或不可用。")}</p>}
        {focus && <button type="button" onClick={() => {
          const next = new URLSearchParams(location.search);
          next.delete('message_id');
          navigate({search: next.toString()});
          setSaved(current => ({...current, selected: null}));
          const scroller = root.current?.closest(".im-agent-panel");
          if (scroller) scroller.scrollTop = 0;
        }}>{tr("查看最新轮次")}</button>}
        {!online && <p className="im-work-callout" role="status">{tr("节点离线，正在显示已保存记录。活动执行状态未知，授权暂不可处理。")}</p>}
        {online && view.record_sync_state !== "current" && <p className="im-work-callout" role="status">{tr(view.record_sync_state === "catching_up" ? "工作记录正在补齐，当前显示已保存内容。" : "当前显示已保存记录，最新进度尚未确认。")}</p>}
        <div className="im-work-latest im-work-card"><Usage value={view.latest_main_usage} label="最近已报告的主上下文" />{view.main_execution === "running" && <small>{tr("新统计尚未报告时沿用最近轮次")}</small>}</div>
        <div className={`im-work-grid ${saved.selected ? "with-child" : ""}`}>
          <section className="im-work-trace"><header className="im-work-section-head"><h3>{tr("主 Agent")}</h3><small>{tr("最新轮次在前 · 轮次内部按实际顺序")}</small></header>
            {mainTurns.length || mainAnchors.length ? <WorkTurnList turns={mainTurns} anchors={mainAnchors} history={separate ? mainHistory : undefined} renderTurn={renderTurn} nextTurnId={viewQuery.data?.pages.at(-1)?.next_turn_id}
              earlier={viewQuery.hasNextPage ? {loading: viewQuery.isFetchingNextPage, load: () => void viewQuery.fetchNextPage()} : undefined} />
              : <p className="im-work-state">{tr("暂无工作记录。符合配置的新消息会进入收件箱。")}</p>}
          </section>
          {saved.selected && <aside className="im-work-child"><button className="im-work-back" onClick={() => selectChild(null)}>{tr("← 返回主轨迹")}</button><header><div><h3>{tr(sessionTitle(selected))}</h3><small>{tr(selected?.scope === "workflow" ? "Workflow 执行" : selected?.scope === "subagent" ? "子 Agent" : selected?.scope || "关联执行")} · {saved.selected}</small></div><button type="button" aria-label={tr("关闭子轨迹")} onClick={() => selectChild(null)}>×</button></header>
            <button type="button" onClick={() => showNative(saved.selected)}>{tr('查看原生轨迹')}</button>
            {childQuery.isError || metadata.isError ? <p role="alert">{tr("关联执行不可访问 ")}<button type="button" onClick={() => { void childQuery.refetch(); if (separate) void metadata.refetch(); }}>{tr("重试")}</button></p>
              : childTurns.length || childAnchors.length ? <WorkTurnList turns={childTurns} anchors={childAnchors} history={separate ? childHistory : undefined} renderTurn={renderTurn} nextTurnId={childQuery.data?.pages.at(-1)?.next_turn_id}
                earlier={childQuery.hasNextPage ? {loading: childQuery.isFetchingNextPage, load: () => void childQuery.fetchNextPage()} : undefined} />
              : childQuery.isLoading ? <p role="status">{tr("加载子轨迹…")}</p> : <p>{tr("尚未报告执行轮次")}</p>}
            {!childQuery.isError && !metadata.isError && <>
              {separate ? <SessionControls key={saved.selected} agentId={agentId} sessionId={saved.selected} title="执行记录" /> : <SessionFacts items={childQuery.data?.pages[0]?.control_items} />}
              <WorkOriginals key={`originals:${saved.selected}`} agentId={agentId} sessionId={saved.selected} />
            </>}
          </aside>}
        </div>
        {separate && view.main_session_id ? <SessionControls key={view.main_session_id} agentId={agentId} sessionId={view.main_session_id} title="控制记录" /> : <SessionFacts items={view.control_items} title="控制记录" />}
        {view.main_session_id && <WorkOriginals key={`originals:${view.main_session_id}`} agentId={agentId} sessionId={view.main_session_id} />}
        {(separate || sessions.length > 0) && <details className="im-work-other" onToggle={event => {if (event.target === event.currentTarget) setCatalogOpen(event.currentTarget.open);}}>
          <summary>{tr("关联执行")}{!separate && ` · ${sessions.length}`}</summary>
          {sessions.map(session => <button type="button" key={session.session_id} onClick={() => selectChild(session.session_id)}>{tr(sessionTitle(session))} <small>{session.session_id}</small></button>)}
          {catalogMore}
        </details>}
        </div>
      </>}
    </div>
  </WorkNavigationContext.Provider>;
}

function Turn({turn, agentId, online, sessions, expanded, expand, onChild, refresh, focusToken, separate, activity, headUpdate}: {
  turn: WorkTurn; agentId: string; online?: boolean; sessions: WorkSession[]; expanded: Record<string, boolean>;
  expand(key: string, open: boolean): void; onChild(id: string): void; refresh(): void; focusToken?: string;
  separate: boolean; activity?: boolean; headUpdate: number;
}) {
  const key = `${turn.session_id}:${turn.turn_id}`;
  const client = useQueryClient();
  const queryKey = ["agent-work", agentId, "items", turn.session_id, turn.turn_id, separate];
  const path = `${workSessionPath(agentId, turn.session_id)}/turns/${encodeURIComponent(turn.turn_id)}/items`;
  const [loaded, setLoaded] = useState(() => Boolean(client.getQueryData(queryKey)) || Boolean(turn.items_deferred && expanded[key]));
  const pages = useInfiniteQuery({
    queryKey,
    enabled: loaded, staleTime: separate ? Infinity : undefined,
    initialPageParam: String(turn.items.at(-1)?.seq ?? 0),
    queryFn: ({pageParam, signal}) => workRequest<WorkItemsPage>(`${path}?after_seq=${pageParam}${separate ? "&catalog=separate" : ""}`, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  useEffect(() => { if (turn.items_deferred && expanded[key]) setLoaded(true); }, [turn.items_deferred, expanded[key]]);
  const watermark = pages.data?.pages[0]?.revision;
  const changesKey = ["work-item-changes", agentId, turn.session_id, turn.turn_id];
  const changes = useQuery({
    queryKey: changesKey, enabled: false, retry: false,
    queryFn: async ({signal}) => {
      const previous = client.getQueryData<WorkItemsPage>(changesKey);
      const page = await workRequest<WorkItemsPage>(`${path}?catalog=separate&after_revision=${previous?.revision ?? watermark}`, signal);
      return {...page, items: [...new Map([...(previous?.items ?? []), ...page.items].map(item => [item.item_id, item])).values()]};
    },
  });
  const priorActivity = useRef(false);
  const refreshedAt = useRef(0);
  const changeRefetch = changes.refetch;
  useEffect(() => {
    if (!separate || !headUpdate || !expanded[key]) return;
    if (watermark === undefined) {
      if (activity) priorActivity.current = true;
      return;
    }
    if (refreshedAt.current === 0 && activity) {
      refreshedAt.current = headUpdate;
      priorActivity.current = true;
      return;
    }
    if (changes.isFetching || refreshedAt.current === headUpdate || (!activity && !priorActivity.current && !changes.data?.next_cursor)) return;
    refreshedAt.current = headUpdate;
    if (activity) priorActivity.current = true;
    void changeRefetch({cancelRefetch: false}).then(result => {
      if (!activity && !result.isError) priorActivity.current = false;
    });
  }, [activity, changes.data?.next_cursor, changes.isFetching, changeRefetch, expanded, headUpdate, key, separate, watermark]);
  const scrolledNavigation = useRef<string | null>(null);
  const focusReady = !turn.items_deferred || Boolean(pages.data) || pages.isError;
  useEffect(() => {
    if (!focusToken || !expanded[key] || !focusReady || scrolledNavigation.current === focusToken) return;
    // Deferred bodies create the scrollable height; scrolling the empty summary
    // can be a no-op and leave the target below the fold once its tools arrive.
    const frame = requestAnimationFrame(() => {
      document.getElementById(turnElementId(turn.session_id, turn.turn_id))?.scrollIntoView({block: 'start'});
      scrolledNavigation.current = focusToken;
    });
    return () => cancelAnimationFrame(frame);
  }, [focusToken, expanded[key], focusReady, turn.session_id, turn.turn_id]);
  const extra = pages.data?.pages.flatMap(page => page.items) ?? [];
  const cursor = pages.data ? pages.hasNextPage : turn.next_items_cursor;
  const byId = new Map<string, WorkItem>();
  for (const item of [...extra, ...turn.items, ...(separate ? changes.data?.items ?? [] : [])]) {
    if ((byId.get(item.item_id)?.revision ?? 0) <= (item.revision ?? 0)) byId.set(item.item_id, item);
  }
  const items = withVisibleReasoning([...byId.values()].sort((a, b) => a.seq - b.seq));
  const status = !online && ["running", "waiting_permission"].includes(turn.status) ? "unknown" : turn.status;
  const load = () => { if (loaded) void pages.fetchNextPage(); else setLoaded(true); };
  const seenBackgroundReturns = new Set<string>();
  const backgroundRows = (raw: unknown, itemKey: string) => !Array.isArray(raw) || raw.length === 0 ? null : <ul>{raw.map((entry, index) => {
    const value = obj(entry);
    const sourceKey = str(value.task_id) ? `${str(value.task_type)}:${str(value.task_id)}` : "";
    // Source sidecars accompany multiple assistant messages in the same turn.
    if (sourceKey && seenBackgroundReturns.has(sourceKey)) return null;
    if (sourceKey) seenBackgroundReturns.add(sourceKey);
    const childId = str(value.child_session_id);
    const agent = str(value.agent_id);
    const children = childId ? sessions.filter(s => s.session_id === childId) : sessions.filter(s => agent && s.child_agent_id === agent);
    const link = childId ? <WorkLink id={childId} session={children[0]} label="查看关联执行" onChild={onChild} />
      : separate && agent ? <LegacyWorkLinks agentId={agentId} filter={{child_agent_id: agent}} onChild={onChild} label="查看关联执行" />
      : children.map(child => <WorkLink key={child.session_id} id={child.session_id} session={child} label="查看关联执行" distinguish={children.length > 1} onChild={onChild} />);
    const backgroundKey = `${itemKey}:background:${str(value.task_id) || index}`;
    return <WorkBackground key={backgroundKey} value={value as unknown as BackgroundReturn} expanded={expanded[backgroundKey] ?? false} onExpandedChange={open => expand(backgroundKey, open)} detailFooter={link} />;
  })}</ul>;
  return <details id={turnElementId(turn.session_id, turn.turn_id)} className="im-work-turn" open={expanded[key] ?? false} onToggle={event => { if (event.target === event.currentTarget) { expand(key, event.currentTarget.open); if (event.currentTarget.open && turn.items_deferred) setLoaded(true); } }}>
    <summary><strong>{tr(turnTitle(separate ? {...turn, items} : turn))}</strong><div className="im-work-turn-summary-meta"><span>{turn.started_at ? new Date(turn.started_at).toLocaleTimeString(i18n.language, {hour12:false}) : tr("时间未报告")}{turn.finished_at ? ` — ${new Date(turn.finished_at).toLocaleTimeString(i18n.language, {hour12:false})}` : ""}</span>{(!separate || pages.data) && <span>{turn.tool_count ?? items.filter(item => item.kind === "tool").length}{turn.tool_count === undefined && cursor ? "+" : ""} {tr("次工具")}</span>}<span className={`im-work-status-label ${status}`}>{statusLabel(status)}</span></div></summary>
    <div className="im-work-turn-body"><div className="im-work-turn-meta"><code>{turn.turn_id}</code><span>{turn.model_id || tr("模型未报告")}</span></div>
      {turn.items_deferred && pages.isLoading && <p role="status">{tr("正在加载工作记录…")}</p>}
      <ul className="im-work-items">{items.map(item => {
        const p = item.payload;
        if (["message", "message_delta", "text_delta", "assistant_message"].includes(item.kind) && !str(p.reasoning_content) && !str(p.text) && !str(p.content) && !str(p.delta) && !str(p.source_session_id) && !(Array.isArray(p.background_returns) && p.background_returns.length)) return null;
        const itemKey = `${key}:${item.item_id}`;
        if (item.kind === "tool") {
          const call = { ...p, input: p.input ?? p.arguments ?? {}, output: p.output ?? p.summary } as unknown as ToolCall;
          const childId = str(p.child_session_id) || str(obj(p.detail).child_session_id);
          const callId = str(p.id) || str(p.call_id) || str(p.tool_call_id);
          const agent = str(obj(p.detail).agent_id) || str(obj(p.input ?? p.arguments).agent_id);
          const exact = sessions.filter(s => callId && s.parent_session_id === turn.session_id && s.parent_tool_call_id === callId);
          const children = childId ? sessions.filter(s => s.session_id === childId) : exact.length ? exact
            : sessions.filter(s => agent && s.parent_session_id === turn.session_id && s.child_agent_id === agent);
          const filter = {parent_session_id: turn.session_id, ...(callId ? {tool_call_id: callId} : {}), ...(agent ? {child_agent_id: agent} : {})};
          const delegation = item.has_exact_child || agent || /agent|workflow/.test(call.name ?? "");
          const link = childId ? <WorkLink id={childId} session={children[0]} label="查看子执行" onChild={onChild} />
            : separate && delegation && (callId || agent) ? <LegacyWorkLinks agentId={agentId} filter={filter} onChild={onChild} label="查看子执行" />
            : children.map(child => <WorkLink key={child.session_id} id={child.session_id} session={child} label="查看子执行" distinguish={children.length > 1} onChild={onChild} />);
          // An exact link can arrive after this historical item was loaded.
          const lateLink = separate && !childId && !delegation && callId
            ? <LegacyWorkLinks agentId={agentId} filter={{parent_session_id: turn.session_id, tool_call_id: callId}} onChild={onChild} label="查看子执行" />
            : null;
          return <WorkTool key={item.item_id} call={call} expanded={expanded[itemKey] ?? false} onExpandedChange={open => expand(itemKey, open)} detailFooter={<><WorkFacts facts={p.work_facts} />{lateLink}</>} childLink={link} />;
        }
        if (item.kind === "permission") return <li key={item.item_id}><PermissionCard request={p as unknown as PermissionRequest} endpoint={`${workBase(agentId)}/permissions/${encodeURIComponent(str(p.request_id))}`} disabled={!online} onResolved={refresh} /></li>;
        if (["message", "message_delta", "text_delta", "assistant_message"].includes(item.kind)) return <li className="im-work-body" key={item.item_id}>{str(p.reasoning_content) && <details open={expanded[itemKey] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(itemKey, event.currentTarget.open); }}><summary>{tr("思考")}</summary><p className="whitespace-pre-wrap">{str(p.reasoning_content)}</p></details>}{(str(p.text) || str(p.content) || str(p.delta) || str(p.source_session_id)) && <div className="im-work-assistant"><header className="im-work-message-head"><strong>{tr(p.source_kind === "subagent-settled" ? "子执行返回" : p.source_kind === "agent-message" ? "Agent 消息" : "Agent 正文")}</strong>{str(p.source_session_id) && <button type="button" className="im-work-child-link" onClick={() => onChild(str(p.source_session_id))}>{tr("查看关联执行")}<span aria-hidden="true">↗</span></button>}</header><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: TaskGraphLink }}>{str(p.text) || str(p.content) || str(p.delta)}</ReactMarkdown></div>}{backgroundRows(p.background_returns, itemKey)}</li>;
        if (["thinking", "thinking_delta", "reasoning"].includes(item.kind)) return <li key={item.item_id}><details open={expanded[itemKey] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(itemKey,event.currentTarget.open); }}><summary>{tr("思考")}</summary><p className="whitespace-pre-wrap">{str(p.text) || str(p.content) || str(p.reasoning_content)}</p></details></li>;
        if (item.kind === "cron_delivery" || item.kind === "cron_trigger") return <li key={item.item_id}><SessionFacts items={[item]} /></li>;
        if (item.kind === "injection_consumed" && (str(p.source_session_id) || Array.isArray(p.background_returns) && p.background_returns.length > 0)) return <li key={item.item_id}>{str(p.source_session_id) && <WorkLink id={str(p.source_session_id)} label="查看关联执行" onChild={onChild} />}{backgroundRows(p.background_returns, itemKey)}</li>;
        if (item.kind === "background_return") return <li key={item.item_id}>{backgroundRows([p], itemKey)}</li>;
        if (item.kind === "injection_consumed" && Number(p.user_message_count) > 0) return <li className="im-work-assistant" key={item.item_id}>{tr("运行中收到补充输入")}</li>;
        if (item.kind === "recording_degraded") return <li className="im-work-callout" key={item.item_id}>{tr("工作记录存在缺口")}</li>;
        // Lifecycle/configuration events remain in the journal, not the user-facing trace.
        return null;
      })}</ul>
      {turn.error?.message && <p className="im-work-error">{turn.error.code && `${turn.error.code}: `}{turn.error.message}</p>}
      {expanded[key] && <WorkOriginals agentId={agentId} sessionId={turn.session_id} turnId={turn.turn_id} />}
      <footer className="im-work-turn-footer"><Usage value={turn.usage} label="本轮统计" />{typeof turn.elapsed_ms === "number" && <small>{formatDuration(turn.elapsed_ms)}</small>}</footer>
      {separate && (changes.data?.next_cursor || changes.isError) && <button type="button" disabled={changes.isFetching} onClick={() => void changes.refetch()}>{tr(changes.isError ? "重试" : "加载更多更新")}</button>}
      {cursor && <button type="button" disabled={pages.isFetching} onClick={load}>{tr("加载更多过程")}</button>}{pages.error && <p role="alert">{pages.error.message}<button type="button" onClick={() => void pages.refetch()}>{tr("重试")}</button></p>}
    </div>
  </details>;
}

function WorkFacts({ facts }: { facts: unknown }) {
  if (!Array.isArray(facts)) return null;
  return <>{facts.filter(raw => obj(raw).type !== "inbox_read_committed").map((raw, index) => { const fact = obj(raw); const target = str(fact.conversation_id) || str(fact.target); const refs = Array.isArray(fact.source_refs) ? fact.source_refs.map(obj) : [];
    return <div key={index} className="im-work-tool-fact">
      <p>{tr(fact.type === "inbox_read_committed" ? "本页正文已持久摄取" : fact.type === "draft_withheld" ? "原草稿 · 未发送" : "实际投递确认")}</p>
      {fact.type === "draft_withheld" && <pre className="chat-tool-call-pre">{str(fact.text) || str(fact.draft)}</pre>}
      {target && <WorkThreadLink conversationId={target} messageId={str(fact.message_id)}>{tr("目标聊天")}{fact.message_id ? ` · ${tr("原消息")}` : ""}</WorkThreadLink>}
      {refs.map((ref, i) => <WorkThreadLink key={i} conversationId={str(ref.conversation_id)} messageId={str(ref.message_id)}>{str(ref.name) || tr("新消息")}</WorkThreadLink>)}
    </div>;
  })}</>;
}
