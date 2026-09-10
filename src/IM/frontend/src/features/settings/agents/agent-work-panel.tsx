import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { subscribeUserStream } from "../../../realtime/user-stream";
import type { BackgroundReturn, PermissionRequest, TokenUsage, ToolCall } from "../../chat/chat-types";
import { formatDuration } from "../../chat/components/tool-calls-panel";
import { WorkTool, WorkBackground, WorkUsage, withVisibleReasoning } from "./agent-work-presenters";
import { tr } from "./agent-work-text";
import { i18n, useTranslation } from "../../../i18n";
import { PermissionCard } from "../../chat/components/permission-card";
import { WorkNavigationContext, WorkThreadLink } from "../../chat/components/work-thread-link";
import { workBase, workRequest, type WorkItem, type WorkSession, type WorkTurn, type WorkTurnPage, type WorkView } from "./agent-work-api";
import "./agent-work.css";

type SavedView = { selected: string | null; expanded: Record<string, boolean>; scroll: number; mainScroll?: number; focus?: string };
const str = (value: unknown) => typeof value === "string" ? value : "";
const obj = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const statusLabel = (status: string) => tr({ running: "运行中", waiting_permission: "等待授权", completed: "已完成", failed: "失败", interrupted: "已中断", unknown: "状态未知", idle: "空闲" }[status] ?? status);

function readSaved(key: string): SavedView {
  try { return JSON.parse(sessionStorage.getItem(key) ?? "null") ?? { selected: null, expanded: {}, scroll: 0 }; }
  catch { return { selected: null, expanded: {}, scroll: 0 }; }
}

const Usage = WorkUsage;

function turnTitle(turn: WorkTurn) {
  const trigger = turn.trigger ?? {};
  const origin = typeof turn.origin === "string" ? turn.origin : str(turn.origin?.kind);
  const type = str(trigger.kind) || origin;
  if (type === "inbox" || type === "global_inbox") return "Inbox 唤醒";
  if (type === "heartbeat") return "Heartbeat";
  if (turn.scope === "cron" || type === "cron") return cronTitle(trigger.source, turn.job_id);
  if (turn.scope === "workflow") return "Workflow 执行";
  if (type === "background_task") {
    const returns = turn.items.flatMap(item => Array.isArray(item.payload.background_returns) ? item.payload.background_returns.map(obj) : item.kind === "background_return" ? [item.payload] : []);
    const taskType = str(trigger.task_type) || str(returns[0]?.task_type);
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

/** Durable main/child timeline. Visual state survives a real Chat navigation. */
export function AgentWorkPanel({ agentId }: { agentId: string }) {
  useTranslation();
  const location = useLocation();
  const client = useQueryClient();
  const namesQuery = useQuery({ queryKey: ["work-conversation-names"], queryFn: () => workRequest<{items: {id: string; title: string; participants?: {id: string; user_id?: string; display_name?: string}[]}[]}>("/im/v1/conversations") });
  const people = Object.fromEntries((namesQuery.data?.items ?? []).flatMap(c => (c.participants ?? []).flatMap(p => p.display_name ? [[p.id, p.display_name], ...(p.user_id ? [[p.user_id, p.display_name]] : [])] : [])));
  const names = Object.fromEntries((namesQuery.data?.items ?? []).map(c => [c.id, c.title]));
  const storageKey = `agent-work:${agentId}`;
  const [saved, setSaved] = useState(() => readSaved(storageKey));
  const root = useRef<HTMLDivElement>(null);
  const restored = useRef(false);
  const viewQuery = useInfiniteQuery({ queryKey: ["agent-work", agentId, "main"], initialPageParam: "", queryFn: ({ pageParam }) => workRequest<WorkView>(`${workBase(agentId)}${pageParam ? `?before_turn=${encodeURIComponent(pageParam)}` : ""}`), getNextPageParam: page => page.next_cursor ?? undefined });
  const view = viewQuery.data?.pages[0];
  const childQuery = useInfiniteQuery({ queryKey: ["agent-work", agentId, "session", saved.selected], initialPageParam: "", enabled: Boolean(saved.selected), queryFn: ({ pageParam }) => workRequest<WorkTurnPage>(`${workBase(agentId)}/sessions/${encodeURIComponent(saved.selected!)}/turns${pageParam ? `?before_turn=${encodeURIComponent(pageParam)}` : ""}`), getNextPageParam: page => page.next_cursor ?? undefined });
  const selected = view?.other_executions.find(s => s.session_id === saved.selected);
  const online = view?.node_connection_state === "online";
  const mainTurns = viewQuery.data?.pages.flatMap(p => p.turns) ?? [];
  const childTurns = childQuery.data?.pages.flatMap(p => p.turns) ?? [];
  const save = () => {
    const scroll = root.current?.closest(".im-agent-panel")?.scrollTop ?? 0;
    sessionStorage.setItem(storageKey, JSON.stringify({ ...saved, scroll, focus: document.activeElement?.id }));
  };
  useEffect(() => { sessionStorage.setItem(storageKey, JSON.stringify(saved)); }, [saved, storageKey]);
  useEffect(() => subscribeUserStream({ onEvent: event => {
    if ((event.eventType === "agent.work.updated" || event.eventType === "agent.status_changed") && event.payload.agent_id === agentId) void client.invalidateQueries({ queryKey: ["agent-work", agentId] });
  }, onRecovery: async () => { await client.invalidateQueries({ queryKey: ["agent-work", agentId] }); } }), [agentId, client]);
  useEffect(() => {
    if (!view || restored.current) return;
    restored.current = true;
    const frame = requestAnimationFrame(() => {
      const scroller = root.current?.closest(".im-agent-panel");
      if (scroller) scroller.scrollTop = saved.scroll;
      if (saved.focus) document.getElementById(saved.focus)?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [view, saved]);
  const expand = (key: string, open: boolean) => setSaved(current => ({ ...current, expanded: { ...current.expanded, [key]: open } }));
  const refresh = () => { void client.invalidateQueries({ queryKey: ["agent-work", agentId] }); };
  const selectChild = (id: string | null) => {
    const scroller = root.current?.closest(".im-agent-panel");
    const mainScroll = saved.selected ? saved.mainScroll ?? 0 : scroller?.scrollTop ?? 0;
    setSaved(current => ({ ...current, selected: id, mainScroll }));
    if (window.matchMedia("(max-width:700px)").matches) requestAnimationFrame(() => {
      if (scroller) scroller.scrollTop = id ? 0 : mainScroll;
    });
  };
  const renderTurn = (turn: WorkTurn) => <Turn key={`${turn.session_id}:${turn.turn_id}`} turn={turn} agentId={agentId} online={online} sessions={view?.other_executions ?? []} expanded={saved.expanded} expand={expand} onChild={selectChild} refresh={refresh} />;
  return <WorkNavigationContext.Provider value={{ returnUrl: `${location.pathname}?view=work`, beforeLeave: save, names, people }}>
    <div ref={root} className="im-work" data-testid="agent-work-panel">
      {viewQuery.isLoading ? <p role="status" className="im-work-state">{tr("正在加载工作记录…")}</p> : viewQuery.isError ? <div role="alert" className="im-work-state">{viewQuery.error.message}<button type="button" onClick={() => void viewQuery.refetch()}>{tr("重试")}</button></div> : view && <>
        <div className="im-work-status im-work-card"><div><h2>{tr("工作")}<small>{tr("全局 · 实验")}</small></h2><p>{tr("跨聊天的主工作轨迹及关联执行")}</p></div><div className="im-work-badges"><span className="im-work-status-label">{tr("主 Agent")} · {statusLabel(online ? view.main_execution : "unknown")}</span><span className="im-work-status-label">{tr(online ? "节点在线" : "节点离线")}</span></div></div>
        {!online && <p className="im-work-callout" role="status">{tr("节点离线，正在显示已保存记录。活动执行状态未知，授权暂不可处理。")}</p>}
        <div className="im-work-latest im-work-card"><Usage value={view.latest_main_usage} label="最近已报告的主上下文" />{view.main_execution === "running" && <small>{tr("新统计尚未报告时沿用最近轮次")}</small>}</div>
        <div className={`im-work-grid ${saved.selected ? "with-child" : ""}`}>
          <section className="im-work-trace"><header className="im-work-section-head"><h3>{tr("主 Agent")}</h3><small>{tr("最新轮次在前 · 轮次内部按实际顺序")}</small></header>
            {mainTurns.length ? mainTurns.map(renderTurn) : <p className="im-work-state">{tr("暂无工作记录。符合配置的新消息会进入收件箱。")}</p>}
            {viewQuery.hasNextPage && <button type="button" disabled={viewQuery.isFetchingNextPage} onClick={() => void viewQuery.fetchNextPage()}>{tr("更早轮次")}</button>}
          </section>
          {saved.selected && <aside className="im-work-child"><button className="im-work-back" onClick={() => selectChild(null)}>{tr("← 返回主轨迹")}</button><header><div><h3>{tr(sessionTitle(selected))}</h3><small>{tr(selected?.scope === "workflow" ? "Workflow 执行" : selected?.scope === "subagent" ? "子执行" : selected?.scope || "关联执行")} · {saved.selected}</small></div><button type="button" aria-label={tr("关闭子轨迹")} onClick={() => selectChild(null)}>×</button></header>
            {childQuery.isLoading ? <p role="status">{tr("加载子轨迹…")}</p> : childQuery.isError ? <p role="alert">{tr("关联执行不可访问 ")}<button type="button" onClick={() => void childQuery.refetch()}>{tr("重试")}</button></p> : childTurns.length ? childTurns.map(renderTurn) : <p>{tr("尚未报告执行轮次")}</p>}
            <SessionFacts items={childQuery.data?.pages[0]?.control_items} />
            {childQuery.hasNextPage && <button type="button" disabled={childQuery.isFetchingNextPage} onClick={() => void childQuery.fetchNextPage()}>{tr("更早轮次")}</button>}
          </aside>}
        </div>
        <SessionFacts items={view.control_items} title={tr("控制记录")} />
        {view.other_executions.length > 0 && <details className="im-work-other"><summary>{tr("关联执行 · ")}{view.other_executions.length}</summary>{view.other_executions.map(session => <button type="button" key={session.session_id} onClick={() => selectChild(session.session_id)}>{tr(sessionTitle(session))} <small>{session.session_id}</small></button>)}</details>}
      </>}
    </div>
  </WorkNavigationContext.Provider>;
}

function Turn({ turn, agentId, online, sessions, expanded, expand, onChild, refresh }: { turn: WorkTurn; agentId: string; online?: boolean; sessions: WorkSession[]; expanded: Record<string, boolean>; expand(key: string, open: boolean): void; onChild(id: string): void; refresh(): void }) {
  const key = `${turn.session_id}:${turn.turn_id}`;
  const client = useQueryClient();
  const queryKey = ["agent-work", agentId, "items", turn.session_id, turn.turn_id];
  const [loaded, setLoaded] = useState(() => Boolean(client.getQueryData(queryKey)));
  const pages = useInfiniteQuery({
    queryKey,
    enabled: loaded,
    initialPageParam: String(turn.items.at(-1)?.seq ?? 0),
    queryFn: ({pageParam}) => workRequest<{items: WorkItem[]; next_cursor: string | null}>(`${workBase(agentId)}/sessions/${encodeURIComponent(turn.session_id)}/turns/${encodeURIComponent(turn.turn_id)}/items?after_seq=${pageParam}`),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  const extra = pages.data?.pages.flatMap(page => page.items) ?? [];
  const cursor = pages.data ? pages.hasNextPage : turn.next_items_cursor;
  const items = withVisibleReasoning([...new Map([...extra, ...turn.items].map(item => [item.item_id, item])).values()].sort((a,b) => a.seq-b.seq));
  const status = !online && ["running", "waiting_permission"].includes(turn.status) ? "unknown" : turn.status;
  const load = () => { if (loaded) void pages.fetchNextPage(); else setLoaded(true); };
  const seenBackgroundReturns = new Set<string>();
  const backgroundRows = (raw: unknown, itemKey: string) => !Array.isArray(raw) || raw.length === 0 ? null : <ul>{raw.map((entry, index) => {
    const value = obj(entry);
    const sourceKey = str(value.task_id) ? `${str(value.task_type)}:${str(value.task_id)}` : "";
    // Source sidecars accompany multiple assistant messages in the same turn.
    if (sourceKey && seenBackgroundReturns.has(sourceKey)) return null;
    if (sourceKey) seenBackgroundReturns.add(sourceKey);
    const child = sessions.find(session => session.session_id === value.child_session_id || (session.child_agent_id && session.child_agent_id === value.agent_id));
    const backgroundKey = `${itemKey}:background:${str(value.task_id) || index}`;
    return <WorkBackground key={backgroundKey} value={value as unknown as BackgroundReturn} expanded={expanded[backgroundKey] ?? false} onExpandedChange={open => expand(backgroundKey, open)} detailFooter={child && <button type="button" className="im-work-child-link" onClick={() => onChild(child.session_id)}>{tr("查看关联执行")} · {child.description || child.child_agent_id || child.session_id}</button>} />;
  })}</ul>;
  return <details className="im-work-turn" open={expanded[key] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(key, event.currentTarget.open); }}>
    <summary><strong>{tr(turnTitle(turn))}</strong><div className="im-work-turn-summary-meta"><span>{turn.started_at ? new Date(turn.started_at).toLocaleTimeString(i18n.language, {hour12:false}) : tr("时间未报告")}{turn.finished_at ? ` — ${new Date(turn.finished_at).toLocaleTimeString(i18n.language, {hour12:false})}` : ""}</span><span>{items.filter(item => item.kind === "tool").length}{cursor ? "+" : ""} {tr("次工具")}</span><span className={`im-work-status-label ${status}`}>{statusLabel(status)}</span></div></summary>
    <div className="im-work-turn-body"><div className="im-work-turn-meta"><code>{turn.turn_id}</code><span>{turn.model_id || tr("模型未报告")}</span></div>
      <ul className="im-work-items">{items.map(item => {
        const p = item.payload;
        if (["message", "message_delta", "text_delta", "assistant_message"].includes(item.kind) && !str(p.reasoning_content) && !str(p.text) && !str(p.content) && !str(p.delta) && !(Array.isArray(p.background_returns) && p.background_returns.length)) return null;
        const itemKey = `${key}:${item.item_id}`;
        if (item.kind === "tool") {
          const call = { ...p, input: p.input ?? p.arguments ?? {}, output: p.output ?? p.summary } as unknown as ToolCall;
          const childId = str(p.child_session_id) || str(obj(p.detail).child_session_id);
          const child = sessions.find(s => s.session_id === childId || (s.parent_session_id === turn.session_id && (s.parent_tool_call_id === call.id || (s.child_agent_id && s.child_agent_id === (obj(p.detail).agent_id ?? obj(p.input ?? p.arguments).agent_id)))));
          return <WorkTool key={item.item_id} call={call} expanded={expanded[itemKey] ?? false} onExpandedChange={open => expand(itemKey, open)} detailFooter={<WorkFacts facts={p.work_facts} />} childLink={child && <button id={`work-child-${child.session_id}`} type="button" className="im-work-child-link" onClick={() => onChild(child.session_id)}>{tr("查看子执行")} · {child.description || child.child_agent_id || child.session_id}</button>} />;
        }
        if (item.kind === "permission") return <li key={item.item_id}><PermissionCard request={p as unknown as PermissionRequest} endpoint={`${workBase(agentId)}/permissions/${encodeURIComponent(str(p.request_id))}`} disabled={!online} onResolved={refresh} /></li>;
        if (["message", "message_delta", "text_delta", "assistant_message"].includes(item.kind)) return <li className="im-work-body" key={item.item_id}>{str(p.reasoning_content) && <details open={expanded[itemKey] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(itemKey, event.currentTarget.open); }}><summary>{tr("思考")}</summary><p className="whitespace-pre-wrap">{str(p.reasoning_content)}</p></details>}{(str(p.text) || str(p.content) || str(p.delta)) && <div className="im-work-assistant"><strong>{tr("Agent 正文")}</strong><ReactMarkdown remarkPlugins={[remarkGfm]}>{str(p.text) || str(p.content) || str(p.delta)}</ReactMarkdown></div>}{backgroundRows(p.background_returns, itemKey)}</li>;
        if (["thinking", "thinking_delta", "reasoning"].includes(item.kind)) return <li key={item.item_id}><details open={expanded[itemKey] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(itemKey,event.currentTarget.open); }}><summary>{tr("思考")}</summary><p className="whitespace-pre-wrap">{str(p.text) || str(p.content) || str(p.reasoning_content)}</p></details></li>;
        if (item.kind === "cron_delivery" || item.kind === "cron_trigger") return <li key={item.item_id}><SessionFacts items={[item]} /></li>;
        if (item.kind === "injection_consumed" && Array.isArray(p.background_returns) && p.background_returns.length > 0) return <li key={item.item_id}>{backgroundRows(p.background_returns, itemKey)}</li>;
        if (item.kind === "background_return") return <li key={item.item_id}>{backgroundRows([p], itemKey)}</li>;
        if (item.kind === "injection_consumed" && Number(p.user_message_count) > 0) return <li className="im-work-assistant" key={item.item_id}>{tr("运行中收到补充输入")}</li>;
        if (item.kind === "recording_degraded") return <li className="im-work-callout" key={item.item_id}>{tr("工作记录存在缺口")}</li>;
        // Lifecycle/configuration events remain in the journal, not the user-facing trace.
        return null;
      })}</ul>
      <footer className="im-work-turn-footer"><Usage value={turn.usage} label="本轮统计" />{typeof turn.elapsed_ms === "number" && <small>{formatDuration(turn.elapsed_ms)}</small>}</footer>
      {cursor && <button type="button" disabled={pages.isFetching} onClick={load}>{tr("加载更多过程")}</button>}{pages.error && <p role="alert">{pages.error.message}<button type="button" onClick={() => void pages.refetch()}>{tr("重试")}</button></p>}
    </div>
  </details>;
}

function WorkFacts({ facts }: { facts: unknown }) {
  if (!Array.isArray(facts)) return null;
  return <>{facts.map((raw, index) => { const fact = obj(raw); const target = str(fact.conversation_id) || str(fact.target); const refs = Array.isArray(fact.source_refs) ? fact.source_refs.map(obj) : [];
    return <div key={index} className="im-work-tool-fact">
      <p>{tr(fact.type === "inbox_read_committed" ? "本页正文已持久摄取" : fact.type === "draft_withheld" ? "原草稿 · 未发送" : "实际投递确认")}</p>
      {fact.type === "draft_withheld" && <pre className="chat-tool-call-pre">{str(fact.text) || str(fact.draft)}</pre>}
      {target && <WorkThreadLink conversationId={target} messageId={str(fact.message_id)}>{tr("目标聊天")}{fact.message_id ? ` · ${tr("原消息")}` : ""}</WorkThreadLink>}
      {refs.map((ref, i) => <WorkThreadLink key={i} conversationId={str(ref.conversation_id)} messageId={str(ref.message_id)}>{str(ref.name) || tr("新消息")}</WorkThreadLink>)}
    </div>;
  })}</>;
}
