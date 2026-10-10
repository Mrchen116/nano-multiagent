import { LongOutput } from "./tool-long-output";
import { useTranslation } from "../../../i18n";
import type { ToolCall } from "../chat-types";

type RecordValue = Record<string, unknown>;
const record = (value: unknown): RecordValue => value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
const records = (value: unknown): RecordValue[] => Array.isArray(value) ? value.map(record) : [];
const text = (value: unknown) => typeof value === "string" ? value : "";

/** Native card shapes own their body; generic arguments are only a presenter-less fallback. */
export function NativeToolDetail({ call }: {call: ToolCall}) {
  const {t} = useTranslation();
  const view = record(call.detail?.native_view);
  const pending = record(call.detail?.native_call);
  const content = records(view.content).filter(part => part.type === "text").map(part => text(part.text)).join("\n");
  const command = text(view.command) || text(pending.command) || (pending.card === "terminal" ? text(pending.title) : "");
  const terminal = pending.card === "terminal" || view.card === "terminal";
  // An explicitly empty result is not the short operation summary.
  const output = typeof view.output === "string" ? view.output : Array.isArray(view.content) ? content : typeof call.detail?.content === "string" ? call.detail.content : call.status === "running" ? "" : text(call.output);
  const error = text(call.detail?.error) || text(record(call.detail?.error).message);
  const body = output || error;
  const renderText = (value: string) => <LongOutput text={value} render={shown => <pre className={`chat-tool-call-pre${call.status === "failed" ? " im-work-error" : ""}`}>{shown}</pre>} />;
  const capped = view.truncated === true && <p className="chat-tool-long-output-source-note">{t("chat.messagePane.toolDetail.truncatedAtSource")}</p>;
  const terminalBody = view.card === "generic" && body.startsWith("```console\n") && body.endsWith("\n```") ? body.slice(11, -4) : body;
  if (terminal) return <div className="chat-tool-detail-term">
    {text(pending.cwd) && <p className="im-work-muted"><code>{text(pending.cwd)}</code></p>}
    {command && <div className="chat-tool-detail-term-cmd">{command}</div>}
    {terminalBody && <LongOutput text={terminalBody} render={shown => <pre className={`chat-tool-detail-term-out${call.status === "failed" ? " chat-tool-detail-term-err" : ""}`}>{shown}</pre>} />}
    {typeof view.exitCode === "number" && <div className="chat-tool-detail-term-meta"><span className={view.exitCode !== 0 ? "chat-tool-detail-exit-bad" : undefined}>exit {view.exitCode}</span></div>}
    {text(view.signal) && <p>{text(view.signal)}</p>}
  </div>;
  const rawInput = pending.rawInput ?? (Object.keys(pending).length === 0 ? call.input : undefined);
  const title = text(view.title) || text(pending.title);
  let result;
  if (call.status === "failed") result = body && renderText(body);
  else if (view.card === "diff" && Array.isArray(view.diffs)) result = records(view.diffs).map((diff, index) => <div key={index}>
    <p><code>{text(diff.path)}</code></p>
    {renderText([...(diff.oldText == null ? [] : text(diff.oldText).split("\n").map(line => `- ${line}`)), ...text(diff.newText).split("\n").map(line => `+ ${line}`)].join("\n"))}
  </div>);
  else if (view.card === "read" && Array.isArray(view.lines)) result = <>
    <p><code>{text(view.path)}</code>{typeof view.totalLines === "number" && <small> · {records(view.lines).length ? `${view.offset}–${records(view.lines).at(-1)?.number}` : "0"} / {view.totalLines}</small>}</p>
    {renderText(records(view.lines).map(line => `${line.number}  ${text(line.text)}`).join("\n"))}
  </>;
  else if (view.card === "search" && (Array.isArray(view.files) || Array.isArray(view.paths))) result = <>
    {typeof view.total === "number" && <p>{view.total} {t("agents.work.匹配", {defaultValue:"匹配"})}</p>}
    {view.shape === "paths" ? renderText((view.paths as string[]).join("\n")) : records(view.files).map((file, index) => <div key={index}><code>{text(file.path)}</code>{renderText(records(file.matches).map(match => `${match.lineNumber}  ${text(match.line)}`).join("\n"))}</div>)}
    {capped}
  </>;
  else if (view.card === "web" && view.kind === "search" && Array.isArray(view.sources)) result = <>
    {text(view.answer) && renderText(text(view.answer))}
    {records(view.sources).map((source, index) => <div key={index}><a href={text(source.url)} target="_blank" rel="noreferrer">{text(source.title) || text(source.url)}</a>{text(source.publishedAt) && <small> · {text(source.publishedAt)}</small>}{text(source.snippet) && <p>{text(source.snippet)}</p>}</div>)}
    {capped}
  </>;
  else if (view.card === "web" && view.kind === "fetch") result = <>
    <p><a href={text(view.url)} target="_blank" rel="noreferrer">{text(view.url)}</a>{typeof view.statusCode === "number" && <small> · HTTP {view.statusCode}</small>}</p>
    {body && renderText(body)}{capped}
  </>;
  else result = body && renderText(body);
  return <div className="chat-native-tool-detail">
    {title && title !== rawInput && <strong>{title}</strong>}
    {rawInput != null && renderText(typeof rawInput === "string" ? rawInput : JSON.stringify(rawInput, null, 2))}
    {result}
  </div>;
}
