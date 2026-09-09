import { useTranslation } from "../../../i18n";
import type { ToolCall } from "../chat-types";
import { LongOutput } from "./tool-long-output";
import { useContext } from "react";
import { WorkNavigationContext, WorkThreadLink } from "./work-thread-link";

type Value = Record<string, unknown>;
const object = (value: unknown): Value => value && typeof value === "object" && !Array.isArray(value) ? value as Value : {};
const entries = (value: unknown): Value[] => Array.isArray(value) ? value.map(object) : [];
const text = (value: unknown): string => typeof value === "string" ? value : "";

/** Inbox and history use Presenter data; opening a card never reads or consumes Inbox. */
export function ConversationToolCard({ call }: { call: ToolCall }) {
  const {t} = useTranslation();
  const people = useContext(WorkNavigationContext)?.people ?? {};
  const tr = (label: string) => t(`agents.work.${label}`, {defaultValue:label});
  const detail = call.detail ?? {};
  const args = { ...object(call.input), ...detail };
  const action = text(args.action);
  const target = text(args.target);
  const pending = call.status === "running";
  const failed = call.status === "failed" || Boolean(detail.error);
  const conversations = entries(detail.conversations);
  const messages = entries(detail.messages);
  return <div className="im-conversation-tool-card">
    <p className="text-xs text-slate-500">{tr(call.name === "conversations" ? "聊天历史查询 · 不推进收件箱" : action === "check" ? "待读摘要 · 不读取正文" : "收件箱消息页")}</p>
    {target && <p>{tr("目标：")}<WorkThreadLink conversationId={target}>{text(args.name) || target}</WorkThreadLink></p>}
    {text(args.query) && <p>{tr("查找")}：{text(args.query)}</p>}
    {args.limit != null && <p className="text-xs text-slate-500">{tr("条数上限")}：{String(args.limit)}</p>}
    {failed ? <pre className="chat-tool-call-pre">{typeof detail.error === "string" ? detail.error : JSON.stringify(detail.error ?? call.output, null, 2)}</pre> : !pending && <>
      {conversations.map((item, index) => <div className="im-work-source-row" key={text(item.target) || index}>
        <WorkThreadLink conversationId={text(item.target) || text(item.conversation_id)}>{text(item.name) || text(item.target) || text(item.conversation_id)}</WorkThreadLink>
        {typeof item.pending_count === "number" && <span>{item.pending_count} {tr("条待读")}</span>}
        {Array.isArray(item.attention_reasons) && <small>{item.attention_reasons.join(" · ")}</small>}
      </div>)}
      {messages.map((item, index) => {
        const source = object(item.source); const sender = object(item.sender);
        return <div className="im-work-read-message" key={`${text(item.message_id)}:${text(item.part_key) || index}`}>
          <small>{text(sender.name) || people[text(sender.id)] || text(sender.id)} · {text(item.source_time) ? new Date(text(item.source_time)).toLocaleString() : ""} · <WorkThreadLink conversationId={text(source.conversation_id) || target} messageId={text(item.message_id)}>{tr("原消息")}</WorkThreadLink></small>
          {entries(item.content).map((content, i) => content.type === "text" ? <LongOutput key={i} text={text(content.text)} truncatedAtSource={detail.truncated === true} render={shown => <p className="whitespace-pre-wrap">{shown}</p>} /> : content.type === "image" && text(content.url) ? <a href={text(content.url)} key={i} target="_blank" rel="noreferrer"><img className="max-h-48 max-w-full" alt={text(content.file_name) || tr("消息图片")} src={text(content.url)} /></a> : <a href={text(content.url)} key={i} target="_blank" rel="noreferrer">{text(content.file_name) || tr("附件")}</a>)}
          {item.complete_message === false && <small>{tr("此条消息的一部分")}</small>}
        </div>;
      })}
      {(Array.isArray(detail.messages) || Array.isArray(detail.conversations)) && messages.length === 0 && conversations.length === 0 && <p>{tr("没有匹配记录")}</p>}
      {typeof detail.has_more === "boolean" && <small>{tr(detail.has_more ? "还有后续页面" : "当前页面已返回")}</small>}
      {detail.truncated === true && <p>{tr("展示已截断")}</p>}
    </>}
  </div>;
}
