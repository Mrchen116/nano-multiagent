# bugfix-413-M1: react-markdown-render — progress

### R1 — 安装依赖 + C1 红测试

- Context: 现有 `MarkdownContent` 是手写渲染器，无 heading/hr/blockquote/链接/嵌套列表分支，mention 靠 `renderInlineContent`（无法注入块级内容）。
- Decision: 安装 `react-markdown@^10.1.0` + `remark-gfm@^4.0.1`；在 `message-pane.test.tsx` 末尾追加块级渲染用例（7 条），验证当前失败点。
- Rationale: 先写红测试再实现，确保测试断言目标是用户可观察行为，不是实现细节。
- Evidence:
  - Tests: 7 新用例全红，37 现有用例全绿（基线保持）。
  - Entry: N/A（C1 阶段）
  - Frontend State Matrix: N/A（C1 阶段）
  - Browser QA: N/A（C1 阶段）
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: cbbd6bf（plan commit）
- Commits: C1=8303767
- Next: R2 实现

---

### R2 — 实现：remark-mention 插件 + MarkdownContent 换 ReactMarkdown

- Context: `<mention .../>` 被 remark-parse 解析为 mdast `html` 节点（不是 `text` 节点）。需要在 remark 层（mdast）用插件将 mention `html` 节点替换为带 `data.hName="span"` + `data.hProperties` 的自定义节点，让 remark-rehype 自动生成 hast `<span>` element，再由 `components.span` 捕获渲染为 `.chat-mention-chip`。
- Decision:
  1. 新建 `remark-mention.ts`：visit mdast `html` 节点，若完整匹配 `MENTION_FULL_RE`，替换为带 `data.hName="span"` + `data.hProperties["data-mention-target-id"]` 的节点（不引 rehype-raw，纯 mdast 改写）。
  2. 改写 `MarkdownContent`：内部换 `ReactMarkdown`（`remarkPlugins=[remarkGfm, remarkMention]`），`components.table` 保留 `.im-md-table` class，`components.span` 识别 `data-mention-target-id` 渲染 chip；删除 `splitMarkdownBlocks` / `renderTableBlock` / `renderInlineMarkdown` / 手写块级分派；`renderInlineContent` 保留（用户气泡 :400 仍调用）。
- Rationale: `data.hName`/`data.hProperties` 是 remark-rehype 官方机制（"Unknown node behavior" in remark-rehype docs），不依赖 rehype-raw，安全且无额外依赖。mention 用自定义 remark 插件在 mdast 层处理，与 rehype-raw XSS 面完全解耦。
- Evidence:
  - Tests: 全 44 条绿（含新增 7 条块级渲染用例 + 37 条现有回归）；全前端套件 395/395 绿。
  - Entry: vitest jsdom 完整链路渲染通过，块级结构/mention chip DOM 逐一断言。
  - Frontend State Matrix: heading/hr/blockquote/unclosed fence/nested list/link/raw HTML/<script> 转义/mention 在段落·标题·引用块·列表项内，全部覆盖。
  - Browser QA: 见 R3（样式 + 浏览器验收合并完成）
  - E2E/Regression: vitest 回归覆盖；现有 mention chip / 表格 / 围栏 / 用户气泡测试均保持绿。
  - Visual/Interaction: 见 R3
- Rollback: 8303767（R1 C1）
- Commits: C2=eefd5a9
- Next: R3 样式 + 构建验收

---

### R3 — 样式：.im-md h1~h6 / hr / blockquote / a；构建验收

- Context: react-markdown 输出标准 HTML tag，`.im-md` 已有 `p/ul/ol/pre/code` 样式，新 tag（h1~h6 / hr / blockquote / a）需补样式与气泡风格协调。
- Decision: 在 `global.css` `.im-md-table tbody tr:nth-child(even)` 后追加新 tag 样式；风格与现有气泡色板（oklch 蓝 `0.50 0.18 255`、边框灰 `0.82 0.01 240`）一致。
- Rationale: 只补新 tag 样式，不重写既有规则，最小化视觉回归面（决策 4）。
- Evidence:
  - Tests: 全前端套件 395/395 绿。
  - Entry: `npm run build` 通过，无 tsc 报错。
  - Frontend State Matrix: 样式视觉覆盖——heading 字重/大小协调；hr 细线；blockquote 左边框+灰色文字；a 蓝色下划线。
  - Browser QA: 浏览器验收（真实 Vite dev 入口）
    - 本地启动：`cd src/IM/frontend && npm run dev -- --port 5174 --strictPort`
    - 发送 agent 含 `## 标题`/`---`/`> 引用`/``` 代码块```/`@mention` 的消息，气泡渲染正确。
    - console error: 无
    - network failure: 无
    - **视觉核对**: 标题层级清晰，hr 细线，blockquote 左边框+灰文，链接蓝色可点，mention chip 保持蓝色高亮，表格样式不回归。
    - 用户气泡：行内渲染不变（renderInlineContent 路径保留）。
  - E2E/Regression: N/A（浏览器临时验收，非 E2E 体系落库；核心行为已通过 vitest 回归保护）
  - Visual/Interaction: 样式新增不引入既有测试回归；视觉验证见 Browser QA 段。
- bundle gzip 增量记录（design.md 预估 45–55 KB）：
  - 改写前（unit/bugfix-413 基线）：JS 167.62 kB gzip，CSS 14.02 kB gzip
  - 改写后（milestone/bugfix-413-M1）：JS 215.53 kB gzip，CSS 14.15 kB gzip
  - **增量：JS +47.91 kB gzip，CSS +0.13 kB gzip** — 在 design 预估范围内，可接受。
- Rollback: eefd5a9（R2 C2）
- Commits: C2=9473b8e（样式），C3=（本 docs commit）
- Next: 本 milestone 已完成，集成到 unit/bugfix-413 分支。
