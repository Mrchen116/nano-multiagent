# Heartbeat 与 Cron

Heartbeat 和 Cron 是两套独立、都由 Gateway 本地调度的主动机制。

| 对比 | Heartbeat | Cron |
|---|---|---|
| 适合 | 周期性检查“现在有什么值得主动推进或提醒” | 在明确时间执行一条确定任务 |
| 上下文 | 携带 Agent 与 owner 的 canonical 直聊上下文 | 在隔离 session 中运行，不带普通聊天上下文 |
| 配置 | per-agent 开关、`heartbeat.every`、activeHours；任务内容在 `<workspace>/.nanoassistant/HEARTBEAT.md` | per-agent 开关；Agent 通过 `cron` 工具创建、查看、立即运行或删除 jobs |
| 结果 | 有可冒泡内容时发到 canonical 直聊；无内容时 `HEARTBEAT_OK` 静默 | 结果发回 canonical 直聊并记录运行历史，用户可继续追问 |
| 错过周期 | 恢复时只推进最近边界，不逐个补跑 | 同样不补跑；已经过期的一次性任务也不补跑 |

补充规则：

- Heartbeat 顶层节律来自 Agent 配置，默认 `30m`；不要把 `<workspace>/.nanoassistant/HEARTBEAT.md` 顶层文本当成调度器主频率。
- `HEARTBEAT.md` 可以包含 freeform 任务清单和可选的 per-task 独立频率。
- activeHours 窗口外不唤醒，避免打扰用户。
- Cron 的手动立即运行和定时触发使用同一执行、投递和历史语义；手动调用只改变触发时机。
- 两种机制都关闭时不创建主动运行。Cron 未启用时，相关 job 不应获得可运行能力。

选择建议：

- “每 30 分钟看看有没有要跟进的事”使用 Heartbeat。
- “每天 9:00 发日报”或“明天 14:00 提醒我”使用 Cron。
- 需要引用近期直聊上下文的周期判断优先 Heartbeat；需要隔离、可列举的固定任务优先 Cron。
