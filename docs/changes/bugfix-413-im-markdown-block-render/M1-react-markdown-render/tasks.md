# bugfix-413-M1: react-markdown-render

## 目标

把 `MarkdownContent` 内部块级渲染从手写渲染器换成 react-markdown + remark-gfm，根治标题/分隔线/引用块/未闭合代码围栏不渲染缺陷；通过自定义 remark-mention 插件保持 @mention 零回归。

## 退出标准（worker 轨）

- `npm run test`（vitest message-pane 套件）全绿，含新增块级渲染用例 + 保留的 mention chip / 表格 / 围栏回归用例
- `npm run build`（tsc + vite build）通过，记录 bundle gzip 增量
- mention 渲染产物 DOM 结构与改写前逐字一致（单测覆盖）
- 不引 rehype-raw；raw HTML 输入被转义不执行（单测覆盖含 `<script>` 的输入）

## 测试策略

| 字段 | 值 |
|---|---|
| 被测行为在哪个文件测 | 已有 `message-pane.test.tsx`，直接扩展 |
| 新建理由 | 无，扩展现有文件 |
| 新增 remark 插件放哪测 | 集成进 MessagePane 行为测试，不测插件内部实现 |
| 判据（半年后还跑吗） | 是——块级渲染和 mention 是核心行为，每次改渲染器都该跑 |

## UI 状态矩阵

| 状态 | 说明 |
|---|---|
| default（有消息） | agent 气泡含各类块级结构 |
| 纯文本 | 无任何 Markdown 标记，不回归 |
| mention 在块级内 | 标题/段落/列表项/引用块内含 mention |
| raw HTML 注入 | 含 `<script>` 标签，应被转义 |
| mobile viewport | N/A（单测不做 viewport，浏览器验收覆盖） |
| dark mode | N/A（本 unit 不加 dark mode 变量） |
| 用户气泡 | 行内渲染路径不受影响 |

## 用户路径分类

- `bug-regression`：块级 Markdown 渲染修复 + 现有表格/围栏回归

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 标题 ##/### 渲染 | vitest 断言 `<h2>`/`<h3>` 存在 | 是 |
| 分隔线 --- 渲染 | vitest 断言 `<hr>` 存在 | 是 |
| 引用块 > 渲染 | vitest 断言 `<blockquote>` 存在 | 是 |
| 未闭合围栏 | vitest 断言 `<pre><code>` 存在 | 是 |
| 嵌套列表 | vitest 断言 `<ul><li><ul>` | 是 |
| 行内链接 | vitest 断言 `<a href>` | 是 |
| mention 在段落内 | vitest 断言 chip DOM | 是 |
| mention 在标题内 | vitest 断言 chip DOM | 是 |
| mention 在引用块内 | vitest 断言 chip DOM | 是 |
| mention 在列表项内 | vitest 断言 chip DOM | 是 |
| raw HTML `<script>` 转义 | vitest 断言无 `<script>` 元素 | 是 |
| 表格不回归 | 现有用例保留 | 是 |
| 围栏空行不回归 | 现有用例保留 | 是 |
| mention chip 现有用例不回归 | 现有用例保留 | 是 |
| 用户气泡不回归 | 现有用例保留 | 是 |
| bundle gzip 增量 | npm run build 输出记录 | 否（progress.md 记录） |
| 浏览器视觉 | 真实浏览器手动验收 | 否（progress.md 记录截图） |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 安装依赖 + C1 红测试（块级渲染 + mention + raw HTML） | DONE |
| R2 | 实现：remark-mention 插件 + MarkdownContent 换 ReactMarkdown | DONE |
| R3 | 样式：.im-md 新增 h1~h6 / hr / blockquote / a；构建验收 | DONE |
