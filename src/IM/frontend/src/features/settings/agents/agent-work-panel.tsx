import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { subscribeUserStream } from "../../../realtime/user-stream";
import type { BackgroundReturn, PermissionRequest, TokenUsage, ToolCall } from "../../chat/chat-types";
import { BackgroundReturnRow, ToolCallRow, formatDuration } from "../../chat/components/tool-calls-panel";
import { TokenChip } from "../../chat/components/token-chip";
import { PermissionCard } from "../../chat/components/permission-card";
import { WorkNavigationContext, WorkThreadLink } from "../../chat/components/work-thread-link";
import { workBase, workRequest, type WorkItem, type WorkSession, type WorkTurn, type WorkTurnPage, type WorkView } from "./agent-work-api";
import "./agent-work.css";

type SavedView = { selected: string | null; expanded: Record<string, boolean>; scroll: number; focus?: string };
const str = (value: unknown) => typeof value === "string" ? value : "";
const obj = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const statusLabel = (status: string) => ({ running: "运行中", waiting_permission: "等待授权", completed: "已完成", failed: "失败", interrupted: "已中断", unknown: "状态未知", idle: "空闲" }[status] ?? status);

function readSaved(key: string): SavedView {
  try { return JSON.parse(sessionStorage.getItem(key) ?? "null") ?? { selected: null, expanded: {}, scroll: 0 }; }
  catch { return { selected: null, expanded: {}, scroll: 0 }; }
}

function Usage({ value }: { value: Partial<TokenUsage> | null }) {
  if (typeof value?.context_used !== "number" || typeof value?.output !== "number") return <span className="im-work-muted">Token 未报告</span>;
  const usage = { ...value, context_used: value.context_used, output: value.output, total: value.total ?? value.context_used + value.output, context_window: value.context_window ?? 0 } as TokenUsage;
  return <div><TokenChip usage={usage} workAccounting />{!value.context_window && <small className="im-work-muted">上下文窗口未报告</small>}</div>;
}

function turnTitle(turn: WorkTurn) {
  const trigger = turn.trigger ?? {};
  const origin = typeof turn.origin === "string" ? turn.origin : str(turn.origin?.kind);
  const type = str(trigger.kind) || origin;
  if (type === "inbox" || type === "global_inbox") return "收件箱通知";
  if (type === "heartbeat") return "Heartbeat";
  if (turn.scope === "cron" || type === "cron") return cronTitle(trigger.source, turn.job_id);
  if (turn.scope === "workflow") return "Workflow 执行";
  if (type === "background_task") return `后台返回${trigger.task_type ? ` · ${str(trigger.task_type)}` : ""}`;
  return type || "执行轮次";
}

function cronTitle(trigger: unknown, jobId?: string) {
  const title = trigger === "manual" ? "Cron · 手动执行" : trigger === "scheduled" ? "Cron · 定时执行" : "Cron";
  return jobId ? `${title} · ${jobId}` : title;
}

function sessionTitle(session?: WorkSession) {
  if (session?.scope === "cron") return cronTitle(session.trigger, session.job_id);
  if (session?.scope === "workflow") return "Workflow 执行";
  return session?.description || session?.title || "关联执行";
}

function SessionFacts({ items, title = "执行记录" }: { items?: WorkItem[]; title?: string }) {
  if (!items?.length) return null;
  return <details className="im-work-other"><summary>{title}</summary>{items.map(item => {
    const p = item.payload;
    return <div key={item.item_id}>
      <strong>{item.kind === "cron_delivery" ? "Cron 实际投递" : item.kind === "cron_trigger" ? cronTitle(p.trigger, str(p.job_id)) : str(p.command) || item.kind}</strong>
      {item.observed_at && <small className="im-work-muted"> · {new Date(item.observed_at).toLocaleString()}</small>}
      {item.kind === "cron_delivery" && str(p.conversation_id) && <div><WorkThreadLink conversationId={str(p.conversation_id)} messageId={str(p.message_id)}>投递聊天 · 原消息</WorkThreadLink><small className="im-work-muted"> · {str(p.conversation_id)}</small></div>}
      <pre className="chat-tool-call-pre">{str(p.text) || str(p.error) || str(p.model) || JSON.stringify(p, null, 2)}</pre>
    </div>;
  })}</details>;
}

/** Durable main/child timeline. Visual state survives a real Chat navigation. */
export function AgentWorkPanel({ agentId }: { agentId: string }) {
  const location = useLocation();
  const client = useQueryClient();
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
    const scroll = root.current?.closest(".im-agent-detail-body")?.scrollTop ?? 0;
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
      const scroller = root.current?.closest(".im-agent-detail-body");
      if (scroller) scroller.scrollTop = saved.scroll;
      if (saved.focus) document.getElementById(saved.focus)?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [view, saved]);
  const expand = (key: string, open: boolean) => setSaved(current => ({ ...current, expanded: { ...current.expanded, [key]: open } }));
  const refresh = () => { void client.invalidateQueries({ queryKey: ["agent-work", agentId] }); };
  const renderTurn = (turn: WorkTurn) => <Turn key={`${turn.session_id}:${turn.turn_id}`} turn={turn} agentId={agentId} online={online} sessions={view?.other_executions ?? []} expanded={saved.expanded} expand={expand} onChild={id => setSaved(current => ({ ...current, selected: id }))} refresh={refresh} />;
  return <WorkNavigationContext.Provider value={{ returnUrl: `${location.pathname}?view=work`, beforeLeave: save }}>
    <div ref={root} className="im-work" data-testid="agent-work-panel">
      {viewQuery.isLoading ? <p role="status" className="im-work-state">正在加载工作记录…</p> : viewQuery.isError ? <div role="alert" className="im-work-state">{viewQuery.error.message}<button type="button" onClick={() => void viewQuery.refetch()}>重试</button></div> : view && <>
        <div className="im-work-status"><strong>主 Agent · {statusLabel(view.main_execution)}</strong><span className="im-work-muted">{online ? "节点在线" : "节点离线"}</span></div>
        {!online && <p className="im-work-callout" role="status">节点离线，正在显示已保存记录。活动执行状态未知，授权暂不可处理。</p>}
        <div className="im-work-latest"><span>最近已报告的主上下文{view.latest_main_usage?.model_id ? ` · ${view.latest_main_usage.model_id}` : ""}</span><Usage value={view.latest_main_usage} />{view.main_execution === "running" && <small>新统计尚未报告时沿用最近轮次</small>}</div>
        <div className={`im-work-grid ${saved.selected ? "with-child" : ""}`}>
          <section className="im-work-trace"><h3>主工作轨迹</h3>
            {mainTurns.length ? mainTurns.map(renderTurn) : <p className="im-work-state">暂无工作记录。符合配置的新消息会进入收件箱。</p>}
            {viewQuery.hasNextPage && <button type="button" disabled={viewQuery.isFetchingNextPage} onClick={() => void viewQuery.fetchNextPage()}>更早轮次</button>}
          </section>
          {saved.selected && <aside className="im-work-child"><header><div><h3>{sessionTitle(selected)}</h3><small>{selected?.scope === "workflow" ? "Workflow 执行" : selected?.scope} · {saved.selected}</small></div><button type="button" aria-label="关闭子轨迹" onClick={() => setSaved(current => ({ ...current, selected: null }))}>×</button></header>
            {childQuery.isLoading ? <p role="status">加载子轨迹…</p> : childQuery.isError ? <p role="alert">关联执行不可访问 <button type="button" onClick={() => void childQuery.refetch()}>重试</button></p> : childTurns.length ? childTurns.map(renderTurn) : <p>尚未报告执行轮次</p>}
            <SessionFacts items={childQuery.data?.pages[0]?.control_items} />
            {childQuery.hasNextPage && <button type="button" disabled={childQuery.isFetchingNextPage} onClick={() => void childQuery.fetchNextPage()}>更早轮次</button>}
          </aside>}
        </div>
        <SessionFacts items={view.control_items} title="控制记录" />
        {view.other_executions.length > 0 && <details className="im-work-other"><summary>其他执行与关联 Session · {view.other_executions.length}</summary>{view.other_executions.map(session => <button type="button" key={session.session_id} onClick={() => setSaved(current => ({ ...current, selected: session.session_id }))}>{sessionTitle(session)} <small>{session.session_id}</small></button>)}</details>}
      </>}
    </div>
  </WorkNavigationContext.Provider>;
}

function Turn({ turn, agentId, online, sessions, expanded, expand, onChild, refresh }: { turn: WorkTurn; agentId: string; online?: boolean; sessions: WorkSession[]; expanded: Record<string, boolean>; expand(key: string, open: boolean): void; onChild(id: string): void; refresh(): void }) {
  const key = `${turn.session_id}:${turn.turn_id}`;
  const [extra, setExtra] = useState<WorkItem[]>([]);
  const [cursor, setCursor] = useState(turn.next_items_cursor);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const items = [...new Map([...extra, ...turn.items].map(item => [item.item_id, item])).values()].sort((a,b) => a.seq-b.seq);
  const status = !online && ["running", "waiting_permission"].includes(turn.status) ? "unknown" : turn.status;
  const load = async () => { setLoading(true); setError(""); try {
    const page = await workRequest<{ items: WorkItem[]; next_cursor: string | null }>(`${workBase(agentId)}/sessions/${encodeURIComponent(turn.session_id)}/turns/${encodeURIComponent(turn.turn_id)}/items?after_seq=${cursor}`);
    setExtra(old => [...old, ...page.items]); setCursor(page.next_cursor);
  } catch (e) { setError(String(e)); } finally { setLoading(false); } };
  const seenBackgroundReturns = new Set<string>();
  const backgroundRows = (raw: unknown, itemKey: string) => !Array.isArray(raw) ? null : <ul>{raw.map((entry, index) => {
    const value = obj(entry);
    const sourceKey = str(value.task_id) ? `${str(value.task_type)}:${str(value.task_id)}` : "";
    // Source sidecars accompany multiple assistant messages in the same turn.
    if (sourceKey && seenBackgroundReturns.has(sourceKey)) return null;
    if (sourceKey) seenBackgroundReturns.add(sourceKey);
    const child = sessions.find(session => session.session_id === value.child_session_id || (session.child_agent_id && session.child_agent_id === value.agent_id));
    const backgroundKey = `${itemKey}:background:${str(value.task_id) || index}`;
    return <BackgroundReturnRow key={backgroundKey} value={value as unknown as BackgroundReturn} expanded={expanded[backgroundKey] ?? false} onExpandedChange={open => expand(backgroundKey, open)} detailFooter={child && <button type="button" className="im-work-child-link" onClick={() => onChild(child.session_id)}>查看关联执行 · {child.description || child.child_agent_id || child.session_id}</button>} />;
  })}</ul>;
  return <details className="im-work-turn" open={expanded[key] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(key, event.currentTarget.open); }}>
    <summary><strong>{turnTitle(turn)}</strong><span>{turn.started_at ? new Date(turn.started_at).toLocaleString() : "时间未报告"}</span><span className={`im-work-status-label ${status}`}>{statusLabel(status)}</span>{typeof turn.elapsed_ms === "number" && <span>{formatDuration(turn.elapsed_ms)}</span>}</summary>
    <div className="im-work-turn-body"><div className="im-work-turn-meta"><span>{turn.model_id || "模型未报告"}</span><Usage value={turn.usage} /></div>
      <ul className="im-work-items">{items.map(item => {
        const p = item.payload; const itemKey = `${key}:${item.item_id}`;
        if (item.kind === "tool") {
          const call = { ...p, input: p.input ?? p.arguments ?? {}, output: p.output ?? p.summary } as unknown as ToolCall;
          const childId = str(p.child_session_id) || str(obj(p.detail).child_session_id);
          const child = sessions.find(s => s.session_id === childId || (s.parent_session_id === turn.session_id && (s.parent_tool_call_id === call.id || (s.child_agent_id && s.child_agent_id === (obj(p.detail).agent_id ?? obj(p.arguments).agent_id)))));
          return <ToolCallRow key={item.item_id} call={call} expanded={expanded[itemKey] ?? false} onExpandedChange={open => expand(itemKey, open)} detailFooter={<><WorkFacts facts={p.work_facts} />{child && <button id={`work-child-${child.session_id}`} type="button" className="im-work-child-link" onClick={() => onChild(child.session_id)}>查看子执行 · {child.description || child.child_agent_id || child.session_id}</button>}</>} />;
        }
        if (item.kind === "permission") return <li key={item.item_id}><PermissionCard request={p as unknown as PermissionRequest} endpoint={`${workBase(agentId)}/permissions/${encodeURIComponent(str(p.request_id))}`} disabled={!online || status === "unknown"} onResolved={refresh} /></li>;
        if (["message", "message_delta", "text_delta", "assistant_message"].includes(item.kind)) return <li className="im-work-body" key={item.item_id}>{str(p.reasoning_content) && <details open={expanded[itemKey] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(itemKey, event.currentTarget.open); }}><summary>思考</summary><p className="whitespace-pre-wrap">{str(p.reasoning_content)}</p></details>}<ReactMarkdown remarkPlugins={[remarkGfm]}>{str(p.text) || str(p.content) || str(p.delta)}</ReactMarkdown>{backgroundRows(p.background_returns, itemKey)}</li>;
        if (["thinking", "thinking_delta", "reasoning"].includes(item.kind)) return <li key={item.item_id}><details open={expanded[itemKey] ?? false} onToggle={event => { if (event.target === event.currentTarget) expand(itemKey,event.currentTarget.open); }}><summary>思考</summary><p className="whitespace-pre-wrap">{str(p.text) || str(p.content) || str(p.reasoning_content)}</p></details></li>;
        if (item.kind === "cron_delivery" || item.kind === "cron_trigger") return <li key={item.item_id}><SessionFacts items={[item]} /></li>;
        if (item.kind === "injection_consumed" && Array.isArray(p.background_returns) && p.background_returns.length > 0) return <li key={item.item_id}>{backgroundRows(p.background_returns, itemKey)}</li>;
        if (item.kind === "background_return") return <li key={item.item_id}>{backgroundRows([p], itemKey)}</li>;
        const child = sessions.find(s => s.session_id === p.child_session_id || (s.child_agent_id && s.child_agent_id === p.agent_id));
        return <li key={item.item_id}><details><summary>{item.kind === "background_return" ? `后台返回 · ${str(p.task_type) || "后台任务"}` : item.kind === "runtime_config_applied" ? "运行配置已应用" : item.kind === "recording_degraded" ? "工作记录存在缺口" : item.kind === "session_linked" ? "关联子执行" : item.kind === "control_result" ? "控制结果" : item.kind}</summary><pre className="chat-tool-call-pre">{JSON.stringify(p, null, 2)}</pre>{child && <button type="button" onClick={() => onChild(child.session_id)}>查看关联执行</button>}</details></li>;
      })}</ul>
      {cursor && <button type="button" disabled={loading} onClick={() => void load()}>加载更多过程</button>}{error && <p role="alert">{error}</p>}
    </div>
  </details>;
}

function WorkFacts({ facts }: { facts: unknown }) {
  if (!Array.isArray(facts)) return null;
  return <>{facts.map((raw, index) => { const fact = obj(raw); const target = str(fact.conversation_id) || str(fact.target); const refs = Array.isArray(fact.source_refs) ? fact.source_refs.map(obj) : [];
    return <div key={index} className="im-work-tool-fact">
      <p>{fact.type === "inbox_read_committed" ? "本页正文已持久摄取" : fact.type === "draft_withheld" ? "原草稿 · 未发送" : "实际投递确认"}</p>
      {fact.type === "draft_withheld" && <pre className="chat-tool-call-pre">{str(fact.text) || str(fact.draft)}</pre>}
      {target && <WorkThreadLink conversationId={target} messageId={str(fact.message_id)}>目标聊天{fact.message_id ? " · 原消息" : ""}</WorkThreadLink>}
      {refs.map((ref, i) => <WorkThreadLink key={i} conversationId={str(ref.conversation_id)} messageId={str(ref.message_id)}>{str(ref.name) || "新消息"}</WorkThreadLink>)}
    </div>;
  })}</>;
}
