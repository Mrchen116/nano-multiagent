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
