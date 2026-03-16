# M211 修复 current-main M170 复验脚本 schema 漂移

## Milestone Summary
- Goal: 修复或替换 current-main 上的 M170 real-browser rerun acceptance 路径，使其适配 fresh runtime schema 与当前 UI，并继续产出 typed mention、picker mention、NO_REPLY 的结构化证据。
- Baseline:
  - Tests: `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py` 已绿。
  - Acceptance: `python ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` 基线失败，现状为 Playwright strict locator 命中多个 `Agent M170 Alpha` 元素；同时脚本源码仍保留旧 schema 查询，属于本 milestone scope。
- Notes:
  - current-main runtime schema 已确认为：`messages.sender_user_id`、`relay_tasks.relay_task_id`、`conversation_events.event_id/payload_json`。
  - 需要以 fresh browser 证据为准，不接受只修 API/mock。

### R1 适配 current-main runtime schema 与结果采集
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 稳定 current-main 群聊 UI 复验路径并补齐 fresh 证据
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
