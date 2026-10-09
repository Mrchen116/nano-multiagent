# Heartbeat 与 Cron

Heartbeat 和 Cron 是两套独立、由节点管理的主动机制。

| 对比 | Heartbeat | Cron |
|---|---|---|
| 适合 | 周期性检查“现在有什么值得主动推进或提醒” | 在明确时间执行一条确定任务 |
| 上下文 | 携带 Agent 与 owner 的 canonical 直聊上下文 | 回到创建它的主会话并沿用上下文；global 使用数字人主会话 |
| 配置 | per-agent 开关、`heartbeat.every`、`heartbeat.active_hours`；任务内容在 `<workspace>/.nanoassistant/HEARTBEAT.md` | per-agent 开关；Agent 通过 `schedule_create/list/update/delete` 管理，`schedule_run/history` 立即运行或查看结果 |
| 结果 | 有可冒泡内容时发到 canonical 直聊；无内容时 `HEARTBEAT_OK` 静默 | 结果回到创建时的聊天，Global 由 Agent 显式选择有权目标；记录运行与交付历史 |
| 错过周期 | 恢复时只推进最近边界，不逐个补跑 | 恢复时沿用原生 Schedule 策略，补发已过期的一次性提醒 |

补充规则：

- Heartbeat 顶层节律来自 Agent 配置，默认 `30m`；不要把 `<workspace>/.nanoassistant/HEARTBEAT.md` 顶层文本当成调度器主频率。
- `HEARTBEAT.md` 可以包含 freeform 任务清单和可选的 per-task 独立频率。
- `heartbeat.active_hours` 窗口外不唤醒，避免打扰用户。
- Cron 的手动立即运行和定时触发使用同一执行、投递和历史语义；手动调用只改变触发时机。
- 两种机制都关闭时不创建主动运行。Cron 未启用时，相关 job 不应获得可运行能力。

选择建议：

- “每 30 分钟看看有没有要跟进的事”使用 Heartbeat。
- “每天 9:00 发日报”或“明天 14:00 提醒我”使用 Cron。
- 需要引用近期直聊上下文的周期判断优先 Heartbeat；需要确定时间、可列举的固定任务使用 Cron。

配置示例（每个 Agent 的 `heartbeat` 字段）：

```yaml
heartbeat:
  every: 30m
  active_hours:
    start: '09:00'
    end: '22:00'
    timezone: Asia/Shanghai
```

活跃窗口包含 start、不包含 end；start 晚于 end 表示跨午夜。未提供时区时按 UTC 判断，未提供完整 start/end 时不限制时段。Web Agent 设置中的 Heartbeat 卡可编辑节律与 start/end。
