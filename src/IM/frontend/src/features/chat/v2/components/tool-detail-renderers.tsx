// feat-409-M2: per-tool expanded-body renderers.
//
// The structured `detail` is produced by the kernel presenter (决策 1/4) and
// forwarded verbatim. Known built-in names get bespoke cards (terminal block,
// diff, web card, agent prompt-before-result, …); unknown / DIY / MCP tools fall
// back to a generic key/value card that renders their detail faithfully (NOT raw
// JSON) — so DIY tools still get their full detail shown, just without bespoke
// visual polish (决策 4). Rows without any detail degrade to the output string
// (historical messages persisted before feat-409).
//
// Field names mirror the presenter schema exactly (bash → command/stdout/…,
// edit → diff/firstChangedLine, agent → prompt/content/…). Access is guarded
// because detail is an open record (DIY tools may carry anything).

import type { ReactNode } from "react";

import { useTranslation } from "../../../../i18n";
import type { ToolCall, ToolDetail } from "../chat-types";

function str(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="chat-tool-call-section">
      <span className="chat-tool-call-section-label">{label}</span>
      {children}
    </div>
  );
}

// ─── error (shared failure path) ─────────────────────────────────────────────

function ErrorCard({ detail }: { detail: ToolDetail }) {
  const message = str(detail.error?.message ?? detail.message ?? "");
  return (
    <div className="chat-tool-detail-error">
      <span className="chat-tool-detail-error-icon" aria-hidden="true">
        ✕
      </span>
      <pre className="chat-tool-call-pre">{message}</pre>
    </div>
  );
}

// ─── bash → terminal block ───────────────────────────────────────────────────

function BashCard({ detail }: { detail: ToolDetail }) {
  const command = str(detail.command);
  const stdout = str(detail.stdout);
  const stderr = str(detail.stderr);
  const exit = detail.exit_code;
  return (
    <div className="chat-tool-detail-term">
      <div className="chat-tool-detail-term-cmd">{command}</div>
      {stdout && <pre className="chat-tool-detail-term-out">{stdout}</pre>}
      {stderr && <pre className="chat-tool-detail-term-out chat-tool-detail-term-err">{stderr}</pre>}
      {typeof exit === "number" && (
        <div className="chat-tool-detail-term-meta">
          <span className={exit !== 0 ? "chat-tool-detail-exit-bad" : undefined}>exit {exit}</span>
        </div>
      )}
    </div>
  );
}

// ─── edit → colourised unified diff ──────────────────────────────────────────

function DiffCard({ detail }: { detail: ToolDetail }) {
  const path = str(detail.path);
  const diff = str(detail.diff);
  const lines = diff.split("\n");
  return (
    <div className="chat-tool-detail-diff">
      {path && <div className="chat-tool-detail-diff-file">{path}</div>}
      <div className="chat-tool-detail-diff-body">
        {lines.map((line, i) => {
          // Skip unified-diff file headers; the path is already shown above.
          if (line.startsWith("+++") || line.startsWith("---")) return null;
          let cls = "chat-tool-detail-diff-ctx";
          if (line.startsWith("+")) cls = "chat-tool-detail-diff-add";
          else if (line.startsWith("-")) cls = "chat-tool-detail-diff-del";
          else if (line.startsWith("@@")) cls = "chat-tool-detail-diff-hunk";
          return (
            <div key={i} className={`chat-tool-detail-diff-line ${cls}`}>
              {line || " "}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── write → file content ────────────────────────────────────────────────────

function WriteCard({ detail }: { detail: ToolDetail }) {
  const path = str(detail.path);
  const content = str(detail.content);
  const bytes = detail.bytes;
  return (
    <div className="chat-tool-detail-write">
      <div className="chat-tool-detail-write-head">
        {path}
        {typeof bytes === "number" && <span className="chat-tool-detail-write-bytes">{bytes} bytes</span>}
      </div>
      <pre className="chat-tool-call-pre">{content}</pre>
    </div>
  );
}

// ─── web_fetch → title + url + content card ──────────────────────────────────

function WebCard({ detail }: { detail: ToolDetail }) {
  const title = str(detail.title);
  const url = str(detail.final_url || detail.url);
  const status = detail.status;
  const content = str(detail.content);
  return (
    <div className="chat-tool-detail-web">
      {title && <div className="chat-tool-detail-web-title">{title}</div>}
      <div className="chat-tool-detail-web-url">
        {url}
        {status != null && ` · ${status}`}
      </div>
      {content && <div className="chat-tool-detail-web-excerpt">{content}</div>}
    </div>
  );
}

// ─── agent → full prompt BEFORE result (spec) ────────────────────────────────

function AgentCard({ detail }: { detail: ToolDetail }) {
  const { t } = useTranslation();
  const prompt = str(detail.prompt);
  const subagent = str(detail.subagent_type);
  const status = str(detail.status);
  const content = str(detail.content);
  const outputFile = str(detail.output_file);
  const error = str(detail.error ?? "");
  return (
    <div className="chat-tool-detail-agent">
      {prompt && (
        <Section label={t("chat.messagePane.toolDetail.agentPromptLabel")}>
          <div className="chat-tool-detail-agent-prompt">{prompt}</div>
        </Section>
      )}
      <div className="chat-tool-detail-agent-result">
        <div className="chat-tool-detail-agent-status">
          {status === "failed" ? "✕" : "✓"}{" "}
          {t("chat.messagePane.toolDetail.agentDone", { status: status || "completed" })}
          {subagent && ` · ${subagent}`}
        </div>
        {content && <div className="chat-tool-detail-agent-content">{content}</div>}
        {outputFile && (
          <div className="chat-tool-detail-agent-file">
            {t("chat.messagePane.toolDetail.agentOutputFile", { file: outputFile })}
          </div>
        )}
        {error && <pre className="chat-tool-call-pre">{error}</pre>}
      </div>
    </div>
  );
}

// ─── memory / skill_manage / task_stop → compact info cards ──────────────────

function MemoryCard({ detail }: { detail: ToolDetail }) {
  const { t } = useTranslation();
  const target = str(detail.target);
  const content = str(detail.content);
  const message = str(detail.message);
  return (
    <div className="chat-tool-detail-info">
      <div className="chat-tool-detail-info-head">
        ✓ {message || t("chat.messagePane.toolDetail.memoryDone", { target })}
      </div>
      {content && <div className="chat-tool-detail-info-body">{content}</div>}
    </div>
  );
}

function SkillCard({ detail }: { detail: ToolDetail }) {
  const message = str(detail.message);
  const path = str(detail.path);
  return (
    <div className="chat-tool-detail-info">
      <div className="chat-tool-detail-info-head">✓ {message || str(detail.name)}</div>
      {path && <div className="chat-tool-detail-info-body">{path}</div>}
    </div>
  );
}

function TaskStopCard({ detail }: { detail: ToolDetail }) {
  const taskId = str(detail.task_id);
  const status = str(detail.status);
  return (
    <div className="chat-tool-detail-info">
      <div className="chat-tool-detail-info-head">
        ✓ {status} · {taskId}
      </div>
    </div>
  );
}

// ─── generic fallback for unknown / DIY / MCP tools ──────────────────────────

function GenericCard({ detail }: { detail: ToolDetail }) {
  const entries = Object.entries(detail);
  return (
    <div className="chat-tool-detail-generic">
      {entries.map(([key, value]) => (
        <div key={key} className="chat-tool-detail-generic-row">
          <span className="chat-tool-detail-generic-key">{key}</span>
          <span className="chat-tool-detail-generic-val">
            {typeof value === "string" ? value : JSON.stringify(value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── dispatch ────────────────────────────────────────────────────────────────

const BESPOKE: Record<string, (p: { detail: ToolDetail }) => ReactNode> = {
  bash: BashCard,
  edit: DiffCard,
  write: WriteCard,
  web_fetch: WebCard,
  agent: AgentCard,
  memory: MemoryCard,
  skill_manage: SkillCard,
  task_stop: TaskStopCard
};

/**
 * Render the expanded body for a tool call. Failures (detail.error present) show
 * the error card regardless of tool. Known names get bespoke cards; unknown
 * tools with a detail get the generic key/value card; rows without detail
 * degrade to the raw output string (historical messages).
 */
export function ToolDetailBody({ call }: { call: ToolCall }) {
  const detail = call.detail;
  if (detail && detail.error) {
    return <ErrorCard detail={detail} />;
  }
  if (detail) {
    const Bespoke = BESPOKE[call.name];
    if (Bespoke) return <Bespoke detail={detail} />;
    return <GenericCard detail={detail} />;
  }
  // No detail (historical message / presenter-less tool with empty result):
  // fall back to the output string so nothing is lost and nothing errors.
  if (typeof call.output === "string" && call.output) {
    return <pre className="chat-tool-call-pre">{call.output}</pre>;
  }
  return null;
}
