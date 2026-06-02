# Verification Report: feat-393

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 tasks + 4/4 requirements |
| Correctness | 7/7 scenarios covered |
| Coherence | Followed (6/6 decisions) |

No critical issues. 1 suggestion. Ready for PR (with noted improvements).

---

## Completeness

### Tasks: 3/3 complete

- R1 — IM turn_start to_user_id 分支 + 集成测试: DONE
- R2 — heartbeat observer 惰性 turn_start + run_context_store 播种: DONE
- R3 — 全套回归验证: DONE

全量测试验证: `pytest -m "not e2e"` — 2351 passed, 4 deselected, 15 warnings.

### Spec 覆盖

所有 4 条 Requirement 均有实现：
- Req-定时结果以 agent 消息出现在 owner 直聊: 实现于 gateway observer + IM turn_start to_user_id 分支
- Req-本轮无内容则静默: 实现于 NO_REPLY/空内容门控
- Req-汇报始终落到 canonical 直聊: 实现于 `_find_or_create_direct_conversation` + canonical 解析
- Req-触发指令不可见: 触发提示词只传给 kernel，IM 仅收 assistant_message 内容

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 本轮有内容可汇报 → 直聊出现 agent 汇报消息 | `main.py:2094` (`_heartbeat_lazy_turn_start` 异步函数) + `gateway_handler.py:756` (to_user_id 分支) | `test_heartbeat_im_delivery.py::test_heartbeat_with_content_creates_real_message_row_in_fk_enforced_db` (FK 强制 DB 验证) | covered |
| 会话开着时实时（流式）呈现 | `main.py:2124` (message_delta 在 turn_start ack 后立即发出) + `gateway_handler.py:821` (message_delta 路径不变) | 上述集成测试含 sent_frames 验证 | covered |
| 会话没开时作为已完成消息留存 | `gateway_handler.py:826` (message_completed 路径) + `event_bridge.py` (DB 持久化) | 整体流程由 FK-enforced DB 测试覆盖 | covered |
| 无可汇报内容 → 静默不发消息 | `main.py:2096` (`_is_no_reply_token` 门控) + `main.py:2084` (空内容 return None) | `test_heartbeat_no_reply_produces_zero_message_rows` + `test_heartbeat_empty_content_produces_zero_message_rows` | covered |
| owner 与同一 agent 有多条单聊 → 落最旧那条 | `gateway_handler.py:776` (`_find_or_create_direct_conversation` → `_find_canonical_direct_conversation` 取最旧) | `test_turn_start_to_user_id_uses_oldest_conversation_when_multiple_exist` (time.sleep 确保 created_at 不同) | covered |
| 尚无任何直聊（首次/空态）→ 自动新建 | `gateway_handler.py:1472` (`_find_or_create_direct_conversation` 无则建) | `test_turn_start_to_user_id_creates_direct_conversation_when_none_exists` | covered |
| 触发指令对用户不可见 | `main.py:2031` observer 仅处理 run_status/assistant_message/tool_start/tool_end/turn_end；heartbeat message 作为 user-side kernel input，无对应 SSE 事件类型回流 IM | 间接覆盖：所有集成测试验证 sent_frames 只含 turn_start+message_delta 不含触发文本 | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: 汇报走共享流式路径（node.streaming_delta），不另起投递通道 | 是 | `main.py:2108` (heartbeat lazy turn_start 发 node.streaming_delta); `main.py:2124` (message_delta 走同一 send_json) |
| 决策 2: 消息气泡惰性创建（有真实内容才发 turn_start），仅作用于 heartbeat | 是 | `main.py:2053` (to_user_id 有值时跳过 eager turn_start); `main.py:2094` (assistant_message 时才触发 lazy turn_start) |
| 决策 3: 目标会话 = (owner,agent) canonical 直聊，由 turn_start 惰性解析/创建 | 是 | `gateway_handler.py:756` (to_user_id 模式); `gateway_handler.py:776` (`_find_or_create_direct_conversation`); ack 返回 conversation_id+message_id 回填 run_context_store (`main.py:2117-2120`) |
| 决策 4: heartbeat run 跑在 agent 专属稳定 :heartbeat 隔离 session | 是 | `heartbeat_scheduler.py:154` (`_heartbeat_sessions` dict); `heartbeat_scheduler.py:197` (`_get_or_create_heartbeat_session` 首次建后复用); `test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks` 断言 created_sessions=1 |
| 决策 5: NO_REPLY / 空内容静默，复用既有 NO_REPLY 约定 | 是 | `main.py:2096` (`_is_no_reply_token` 检测); `main.py:2084` (空内容 return None); 复用 `InboundPipeline._is_no_reply_token` 不自造新词 |
| 决策 6: 投递行为继承普通流式路径，不单造重试/持久化 | 是 | `main.py:858-890` (失败 swallowed + 记日志，无重试队列); `main.py:893` (pop run_context_store); 注释明确引用 design decision 6 |

### 额外核查：普通聊天零改动

- `gateway_handler.py:799-819` 的普通聊天 conversation_id 分支完全独立，to_user_id=None 时原样走旧路径
- `run_context_store` 播种（relay lifecycle callback）对普通聊天不注入 `to_user_id`（`main.py:1923`），保证门控不触发
- 测试 `test_turn_start_conversation_id_mode_unchanged_normal_chat_path` 和 `test_normal_chat_run_context_store_eager_bubble_unchanged` 通过

### 额外核查：FK 强制路径（M138 假绿教训防守）

测试文件 `test_heartbeat_im_delivery.py:98` 使用 `initialize_schema(connection)`，该函数调用 `PRAGMA foreign_keys=ON`，确保任何合成 FK 路径会在 DB 层抛出 `sqlite3.IntegrityError`。`test_gateway_handler.py:526` 同样注明此为 M138 fake-green guard。测试确实走了真实 message 行创建路径而非 mock。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

- **`_consume_heartbeat_run` 的 `after_sequence=0` 在多 tick 后效率递减**
  - `main.py:878`: `async for event in self._kernel.stream(kernel_session_id, after_sequence=0)` 每次从 session 头开始重播所有历史事件，靠 run_id 过滤跳过旧事件。
  - 随着同一 `:heartbeat` session 积累越来越多 run，每次消费扫描的历史事件线性增长。
  - 建议：在 `run_context_store` 播种时记录提交 run 前的 session sequence（可通过 `stream_session` 的最新 sequence 号获取），消费时传 `after_sequence=last_known_sequence` 而非 0。
  - 注：这不影响正确性（run_id 过滤保证无漏无误），仅是长期运行下的性能优化。

---

All checks passed. Ready for PR.

---

# Round 3 — 2026-06-02

> 针对 fix-r1 / fix-r2 两轮 post-acceptance fix 后的重新核验。核查重点：两轮 fix 是否引入 spec/design 偏离；catch-up 折叠决策的设计文档缺口；Kernel.current_event_sequence() SDK 分层合规；fix 路径测试覆盖。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 tasks（两轮 fix 均有配套红→绿测试）|
| Correctness | 7/7 scenarios 仍 covered；fix-r1/r2 新引入边界均有测试 |
| Coherence | Followed（6/6 original decisions）；catch-up 折叠与 spec 意图一致但 design.md Changelog 未记录 |

No critical issues. 1 warning (design.md Changelog 空白). 1 suggestion (stream_anchor 非零路径无断言). Ready for PR (with noted improvements).

---

## fix-r1 核验

### Fix1: owner_unresolved 返回 skipped ack，不关 WS

- **实现**：`src/IM/ws/gateway_handler.py:783-800` — `_find_or_create_direct_conversation` 外包 `try/except (ValueError, Exception)`，失败时返回 `{"skipped": "owner_unresolved"}` ack 而非冒泡。`src/personal_assistant/main.py:2132-2142` — observer 收到 `skipped` 字段时记日志、直接 return，heartbeat run 正常收尾。
- **spec/design 对齐**：design.md 决策 6"投递行为继承普通流式路径，失败记日志不重试"明确覆盖此语义；`skipped ack` 而非抛异常是对该决策的正确延伸，无偏离。
- **测试**：`test_gateway_handler.py::test_turn_start_to_user_id_owner_not_in_db_returns_skipped_ack_not_exception`（FK-enforced DB，nonexistent owner_id → `IntegrityError` → `skipped=owner_unresolved` ack，断言无 conversation 被创建）。覆盖充分，失败路径真实走到 DB 层。

### Fix2: e2e-up.sh 同步 node.user_id

- 纯测试基础设施修复，不涉及 unit 功能代码，无 spec/design 偏离风险。

### Fix3: heartbeat_runner.start() 移到 im.connect_once() 之后

- **实现**：`src/personal_assistant/main.py:1040-1046` — heartbeat runner 的 start 在 `im_connection_manager.connect_once()` 和 `post_im_connect` 回调完成之后才执行。
- **spec/design 对齐**：design.md 未规定启动顺序；修复属于 gateway 运行时序修正，与 spec 的"投递走普通 WS 路径"语义完全一致，无偏离。
- **测试**：`test_gateway_process_manager.py::test_gateway_runtime_keeps_running_until_shutdown_requested` + `test_gateway_runtime_cleans_up_reverse_order_when_im_start_fails` 断言事件顺序（heartbeat.start 在 im.connect/im.bootstrap 之后），时序倒退会失败。

### Fix1b: _find_or_create_direct_conversation 补 caller_owner_id

- **实现**：`gateway_handler.py:792` — `caller_owner_id=to_user_id` 确保新建 direct conversation 的 owner_id 正确指向 heartbeat 目标 owner，而非从 users 表动态推断（跨 e2e 运行可能取到旧 id）。
- **spec/design 对齐**：符合决策 3"canonical 直聊惰性创建，inert 时 auto-create"，参数补全无语义变化。

---

## fix-r2 核验

### FixA: catch-up 折叠（interval/cron 长 gap → 最多 1 条）

- **实现**：
  - `heartbeat_scheduler.py:280-297` (`_IntervalSchedule.due_times_up_to`)：用 floor division 直接算最近 due time，不再枚举 backlog。
  - `heartbeat_scheduler.py:308-322` (`_CronSchedule.due_times_up_to`)：扫历史取最后一个命中点，只返回那一条。
- **spec 对齐**：spec 描述 heartbeat 为"定时汇报"（"到点后 agent 跑一轮"），不含"补跑历史所有漏掉的轮次"语义。用户场景描述"没什么可说的就闭嘴"，可类推为长 gap 后也只报最近状态一次。catch-up 折叠与 spec 意图一致。
- **design.md 记录**：design.md `## Changelog` 为空，catch-up 折叠这一行为决策（属于 scheduler 运行语义，非仅性能）**未在 design.md 中留档**。（详见 WARNING 段。）
- **测试**：
  - `test_scheduler_catches_up_missed_interval_run_after_restart`：1h31m gap → 断言 1 条 run，且 due_at = 最近对齐点 10:30，`sent_messages=1`。
  - `test_scheduler_normal_cadence_produces_exactly_one_run_per_interval`：连续正常节奏每 interval 恰好 1 条，防止折叠过度压制正常轮次。
  - `test_scheduler_cron_catchup_collapses_to_one_run`：cron 5 分钟 gap → 1 条 run，due_at = 最近命中点。
  - 三个测试充分覆盖 catch-up 折叠的核心路径和正常节奏不受影响的回归。

### FixB: stream anchor（Kernel.current_event_sequence()）

- **实现**：
  - `agent/sdk/kernel.py:551-563` — `Kernel.current_event_sequence()` 方法，委托 `self._c.event_hub.current_sequence()`（`agent/core/events/hub.py:162-165`，原子读 `_next_sequence_num - 1`）。
  - `personal_assistant/main.py:1379-1385` — `_KernelClientShim.current_event_sequence()` 委托到 `Kernel.current_event_sequence()`。
  - `heartbeat_scheduler.py:246-247` — `_submit_run` 在 submit 前通过 `getattr` 安全取锚点（不实现此方法的 test fake 回落 0）。
  - `personal_assistant/main.py:880` — `_consume_heartbeat_run` 传 `after_sequence=record.stream_anchor`。
- **SDK 分层合规**：`Kernel.current_event_sequence()` 是 `Kernel` 类的实例方法，定义于 `agent/sdk/kernel.py`（SDK 层），读 `_KernelComponents.event_hub`（SDK 内部组装，`agent/core` 不暴露给外层）。`personal_assistant` 通过 `_KernelClientShim` 持有 `Kernel` 实例并调用其 public 方法——未 import `agent.core` 或 `agent.platform` 内部，符合 AGENTS.md 依赖方向硬规则。
- **初始值边界**：`EventStreamHub._next_sequence_num` 初始为 1；无 events 时 `current_sequence()` 返回 0。`stream(after_sequence=0)` 语义为"从头"，即 fallback 全历史扫描，功能正确。
- **测试覆盖**：scheduler 测试中 `_FakeKernelClient.current_event_sequence()` 固定返回 0（注释注明"tests do not exercise stream-from-anchor path"），`test_heartbeat_im_delivery.py` 也未注入非零 anchor 验证流式消费实际跳过历史事件。（详见 SUGGESTION 段。）

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1: design.md Changelog 未记录 catch-up 折叠决策**

catch-up 折叠是 fix-r2 引入的 scheduler 运行语义决策，不仅是性能优化——它决定了"重启/长 gap 后用户只收到 1 条汇报"这一可观察行为（对应 spec 的"定时汇报"用户体验）。design.md 的 `## Changelog` 目前为空，未记录此决策。

建议：在 `docs/changes/feat-393-heartbeat-cron-im-delivery/design.md` 的 `## Changelog` 段补一条，说明 fix-r2 引入 catch-up 折叠语义（interval/cron 长 gap 后最多补 1 条最近 due run）及其理由（避免 backlog 刷屏，符合"定时汇报"语义）。

注：verifier 不改 design.md，建议由 worker 补一笔。

### SUGGESTION（可以修）

**S1: stream_anchor 非零路径无测试断言**

`test_heartbeat_scheduler.py` 的 `_FakeKernelClient.current_event_sequence()` 固定返回 0；`test_heartbeat_im_delivery.py` 同样未验证非零 anchor 实际使消费者跳过历史事件。当 anchor > 0 时，`_consume_heartbeat_run` 中 `stream(after_sequence=record.stream_anchor)` 的跳过逻辑未经测试断言。

正确性靠 run_id 过滤兜底（即使 anchor=0 也不会漏投或重投），但长期运行的性能保证没有测试作安全网。

建议：在 `test_heartbeat_im_delivery.py` 或 `test_heartbeat_scheduler.py` 中增加一个测试，验证非零 anchor 时消费者只处理 anchor 之后的事件（可通过在 `HeartbeatRunRecord` 中注入一个 `stream_anchor > 0` 的 fake kernel，断言 anchor 前的 run events 不被处理）。

---

全量测试: `pytest -m "not e2e"` — 2354 passed, 4 deselected, 16 warnings.

No critical issues. Ready for PR (with WARNING W1 noted for design.md update).
