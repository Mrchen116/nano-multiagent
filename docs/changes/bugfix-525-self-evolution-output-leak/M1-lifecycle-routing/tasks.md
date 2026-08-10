# bugfix-525-M1: lifecycle routing — Tasks

> 对齐: ../design.md @ 4fae135b6

## 目标

self-evolution fork 的 raw assistant/tool/turn 过程保持私有，真实 memory/Skill 更新不变；source-marked `skill_created` 由 Gateway session 级持久 subscriber 单一消费并进入既有 config sync，最终 structured review notice 保持一次。通用 fork 默认事件继承、普通 `BACKGROUND_TASK` Agent 结果和普通前台 `skill_created` 均不回归。

## 退出标准

- [x] 通用 `fork_conversation` 显式支持 `inherit` / `self_evolution` policy，默认 inherit，未知值拒绝；仅 self-improvement caller 选择 self_evolution。
- [x] self-evolution raw assistant/tool/turn 不进入父 session；`skill_created` 保留业务数据并带 `source=self_evolution`，memory/Skill 文件更新与 parent model/tool/permission 继承不变。
- [x] source-marked `skill_created` 只由 persistent `BackgroundSubscriptionManager` 使用 request.agent_id 调现有 config-sync handler；per-run observer 跳过 marked event，普通 skill event 仍由 per-run owner 处理。
- [x] 永久 regression 覆盖 fast/slow review、后续 turn 已有 subscriber、reconnect/replay、普通 background Agent output、真实 memory add、真实 skill create，以及 production Gateway manager/composition 到 config-sync 可观察结果。
- [x] 最窄相关测试、全量非 E2E、Ruff、docs-check 与 `git diff --check` 全绿；隔离真实入口完成且清理干净。

## 测试策略

- 保护的回归风险与可观察 seam: 通用 fork 事件 policy、public Kernel session stream/真实文件 side effect、Gateway persistent subscriber 的 post-terminal route、per-run observer 单 owner、composition 注入与现有 config-sync 持久结果。
- 已有保护与处置: 扩展/重写 `tests/unit/test_background_hook_fork.py`、`tests/unit/test_self_improvement_hook.py`、`tests/unit/personal_assistant/test_background_session_events.py`、`tests/unit/personal_assistant/test_background_subscription_manager.py`、`tests/unit/personal_assistant/test_tool_end_detail_passthrough.py`、`tests/integration/test_self_evolution_output_visibility.py`；在现有 Gateway composition/config-sync 测试归属处加入唯一 cross-layer 接线保护，不新增 milestone 命名文件。
- 落层/目录/marker: `tests/unit/` + `tests/integration/`, marker: 无；unit 是 policy/filter/single-owner 的最低 seam，integration 才能观察真实 Kernel fork side effect 与 production composition/config-sync 跨边界结果。
- 文件归属: Kernel raw visibility/side effect 扩展 `tests/integration/test_self_evolution_output_visibility.py`；Gateway 生命周期是不同 failure seam，新建 `tests/integration/test_self_evolution_gateway_skill_sync.py`；两者共用受控 driver `tests/helpers/self_evolution.py`，避免内部 prompt 文案和重复 harness。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 隔离 `e2e-up.sh` runtime 及其本地日志/数据库/workspace；结论和 locator 只写 progress，不提交 runtime 产物。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 通用 fork 事件可见性 | `tests/unit/test_background_hook_fork.py::test_fork_inherits_parent_execution_context` | rewrite-merge | 旧测试错误地把通用 fork 等同 self-evolution；拆出 default inherit 与 opt-in filter/source，同时保留 context 继承断言 | R1 focused pytest |
| self-improvement policy selection | `tests/unit/test_self_improvement_hook.py` threshold tests | rewrite-merge | 在既有 hook owner 中断言 caller 显式传 policy，不依赖 prompt 文案 | R1 focused pytest |
| 真实 memory/Skill side effect 与 raw 隔离 | `tests/integration/test_self_evolution_output_visibility.py` 两例 | rewrite-merge | 保留 public Kernel seam、增加 source；Gateway post-terminal/config 状态移入独立 lifecycle owner，避免新文件超限和 failure seam 混杂 | R1/R3 focused pytest |
| structured review exact-once | `tests/unit/test_self_improvement_hook.py` review publisher test | keep | hook 是 notice 唯一 owner；不在提前结束 collector 上做同义计数 | R1 focused pytest |
| persistent session filter、普通 background output 与 reconnect | `tests/unit/personal_assistant/test_background_session_events.py` | rewrite-merge | 扩展 source-marked skill route 与 replay cursor，同时保留 ordinary background assistant path | R2 focused pytest |
| manager post-terminal/后续 turn lifecycle | `tests/unit/personal_assistant/test_background_subscription_manager.py` | rewrite-merge | manager 是 agent identity、already-active 与 handler ownership 的最低 seam | R2 focused pytest |
| ordinary vs marked skill single owner | `tests/unit/personal_assistant/test_tool_end_detail_passthrough.py::test_skill_created_event_reaches_handler_without_im_connection` | rewrite-merge | 保留 ordinary per-run behavior并添加 marked skip；marked route 由 manager test 保护 | R2 focused pytest |
| mode-aware config reconciliation | `tests/unit/personal_assistant/test_gateway_im_config_sync.py` skill-created tests | keep | 已覆盖 default/explicit、agent/global 真实 config state；cross-layer 只需证明 production wiring reaches this handler | R3 focused pytest |
| production Gateway post-terminal lifecycle | 无（搜索 manager/composition/config-sync integration） | rewrite-merge | 新建 `test_self_evolution_gateway_skill_sync.py`，因为 Kernel-only integration 与 unit wiring 均无法暴露 terminal 后 consumer 丢失 | R3 integration pytest |

UI / Prototype / Reference Contract: N/A（后端 Kernel/Gateway 生命周期修复，无前端展示设计）。

## Roadpoints

### R1 — 显式 fork event policy 与 Kernel 业务事件标记

- 步骤: 先写 default-inherit、self-evolution opt-in/source 与 unknown-policy 红测；实现最小 policy；self-improvement 显式选择；更新真实 memory/Skill integration driver。
- 验证: fork/hook + public Kernel self-evolution focused pytest，记录 red→green。

### R2 — Gateway persistent 单 owner 路由

- 步骤: 先写 subscriber/manager post-terminal、already-active、reconnect/replay、ordinary background output 与 per-run owner 红测；实现 marked-skill filter/callback、manager request.agent_id route、observer skip。
- 验证: subscriber/manager/observer/coordinator focused pytest，记录 replay cursor 与无重复 owner 证据。

### R3 — Production composition 到 config-sync 的跨层闭环

- 步骤: 先写 production composition 注入的跨层红测，驱动 real Kernel skill-create event 穿过 manager 到现有 AgentConfigSync，并覆盖 fast/slow 与后续 turn；保持现有 mode-aware config-sync assertions。
- 验证: integration + composition/config-sync focused pytest；以持久配置/catalog/session refresh 可观察结果证明，不止 Kernel stream。

### R4 — 比例验证与真实入口

- 步骤: 跑完整受影响矩阵、全量非 E2E、Ruff、docs-check、diff gate；按 worktree runtime 契约起隔离栈验证正常回答 + structured notice/无 raw bubble，随后 down 并确认进程/端口/secret 清理。
- 验证: 命令、结果、runtime locator/限制写入 progress；更新 milestone 实施证据，不改 frozen delta-spec。
