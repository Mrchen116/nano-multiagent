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
  const command = text(view.command) || text(pending.command);
  const output = text(view.output) || content || text(call.detail?.content) || text(call.output);
  return <div className="chat-native-tool-detail">
    {(text(view.title) || text(pending.title)) && <strong>{text(view.title) || text(pending.title)}</strong>}
    {pending.rawInput != null && <pre className="chat-tool-call-pre">{typeof pending.rawInput === "string" ? pending.rawInput : JSON.stringify(pending.rawInput, null, 2)}</pre>}
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
