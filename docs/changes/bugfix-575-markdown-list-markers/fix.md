# bugfix-575: 恢复聊天 Markdown 列表标记

## Relations

- Related: bugfix-413

## 原始报告

> 你怎么看出三点？是显示有bug嘛，我没看到左边有点

用户提供手机端群聊截图 `Photo 1.jpg`：Agent 的三条协作约定有缩进、无数字编号。随后要求：

> 提个git issues
> 反复提个unit修这个问题，单独提pr，后面我审核后先合入这个

关联 [Issue #318](https://github.com/Mrchen116/nano-multiagent/issues/318)。Agent 解读：建立独立 Bugfix lite，不依赖公司成员功能 PR #317，由用户审核、合入，不自动合并或部署。

## 现象 / 复现

Agent 回复正文包含 `1. 第一项`、`2. 第二项`、`3. 第三项` 三行 Markdown。手机聊天气泡只显示三段缩进文本，未显示编号。原始 `send_message` 正文已确认包含编号，缺陷在展示层。主分支也保留同一消息样式，不依赖 PR #317。

修复范围限定 `.im-md` 消息富文本内的列表呈现：有序列表显示正确编号（包括非 1 起始），无序列表显示圆点；长文本折行和嵌套列表可读；GFM 任务列表使用原有复选框，不增加重复圆点。桌面与手机都需真实渲染核验；页面导航等非 Markdown 列表保持原样。不改变消息内容、模型调用、权限或 Markdown 解析管线。

## 根因

Tailwind Preflight 的 `ol, ul, menu { list-style: none; }` 清除原生列表标记。`src/IM/frontend/src/styles/global.css` 的 `.im-md ul, .im-md ol` 只恢复 `padding-left: 1.1rem`，没有恢复列表类型，因而 ReactMarkdown 生成 `<ol>/<li>` 也无法显示编号。git blame 显示此样式块来自 `ec1106c0b2`；本轮并不把该提交认定为唯一回归点，因为 Tailwind reset 与解析器组合的历史演变尚未完整追溯。

原始意图见归档 bugfix-413 的 incident：Agent 回复使用可读的块级 Markdown，已有有序/无序列表、代码、表格和 mention 不能回归。当前缺陷在 DOM 结构正确时仍可存在，故只验证 `<ol>/<li>` 的测试无法证明标记可见。本修复保留现有解析器、消息复制和 mention 行为，仅补齐列表样式；验收以实际浏览器画面与计算样式为证。

## 修复

仅在消息 `.im-md` 下显式恢复 `ol` 的 decimal 和 `ul` 的 disc，针对 `.task-list-item` 保持 none，避免 GFM 复选框旁再出现圆点。不改共享 Preflight、解析器或全局导航列表。无 canonical spec delta：这是恢复既有 Markdown 列表呈现，不新增交互契约。

## 验证

真实浏览器已取得修前无编号、修后编号可见的同文案证据，并核验非1起始、嵌套、任务与普通项混排、长文本换行和非 Markdown 列表隔离。见 [证据](M1-fix/evidence/README.md)。使用已有消息组件与内容策略回归，不新增只锁定样式文本或 DOM 标签存在的测试。
