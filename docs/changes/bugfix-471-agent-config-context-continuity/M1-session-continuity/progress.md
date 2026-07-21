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
- Commits: C1=a8e5572dc，C2=190ba1dab，C3=待提交。
- Next: R3 让 heartbeat 与 cron 采用同一完整 runtime，并完成真栈验证。

## [范围确认] R3: 完整 runtime 的必要投影与 Gateway adapter seams

- 原范围清单遗漏: Milestone 范围列出 `heartbeat_scheduler.py` 与 `cron_runner.py`，未列出 `src/personal_assistant/gateway/kernel_client.py`。
- Decision: 按 orchestrator 确认将该 adapter 纳入 M1；在已解析 model 时由它把完整 `SessionRuntimeConfig` 传入 Kernel 创建后台会话，并在复用 heartbeat session 前调用 SDK inspection/reconfigure。
- Rationale: heartbeat 与 cron scheduler 只经 adapter 的 `create_session` / `submit_message` 进入 in-process Kernel，不能自行传递 typed runtime。维持 capability-only create 会生成缺少 runtime model 的后台 session，不能满足 design 已明确的 M1-C5 和 Background run admission。该改动是必要 seam 的最小实现，不新增设计决策。
- 影响范围: 仅本 milestone。
- `product.py` 原范围清单遗漏: `project_agent_runtime()` 的唯一 projection 最终调用 `prompt_for()`，但该函数原先忽略 `AgentWorkspaceConfig.system_prompt`，使完整 runtime identity 与实际模型 prompt 都缺少该字段。
- Decision: 按 orchestrator 确认将 `src/personal_assistant/product.py` 纳入 M1；将非空 system_prompt 作为 `pa.system_prompt_override` 固定置于 custom slot 的 `pa.user_custom` 前，成为完整 runtime 与 identity 的一部分。
- Rationale: system_prompt 是 M1-C1 明确要求下一新回复采用的运行配置；不在唯一投影点纳入会使 reconfigure 后的真实请求仍沿用旧语义。该最小改动不引入新决策，并保持未设置 system_prompt 的 golden 不变。
- design.md 是否同步改: 否；orchestrator 明确无需修改。
- 状态: R3 BLOCKED；完整 runtime 的 adapter/scheduler、system_prompt projection 与 Kernel fork/idempotency 修复已落地。
- 已完成真栈 Web IM 证据：`evidence/live-web-im.json` 记录同一 direct session 在配置更新及 Gateway restart 后回复 `FINAL-DIRECT DIRECT-858E651CD8`，同一 group session 在配置更新后回复 `FINAL-GROUP GROUP-C199C4971D`。`evidence/live-llm-request-summary.json` 对账 direct/group 边界前后请求：后请求仍含前一 user message，model 为 `kimiCoding:kimi-for-coding`，tools 由 direct 的 `[]→[read]`、group 的 `[read]→[]` 采用最终完整配置。
- 真栈 features 发现：IM profile 的显式 `{}` 在运行投影 `session_composition.py` 中被 truthiness 归并成 `None`；实测记录为 `config_features={}; runtime_features=None`。这违反 design 对 `None` 与 `{}` identity/persistence 区分的要求，不能声称该语义通过。
- 真正 Feishu 外部旅程阻塞：授权最小 probe（含 @bot）已成功写入测试群，但未收到 bot 回复；受管 Gateway 持续记录 `open.feishu.cn` DNS/WS 连接失败，隔离 Gateway 的 `credentialRef` 也因 ephemeral IM 无 encrypted managed-channel manifest 被显式跳过。详见 `evidence/live-feishu-blocked.json`；等待可用的真实 channel 运行环境。
- 验证：窄回归 `25 passed`；完整 `PYTHONPATH=src pytest -m 'not e2e'` — 3637 passed，20 deselected；modified-files `ruff check` 通过。
- Commits: C2=`062fb92ea`；C3 待外部 blocker 与 features 语义解决后提交。
