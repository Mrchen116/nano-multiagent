# bugfix-383: design — IM relay watchdog 改"最近 event 时间"判活，阈值 300→120s

Unit branch: `unit/bugfix-383`

## 范围

仅改 IM 单一后台 watchdog 的判活信号与阈值。Gateway 侧、前端侧、事件 schema 不动。

## 关键决策

### D1: 判活信号从 `messages.created_at` 改为"最后 event 时间"

新 SQL：

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

为什么不在 `messages` 上加 `last_event_at` 冗余列：bugfix-361 已经写好的 event-append 路径不动；本 unit 不引入 schema 迁移。`conversation_events` 表本来就有 `(message_id, event_id)` 顺序，子查询 GROUP BY 在每个 message 的事件量级下（最多几百条）成本可接受，且 watchdog 30s 跑一次，不在热路径。

`COALESCE` fallback 处理 gateway 在 `relay.processing` 之前就崩了、message 一个 event 都没有的极端 case —— 此时退化为旧行为（按 created_at 算）。

### D2: 阈值 300s → 120s

判活信号改进后，"活着"的 relay 不会被算到 idle 里；只剩"真的 idle"才计时。120s 对正常 streaming relay 远远够（每条 `tool_call.upserted` 或 `message.delta` 都重置计时），对真死的 relay 早 3 分钟收尾。

环境变量 `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS` 的 default 同步改为 `"120"`（`src/IM/app.py:298`）；运行时仍可 override。

### D3: 失败文案

`relay_watchdog.py:56, 117` 里两处硬编码 `"relay timed out after {timeout_seconds}s with no completion event"` 调整语义：

新文案：`"relay idle for {timeout_seconds}s with no new event"`

理由：旧文案隐含"relay 从未完成"，新逻辑下消息可能已有大量 event 但最后 N 秒没动；"idle"更准确，也不让用户误以为没跑过任何东西。

### D4: 不动的部分

- `_build_failed_payload` 全部行为保留（agent identity 恢复、payload 字段继承）—— bugfix-365 修过的，本 unit 不碰。
- `_backfill_failure_detail_into_message_content` 保留 —— failed 气泡里仍写 detail，只是文案换成 D3 的版本。
- `run_relay_watchdog` 的 interval（30s）不变。

## 测试策略

`tests/im_service/unit/test_relay_watchdog.py` 既有用例多数继续有效（"老 message + 无 event" 路径走 COALESCE fallback 走旧逻辑）。需要新增的：

1. **不杀活跃 relay**：seed message 10 分钟前创建，但 conversation_events 里 30 秒前刚 append 一条 `tool_call.upserted` → `scan_and_fail_stuck_running_messages` 返回 0，message 仍 `running`。
2. **杀真 idle relay**：seed message 10 分钟前创建，最后 event 在 5 分钟前 → 返回 1，message flip 到 `failed`，content 含 "relay idle for 120s ..." 文案。
3. **无 event 退化**：message 4 分钟前创建，零 conversation_events → 按 created_at 算，应被杀（满足 > 120s）。
4. **边界**：message 在阈值边缘（last event 121s 前 / 119s 前）的行为符合预期。

不做：integration / e2e 不动；既有 bugfix-365 测试（detail backfill / agent identity 恢复）保留通过即可。

## 实施风险

- **既有用例文案断言**：grep `tests/im_service/unit/test_relay_watchdog.py` 是否硬比对 "timed out after" 字符串。若有，同步改文案。M1/R3 处理。
- **环境覆盖**：若线上 / 部署脚本显式 export `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS=300`，default 改成 120 不会生效——但本项目目前没有这类持久化 override，仅 unit / e2e 脚本 ad-hoc 设置。不阻塞。

## Milestone 拆分

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-383-M1 | watchdog-idle-signal | — | A | `src/IM/application/relay_watchdog.py` + `src/IM/app.py:298` default + `tests/im_service/unit/test_relay_watchdog.py` | (a) `pytest tests/im_service/unit/test_relay_watchdog.py` 全绿 (b) `pytest tests/im_service` 无连带回归 (c) 手工验证：起 IM/Gateway/agent 跑 > 2 分钟的长 tool 循环（event 持续推进），UI 不再出现 `[error] relay ...` 误杀 [reviewer 验] (d) `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS` env override 仍生效（用 `env IM_RELAY_WATCHDOG_TIMEOUT_SECONDS=60` 起 IM，verifier 在日志里能看到 60 生效） [worker] |

不拆 R 的理由：所有改动集中在 `relay_watchdog.py` 一个函数 + `app.py` 一行 default + 一个测试文件；TDD 三提交循环（C1 测试 → C2 实现 → C3 文档）就够。worker 在 tasks.md 内自行拆 R。
