# M211 修复 current-main M170 复验脚本 schema 漂移

## Milestone Context
- Goal: 让 current-main 的 M170 fresh runtime 复验路径不再依赖历史 schema/旧 UI 假设，能在同一轮 fresh runtime 中继续完成 typed mention、picker mention、NO_REPLY 终证，并输出当前主线可信结构化证据。
- Test Command: `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py && python ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
- Scope Guard: 仅修改 `ACCEPTANCE/**`、`scripts/acceptance/**`、`src/IM/**`、`tests/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`；禁止修改 `data/dev-tasks.json`。
- Prevention: 必须以 fresh runtime 的真实 IM 前端为准；不能继续依赖旧列名；若替换脚本也必须保留 fresh browser 结构化证据与截图。

## Roadpoints

### R1 适配 current-main runtime schema 与结果采集
- Status: TODO
- Acceptance:
  - 复验脚本不再查询 `messages.sender_id`、`relay_tasks.id`、`conversation_events.detail` 等旧字段。
  - 结构化结果改为记录 current-main schema 下的消息、relay、event 关键字段。
  - 运行脚本时，fresh runtime 上不会再因 SQL schema 漂移而崩溃。
  - 结果 JSON 能清晰区分 typed mention、picker mention、NO_REPLY 三段证据。
- Tests Plan:
  - unit: 覆盖 SQL 查询与结果整理，快速锁定 schema 漂移。
  - contract: 断言脚本输出字段与 current-main schema 对齐。
  - integration: 暂不新增，已有 runtime/relay 门禁负责后端链路。
  - e2e: 由 `python ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` 验证真实入口。
- Expected Tests:
  - `tests/unit/test_m170_rerun_acceptance.py::test_latest_message_matching_reads_current_main_message_schema`
  - `tests/unit/test_m170_rerun_acceptance.py::test_events_for_message_reads_current_main_event_schema`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - `PROGRESS` 记录 schema 取舍、证据与提交哈希。

### R2 稳定 current-main 群聊 UI 复验路径并补齐 fresh 证据
- Status: TODO
- Acceptance:
  - 复验脚本在 current-main UI 上不因 strict locator 冲突崩溃。
  - 同一轮 fresh runtime 可完成群聊创建、typed mention、picker mention。
  - 脚本产出 fresh screenshot 与 JSON，记录 mention picker 候选、composer 值、relay 结果。
  - 若 NO_REPLY 失败，失败点来自 fresh browser 终证而非脚本自身崩溃。
- Tests Plan:
  - unit: 覆盖关键 locator/文本探测辅助函数的选择策略。
  - contract: 断言 NO_REPLY 检查关键词列表稳定输出。
  - integration: 复用现有 pytest 门禁，不额外扩张范围。
  - e2e: `python ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` 在 fresh runtime 上实跑。
- Expected Tests:
  - `tests/unit/test_m170_rerun_acceptance.py::test_no_reply_probe_flags_internal_status_leaks`
  - `tests/unit/test_m170_rerun_acceptance.py::test_result_json_includes_current_main_turn_summaries`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - `PROGRESS` 写清 fresh runtime 入口验证、证据文件与回滚点。
