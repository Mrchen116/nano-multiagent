import { LongOutput } from "./tool-long-output";
import type { ToolCall } from "../chat-types";

type RecordValue = Record<string, unknown>;
const record = (value: unknown): RecordValue => value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
const records = (value: unknown): RecordValue[] => Array.isArray(value) ? value.map(record) : [];
const text = (value: unknown) => typeof value === "string" ? value : "";

/** One bridge for native presenter card shapes; tools keep their original names. */
export function NativeToolDetail({ call }: {call: ToolCall}) {
  const view = record(call.detail?.native_view);
  const pending = record(call.detail?.native_call);
  const content = records(view.content).filter(part => part.type === "text").map(part => text(part.text)).join("\n");
  const command = text(view.command) || text(pending.command) || (pending.card === "terminal" ? text(pending.title) : "");
  const terminal = pending.card === "terminal" || view.card === "terminal";
  const output = text(view.output) || content || text(call.detail?.content) || (call.status === "running" ? "" : text(call.output));
  if (terminal) return <div className="chat-tool-detail-term">
    {text(pending.cwd) && <p className="im-work-muted"><code>{text(pending.cwd)}</code></p>}
    {command && <div className="chat-tool-detail-term-cmd">{command}</div>}
    {output && <LongOutput text={output} render={shown => <pre className={`chat-tool-detail-term-out${call.status === "failed" ? " chat-tool-detail-term-err" : ""}`}>{shown}</pre>} />}
    {typeof view.exitCode === "number" && <div className="chat-tool-detail-term-meta"><span className={view.exitCode !== 0 ? "chat-tool-detail-exit-bad" : undefined}>exit {view.exitCode}</span></div>}
    {text(view.signal) && <p>{text(view.signal)}</p>}
  </div>;
  // A native presenter chooses salient input; full arguments are only a fallback without one.
  const rawInput = pending.rawInput ?? (Object.keys(pending).length === 0 ? call.input : undefined);
  return <div className="chat-native-tool-detail">
    {(text(view.title) || text(pending.title)) && <strong>{text(view.title) || text(pending.title)}</strong>}
    {rawInput != null && <pre className="chat-tool-call-pre">{typeof rawInput === "string" ? rawInput : JSON.stringify(rawInput, null, 2)}</pre>}
    {text(pending.cwd) && <p><code>{text(pending.cwd)}</code></p>}
    {command && <pre className="chat-tool-call-pre">{command}</pre>}
    {text(view.path) && <p><code>{text(view.path)}</code></p>}
    {view.card === "diff" ? records(view.diffs).map((diff, index) => <div key={index}>
      <p><code>{text(diff.path)}</code></p>
      {diff.oldText != null && <pre className="chat-tool-call-pre">{text(diff.oldText).split("\n").map(line => `- ${line}`).join("\n")}</pre>}
      <pre className="chat-tool-call-pre">{text(diff.newText).split("\n").map(line => `+ ${line}`).join("\n")}</pre>
    </div>) : <pre className={`chat-tool-call-pre${call.status === "failed" ? " im-work-error" : ""}`}>{output}</pre>}
    {typeof view.exitCode === "number" && <p>Exit code: {view.exitCode}</p>}
    {text(view.signal) && <p>{text(view.signal)}</p>}
  </div>;
}
