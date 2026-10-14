# bugfix-605: As-built Design

> 本文在实现完成后根据实际代码和已确认修复意图整理。

## 实现范围

Base 为 `9ebe12f8553a593f6179784b0276849fb14e5358`。产品改动仅位于 `packages/personal-assistant/src/global-agent.ts`；回归扩展既有 `packages/personal-assistant/tests/global-agent.test.ts`。

## 最终结构与数据流

全局消息仍由 Inbox 持久接收，DSH 调度保持原样。send_message 在已有 durable observation 和目标信息查询之后，检查 Web 内置群或任意已有私聊的需处理未读输入。检查候选身份包含请求的会话 ID、可信查询返回的真实目标及 NodeStore 已有的外部镜像 ID；不新增映射存储。

命中时沿用 publication 的 held 状态和 draft_withheld 工作事件，工具返回真实未发送事实、inbox_targets 与重新读取/判断方向。原调用重试仍返回原 held 回执；完成 Inbox 读取后须用新的调用身份发送。无阻塞时继续原投递链路；外部发送成功仍以平台回执为准。

## 决策、失败和回退

只在当前节点同步的接收/派发边界复核，不取消正在执行的工具，不把其他聊天或 attention=false 的背景消息当阻塞。沿用已有存储、幂等与未知投递语义。已开始投递之后到达的输入由后续处理接管，不撤回已投递正文。回退本 unit 的源码提交即可恢复旧范围，无 schema 迁移。

## 验证定位

- 最窄回归：`pnpm exec vitest run packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/external.test.ts`，32 tests 通过。
- 修复前：Web/Feishu 私聊及双向镜像场景四项失败；原群复核通过。
- 构建与类型：`pnpm build && pnpm typecheck` 通过；最终发送反馈变更后另运行 PA build 与后端全套。
- 完整检查和独立审查结论追加至 code-review.md。
- 用户验收：待用户亲自体验候选版本，未记录为完成。

## Canonical 文档影响

delta 位于 `specs/gateway/global-agent.md`。待快速开发用户确认门禁完成后归并 global-agent.md 及包入口的范围摘要；当前不覆盖 current spec。
