/**
 * remark-mention.ts — remark 插件，将消息文本里的 <mention .../> inline HTML 节点
 * 转为带 data.hName/data.hProperties 的自定义 mdast 节点，供 remark-rehype 自动
 * 转换为 hast <span> 元素，再由 react-markdown components.span 渲染成 .chat-mention-chip。
 *
 * 管线路径（bugfix-413 决策 2）：
 *   remark-parse 把 <mention .../> 解析成 mdast `html` 节点
 *   → remarkMention 识别并替换为带 data.hName="span" + data.hProperties 的节点
 *   → remark-rehype 按 data.hName 自动生成 hast element（无需 allowDangerousHtml）
 *   → react-markdown components.span 捕获 data-* 属性渲染成 .chat-mention-chip
 *
 * 安全保证：不引 rehype-raw，只有明确匹配 MENTION_TAG_RE 的标签才被处理，
 * 其余 raw HTML（含 <script>）仍被 remark-rehype 默认转义为 `raw` 节点丢弃。
 *
 * 复用 MENTION_TAG_RE 保持与 mention-parser.ts 同步，避免两套解析 drift。
 */

import type { Root } from "mdast";
import type { Plugin } from "unified";
import { visit } from "unist-util-visit";

// Matches a complete self-closing mention tag (single node value).
// Attribute order (type before target_id) matches mention-parser.ts.
const MENTION_FULL_RE =
  /^<mention\s+type="(agent|user)"\s+target_id="([^"]+)"\s*\/>$/;

/**
 * remarkMention — remark (mdast) plugin.
 *
 * Visits every `html` node (inline raw HTML segments parsed by remark-parse).
 * When the node's value is exactly a mention self-closing tag, replaces it
 * with a custom mdast node carrying `data.hName`/`data.hProperties` so that
 * remark-rehype auto-generates a hast `<span>` element without allowDangerousHtml.
 */
export const remarkMention: Plugin<[], Root> = () => {
  return (tree: Root) => {
    visit(tree, "html", (node, index, parent) => {
      if (!parent || index === undefined) return;

      const m = MENTION_FULL_RE.exec(node.value.trim());
      if (!m) return;

      const mentionType = m[1]!;
      const targetId = m[2]!;

      // Replace html node with a custom node whose `data.hName` tells
      // remark-rehype to emit a <span> hast element with these properties.
      // This does not require rehype-raw or allowDangerousHtml.
      (parent.children as typeof parent.children)[index] = {
        type: "mentionNode" as "html",   // type field is opaque; hName drives output
        value: "",
        data: {
          hName: "span",
          hProperties: {
            "data-mention-target-id": targetId,
            "data-mention-type": mentionType,
          },
        },
      } as typeof node;
    });
  };
};
