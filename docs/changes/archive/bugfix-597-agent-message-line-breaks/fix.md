# bugfix-597: Agent 消息保留换行并继续支持 Markdown

## Relations

- Related: bugfix-413

## 原始报告

> 他明明有换行，为啥发出来没看到换行

附件为用户提供的 Web IM 原生轨迹截图，`send_message` 的 `text` 参数包含换行和 `•` 条目。

> 修一下，Agent 消息里的换行要正常显示，同时保留 Markdown 支持。

## 现象 / 复现

Agent 发布含普通换行的正文时，Web IM 将同段内的多行合并显示。例如 `你可以找我：\n• 理思路\n• 做功课` 显示为连续文本，而用户消息保留换行。当前 Markdown 管线可复现：输入含单换行，渲染结果仍为一个没有显式换行的段落。

验收范围为 Web IM 中 Agent 正文：普通换行可见、空行继续分段，已有标题、强调、链接、列表、引用、表格、代码块和 mention 继续正常显示；显式 Markdown 换行不能重复成空行，代码块保留原内容。实时消息与历史消息共用同一显示规则。不修改消息发送协议、存储内容或其他客户端。

## 根因

`send_message` 经 PA 转发正文，IM 只 trim 首尾后持久化，不删除正文内的换行。Web 消息组件对真人消息启用 `white-space: pre-wrap`，而 Agent 正文进入 `react-markdown`、`remark-gfm` 与 mention 插件。普通单换行保留为文本节点中的软换行，没有转为显式换行；浏览器按默认空白规则折叠它。`•` 本身不是 Markdown 列表标记，因此该写法不能借列表结构分行。

引入该管线的 bugfix-413（实现提交 `7593a8b41d`）旨在统一支持块级 Markdown，替代逐项补丁的手写解析器，并保留 mention 和 HTML 安全边界。该次迁移及后续测试保护了 Markdown 结构，但没有覆盖聊天中普通换行的显示需求。当前 `docs/specs/im/web-chat-ux.md` 尚未声明 Agent 普通换行的显示规则，本次按用户明确要求补齐。修复必须保留现有 Markdown 解析和原始 HTML 不执行的约束。

独立审查补充确认：mention 独占首行且后面没有空行时，CommonMark 将整段识别为 HTML block；原 mention 插件仍用 HTML 节点承接后续普通正文，导致它直到 ReactMarkdown 最后转义时才变成文本，绕过了换行转换。

## 修复

实现提交 `762d4a463` 在既有 remark 管线中加入 `remark-breaks` 4.0.0，将正文软换行转换为可见换行；Markdown 块结构、mention 插件和 HTML 安全边界沿用现有实现。依赖及锁文件同步更新，新增两个包，不做字符串替换或 CSS 空白规则扩张。用户消息与消息数据无变更。

审查修正使 mention 插件拆出的普通正文及早成为文本节点，并将独占首行的 mention block 收束为一个段落；换行插件在 mention 插件之后执行。任意 HTML 仍作为字面文本转义，避免根级换行节点被 grid 排成额外空行。同步修正 IM spec 索引的 Requirement 数量。

已将用户可观察规则归并到 `docs/specs/im/web-chat-ux.md`。本 unit 保持唯一 `M1-fix`。

## 验证

- Red：通过 Vitest CLI 执行新增换行用例，期望同段内两个换行，修前实际为零；两种既有 Markdown hard break 用例通过。
- Green：`message-pane.test.tsx` 97 个测试通过；普通换行、分段、强调与链接共同显示，行末两个空格和反斜线两种 hard break 均只产生一次换行。
- 审查回归：扩展既有 type-7 mention 用例，修前没有段落及可见换行而失败；修后 mention chip 与后续两行同属一个段落，两个换行均可见。修正后重跑消息组件及前端全量测试和构建。
- mention 真实浏览器复验：按现行 `type="user"` wire 格式预置首行 mention，聊天页显示 chip、第一行、第二行三个连续行，未出现额外空行；同页的普通正文和 Markdown 继续正确显示。
- 前端全量：92 个文件、862 个测试通过；`npm run build` 通过，`npm audit --audit-level=critical` 为零漏洞。构建仅有既存的 chunk 大小与动态导入提示。
- 其他本地 CI 等价检查：`pnpm install --frozen-lockfile`、`pnpm build`、`pnpm typecheck`、后端 74 个文件 / 272 个测试、Python 非 E2E 56 个测试、ruff check / format、docs-check 和 diff-check 通过。
- 真实浏览器：以分支生产构建启动隔离 IM，使用专用本地账号和数据库，在真实 `/chat/<id>` 页面读取与截图同结构的 Agent 正文，四个 `•` 条目逐行显示。另核对标题、加粗、链接、Markdown 列表、表格及带空行和缩进的代码块。通过真实 user-stream 发布一条两行消息，实时读取和刷新后 `innerText` 均为 `实时换行第一行\n实时换行第二行 加粗`。
- 浏览器验证使用本地预置 Agent 消息，没有调用真实模型或部署生产；验证后关闭临时页面与 IM 进程，端口 55936 已释放。截图及临时数据库留在本地验收产物中，不提交到仓库。
- 测试归属：扩展现有 `message-pane.test.tsx` 的 Markdown 渲染用例，守护同一个聊天正文 seam；保留已有列表、表格、mention、HTML 安全和 fenced code 覆盖，不新增重复测试文件。

独立代码审查和最终集成版本见同目录 `code-review.md`；iOS 未改动，适用远端 CI 仍须通过后交付。
