# bugfix-383: IM relay watchdog 误杀正在活跃跑工具循环的长 relay

## Relations

- Related: bugfix-361 (本 unit 修的就是 361 引入的 watchdog 的判活信号)
- Follow-up to: bugfix-365 (failure detail 回填 message content — 保留此行为，仅修判活逻辑)

## 原始报告

> 用户在 web IM 会话 `3df067a7de3f4feb9da19c242a87758a` 看到一条 agent 消息收尾被追加：
>
> > `[error] relay timed out after 300s with no completion event`
>
> 但前半部分文本正常显示 agent 在做事："I'll inspect the recent commits of the nano-multiagent repository for critical bugs. Let me start by examining the repository locally."
>
> 用户怀疑 relay 实际在正常跑多轮工具调用，被误杀了。

## 现场证据

`data/im_service.sqlite3` 上对该 message 的 event timeline（节选）：

| event_id | event_type | created_at |
|---|---|---|
| 4264 | message.sent | 03:38:57.597 |
| 4265 | message.created (running) | 03:38:57.599 |
| 4266 | message.delta | 03:39:04.613 |
| 4267..4315 | **连续 49 条 `tool_call.upserted` / `tool_call.completed`** | 03:39:05 → **03:43:51.926** |
| **4316** | **relay.failed (watchdog)** | **03:43:59.607** |
| 4317..4364 | **tool_call.upserted / completed 仍在继续** | 03:44:10 → 03:49:16 |
| 4365 | permission.request | 03:50:43 |

关键观察：

1. **agent 完全活着**：watchdog 触发前 8 秒（03:43:51）刚完成一次 tool_call；触发后 11 秒（03:44:10）又开始下一次 tool_call，并一直跑到 03:50:43 还在请求权限。
2. **watchdog 触发点**：`relay.failed` 落在 `03:43:59.607`，距 message `created_at=03:38:57.596` 恰好 302 秒 —— 即 `relay_watchdog.py` 的 `timeout_seconds=300` 硬上限。
3. **没有任何 idle 缝隙**：从 03:39:04 起到被杀的瞬间，event 间最大空窗未超过 ~10 秒（每轮 tool 都正常往出推 event）。relay 链路毫无"卡死"特征。

## 根因

`src/IM/application/relay_watchdog.py:42-51`：

```python
cutoff = now - timedelta(seconds=timeout_seconds)  # 默认 300
rows = connection.execute("""
    SELECT id, conversation_id, created_at
    FROM messages
    WHERE delivery_status = 'running'
      AND created_at < ?
""", (cutoff,)).fetchall()
```

判活信号用的是 **`messages.created_at`**（消息创建那一刻），而不是"距最近一次 event 的时间"。意味着只要某条 relay 总耗时 > 300s，无论这中间是否一直在活跃推 `tool_call.*` / `message.delta`，都会被无条件 flip 成 `failed`。

bugfix-361 当初注释里的假设 `"long enough to cover normal LLM latency"`（第 36 行）对**单轮 LLM 调用**成立，但对个人助手这类**多轮 tool 循环**（一次 user message 触发几十轮 tool call）完全不够。一次"读 git log + grep 多个文件 + 起 subagent"的常规任务就能轻易 > 5 分钟。

## 影响范围

- **受影响用户**：所有跑长链路 multi-turn tool 使用的会话；尤其是触发 sub-agent / 大量 read+grep / 跑测试的请求。
- **症状**：
  1. UI 上消息被标 failed，正文末尾出现 `[error] relay timed out after 300s ...`
  2. 但 Gateway / agent 进程仍在后台继续跑 tool（事件还在 append 到 conversation_events，message content 也仍在累加，但 delivery_status 已锁死 failed）
  3. 用户看到「失败」会重发，造成重复 dispatch；agent 后续真完成时，UI 仍显示 failed（completed 事件已无法把 failed 翻回来 —— 即使能翻，用户已操作过了）
- **严重度**：silent corruption of UX —— 用户被欺骗以为失败、agent 实际仍在消耗 LLM token / 工具调用。

## 澄清记录

- Q1: 修复方向 — 把判活信号从"消息创建时间"改为"最近一次 event 时间"，并把 timeout 从 300s 压缩到 120s？
  A(原话): 提。然后300s压缩到120s
  Agent 解读: 用户同意采纳此方向。判活信号改为 `MAX(conversation_events.created_at WHERE message_id=?)`（无 event 时 fallback 到 `messages.created_at`），阈值由 300s 降到 **120s**。"120s 无任何 event 推进"才算 stuck，正常长 tool 循环不再被误杀。

## 修复方向（待 design 阶段细化）

1. **改 watchdog SQL**：把 `WHERE created_at < cutoff` 改为按"最后 event 时间 < cutoff"判断，类似：
   ```sql
   SELECT m.id, m.conversation_id, m.created_at
   FROM messages m
   LEFT JOIN (
     SELECT message_id, MAX(created_at) AS last_evt
     FROM conversation_events
     GROUP BY message_id
   ) e ON e.message_id = m.id
   WHERE m.delivery_status = 'running'
     AND COALESCE(e.last_evt, m.created_at) < ?
   ```
2. **timeout 阈值**：`300 → 120` 秒。文案 `relay timed out after Ns ...` 同步更新到使用变量。
3. **保留 bugfix-365 行为**：失败 detail 仍 backfill 到 message content；agent identity 仍从 event/message 行恢复。
4. **测试覆盖**：
   - 长 multi-turn 模拟：message 创建 10 分钟前，但 event 在 30 秒前刚 append → **不应**被杀。
   - 真 stuck：message 创建 10 分钟前，最后 event 也在 5 分钟前 → **应**被杀。
   - 无任何 event 的 stuck（gateway 在 relay.processing 之前就崩了）→ fallback 到 created_at，120s 后被杀。

## 范围与非目标

- **In scope**：`src/IM/application/relay_watchdog.py` 的 SQL / 阈值修改 + 单元测试。
- **Out of scope**：Gateway 侧 try/finally 兜底（bugfix-361 时点明不做，本 unit 也不做）；前端 placeholder 超时 UX；watchdog interval（30s 扫描周期）不变。
