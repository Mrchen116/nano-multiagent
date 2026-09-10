import { useContext, type ReactNode } from "react";
import { useTranslation } from "../../../i18n";
import type { BackgroundReturn, TokenUsage, ToolCall } from "../../chat/chat-types";
import { ToolDetailBody } from "../../chat/components/tool-detail-renderers";
import { formatDuration } from "../../chat/components/tool-calls-panel";
import { WorkNavigationContext, WorkThreadLink } from "../../chat/components/work-thread-link";
import { tr } from "./agent-work-text";
import type { WorkItem } from "./agent-work-api";

const text = (v: unknown) => typeof v === "string" ? v : "";
const record = (v: unknown): Record<string, unknown> => v && typeof v === "object" ? v as Record<string, unknown> : {};
const icons: Record<string, string> = { inbox: "↓", conversations: "☰", send_message: "↗", agent: "◇", bash: "⌘", read: "▤", edit: "✎", write: "✎" };

/** Match chat delivery: repeated reasoning snapshots belong to a run/output group. */
export function withVisibleReasoning(items: WorkItem[]): WorkItem[] {
  const seen = new Map<string, string>();
  return items.map(item => {
    const reasoning = text(item.payload.reasoning_content).trim();
    const group = text(item.payload.group_id);
    if (!reasoning || !group) return item;
    const key = JSON.stringify([item.payload.run_id, group]);
    const previous = seen.get(key);
    seen.set(key, reasoning);
    const visible = previous && reasoning.startsWith(previous) ? reasoning.slice(previous.length).trim() : reasoning;
    return visible === reasoning ? item : { ...item, payload: { ...item.payload, reasoning_content: visible } };
  });
}

/** Work cards share presenter data and detail rendering, with their own visual hierarchy. */
export function WorkTool({ call, expanded, onExpandedChange, detailFooter, childLink }: { call: ToolCall; expanded?: boolean; onExpandedChange?: (open: boolean) => void; detailFooter?: ReactNode; childLink?: ReactNode }) {
  useTranslation();
  const navigation = useContext(WorkNavigationContext);
  const names = navigation?.names ?? {};
  const people = navigation?.people ?? {};
  const input = record(call.input), detail = record(call.detail);
  const targetId = text(input.target) || text(input.to) || text(detail.target);
  const target = names[targetId] || people[targetId] || text(detail.target_name) || targetId;
  let summary = text(call.output);
  if (call.name === "inbox") summary = input.action === "check" ? tr("查看待读来源") : `${tr("读取新消息")} ${target}`;
  if (call.name === "conversations") summary = input.action === "list" ? `${tr("查找聊天")} · ${text(input.query)}` : `${tr("回查历史")} ${target}`;
  if (call.name === "send_message") summary = `${tr("发送到")} ${target}`;
  const sendError = call.name === "send_message" && text(detail.status) && !["ok", "held_for_revalidation", "pending_revalidation"].includes(text(detail.status)) ? text(detail.status) : "";
  const error = Boolean(sendError) || Boolean(detail.error) || detail.success === false || call.status === "failed";
  const pending = call.status === "running";
  const denied = call.approval === "user_deny" || call.reason === "denied";
  const business = text(detail.status);
  const labels: Record<string, string> = { async_launched: "子执行已启动", message_queued: "补充已排队", held_for_revalidation: "未发送", pending_revalidation: "待发送" };
  const prompt = text(detail.prompt) || text(input.prompt);
  return <li className="im-work-tool-group" data-testid="process-item"><div className="im-work-tool">
    <button type="button" className="im-work-tool-head" aria-expanded={expanded ?? false} onClick={() => onExpandedChange?.(!expanded)}>
      <span className="im-work-tool-icon" aria-hidden="true">{icons[call.name] || "◇"}</span><strong>{call.name}</strong><span className="im-work-tool-summary">{summary}</span>
      {(call.approval === "user_allow" || denied) && <span className="im-work-status-label">{tr(denied ? "已拒绝" : "已授权")}</span>}
      <span className={error ? "im-work-error" : "im-work-muted"}>{tr(denied ? "未执行" : error ? "调用失败" : pending ? "调用中" : "调用完成")}</span>
      {labels[business] && <span className="im-work-status-label">{tr(labels[business])}</span>}
      {typeof call.duration_ms === "number" && <time>{formatDuration(call.duration_ms)}</time>}
    </button>
    {expanded && <div className="im-work-tool-body">{call.name === "agent" && prompt ? <>
      <strong className="im-work-detail-label">{tr(input.agent_id ? "补充给" : "委派")} {text(input.agent_id) || text(input.description)}</strong>
      <pre>{prompt}</pre>
      {detail.error && <p className="im-work-error">{text(detail.error) || text(record(detail.error).message)}</p>}
      {!pending && <p><span className="im-work-status-label">{tr(labels[business] || (error ? "失败" : "已完成"))}</span> {text(detail.agent_id)}</p>}
      {text(detail.content) && <pre>{text(detail.content)}</pre>}
      {text(detail.output_file) && <p className="im-work-muted">{tr("结果文件")}：<code>{text(detail.output_file)}</code></p>}
    </> : call.name === "send_message" ? <><p>{tr("发送到")} {people[targetId] && !names[targetId] ? <span>{target}</span> : <WorkThreadLink conversationId={targetId}>{target}</WorkThreadLink>}</p><pre>{text(detail.text) || text(input.text)}</pre>{(detail.error || sendError) && <p className="im-work-error">{text(detail.error) || text(record(detail.error).message) || sendError}</p>}</> : <ToolDetailBody call={call} />}{detailFooter}</div>}</div>{expanded && childLink}
  </li>;
}

export function WorkBackground({ value, expanded, onExpandedChange, detailFooter }: { value: BackgroundReturn; expanded?: boolean; onExpandedChange?: (open: boolean) => void; detailFooter?: ReactNode }) {
  useTranslation();
  return <li className="im-work-background"><button type="button" data-testid="process-background-return-toggle" aria-expanded={expanded ?? false} onClick={() => onExpandedChange?.(!expanded)}><strong>{tr("后台结果")} · {value.description || value.task_type}</strong><span className="im-work-status-label">{tr(value.status === "completed" ? "已完成" : value.status === "failed" ? "失败" : value.status === "stopped" ? "已停止" : value.status === "killed" ? "已终止" : "状态未知")}</span></button>{expanded && <div>{value.result != null && <pre>{typeof value.result === "string" ? value.result : JSON.stringify(value.result, null, 2)}</pre>}{value.error && <pre className="im-work-error">{value.error}</pre>}{detailFooter}</div>}</li>;
}

/** Context is the last input; output and cache counters accumulate within this turn. */
export function WorkUsage({ value, label = "本轮统计" }: { value: Partial<TokenUsage> | null; label?: string }) {
  useTranslation();
  if (typeof value?.context_used !== "number" || typeof value.output !== "number") return <span className="im-work-muted">{tr("Token 未报告")}</span>;
  const fmt = (n: number) => n.toLocaleString();
  const percent = value.context_window ? Math.round(value.context_used / value.context_window * 100) : null;
  const cache = value.cache_read_tokens != null && value.cache_total_input_tokens != null ? `${fmt(value.cache_read_tokens)} (${value.cache_total_input_tokens ? Math.round(value.cache_read_tokens / value.cache_total_input_tokens * 100) : 0}%)` : tr("未报告");
  return <details className="im-work-usage"><summary><span>{tr(label)}</span><strong>{fmt(value.context_used)}</strong><span className="im-work-meter"><i style={{width:`${Math.min(percent ?? 0,100)}%`}} /></span><small>{percent === null ? tr("上下文窗口未报告") : `${percent}%`}</small><span className="im-work-usage-toggle">{tr("统计详情")}</span></summary><div className="im-work-usage-details"><dl><div><dt>{tr("上下文")}</dt><dd>{fmt(value.context_used)}</dd><small>{value.context_window ? `/ ${fmt(value.context_window)}` : tr("上下文窗口未报告")}</small></div><div><dt>{tr("本轮输出")}</dt><dd>{fmt(value.output)}</dd></div><div><dt>{tr("缓存命中")}</dt><dd>{cache}</dd></div></dl><p>{tr("上下文取本轮最近一次输入，输出为本轮累计；主、子执行分别统计，不代表计费总量。")}</p></div></details>;
}
