import { useContext, useState, type ReactNode, type Ref } from "react";
import { useTranslation } from "../../../i18n";
import type { BackgroundReturn, TokenUsage, ToolCall } from "../../chat/chat-types";
import { ConversationToolCard } from "../../chat/components/conversation-tool-card";
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

function WorkFields({value}: {value: unknown}) {
  if (value == null) return value === null ? <code>null</code> : null;
  if (typeof value === "string") return value ? <pre>{value}</pre> : null;
  if (typeof value !== "object") return <code>{String(value)}</code>;
  const fields = Object.entries(value);
  if (!fields.length) return <code>{Array.isArray(value) ? "[]" : "{}"}</code>;
  return <dl className="im-work-fields">{fields.map(([key, item]) => <div key={key}>
    <dt>{key}</dt><dd>{item !== null && typeof item === "object" ? <NestedWorkField value={item} /> : <WorkFields value={item} />}</dd>
  </div>)}</dl>;
}

function NestedWorkField({value}: {value: object}) {
  const [open, setOpen] = useState(false);
  return <details onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{Array.isArray(value) ? tr("列表") : tr("对象")}</summary>
    {open && <WorkFields value={value} />}
  </details>;
}

function WorkToolSection({title, children}: {title: string; children: ReactNode}) {
  return <section className="im-work-tool-section"><h4>{tr(title)}</h4>{children}</section>;
}

/** Work cards share presenter data and detail rendering, with their own visual hierarchy. */
export function WorkTool({ call, expanded, onExpandedChange, detailFooter, childLink, observedAt, previewOnly, itemRef }: { call: ToolCall; expanded?: boolean; onExpandedChange?: (open: boolean) => void; detailFooter?: ReactNode; childLink?: ReactNode; observedAt?: string; previewOnly?: boolean; itemRef?: Ref<HTMLLIElement> }) {
  useTranslation();
  const navigation = useContext(WorkNavigationContext);
  const names = navigation?.names ?? {};
  const people = navigation?.people ?? {};
  const input = record(call.input), detail = record(call.detail);
  const targetId = text(input.target) || text(input.to) || text(detail.target);
  const target = names[targetId] || people[targetId] || text(detail.target_name) || targetId;
  let summary = text(call.output);
  if (call.name === "inbox" && input.action) summary = input.action === "check" ? tr("查看待读来源") : `${tr("读取新消息")} ${target}`;
  if (call.name === "conversations" && input.action) summary = input.action === "list" ? `${tr("查找聊天")} · ${text(input.query)}` : `${tr("回查历史")} ${target}`;
  if (call.name === "send_message" && !input.agent_id && target) summary = `${tr("发送到")} ${target}`;
  const sendError = call.name === "send_message" && text(detail.status) && !["ok", "sent", "held_for_revalidation", "pending_revalidation"].includes(text(detail.status)) ? text(detail.status) : "";
  const error = Boolean(sendError) || Boolean(detail.error) || detail.success === false || call.status === "failed";
  const pending = call.status === "running";
  const denied = call.approval === "user_deny" || call.reason === "denied";
  const business = ["continuable", "background"].includes(text(detail.delegation_kind)) ? "async_launched" : text(detail.status);
  const labels: Record<string, string> = { async_launched: "子执行已启动", message_queued: "补充已排队", held_for_revalidation: "未发送", pending_revalidation: "待发送" };
  const internalMessage = call.name === "send_message" && Boolean(input.agent_id);
  const prompt = text(detail.prompt) || text(input.prompt);
  const delegation = ["agent", "subagent"].includes(call.name) && prompt;
  const outgoing = call.name === "send_message" && !internalMessage;
  const delivery = text(detail.status);
  const deliveryLabel = {sent: "已发送", ok: "成功", pending_revalidation: "待发送", held_for_revalidation: "未发送"}[delivery];
  const deliveryFields = Object.fromEntries(Object.entries(detail).filter(([key]) =>
    !["status", "target", "message_id", "text", "error"].includes(key)
  ));
  const argumentFields = Object.entries(input);
  const requestText = text(input.text) || text(input.message) || text(detail.text);
  const structuredInput = Object.fromEntries(argumentFields.filter(([key]) =>
    !(delegation && ["description", "agent_id", "prompt"].includes(key)) &&
    !(internalMessage && ["agent_id", "message"].includes(key)) &&
    !(outgoing && ["target", "to", "text", "message"].includes(key)) &&
    !((call.name === "bash" && detail.native_view) && ["command", "cmd", "cwd"].includes(key))
  ));
  return <li ref={itemRef} className="im-work-tool-group" data-testid="process-item"><div className="im-work-tool">
    <button type="button" className="im-work-tool-head" aria-expanded={expanded ?? false} onClick={() => onExpandedChange?.(!expanded)}>
      <span className="im-work-tool-icon" aria-hidden="true">{icons[call.name] || "◇"}</span><strong>{call.name}</strong><span className="im-work-tool-summary">{summary}</span>
      {(call.approval === "user_allow" || denied) && <span className="im-work-status-label">{tr(denied ? "已拒绝" : "已授权")}</span>}
      <span className={error ? "im-work-error" : "im-work-muted"}>{tr(denied ? "未执行" : call.reason === "interrupted" ? "已中断" : error ? "调用失败" : pending ? "调用中" : !call.status ? "状态未知" : "调用完成")}</span>
      {labels[business] && <span className="im-work-status-label">{tr(labels[business])}</span>}
      {observedAt && <time dateTime={observedAt}>{new Date(observedAt).toLocaleTimeString(undefined, {hour12: false})}</time>}
      {typeof call.duration_ms === "number" && <span>{formatDuration(call.duration_ms)}</span>}
    </button>
    {expanded && <div className="im-work-tool-body">
      {previewOnly ? detailFooter : <>
        <WorkToolSection title="调用">
          {delegation && <><strong className="im-work-detail-label">{tr(input.agent_id ? "补充给" : "委派")} {text(input.agent_id) || text(input.description)}</strong><pre>{prompt}</pre></>}
          {internalMessage && <><p>{tr("补充给")} {text(input.agent_id)}</p><pre>{text(input.message)}</pre></>}
          {outgoing && <>{target && <p>{tr("发送到")} {people[targetId] && !names[targetId] ? <span>{target}</span> : <WorkThreadLink conversationId={targetId}>{target}</WorkThreadLink>}</p>}{requestText && <pre>{requestText}</pre>}</>}
          {Object.keys(structuredInput).length > 0 ? <WorkFields value={structuredInput} />
            : !delegation && !internalMessage && !outgoing && <code>{call.name}</code>}
        </WorkToolSection>
        <WorkToolSection title="结果">
          {delegation ? <>
            {detail.error && <p className="im-work-error">{text(detail.error) || text(record(detail.error).message)}</p>}
            {!pending && <p><span className="im-work-status-label">{tr(labels[business] || (error ? "失败" : "已完成"))}</span> {text(detail.agent_id)}</p>}
            {text(detail.content) && <pre>{text(detail.content)}</pre>}
            {text(detail.output_file) && <p className="im-work-muted">{tr("结果文件")}：<code>{text(detail.output_file)}</code></p>}
          </> : internalMessage ? <>
            {text(detail.content) && <pre>{text(detail.content)}</pre>}
            {detail.error && <p className="im-work-error">{text(detail.error) || text(record(detail.error).message)}</p>}
          </> : outgoing ? <>
            {(detail.error || sendError) && <p className="im-work-error">{text(detail.error) || text(record(detail.error).message) || sendError}</p>}
            {text(detail.text) && text(detail.text) !== requestText && <pre>{text(detail.text)}</pre>}
            {deliveryLabel && <p>{tr(deliveryLabel)}</p>}
            {Object.keys(deliveryFields).length > 0 && <WorkFields value={deliveryFields} />}
            {!Object.keys(detail).length && call.output && call.output !== requestText && <pre>{call.output}</pre>}
          </> : call.name === "inbox" ? <ConversationToolCard call={call} compact />
            : <ToolDetailBody call={call} renderResult={result => <WorkFields value={result} />} />}
        </WorkToolSection>
        {detailFooter && <WorkToolSection title="来源">{detailFooter}</WorkToolSection>}
      </>}
    </div>}{childLink && <footer className="im-work-link-footer">{childLink}</footer>}</div>
  </li>;
}

export function WorkBackground({ value, expanded, onExpandedChange, detailFooter }: { value: BackgroundReturn; expanded?: boolean; onExpandedChange?: (open: boolean) => void; detailFooter?: ReactNode }) {
  useTranslation();
  return <li className="im-work-background"><button type="button" data-testid="process-background-return-toggle" aria-expanded={expanded ?? false} onClick={() => onExpandedChange?.(!expanded)}><strong>{tr("后台结果")} · {value.description || value.task_type}</strong><span className="im-work-status-label">{tr(value.status === "completed" ? "已完成" : value.status === "failed" ? "失败" : value.status === "stopped" ? "已停止" : value.status === "killed" ? "已终止" : "状态未知")}</span></button>{expanded && <div>{value.result != null && <pre>{typeof value.result === "string" ? value.result : JSON.stringify(value.result, null, 2)}</pre>}{value.error && <pre className="im-work-error">{value.error}</pre>}</div>}{detailFooter && <footer className="im-work-link-footer">{detailFooter}</footer>}</li>;
}

/** Context is the last input; output and cache counters accumulate within this turn. */
export function WorkUsage({ value, label = "本轮统计" }: { value: (Partial<TokenUsage> & {total_tokens?: number}) | null; label?: string }) {
  useTranslation();
  if (typeof value?.context_used !== "number" || typeof value.output !== "number") return <span className="im-work-muted">{typeof value?.total_tokens === "number" ? `${value.total_tokens.toLocaleString()} tok` : tr("Token 未报告")}</span>;
  const fmt = (n: number) => n.toLocaleString();
  const percent = value.context_window ? Math.round(value.context_used / value.context_window * 100) : null;
  const cache = value.cache_read_tokens != null && value.cache_total_input_tokens != null ? `${fmt(value.cache_read_tokens)} (${value.cache_total_input_tokens ? Math.round(value.cache_read_tokens / value.cache_total_input_tokens * 100) : 0}%)` : tr("未报告");
  return <details className="im-work-usage"><summary><span>{tr(label)}</span><strong>{fmt(value.context_used)}</strong><span className="im-work-meter"><i style={{width:`${Math.min(percent ?? 0,100)}%`}} /></span><small>{percent === null ? tr("上下文窗口未报告") : `${percent}%`}</small>{label === "本轮统计" && typeof value.total_tokens === "number" && <small>{fmt(value.total_tokens)} tok</small>}<span className="im-work-usage-toggle">{tr("统计详情")}</span></summary><div className="im-work-usage-details"><dl><div><dt>{tr("上下文")}</dt><dd>{fmt(value.context_used)}</dd><small>{value.context_window ? `/ ${fmt(value.context_window)}` : tr("上下文窗口未报告")}</small></div><div><dt>{tr("本轮输出")}</dt><dd>{fmt(value.output)}</dd></div><div><dt>{tr("缓存命中")}</dt><dd>{cache}</dd></div></dl><p>{tr("上下文取本轮最近一次输入，输出为本轮累计；主、子执行分别统计，不代表计费总量。")}</p></div></details>;
}
