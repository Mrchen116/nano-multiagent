# M207 Task — 修复 M103 browserless roundtrip 长跑卡住

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M207/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M207/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M206/PROGRESS/M206-修复真实群聊中的-NO_REPLY-前端静默泄漏.md`。
- 当前处境：M207 / 修复 M103 browserless roundtrip 长跑卡住；`execution_mode=parallel`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M207`；branch=`milestone/M207`。
- 测试门禁：`pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py`
- 允许范围：`src/IM/**`、`src/personal_assistant/**`、`tests/**`、`scripts/**`、`TASKS/**`、`PROGRESS/**`、`ACCEPTANCE/**`、`LOGBOOK.md`
- 禁止范围：`data/dev-tasks.json`、`.worktrees/M205/**`、`.worktrees/M206/**`、`.worktrees/M104/**`
- Prevention rules:
  - 先定位 hang 根因，不靠放宽 timeout 掩盖。
  - 不回归已通过的 gateway registration / group creation / mention 路径。
  - 修复后必须给出稳定完成的测试证据。
  - 若根因属于既有基线问题，也按最小范围修复，但不扩散改动面。
- 基线结果：`pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py` 当前卡在 `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless`，属于本 Milestone scope，需先收口该 hang 后再跑全门禁。
- 根因假设（待 Red 证实）：`InboundPipeline._await_terminal_run()` 在存在 `stream_session_events()` 的路径下只以 `run_state.status` 作为终态判据；而 M103/M136 相关 fake kernel client 返回的 run snapshot 只含 `run_id/output_text`、缺少 `status`，导致轮询永远看不到 terminal status，从而长时间卡住。

## Roadpoints

### R1. 锁定 browserless hang 的最小根因并补红测
- Status: TODO
- Acceptance:
  - 能稳定复现并定位 `test_web_im_message_roundtrip_browserless` 的卡住点。
  - 红测直接约束当前缺陷，不依赖手工超时观察。
  - 红测覆盖 `stream_session_events` 路径与缺失 `status` 的 run snapshot 组合。
  - 红测不改变 gateway registration / group creation / mention 既有断言。
- Tests Plan:
  - unit: 在 `tests/unit/personal_assistant/test_gateway_pipeline.py` 增补最小红测，直接卡住当前 `_await_terminal_run` 终态判定缺口。
  - contract: 不新增；`get_run` 既有 contract 已定义正式客户端必须返回 `status`，本次聚焦基线测试桩与 pipeline 健壮性接缝。
  - integration: 复用 `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless` 作为真实链路复现。
  - e2e: 不新增浏览器测试；browserless 集成本身即是本里程碑真实入口。
- Expected Tests:
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::<新增红测>`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless`
- DoD:
  - 红测先失败并明确指出 hang 根因。
  - C1/C2/C3 齐全。
  - `test_command` 全绿且 PROGRESS 记录证据/回滚点/提交哈希。

### R2. 最小修复 browserless roundtrip，并回归 M103 全文件
- Status: TODO
- Acceptance:
  - `test_web_im_message_roundtrip_browserless` 在合理时间内稳定完成。
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py` 全文件通过。
  - 不回归 gateway registration、canonical agent labels、group creation before bind、group mention/NO_REPLY 路径。
  - `tests/im_service/unit/test_relay_service.py` 继续为绿。
- Tests Plan:
  - unit: 复用 R1 红测与现有 gateway pipeline 单测验证最小修复边界。
  - contract: 不新增；避免修改正式 kernel API 契约。
  - integration: 跑整份 `tests/im_service/integration/test_m103_im_gateway_e2e.py` 与 milestone `test_command`。
  - e2e: 以 browserless roundtrip 作为入口证据，不扩展到产品验收。
- Expected Tests:
  - `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py -k test_web_im_message_roundtrip_browserless`
  - `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py`
- DoD:
  - 最小实现后门禁全绿。
  - 证据写清运行时间/稳定性观察。
  - C1/C2/C3 齐全，PROGRESS 完整记录可回滚点与下一步。

## 当前结果
- 待执行。

## 回滚点
- 当前最近稳定点：`eeb7b80`（M207 worktree 创建基线）。
