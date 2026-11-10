# feat-760 审查与验证

## 范围与版本

- 需求见 [spec](spec.md)，实现见 [design](design.md)。
- 独立 `change-code-review` 执行者为 `receipt_review`，审查范围为 `bfc908101..b416109a4`。已收到首项发现，完整结论待回报。
- 主会话验证的实现版本为 `13b7df8b5`，包含 iOS 布局、IM 回执事件与 Web 类型边界修复。

## 审查结果

| 问题 | 执行者与模式 | 结果与证据 |
| --- | --- | --- |
| 回执刷新与 Dreaming 冻结快照 | `receipt_review` 独立审查 | 发现 Gateway 将回执事件绑定到消息版本，见下方 R1。 |
| iOS 气泡间距与详情 | 主会话体验自检 | iPhone 17 模拟器连接隔离 IM，三态图标在气泡内，点击可打开两名收件人的无标题详情。XCTest 检查单行正文和勾的中心高度相差不超过 14 pt。 |
| 回执与 Inbox 读取路径 | 主会话定向验证 | IM relay recovery 与 PA 的 Inbox、Global、外部通道、单会话及生命周期套件合计 120 项通过。本地读取提交对照见 [design](design.md)。 |
| Web 与仓库契约 | 主会话验证 | Web 套件 1,179 项通过，随后调整的 Web 类型边界通过 iOS Web 资源构建与架构测试。Python 非 E2E 135 项、Ruff 和 TS 类型检查通过。 |

## Findings 与关闭

- R1。Gateway 的 `message.receipts_changed` 曾携带实际 `message_id`。Dreaming 的截止点查询会将随后出现的关联事件视为消息版本变化，进而排除原消息。`13b7df8b5` 将它改成会话级刷新，定向端到端用例检查收件和已读事件均不关联消息版本。独立关闭待复核。

## 流程收口

- 本地全量 `pnpm test` 并发执行时多个运行时套件超时，已停止该轮。iOS 全套 XCTest 在模拟器启动阶段中止。最终 iOS 界面旅程和回执定向验证单独通过。
- 两台临时 iPhone 模拟器、隔离 IM 及 Web 代理已回收。本地截图留作验收证据。
- 独立审查结论和用户验收仍待完成。当前保留活动单元与 delta-spec，按已授权范围提交草稿 PR。
