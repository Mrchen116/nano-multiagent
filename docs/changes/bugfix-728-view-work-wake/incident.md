# bugfix-728: View Work 定位产生回复的唤醒

> 快速开发事后记录；active，尚待用户亲自试用确认，不作已验收归档。

## Relations

- Related: feat-727
- Issue: https://github.com/Mrchen116/nano-multiagent/issues/473

## 原始报告

用户交办原话：

> https://github.com/Mrchen116/nano-multiagent/issues/473 然后这个问题是个相对明确的问题，走快修模式把它解决。

Issue #473 原文：

## 使用场景

在 Web IM 里看到一条 Global Agent 回复，想查看它当时处理了哪些输入、调用了哪些工具、如何派工。

## 当前行为

点击回复气泡里的 **View Work** 会打开该 Agent 的 Work 页面。页面没有定位或展开产生这条回复的唤醒记录。一个 Agent 有多次同名的 **Inbox wake-up** 时，要对照聊天时间逐条找、逐条展开。

## 期望行为

点击 **View Work** 后，进入对应 Agent 的 Work 页面，自动滚动到产生这条回复的那次唤醒，并展开该记录，直接看到执行和工具调用。

## 验收

- 用同一个 Global Agent 生成多次 **Inbox wake-up**，其中至少两次分别发出聊天回复。
- 分别点击两条回复的 **View Work**，验证每次都进入同一个 Agent 的 Work 页面，并定位、展开各自对应的唤醒。
- 对较早的回复重复验证，确认能定位到它对应的历史记录。

## 澄清记录

- 用户明确选择快修；不增加事前大设计。
- 本事项授权源码、独立工作区、验证、分支和 PR，不包括合并或生产部署。
- 用户需要可真实点击的隔离试用入口；Agent 自测不替代用户亲自验收。

## 现象与复现

同一 Global Agent 有多次发信轮次时，从任一回复的 View Work 进入相同、不含消息锚点的 Work URL；初始查询只显示最新 20 轮，展开状态与该回复没有关联。

## 影响范围

Web Global Agent 回复到 Work 的追溯操作，包括历史回复。无聊天数据损坏，不改变 iOS、Agent 输入、执行或发送权限。

## 根因分析（RCA）

`message-pane.tsx` 仅将 Agent 身份写入链接。`AgentWorkPanel` 不消费消息锚点，初次 Work 查询只能从最新页开始，展开状态仅来自 sessionStorage。已有 journal 的 `message_sent` 明确保存真实 message ID、session ID 与 turn ID，但此前没有消费者将聊天回复关联到该事实。仅添加前端时间匹配或标题匹配不能区分同名唤醒，也不能可靠覆盖第一页外的历史。

## 修复方向

沿用既有 Work 访问资格与持久投递事实。链接携带消息 ID；Work 读取直接以所属 Agent 的真实投递定位所在主执行与轮次，从目标开始分页；客户端自动展开、加载完整过程并滚动到目标。缺失关联时明确说明，不能猜测或误展开其他轮次。保留查看最新轮次入口和原生轨迹能力。
