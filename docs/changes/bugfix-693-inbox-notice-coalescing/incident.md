# bugfix-693: 合并下一次模型请求前的 Inbox 提醒

## 原始报告

> 改成下一个 LLM 请求前最多只收到一条 Inbox 提醒，多条消息合并提醒，避免重复占用上下文。快修模式修

## 澄清记录

用户明确选择快速开发；范围明确，无额外澄清。用户尚未亲自验收，本 unit 保持 active；未归并 canonical spec，未归档或发布。

## 现象与复现

Global Agent 正在模型请求或工具执行时，顺序收到三条符合 attention 条件的消息。原实现为三次 watermark 分别提交三个系统提醒，下一次请求同时包含三条重复通知。新增 native 回归测试在修复前捕获到提醒总数由 1 增至 4（期望增至 2）。

## 影响范围

Global 主 Agent 与 PA participant Inbox 提醒重复占用上下文。消息正文、Inbox 消费和发送前复核没有变化。PA observer 后台批次使用独立 channel，不属于此次合并范围。

## 根因分析

产品层仅按已提交 watermark 去重相同输入；后续消息具有新 watermark，因此会继续提交。运行时把每次 steer 追加到 next-step，未合并尚未消费的同类系统提醒。

## 目标与验收

- 下一次模型请求最多新增一条 Inbox 提醒，多条消息完整保留在 Inbox。
- 提醒消费后再来的新消息，可以在再下一次请求触发新提醒。
- 不硬中断模型或工具执行，不在提醒中注入正文，不影响其他系统通知及发送前复核。

## 修复方向

在 Nano 的公开 DSH 接入层入队 Inbox steer 时，删除该 session 尚未消费的同类系统提醒，再提交最新提醒。保持最新 watermark 对应的 durable input ID；不修改 DSH，不维护第二套待提醒状态。
