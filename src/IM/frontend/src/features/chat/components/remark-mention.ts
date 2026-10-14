/**
 * remark-mention.ts — remark 插件，将消息文本里的 <mention .../> 标签从 mdast
 * `html` 节点中切出，转为带 data.hName/data.hProperties 的节点序列，供 remark-rehype
 * 自动转换为 hast <span> 元素，再由 react-markdown components.span 渲染成 .chat-mention-chip。
 *
 * 管线路径（bugfix-413 决策 2）：
 *   remark-parse 把 <mention .../> 解析成 mdast `html` 节点
 *   → remarkMention 扫描节点 value，切出 mention 片段，替换为节点序列
 *   → remark-rehype 按 data.hName 自动生成 hast element（无需 allowDangerousHtml）
 *   → react-markdown components.span 捕获 data-* 属性渲染成 .chat-mention-chip
 *
 * 安全保证：不引 rehype-raw，只有匹配 MENTION_TAG_RE_SOURCE 的标签才被处理，
 * 其余 raw HTML（含 <script>）仍被 remark-rehype 默认丢弃，不执行。
 *
 * 正则共源：从 mention-parser.ts 导入 MENTION_TAG_RE_SOURCE，避免两套解析 drift。
 *
 * type-7 html block 处理：remark-parse 在 mention 独占首行紧跟非空行时会把该行
 * 及后续文本打包进同一个 html 节点（CommonMark type-7 block）。旧的全锚 ^ $ 正则
 * 在此场景失配，本实现改为全局扫描节点 value，正确切出任意位置的 mention 标签。
 */

import type { Root, Html, RootContent, PhrasingContent } from "mdast";
import type { Plugin } from "unified";
import { visit } from "unist-util-visit";

import { MENTION_TAG_RE_SOURCE } from "./mention-parser";

// Global variant of the shared mention regex — scans across full html node values.
const MENTION_GLOBAL_RE = new RegExp(MENTION_TAG_RE_SOURCE.source, "g");

/** Build the replacement node array for one html node's value.
 *
 * Splits node.value on MENTION_GLOBAL_RE into alternating text and mention
 * nodes, mirroring parseMentions' split semantics. Each mention becomes a
 * node with data.hName="span" so remark-rehype auto-emits a hast element.
 * Other content remains literal text, allowing later prose plugins to handle
 * its line breaks while keeping arbitrary HTML escaped.
 */
function splitHtmlNodeIntoMentionNodes(value: string): PhrasingContent[] {
  const nodes: PhrasingContent[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  MENTION_GLOBAL_RE.lastIndex = 0;
  while ((match = MENTION_GLOBAL_RE.exec(value)) !== null) {
    if (match.index > last) {
      nodes.push({ type: "text", value: value.slice(last, match.index) });
    }
    nodes.push({
      type: "html",
      value: "",
      data: {
        hName: "span",
        hProperties: {
          "data-mention-target-id": match[2],
          "data-mention-type": match[1],
        },
      },
    } as Html);
    last = match.index + match[0].length;
  }

  if (last < value.length) {
    nodes.push({ type: "text", value: value.slice(last) });
  }

  return nodes;
}

/**
 * remarkMention — remark (mdast) plugin.
 *
 * Visits every `html` node. When the node's value contains one or more mention
 * tags (anywhere in the value, including type-7 html block scenarios where the
 * mention line and following prose are packed into one node), splits the node
 * into the appropriate sequence and splices the replacements into parent.children.
 */
export const remarkMention: Plugin<[], Root> = () => {
  return (tree: Root) => {
    visit(tree, "html", (node: Html, index, parent) => {
      if (!parent || index === undefined) return;

      // Fast path: no mention tag in value.
      MENTION_GLOBAL_RE.lastIndex = 0;
      if (!MENTION_GLOBAL_RE.test(node.value)) return;

      const phrasing = splitHtmlNodeIntoMentionNodes(node.value);
      // A standalone mention creates an HTML block. Keep its prose in one
      // paragraph so line breaks do not become separate grid items.
      const replacements: RootContent[] = parent.type === "root"
        ? [{ type: "paragraph", children: phrasing }]
        : phrasing;

      // Splice replacements into parent.children at current index.
      (parent.children as RootContent[]).splice(index, 1, ...replacements);

      // Advance past all inserted nodes so visit doesn't revisit them.
      return index + replacements.length;
    });
  };
};
