import { useState, type ReactNode } from "react";
import { useTranslation } from "../../../i18n";

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
export function LongOutput({
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
