# M6 Fast-Lane Fixes — Progress

## R1 — Reviewer 反馈三处缺陷修复

- Context: reviewer 反馈循环中发现三个独立 bug
- Decision: 单 commit 修复（lite 模式，§FL 判据满足）
- Rationale: 三个 bug 各自独立、单点修复、总改动 < 100 行
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_*.py` — 59 passed
  - Full suite: `pytest -m "not e2e"` — 3175 passed, 1 skipped
  - Entry: N/A（纯后端 channel 修复，无新用户入口）
- Rollback: `git revert 925efc33`
- Commits: C1=`cd416146` (红测), C2=`925efc33` (实现)
- Next: M6 DONE，合并到 unit/feat-447

### Bug 1: DM receive_id_type

- **现象**: FeishuAdapter.send() 对所有消息使用 `receive_id_type="chat_id"`，导致 DM 消息发送失败
- **根因**: 未区分 DM (`feishu:<app_id>:dm:<user_open_id>`) 和 group (`feishu:<app_id>:group:<chat_id>`)
- **修复**: `feishu_adapter.py:100-102` 根据 `":dm:" in outbound.target_chat_id` 选择 `"open_id"` 或 `"chat_id"`
- **测试**: `test_send_dm_uses_open_id`, `test_send_group_uses_chat_id`

### Bug 2: 共享重试计数器

- **现象**: 429 重试耗尽后，5xx 错误无法获得自己的重试机会
- **根因**: `send_message()` 中 `attempt` 变量被 429 和 5xx 共享
- **修复**: `feishu_client.py:212-258` 拆分为 `rate_limit_attempt` / `server_error_attempt` 两个独立计数器，各配 `rate_limit_exhausted` / `server_error_exhausted` 标志
- **测试**: `test_rate_limit_then_server_error_retries_independently`

### Bug 3: group_context_store=None 时创建 broken adapter

- **现象**: `_build_channel_registry` 允许 `group_context_store=None`，导致 FeishuAdapter 构造时传入 None 引发后续 NPE
- **根因**: 参数类型标注 `GroupContextStore | None = None`，无运行时校验
- **修复**: `main.py:2890-2896` 当 feishu channel 启用且 `group_context_store is None` 时立即 raise ValueError
- **测试**: `test_build_channel_registry_without_group_context_store_raises`
