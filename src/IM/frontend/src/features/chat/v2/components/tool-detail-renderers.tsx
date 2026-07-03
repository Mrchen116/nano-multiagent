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

import { useState, type ReactNode } from "react";

import { useTranslation } from "../../../../i18n";
import type { ToolCall, ToolDetail } from "../chat-types";

function str(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

/**
 * Unwrap a tool-call error field that may be a plain string (in-band failures:
 * output.error) or a {message} wrapper (out-of-band: result.error). feat-409
 * Round-1 fix — agent in-band failures carry a bare string.
 */
function errorText(error: unknown): string {
  if (typeof error === "object" && error !== null && "message" in error) {
    return str((error as { message?: unknown }).message);
  }
  return str(error);
}

// 决策 5: front-end truncation threshold — an independent visual gate from the
// kernel's 256KB byte cap. Above this line count, long fields collapse to a
// preview + "expand all" → height-capped inner scroll, so a single expand never disrupts
// the chat list scroll.
const LONG_OUTPUT_LINE_THRESHOLD = 50;

/**
 * Two-level expand for a large text field. Short text renders inline. Long text
 * shows a line-clamped preview with an "expand all" toggle; expanded, it scrolls
 * inside a height-capped container with a "collapse" toggle. `truncatedAtSource`
 * (detail.truncated) appends a note that the kernel already tail-truncated.
 *
 * `render` lets callers choose the inner element (a `<pre>` terminal block, a
 * plain excerpt div, …) while sharing the truncate/scroll/note chrome.
 */
function LongOutput({
  text,
  truncatedAtSource,
  className,
  render
}: {
  text: string;
  truncatedAtSource?: boolean;
  className?: string;
  render: (shownText: string) => ReactNode;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const lines = text.split("\n");
  const isLong = lines.length > LONG_OUTPUT_LINE_THRESHOLD;
  const shown = !isLong || expanded ? text : lines.slice(0, LONG_OUTPUT_LINE_THRESHOLD).join("\n");
  const containerCls = [
    "chat-tool-long-output",
    expanded ? "chat-tool-long-output--expanded" : "",
    className ?? ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="chat-tool-long-output-wrap">
      <div className={containerCls}>{render(shown)}</div>
      {truncatedAtSource && (
        <div className="chat-tool-long-output-source-note">
          {t("chat.messagePane.toolDetail.truncatedAtSource")}
        </div>
      )}
      {isLong && (
        <button
          type="button"
          className="chat-tool-long-output-toggle"
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded
            ? t("chat.messagePane.toolDetail.collapse")
            : // feat-409 protoalign (BUG2): truncated hint carries the total line
              // count so the user knows how much is hidden (prototype: 「… 已截断，
              // 共 N 行（点击展开全部）」), not just a bare "expand all".
              t("chat.messagePane.toolDetail.expandAll", { count: lines.length })}
        </button>
      )}
    </div>
  );
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
  // detail.error may be a {message} wrapper (out-of-band: result.error) or a
  // plain string (in-band: output.error). Tolerate both; fall back to
  // detail.message.
  const message = errorText(detail.error) || str(detail.message);
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
  const truncated = detail.truncated === true;
  // feat-409 failalign: out-of-band bash failures carry no stdout/stderr/exit —
  // only command + error. Render the error in the stderr slot so the terminal
  // block still shows what went wrong (it appears exactly once, here).
  const error = errorText(detail.error);
  return (
    <div className="chat-tool-detail-term">
      <div className="chat-tool-detail-term-cmd">{command}</div>
      {stdout && (
        <LongOutput
          text={stdout}
          truncatedAtSource={truncated}
          render={(shown) => <pre className="chat-tool-detail-term-out">{shown}</pre>}
        />
      )}
      {stderr && (
        <LongOutput
          text={stderr}
          render={(shown) => (
            <pre className="chat-tool-detail-term-out chat-tool-detail-term-err">{shown}</pre>
          )}
        />
      )}
      {!stderr && error && (
        <pre className="chat-tool-detail-term-out chat-tool-detail-term-err">{error}</pre>
      )}
      {typeof exit === "number" && (
        <div className="chat-tool-detail-term-meta">
          <span className={exit !== 0 ? "chat-tool-detail-exit-bad" : undefined}>exit {exit}</span>
        </div>
      )}
    </div>
  );
}

// ─── edit → colourised unified diff ──────────────────────────────────────────

function diffLineClass(line: string): string {
  if (line.startsWith("+")) return "chat-tool-detail-diff-add";
  if (line.startsWith("-")) return "chat-tool-detail-diff-del";
  if (line.startsWith("@@")) return "chat-tool-detail-diff-hunk";
  return "chat-tool-detail-diff-ctx";
}

function DiffCard({ detail }: { detail: ToolDetail }) {
  const path = str(detail.path);
  const diff = str(detail.diff);
  // Drop unified-diff file headers; the path is already shown above.
  const bodyLines = diff.split("\n").filter((l) => !l.startsWith("+++") && !l.startsWith("---"));
  return (
    <div className="chat-tool-detail-diff">
      {path && <div className="chat-tool-detail-diff-file">{path}</div>}
      <LongOutput
        text={bodyLines.join("\n")}
        truncatedAtSource={detail.truncated === true}
        render={(shown) => (
          <div className="chat-tool-detail-diff-body">
            {shown.split("\n").map((line, i) => (
              <div key={i} className={`chat-tool-detail-diff-line ${diffLineClass(line)}`}>
                {line || " "}
              </div>
            ))}
          </div>
        )}
      />
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
      <LongOutput
        text={content}
        truncatedAtSource={detail.truncated === true}
        render={(shown) => <pre className="chat-tool-call-pre">{shown}</pre>}
      />
    </div>
  );
}

// ─── web_fetch → url + status + content card (feat-425 决策 4) ────────────────
// 去掉恒空的 title(工具从不返回);展开显 URL + 状态码 + 抓到的正文(修 #131 空正文)。

function WebCard({ detail }: { detail: ToolDetail }) {
  const url = str(detail.final_url || detail.url);
  const status = detail.status;
  const content = str(detail.content);
  return (
    <div className="chat-tool-detail-web">
      <div className="chat-tool-detail-web-url">
        {url}
        {status != null && ` · ${status}`}
      </div>
      {content && (
        <LongOutput
          text={content}
          truncatedAtSource={detail.truncated === true}
          render={(shown) => <div className="chat-tool-detail-web-excerpt">{shown}</div>}
        />
      )}
    </div>
  );
}

// ─── web_search → result-entry list card (feat-425 决策 5) ────────────────────

interface SearchResult {
  title?: unknown;
  url?: unknown;
  snippet?: unknown;
}

type ToolDetailCardProps = {
  detail: ToolDetail;
  isResultPending?: boolean;
};

function WebSearchCard({ detail, isResultPending = false }: ToolDetailCardProps) {
  const { t } = useTranslation();
  const query = str(detail.query);
  const rawResults = Array.isArray(detail.results) ? (detail.results as SearchResult[]) : [];
  if (rawResults.length === 0) {
    if (isResultPending && query) {
      return (
        <div className="chat-tool-detail-search">
          <div className="chat-tool-detail-search-title">{query}</div>
        </div>
      );
    }
    // 空态:明确"无结果"文案,而非空白或原始字符串。
    return (
      <div className="chat-tool-detail-search">
        <div className="chat-tool-detail-search-empty">
          {t("chat.messagePane.toolDetail.searchNoResults")}
        </div>
      </div>
    );
  }
  return (
    <div className="chat-tool-detail-search">
      {rawResults.map((r, i) => {
        const title = str(r.title);
        const url = str(r.url);
        const snippet = str(r.snippet);
        return (
          <div key={i} className="chat-tool-detail-search-item">
            {title && <div className="chat-tool-detail-search-title">{title}</div>}
            {/* URL 纯文本展示(可手动复制),不做可点击跳转(spec 非目标:外链安全面)。 */}
            {url && <div className="chat-tool-detail-search-url">{url}</div>}
            {snippet && <div className="chat-tool-detail-search-snippet">{snippet}</div>}
          </div>
        );
      })}
    </div>
  );
}

// ─── agent → full prompt BEFORE result (spec) ────────────────────────────────

function AgentCard({ detail, isResultPending = false }: ToolDetailCardProps) {
  const { t } = useTranslation();
  const prompt = str(detail.prompt);
  const subagent = str(detail.subagent_type);
  const status = str(detail.status);
  const content = str(detail.content);
  const outputFile = str(detail.output_file);
  const error = errorText(detail.error);
  return (
    <div className="chat-tool-detail-agent">
      {prompt && (
        <Section label={t("chat.messagePane.toolDetail.agentPromptLabel")}>
          <div className="chat-tool-detail-agent-prompt">{prompt}</div>
        </Section>
      )}
      {!isResultPending && (
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
      )}
    </div>
  );
}

// ─── read → path + line range (failures show path + error, red) ──────────────

function ReadCard({ detail }: { detail: ToolDetail }) {
  const { t } = useTranslation();
  const path = str(detail.path);
  // feat-409 readfix: read 失败态最易丢路径——截图实证里只剩 "file does not
  // exist | 0 lines"。失败时优先把 path 顶在前,再走失败样式(✕ + 错误文本)。
  const error = errorText(detail.error);
  if (error) {
    return (
      <div className="chat-tool-detail-info chat-tool-detail-info--failed">
        <div className="chat-tool-detail-info-head">✕ {path}</div>
        <pre className="chat-tool-call-pre">{error}</pre>
      </div>
    );
  }
  // feat-409 protoalign: read 展开态对齐原型的 .term 单行风格
  // (`<path> · 86 行 · 读取 1-86`),而非旧 info 卡的两行 ✓path + meta。
  // 把路径与行计数/范围/图片/未变更等片段用 · 串成一行,空片段省略。
  const parts: string[] = [path].filter(Boolean);
  if (detail.image === true) {
    parts.push(t("chat.messagePane.toolDetail.readImage"));
  } else if (detail.unchanged === true) {
    parts.push(t("chat.messagePane.toolDetail.readUnchanged"));
  } else {
    const total = detail.total_lines;
    const offset = detail.offset;
    const limit = detail.limit;
    // cr4: total_lines 缺失时不伪造 "0 行"——省略行计数(只显路径)。
    if (typeof total === "number") {
      parts.push(t("chat.messagePane.toolDetail.readLines", { count: total }));
    }
    if (typeof limit === "number" && typeof offset === "number") {
      parts.push(
        t("chat.messagePane.toolDetail.readLineRange", {
          from: offset,
          to: offset + limit - 1
        })
      );
    }
  }
  return (
    <div className="chat-tool-detail-term">
      <div className="chat-tool-detail-term-out">{parts.join(" · ")}</div>
    </div>
  );
}

// ─── memory / skill_manage / task_stop → compact info cards ──────────────────

function MemoryCard({ detail, isResultPending = false }: ToolDetailCardProps) {
  const { t } = useTranslation();
  const action = str(detail.action);
  const target = str(detail.target);
  const content = str(detail.content);
  const message = str(detail.message);
  // Round-3 fix: memory never raises — failures come back as success:false with
  // the reason in `message`. Render a failure state (✕ + error text), not ✓.
  const failed = detail.success === false;
  if (failed) {
    return (
      <div className="chat-tool-detail-info chat-tool-detail-info--failed">
        <div className="chat-tool-detail-info-head">✕ {message || str(detail.error)}</div>
      </div>
    );
  }
  if (isResultPending) {
    return (
      <div className="chat-tool-detail-info">
        <div className="chat-tool-detail-info-head">
          {[action, target].filter(Boolean).join(" · ")}
        </div>
        {content && <div className="chat-tool-detail-info-body">{content}</div>}
      </div>
    );
  }
  return (
    <div className="chat-tool-detail-info">
      <div className="chat-tool-detail-info-head">
        ✓ {message || t("chat.messagePane.toolDetail.memoryDone", { target })}
      </div>
      {/* minor: surface what was written — action + target, then the content. */}
      <div className="chat-tool-detail-info-meta">
        {action}
        {target && ` · ${target}`}
      </div>
      {content && <div className="chat-tool-detail-info-body">{content}</div>}
    </div>
  );
}

function SkillCard({ detail, isResultPending = false }: ToolDetailCardProps) {
  const action = str(detail.action);
  const name = str(detail.name);
  const message = str(detail.message);
  const path = str(detail.path);
  const failed = detail.success === false;
  if (failed) {
    return (
      <div className="chat-tool-detail-info chat-tool-detail-info--failed">
        <div className="chat-tool-detail-info-head">
          ✕ {[action, name].filter(Boolean).join(" ")}
        </div>
        <div className="chat-tool-detail-info-body">{message || str(detail.error)}</div>
      </div>
    );
  }
  if (isResultPending) {
    return (
      <div className="chat-tool-detail-info">
        <div className="chat-tool-detail-info-head">{[action, name].filter(Boolean).join(" ")}</div>
      </div>
    );
  }
  return (
    <div className="chat-tool-detail-info">
      {/* minor: show the skill name + action explicitly, not just ✓. */}
      <div className="chat-tool-detail-info-head">✓ {[action, name].filter(Boolean).join(" ")}</div>
      {message && <div className="chat-tool-detail-info-meta">{message}</div>}
      {path && <div className="chat-tool-detail-info-body">{path}</div>}
    </div>
  );
}

function SkillViewCard({ detail }: { detail: ToolDetail }) {
  const name = str(detail.name);
  const location = str(detail.location);
  const content = str(detail.content);
  const error = errorText(detail.error) || str(detail.message);
  const failed = detail.success === false;
  if (failed) {
    return (
      <div className="chat-tool-detail-info chat-tool-detail-info--failed chat-tool-detail-skill-view">
        <div className="chat-tool-detail-info-head">✕ {name}</div>
        {error && <div className="chat-tool-detail-info-body">{error}</div>}
      </div>
    );
  }
  return (
    <div className="chat-tool-detail-skill-view">
      {name && (
        <Section label="name">
          <div className="chat-tool-detail-info-body">{name}</div>
        </Section>
      )}
      {location && (
        <Section label="location">
          <div className="chat-tool-detail-info-meta">{location}</div>
        </Section>
      )}
      {content && (
        <Section label="content">
          <LongOutput
            text={content}
            truncatedAtSource={detail.truncated === true}
            render={(shown) => <pre className="chat-tool-call-pre">{shown}</pre>}
          />
        </Section>
      )}
    </div>
  );
}

function TaskStopCard({ detail, isResultPending = false }: ToolDetailCardProps) {
  const taskId = str(detail.task_id);
  const status = str(detail.status);
  if (isResultPending) {
    return (
      <div className="chat-tool-detail-info">
        <div className="chat-tool-detail-info-head">{taskId}</div>
      </div>
    );
  }
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

const BESPOKE: Record<string, (p: ToolDetailCardProps) => ReactNode> = {
  read: ReadCard,
  bash: BashCard,
  edit: DiffCard,
  write: WriteCard,
  web_fetch: WebCard,
  web_search: WebSearchCard,
  agent: AgentCard,
  memory: MemoryCard,
  skill_manage: SkillCard,
  skill_view: SkillViewCard,
  task_stop: TaskStopCard
};

/**
 * A detail is "error-only" when its single meaningful key is `error` (besides
 * the `truncated` flag). bash/edit/web out-of-band failures carry just
 * `{error:{message}}` → ErrorCard. agent in-band failures carry the full schema
 * (prompt/status/error/…) → their bespoke card, so the prompt — most valuable on
 * failure — is preserved.
 */
function isErrorOnly(detail: ToolDetail): boolean {
  if (detail.error == null) return false;
  return Object.entries(detail).every(
    ([key, value]) => key === "error" || key === "truncated" || value == null || value === ""
  );
}

function hasValue(detail: ToolDetail, key: string): boolean {
  const value = detail[key];
  return value != null && value !== "";
}

function hasAnyValue(detail: ToolDetail, keys: string[]): boolean {
  return keys.some((key) => hasValue(detail, key));
}

function hasTerminalDetail(name: string, detail: ToolDetail): boolean {
  switch (name) {
    case "web_search":
      return Object.prototype.hasOwnProperty.call(detail, "results") || hasAnyValue(detail, ["error", "message"]);
    case "agent":
      return hasAnyValue(detail, ["status", "content", "output_file", "error", "agent_id"]);
    case "memory":
      return detail.success != null || hasAnyValue(detail, ["message", "error"]);
    case "skill_manage":
      return detail.success != null || hasAnyValue(detail, ["message", "path", "error"]);
    case "skill_view":
      return detail.success != null || hasAnyValue(detail, ["name", "location", "content", "error", "message"]);
    case "task_stop":
      return hasAnyValue(detail, ["status", "error", "message"]);
    default:
      return true;
  }
}

function isResultPending(call: ToolCall, detail: ToolDetail): boolean {
  if (call.status === "running") return true;
  return call.status === "failed" && !hasTerminalDetail(call.name, detail);
}

/**
 * Render the expanded body for a tool call. Error-only details (out-of-band
 * failures) show the generic error card. Known names get bespoke cards (which
 * render their own failure state, keeping prompt/status/etc.); unknown tools with
 * a detail get the generic key/value card; rows without detail degrade to the
 * raw output string (historical messages).
 */
export function ToolDetailBody({ call }: { call: ToolCall }) {
  const detail = call.detail;
  if (detail && isErrorOnly(detail)) {
    return <ErrorCard detail={detail} />;
  }
  if (detail) {
    const Bespoke = BESPOKE[call.name];
    if (Bespoke) return <Bespoke detail={detail} isResultPending={isResultPending(call, detail)} />;
    return <GenericCard detail={detail} />;
  }
  // No detail (historical message / presenter-less tool with empty result):
  // fall back to the output string so nothing is lost and nothing errors.
  if (typeof call.output === "string" && call.output) {
    return <pre className="chat-tool-call-pre">{call.output}</pre>;
  }
  return null;
}
