# bugfix-733: 聊天历史回读保留纯 UI 消息

## Relations

- Related: bugfix-729

## 原始报告

> 当前 `conversations.read` 会跳过既无正文又无附件的纯 UI 消息？

> 赶紧快修啊，你这是bug

## 现象 / 复现

Agent 已能发送无正文的 UI 卡片。另一 Agent 回查有权访问的聊天时，纯 UI 消息从 `conversations.read` 结果消失，按其消息 ID 读取也为空。Inbox 摄取和客户端聊天仍能看到原卡片。

## 根因

IM 的 `Work.query` 在 `2d51d501da` 已将 `interactive` 纳入非空消息判据，但沿用只为正文和附件建立分页分段的逻辑。纯 UI 消息通过判据后分段数为零，附带 `interactive` 的结果构造分支从未执行。bugfix-729 取消独立摘要后，纯 UI 消息成为正常发送形态，暴露了这个旧假设。

预期是返回原消息身份、来源和卡片内容。纯 UI 消息应计为一条完整结果，正文和附件为空，继续沿用权限、游标和去除渲染协议元数据的规则。关键词搜索范围不变。

## 本次审查安排

独立代码与契约审查核对分页、权限和模型投影。复用实际消息存储与聊天查询 fixture，先复现按消息 ID 读取为空，再验证直接回读与分页均返回同一卡片。

## 修复

`276e6779b` 将已通过非空检查的纯 UI 消息计为一个完整分段。沿用既有结果构造返回 `interactive` 和消息来源，`content` 为空数组。新增用例覆盖按 ID 回读、正常翻页和空占位跳过。

## 验证

- 修前新增用例按 ID 读取返回 `messages: []`（`/tmp/nano-733-read-red.log`）。修后历史、权限和 PA 相关 26 项通过，IM 全量 64 文件 407 项通过（`/tmp/nano-733-im-regression.log`）。IM、PA 和 DSH 构建及文档检查通过。
- 临时受控用例在真 IM 进程经鉴权 WebSocket 发布纯 UI，再由真实 DSH 的 `conversations.read` 经 GlobalAgent 与 Gateway 读取。后续 Anthropic adapter 请求含原消息 ID、来源和完整 UI 源码，`content` 为空数组，无 `partial` 或目录版本；本地 provider 只提供确定性调用和结束响应。结果位于 `~/.codex/reports/bugfix-733-ui-history-read/ui-history-wire.json`，临时进程与 fixture 已回收。未评估真实模型选择行为。
