# bugfix-471-M1 — Progress

## 启动记录

- 已读 `incident.md`、`design.md`、项目规则、`docs/TESTING_GUIDE.md`、现有 Kernel/Gateway/session/scheduler 实现与测试。
- 基线：`PYTHONPATH=src pytest -m 'not e2e'` — 3628 passed，1 skipped，20 deselected（2026-07-21）。
- 本 milestone 不修改前端、IM timeline 或 divider；M2 负责这些可见缓存边界。

### R1 — Kernel runtime replacement

- Context: 配置变更不能创建第二份 session 或 transcript，且 model 与 capabilities 必须同一原子配置。
- Decision: 增加 SDK `SessionRuntimeConfig` 及 identity/state/result DTO；创建和 replacement 都在 transcript 持久化完整 raw runtime。`ConversationSession` 经既有 turn gate 执行 replacement，`Kernel.submit()` 从会话 runtime 获取 model 并拒绝冲突的 per-run override。
- Rationale: session 自己拥有 transcript、payload 与 turn 串行；把 replacement 放入该事务边界，防止 active turn 中途混用配置，并在重启后可由 transcript 还原。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/agent/session tests/integration/test_session_run_coordinator_real_kernel.py` — 24 passed；`PYTHONPATH=src ruff check src/agent/sdk src/agent/core/session src/agent/core/runs/executor.py tests/integration/test_session_run_coordinator_real_kernel.py` — passed。
  - Entry: integration 用真实 `build_kernel()`、会话、run 和 fake LLM 验证 replacement 后同一 session 以新 model 发起请求且请求历史保留前一轮用户内容。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_session_run_coordinator_real_kernel.py::test_kernel_reconfigures_one_session_without_losing_transcript`，见 Tests。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A（M2）。
- Rollback: 回退 `469c4eeb0`，恢复 per-run model 语义与无 replacement 的 session API。
- Commits: C1=c2e46af7f，C2=469c4eeb0，C3=34305241b。

### R2 — Gateway admission continuity

- Context: Agent 发布新配置后，旧机制按 catalog revision 删除 binding，导致下一条消息被送进空 transcript。
- Decision: Gateway 用 `project_agent_runtime()` 统一创建与 reconfigure 的完整 raw runtime；binding SQLite 持久 applied identity/schema/profile provenance，正常新 run 在同一 transition lock 下读取最新 snapshot、inspect/reconfigure、持久 applied identity 后才 submit。发布只更新 catalog，不删除 binding。
- Rationale: 只由 Kernel 生成 identity，且配置变更、runtime replacement 与 submit 的线性顺序由同一个聊天锁维护，避免 model 与能力集撕裂；活跃 run 的 steer 仍只复用冻结的 handle。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/unit/personal_assistant/test_gateway_session_binder.py tests/unit/personal_assistant/test_persistent_session_binding_store.py tests/unit/personal_assistant/test_config_sync_concrete_owners.py tests/integration/test_session_run_coordinator_real_kernel.py tests/contract/test_gateway_inbound_ownership_contract.py` — 54 passed。
  - Entry: 真实 `build_kernel()` integration 通过 coordinator 的 public `dispatch()` 入口运行，覆盖 Kernel terminal 与 Gateway active marker 的重叠窗口；其余配置更新行为以 Gateway 公开 binder/coordinator 接口回归保护。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_session_run_coordinator_admission.py::test_config_publish_reconfigures_same_session_only_for_next_run` 验证同一 `kernel_session_id` 保持且下一 run 才换完整 runtime；`test_active_run_steer_keeps_original_runtime_after_config_publish` 验证活跃 steer 不热切换。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A（M2）。
- Rollback: 回退 `190ba1dab`，恢复旧的按 revision 删除 binding 行为。
- Commits: C1=a8e5572dc，C2=190ba1dab，C3=4179277d6。
- Next: M1 的三个 roadpoint 均已完成；证据矩阵见本文末尾。

### R3 — Background parity and live verification

- Context: heartbeat 复用既有专用 session、cron 创建新专用 session；两者都必须使用与聊天新 run 相同的完整 runtime，但不具备聊天时间线边界。唯一产品 projection 的 `prompt_for()` 也必须让 system prompt 进入实际请求和 runtime identity。真栈验收须覆盖 Web IM、Feishu、配置边界和 Gateway restart。
- Decision: 让 `gateway/kernel_client.py` 在后台创建与 heartbeat 复用路径中传递并检查 `SessionRuntimeConfig`；让 `product.py` 将非空 system prompt 固定投影为 `pa.system_prompt_override`，位于用户 custom prompt 前。`session_composition.py` 两个投影路径均以 `dict(config.features)` 保留显式空映射。真栈以同一 session 的前后请求及用户可见回复为准。
- Rationale: scheduler 只能经 Gateway adapter 调用 in-process Kernel；若沿用 capability-only 创建，后台 session 不会拥有 resolved model 和完整 runtime。system prompt、features 以及 tools 都属于有效运行配置，必须与 model 一起进入 identity。把空 map 折叠为 `None` 会违背 SDK 的显式语义。按同一 external/session binding 对账才能证明配置变化没有换会话或丢历史。
- Scope confirmation: `gateway/kernel_client.py` 是 scheduler 的必要 adapter seam，`product.py` 是 system prompt 的唯一 runtime projection seam；两者按 orchestrator 确认纳入 M1，未改动 `design.md`。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_heartbeat_session_binding.py tests/unit/personal_assistant/test_unattended_session_skills.py tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/integration/test_session_run_coordinator_real_kernel.py tests/integration/test_prompt_sections_golden.py` 覆盖 heartbeat reuse runtime 对齐、cron 完整 runtime 创建、空 features、system prompt 顺序/identity、恢复及 fork。最终全树 `PYTHONPATH=src pytest -m 'not e2e'` 为 3637 passed，1 skipped，20 deselected；`ruff check` 与 `ruff format --check` 通过。
  - Entry: `evidence/live-web-im.json` 记录同一 direct session 在配置更新与 Gateway restart 后回复 `FINAL-DIRECT DIRECT-858E651CD8`，同一 group session 在配置更新后回复 `FINAL-GROUP GROUP-C199C4971D`。`evidence/live-empty-features-runtime.json` 记录空 features 的用户可见回复、restart 后历史理解和 transcript 内的显式 `{}`。
  - E2E/Regression: `evidence/live-llm-request-summary.json` 记录 direct 的 `[]→[read]` 与 group 的 `[read]→[]`，两条边界后请求均带前一 user message。`evidence/live-feishu.json` 记录同一 Feishu binding `sess_2b91b25422a18eee` 的 phase-one、phase-two 和 restart 后可见回复与 request 对账。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A（本 roadpoint 不修改前端）；Web IM 真实入口验收已作为 Entry 证据执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A（M2）。
- Rollback: 回退 `f545b307e`、`062fb92ea` 与 `2bec35fbf` 可恢复后台 capability-only/旧投影行为；回退真栈文档提交不影响运行时。不得只恢复 features truthiness 而保留 SDK 的 `None`/`{}` 区分。
- Commits: C1=e9070bda1、c0675b5ec；C2=f545b307e、062fb92ea、2bec35fbf；C3=6aa3d9095、43630400b、cd2e5f362、84c594813。
- Next: M1 已完成；M2 负责缓存边界与 timeline 语义。

## M1-C1～C6 证据矩阵

| 退出标准 | 自动化回归 | 真栈/请求证据 | 结论 |
|---|---|---|---|
| M1-C1：direct/group 的 model、prompt、skills、tools、features 变化后保持历史 | `tests/integration/test_session_run_coordinator_real_kernel.py::test_kernel_reconfigures_one_session_without_losing_transcript`；`tests/integration/test_prompt_sections_golden.py::test_pa_system_prompt_precedes_custom_prompt_in_runtime_identity`；`tests/unit/personal_assistant/test_session_run_coordinator_admission.py::test_config_publish_reconfigures_same_session_only_for_next_run` | `evidence/live-llm-request-summary.json`：direct tools `[]→[read]`、group tools `[read]→[]`；两者后请求保留前一 user message，model 与 phase system prompt 正确。`evidence/live-empty-features-runtime.json` 锁定显式 `{}`。 | 通过 |
| M1-C2：active steer 保持旧配置，排队新 run 只采用最终版本 | `tests/unit/personal_assistant/test_session_run_coordinator_admission.py::test_active_run_steer_keeps_original_runtime_after_config_publish`；`test_config_publish_reconfigures_same_session_only_for_next_run` | coordinator 在 per-session admission 读取 latest catalog；上述回归锁定 steer 与最终 runtime 的顺序。 | 通过 |
| M1-C3：restart、不同聊天不串线、Feishu 同外部对话连续 | `tests/integration/test_session_run_coordinator_real_kernel.py::test_kernel_recovery_preserves_empty_feature_runtime_identity`；`tests/unit/personal_assistant/test_inbound_pipeline_agent_sessions.py::test_config_publish_reconfigures_group_session_without_changing_address` | `evidence/live-web-im.json` 覆盖 direct/group 与 restart；`evidence/live-feishu.json` 覆盖同一 Feishu binding 在 phase one、phase two、restart 后的连续历史及三次可见回复。 | 通过 |
| M1-C4：Kernel replacement、identity、恢复、fork 与 Gateway admission failure/ordering | `tests/integration/test_session_run_coordinator_real_kernel.py` 的 reconfigure、recovery、identity canonicalization、fork 场景；`tests/unit/personal_assistant/test_gateway_session_binder.py`、`test_persistent_session_binding_store.py`、`test_session_run_coordinator_admission.py` 的 admission、baseline、failure 与不提交场景。 | R1/R2 的 Tests/Entry 记录和最终全树运行。 | 通过 |
| M1-C5：heartbeat/cron 使用完整 runtime，且无聊天边界 | `tests/unit/personal_assistant/test_heartbeat_session_binding.py::test_heartbeat_reused_session_aligns_current_agent_runtime`；`tests/unit/personal_assistant/test_unattended_session_skills.py::test_unattended_session_creates_complete_runtime_when_model_resolves`；`test_cron_runner_creates_complete_runtime_through_gateway_adapter` | 后台 session 没有聊天 anchor；不产生聊天 divider 是 adapter/session 边界的自动化断言范围。 | 通过 |
| M1-C6：边界前后 messages/tools/model、restart、Web IM direct/group、真实 Feishu 与全树 | 对应 R1–R3 窄回归与完整 `PYTHONPATH=src pytest -m 'not e2e'`：3637 passed，1 skipped，20 deselected。 | `evidence/live-llm-request-summary.json`、`live-web-im.json`、`live-empty-features-runtime.json`、`live-feishu.json`。Feishu 结束后恢复原 profile 与主 Gateway 的单一 listener。 | 通过 |

> 测试计数说明：3628 passed，1 skipped，20 deselected 是 M1 启动时的基线；3637 passed，1 skipped，20 deselected 是实现与文档收尾后的完成态全树结果。此前将基线数字写入最终回报不代表完成态测试计数。
