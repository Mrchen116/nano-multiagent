# Verification Report: bugfix-413

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 tasks complete; all spec requirements covered |
| Correctness | 11/11 scenarios covered with tests |
| Coherence | 有偏离（决策 2 字面要求"复用 MENTION_TAG_RE"，实现为独立副本） |

No critical issues. 1 warning, 1 suggestion. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 3/3 complete**

| Roadpoint | 状态 |
|---|---|
| R1 — 安装依赖 + C1 红测试 | DONE |
| R2 — remark-mention 插件 + MarkdownContent 换 ReactMarkdown | DONE |
| R3 — 样式 + 构建验收 | DONE |

**Spec 覆盖（两条 Requirement 全覆盖）：**

- Requirement: agent 回复的块级 Markdown 正确渲染 — 有实现（`message-pane.tsx:460-518`）
- Requirement: 用户自己消息渲染不变 — 有实现（`message-pane.tsx:402-404`，`renderInlineContent` 保留）

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 标题渲染成层级标题（`##`/`###` → `<h2>`/`<h3>`） | `message-pane.tsx:460-518`，react-markdown 原生支持 | `message-pane.test.tsx:732-756`（两条用例，全绿） | covered |
| 分隔线渲染成横线（`---` → `<hr>`） | react-markdown + remark-gfm 原生处理 | `message-pane.test.tsx:757-769` | covered |
| 闭合代码围栏渲染成代码块 | react-markdown 原生 | `message-pane.test.tsx:132`（保留既有用例，绿） | covered |
| 未闭合代码围栏（CommonMark 默认行为） | react-markdown 原生 | `message-pane.test.tsx:784-796`（全绿） | covered |
| 引用块渲染（`>` → `<blockquote>`） | react-markdown 原生 | `message-pane.test.tsx:771-782` | covered |
| 嵌套列表渲染 | remark-gfm 支持 | `message-pane.test.tsx:797-810`（断言 `ul ul` 存在） | covered |
| 行内链接渲染（`[t](url)` → `<a>`） | react-markdown 原生 | `message-pane.test.tsx:812-825` | covered |
| @mention 在块级内容内仍渲染 | `remark-mention.ts`（mdast 层处理）+ `components.span`（`message-pane.tsx:482-505`） | `message-pane.test.tsx:856-918`（段落/标题/引用块/列表项内各一条，全绿） | covered |
| 已支持构造不回归（表格/列表/bold/inline code） | react-markdown + remark-gfm 承接 | `message-pane.test.tsx:87-130`（表格）、`132-174`（围栏空行）、保留全部现有用例（395/395 绿） | covered |
| 纯文本回复不变 | react-markdown 对纯文本输出 `<p>` 不改内容 | `message-pane.test.tsx:73-85`（现有"Hi back"用例，绿） | covered |
| 用户消息保持行内渲染 + @mention 编辑链路不变 | `message-pane.tsx:403`（`renderInlineContent` 路径保留）；composer 链路不动 | `message-pane.test.tsx:334-396`（composer mention 选取/发送/删除三条，全绿） | covered |

**测试套件整体状态：** 395/395 绿，0 失败（vitest 3.2.4，jsdom 环境）

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1：换 react-markdown + remark-gfm，删手写渲染器 | 是 | `package.json:24-26`（新增依赖）；`message-pane.tsx:460-518`（ReactMarkdown 替换 MarkdownContent 内部）；`splitMarkdownBlocks` / `renderTableBlock` / `renderInlineMarkdown` 手写分支已全部删除 |
| 决策 2：@mention 经自定义 remark 插件接入，复用既有正则 | **部分**（见 WARNING） | `remark-mention.ts:24`（`MENTION_FULL_RE`）；未 import `mention-parser.ts` 的 `MENTION_TAG_RE` |
| 决策 3：不引 rehype-raw，raw HTML 走默认转义 | 是 | `package.json` 无 `rehype-raw`；`message-pane.tsx:458` 注释确认；测试 `message-pane.test.tsx:827-838`（`<script>` 转义，绿） |
| 决策 4：复用 `.im-md` 容器 + 新增 h1~h6/hr/blockquote/a 样式 | 是 | `global.css:1618-1665`（四类新样式）；既有 `p/ul/ol/pre/code/table` 规则保留不变 |
| renderInlineContent 保留供用户气泡使用 | 是 | `message-pane.tsx:403`（用户气泡仍调 `renderInlineContent`）；`message-pane.tsx:525-564`（函数保留） |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1: design 决策 2 要求"复用 MENTION_TAG_RE"，实现为独立副本正则，存在 drift 风险**

- 位置：`src/IM/frontend/src/features/chat/v2/components/remark-mention.ts:24`
- 现象：`remark-mention.ts` 定义了自己的 `MENTION_FULL_RE`（`/^<mention\s+type="(agent|user)"\s+target_id="([^"]+)"\s*\/>$/`），未 import `mention-parser.ts` 的 `MENTION_TAG_RE`。
- 风险：design 决策 2 的核心动机是"避免两套 mention 解析 drift"——若日后 `mention-parser.ts` 的 mention 格式演进（如新增 `display_name` 属性），`remark-mention.ts` 不会自动跟进。功能上当前两正则等价（`MENTION_FULL_RE` 加了 `^$` 锚点，适配 remark 单节点值），但维护约定被打破。
- 建议修法：在 `remark-mention.ts` 从 `mention-parser.ts` import 并复用 `MENTION_TAG_RE`（或将共享正则 export 为不带 `g` flag 的版本），再在 `MENTION_FULL_RE` 的逻辑里组合 `^` / `$` 锚点；或在文件内注明"与 MENTION_TAG_RE 刻意同步，若 mention 格式变更须同步改此处"。具体：
  ```ts
  // remark-mention.ts
  // 从 mention-parser.ts export MENTION_TAG_BASE_RE（无 g flag）
  import { MENTION_TAG_BASE_RE } from "./mention-parser";
  const MENTION_FULL_RE = new RegExp(`^${MENTION_TAG_BASE_RE.source}$`);
  ```

### SUGGESTION（可以修）

**S1: `MarkdownContent` 注释中把 `remarkMention` 误写成 `rehypeMention`**

- 位置：`src/IM/frontend/src/features/chat/v2/components/message-pane.tsx:454`
- 现象：注释写 "@mention 经 **rehypeMention** 插件在 hast 层切出"，但实际插件是 `remarkMention`，工作在 **mdast 层**（remark 层，不是 rehype 层）。这是本 unit 核心安全保证（不经过 rehype-raw），注释层描述错误会误导维护者。
- 建议修法：将 `message-pane.tsx:454` 改为：
  "@mention 经 **remarkMention** 插件在 **mdast** 层切出，注入带 data-* 属性的 `<span>`，..."

---

No critical issues. 1 warning, 1 suggestion. Ready for PR (with noted improvements).
