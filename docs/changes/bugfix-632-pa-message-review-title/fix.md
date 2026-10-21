# bugfix-632: 工作记录准确显示 PA 定期查看主人消息

## Relations

- Related: feat-623
- Related: bugfix-631

## 原始报告

> 另一个问题，页面为啥写的是“执行轮次”？也不精准
>
> 历史遗留删了吧，`inbox-background`，也不应该写为“背景消息唤醒”，你要理解他的作用是PA定期看主人的消息。换个名字

## 现象 / 复现

2026-10-21 生产 PA 工作视图的第 186、187 轮收到 `inbox-background`，却显示通用“执行轮次”。用户应能直接看出这类执行是在定期查看主人的聊天消息，而不是由内部的 background/wake 术语推测用途。

Web 与原生 iOS 使用一致的产品语义名称。删除两端 `global_inbox` 遗留识别分支；当前运行时写入的是 `inbox` 与 `inbox-background`，没有 `global_inbox` 生产方。普通 Inbox 消息、Heartbeat、Cron 和子执行的分类保留各自语义。

## 命名澄清

> “定期查看主人消息”也不好，太糙了
>
> 在给几个
>
> 近况同步

用户已否定“背景消息唤醒”和“定期查看主人消息”，最终选定“近况同步”。Web 与原生 iOS 对 `inbox-background` 均显示该名称，英文为“Catch up on recent conversations”。

## 根因

feat-623 引入 PA 观察消息的十分钟合批：PA 定期读取主人的其他聊天，理解沟通背景并依据既有目标判断是否协助。Gateway 已持久记录真实 `trigger.kind=inbox-background`，但 Web 的 `turnTitle` 和 iOS 的 `AgentWorkTurn.title` 未接入这个类型，落入通用标题。两端仍保留最初全局工作视图中 `global_inbox` 的识别分支，目前没有写入方。

原始功能意图及边界见 feat-623 的 spec“背景通知按十分钟累计且不丢消息”和 current `docs/specs/gateway/personal-agent.md`：“定期查看”只描述这种 PA 工作目的，不把主人收到的消息自动视为对 PA 的交办，不意味着没有新增未读也会周期空转。本修复只调整显示分类、翻译及已退役别名，不改变接收、节律、消费、权限或发送语义。

## 修复

Web 和原生 iOS 为真实的 `inbox-background` 类型显示“近况同步”，英文为“Catch up on recent conversations”。删除两端 `global_inbox` 的识别分支，并在 current Agent Work spec 中归并该显示语义。

## 验证

- 修改前用隔离 Vite、固定 API 数据和真实 Work 组件在 Playwright 浏览器复现：`inbox-background` 显示“执行轮次”，同页 `inbox` 显示“Inbox 唤醒”。
- 修改后检查中文桌面和英文 390px 窄屏：分别显示“近况同步”和“Catch up on recent conversations”，标题完整；普通 Inbox 分类保留。此次为真实组件、隔离数据的显示验证，不声明生产部署或完整服务 E2E。
- 既有 `agent-work-panel.test.tsx` 17 项通过，覆盖工作记录与子执行展示、刷新、导航和状态。此低影响显示修正不新增仅锁文案的永久测试。
- `swiftc -frontend -parse src/IM/ios/NanoIM/Features/Agents/AgentWorkModels.swift` 通过；本机没有完整 Xcode，iOS 模拟器测试及 Release 归档交由本 PR 的必跑 CI 验证。
- 产品源代码检索确认 Web 与 iOS 不再包含 `global_inbox`；历史变更文档中记录的旧模块名称继续保留。
