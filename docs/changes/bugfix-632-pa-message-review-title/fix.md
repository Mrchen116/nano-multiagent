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

Web 与原生 iOS 均需显示“定期查看主人消息”，英文为“Periodic review of owner messages”。删除两端 `global_inbox` 遗留识别分支；当前运行时写入的是 `inbox` 与 `inbox-background`，没有 `global_inbox` 生产方。普通 Inbox 消息、Heartbeat、Cron 和子执行的分类保留各自语义。

## 根因

feat-623 引入 PA 观察消息的十分钟合批：PA 定期读取主人的其他聊天，理解沟通背景并依据既有目标判断是否协助。Gateway 已持久记录真实 `trigger.kind=inbox-background`，但 Web 的 `turnTitle` 和 iOS 的 `AgentWorkTurn.title` 未接入这个类型，落入通用标题。两端仍保留最初全局工作视图中 `global_inbox` 的识别分支，目前没有写入方。

原始功能意图及边界见 feat-623 的 spec“背景通知按十分钟累计且不丢消息”和 current `docs/specs/gateway/personal-agent.md`：“定期查看”只描述这种 PA 工作目的，不把主人收到的消息自动视为对 PA 的交办，不意味着没有新增未读也会周期空转。本修复只调整显示分类、翻译及已退役别名，不改变接收、节律、消费、权限或发送语义。
