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
