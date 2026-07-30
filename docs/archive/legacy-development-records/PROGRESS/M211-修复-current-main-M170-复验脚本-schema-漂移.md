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
- Context: 旧 rerun 脚本直接查询 `messages.sender_id`、`relay_tasks.id`、`conversation_events.detail`，在 current-main fresh runtime 上已不存在，且模块 import 时就会直接执行主流程，导致单测无法稳定锁定漂移点。
- Decision: 将脚本改为可导入模块，查询切到 `sender_user_id` / `relay_task_id` / `event_id,payload_json`，并新增 turn summary / NO_REPLY probe 结果整理函数。
- Rationale: 先把 schema 与结果契约收敛到 current-main 单一真源，后续 UI 复验与 fresh 证据才能稳定复用。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
  - Entry: 单测已能直接 import 脚本并验证 current-main schema 查询结果，无需触发真实浏览器主流程。
- Rollback: `f6bcb46`.
- Commits: C1=f6bcb46, C2=d026ec4, C3=e92a45b
- Next: 继续修 current-main UI locator 与 fresh browser 复验路径。

### R2 稳定 current-main 群聊 UI 复验路径并补齐 fresh 证据
- Context: current-main 群聊创建页与线程中同名文本会重复出现，旧 `get_by_text(...).click()` strict 模式不稳定；NO_REPLY 也要求在同一轮 fresh runtime 中继续得到终证，而不能停在脚本崩溃。
- Decision: 群聊参与者改用 `label` 容器点击，mention picker 改用 label+handle 组合定位；fresh result JSON 统一输出截图、typed mention、picker mention、NO_REPLY probe，NO_REPLY probe 明确汇总前端泄漏关键词。
- Rationale: 让脚本适配 current-main UI，而不是继续依赖历史 DOM 假设；同时把失败归因收束到真实浏览器终态，而不是脚本自身脆弱性。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/tests/im_service/unit/test_relay_service.py /Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py && python /Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
  - Entry: fresh browser 已产出 `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-result.json` 与 5 张 rerun 截图；typed mention、picker mention 成功，NO_REPLY 终证来自 fresh browser，仍暴露 `Agent replied` 与 `The latest agent response finished successfully.`。
- Rollback: `f6bcb46`.
- Commits: C1=f6bcb46, C2=d026ec4, C3=e92a45b
- Next: 可直接重派 current-main M170 验收；若继续修 NO_REPLY，应以前端泄漏文案为主因切新 milestone。
