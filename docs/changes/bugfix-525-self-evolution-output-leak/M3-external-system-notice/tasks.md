# bugfix-525-M3: external system notice — Tasks

> 对齐: ../design.md（Design Review Round 6 approved）

## 目标

只有 self-improvement 真实成功写入 memory/skills 时才产生可归因的更新回执；Gateway 用本轮 originating trace 精确恢复触发源，向 shadow IM 投递既有 structured notice，并仅在飞书触发时经既有 external sender 向原 chat 投递一行简短 Bot 文本。无写入、失败和 raw side-chain 过程保持私有，CLI 只显示真实更新对象。

## 退出标准

- [x] hook 以 call id 关联 tool call/result，仅认可批准的 mutating action、`error is None` 且 structured `success` 不为 `false`；真实目标非空才发布，incomplete 已写入仍发布。
- [x] public Kernel 的既有 trace 从 `RunRecord` 贯通 `TurnRequest` 到本轮 HookContext，并进入 review event。
- [x] coordinator 在 submit 前注册 immutable trace route、submit 失败撤销；manager 精确消费，缺失 fail-closed，最多保留 4096 项且 oldest-first 淘汰。
- [x] shadow IM 与 external sender 独立 best-effort；仅飞书来源外发当前 notice，稳定 identity 支持 replay 去重，其他 system/runtime event 不外发。
- [x] CLI 对 memory/skills/both 显示既有 updated line，无写入时无误导行；ordinary background output、Skill config-sync 与 raw privacy 不回归。
- [x] 专用非生产 Feishu profile 真栈验收覆盖成功通知、no-save/失败静默、原 chat/shadow 路由、raw 不泄漏与 cleanup。
- [x] focused、affected、full non-E2E、Ruff、docs-check、diff-check 全绿。

## 测试策略

- 保护的回归风险与可观察 seam: hook 的真实更新事实从 `ForkResult.turn_result` 可观察；Kernel trace 从 public submit/session event 可观察；Gateway route 从 manager/coordinator 与 production composition 的 shadow/external 投递结果可观察；CLI 从 event consumer 输出可观察；外部产品路径从专用 Feishu chat + shadow IM 可观察。
- 已有保护与处置: 扩展 `tests/unit/test_self_improvement_hook.py`、`tests/unit/test_background_hook_fork.py`、`tests/unit/personal_assistant/test_background_subscription_manager.py`、`test_session_run_coordinator_terminal.py`、`test_external_visible_delivery.py`、`test_gateway_build_runtime.py`、`tests/unit/test_cli_background_runs.py`；扩展现有 self-evolution Kernel/Gateway integration 与 critical-path fixture，不创建按 milestone 命名的平行测试。
- 落层/目录/marker: pure outcome/route/projection 在 `tests/unit/`（无 marker）；public Kernel + production Gateway 交错在 `tests/integration/`（无 marker）；真 IM/Gateway/Feishu 在 `tests/e2e/`（`e2e`）。
- 可选依赖 importorskip: 无；真 Feishu 依赖由仓库 identity guard 和私有 profile 前置明确阻断，不能用 skip 代替验收。
- 本 milestone 产生的一次性验收证据: 专用 Feishu nonce、message id、shadow system notice 摘要及 cleanup 记录写入本目录 `evidence/feishu-self-evolution.md`；secret、完整日志、PID/runtime 不提交。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| hook 当前按 review 范围发布而非真实写入 | `tests/unit/test_self_improvement_hook.py::TestSessionEventPublish` | rewrite-merge | 改为结构化 call/result outcome，覆盖成功、read/no-save、失败、incomplete | focused hook suite |
| fork raw 隔离与真实 memory/skill 写入 | `tests/integration/test_self_evolution_output_visibility.py` | rewrite-merge | 保留真实 fork，更新 event 判据与 originating trace | focused integration |
| persistent manager 固定首次 reply context | `tests/unit/personal_assistant/test_background_subscription_manager.py::test_session_event_uses_subscription_reply_context_after_binding_invalidation` | rewrite-merge | 旧前提正是串路由风险，改成 per-trace route、容量、missing/submit failure | manager/coordinator suites |
| shadow-only structured notice | `tests/unit/personal_assistant/test_external_visible_delivery.py::test_system_notification_for_feishu_binding_targets_shadow_im_only` | rewrite-merge | 飞书触发改为 shadow + external；补 IM origin、overlap、dedupe、独立失败 | delivery suite |
| production composition wiring | `tests/unit/personal_assistant/test_gateway_build_runtime.py` | keep/extend | 证明复用现有 sender/config-sync，无新 adapter | composition suite |
| CLI subject renderer | `tests/unit/test_cli_background_runs.py::test_processor_renders_flat_self_evolution_review_subject` | keep/extend | success memory/skills/both 继续由同一 consumer 显示；no-write 由 upstream event absence 保证 | CLI + hook tests |
| M2 真栈 raw privacy/skill activation | `tests/e2e/critical_paths/test_self_evolution_*` | keep/extend | 保留不同失败原因；扩 controlled fixture 支持 M3 外部 journey，不复制 Kernel 单测 | critical-path + Feishu run |
| macOS spawn 导入超过 shutdown join budget | `tests/unit/personal_assistant/test_feishu_worker_runtime.py` | extend | startup 与 stop 是不同生命周期边界；固定独立 30 秒 startup budget，保留原 join timeout | worker focused suite + 真飞书启动 |

Frontend UI: N/A。M3 不改前端或视觉；shadow IM 沿既有 system notice schema/UI，验收观察产品状态但不新增 UI 状态矩阵。

Prototype / Reference Contract: N/A。

## Roadpoints

### R1 — 真实更新回执与 Kernel trace

- 状态: DONE
- 步骤: 先补 hook outcome/trace 与 core propagation 红测；实现 call-id 成功分类和 opaque trace 贯通。
- 验证: hook/core focused tests；真实 public Kernel memory/skill/no-write/incomplete integration。

### R2 — 精确 per-run route 生命周期

- 状态: DONE
- 步骤: 先补 manager route、4096 oldest-first、missing fail-closed、coordinator pre-submit/submit-failure 红测；实现 route registry 与 trace admission。
- 验证: manager/coordinator unit + Kernel/Gateway overlap integration。

### R3 — structured notice 双出口与 composition

- 状态: DONE
- 步骤: 先补飞书/IM origin switching、overlap、stable dedupe、external/shadow independent best-effort 红测；扩既有 callback 并接入 existing external sender。
- 验证: delivery/composition/observer/background affected suites。

### R4 — CLI、跨层与真栈 fixture

- 状态: DONE
- 步骤: 更新 CLI contract coverage；扩受控 LLM/critical-path journey，证明真实 Kernel/Gateway 交错并发、no-write 静默与 raw 隔离。
- 验证: CLI、Kernel/Gateway integration、M2 critical-path journeys。

### R5 — 专用 Feishu 验收与收尾门禁

- 状态: DONE
- 步骤: identity guard 后启动隔离 `--feishu` 栈，执行 probe 和成功/no-save/failure/source-switch journey，保存脱敏证据并清理；归并 delta 到 canonical docs。
- 验证: 真飞书 message ids/nonce + shadow IM state；full non-E2E、Ruff、docs-check、diff/shell checks。

### R6 — Round 4 飞书 route-anchor 稳定性闭环

- 状态: DONE
- 步骤: 按 systematic-debugging 先复现并比较 probe/route-anchor 的发送身份、chat/message form、dedupe/window、listener 生命周期和 Gateway 边界日志；只修已证明根因，不延长 timeout 或加盲重试；成功/失败都清理 fixture/config receipts。
- 验证: 同一持久 shell 的 exact `up -> probe -> journey -> down` 连续可重复，route anchor 经真实 Feishu ingress 到达受控 LLM，runtime 无残留。

### R7 — 真实 Coding CLI / PTY 产品验收入口

- 状态: DONE
- 步骤: 复用现有 OpenAI-compatible 受控 fixture 与 Coding CLI public entry，提供 worktree-local PTY journey；覆盖 memory/skills/both 与 no-save/read/failure，并保存脱敏 transcript/断言和 cleanup 证据。
- 验证: reviewer 不读取源码或单测即可从真实终端观察三类既有 `... updated` system line，负面场景无误导 update line。

### R8 — Round 4 收尾门禁

- 状态: DONE
- 步骤: 更新 acceptance runbook/evidence/progress；运行 focused、affected、full non-E2E、Ruff、docs-check、diff/shell gates；合并推送 unit 并清理 fix worktree/branch。
- 验证: reviewer-fix commits 已进入 `unit/bugfix-525`，远端同步且运行资源、runtime artifacts、worktree/branch 全清理。

### R9 — Code review：全 origin 的 Skill 唯一 owner

- 状态: DONE
- 步骤: 先补 foreground、heartbeat、cron 在无现存 subscriber 时的红测；让 owner-direct 共用 stream 在 per-run observer 前按 run anchor admission persistent subscriber，保留 foreground terminal replay 与 observer 对 marked Skill 的隔离。
- 验证: early/terminal-late Skill 均只由 persistent manager 调用一次 config-sync；已 active session 不创建第二 subscriber，普通 realtime/后台输出契约不变。

### R10 — Code review：异步通知与 subscriber callback 生命周期

- 状态: IN PROGRESS
- 步骤: 先补阻塞 external sender 的 event-loop 红测和三类 callback in-flight close 红测；最窄 offload 同步 sender，并抽取模块内 callback envelope。
- 验证: sync sender 在线程执行、awaitable sender 仍可用；ordinary output、Skill、structured notice 的分类、日志、取消和 shutdown handoff 不变。

### R11 — Code review：共享 Skill config mutation 串行化

- 状态: TODO
- 步骤: 先补 `ensure_agent_skills_enabled` 与 `handle_skill_created` 跨线程竞争红测；在共享 read/merge/PATCH seam 复用既有 `RLock`。
- 验证: 最终 explicit allowlist 同时包含 activation bundle 与 self-evolution Skill，无 409 丢更新；default discovery/global scope 保持。

### R12 — Code review：Feishu pre-ready child fail-fast

- 状态: TODO
- 步骤: 先用真实 spawn 补 child 在 ready 前退出却消耗完整 startup budget 的红测；在既有 monotonic deadline 内使用短有界 wait slice 并检查 child liveness。
- 验证: pre-ready exit 快速失败；early-False/慢 ready 可继续使用完整 30 秒总预算，shutdown join timeout 不变。

### R13 — Code review closure gates

- 状态: TODO
- 步骤: 汇总 finding closure 与证据；运行 focused、affected、full non-E2E、Ruff、docs-check、diff-check。
- 验证: reviewer-fix commits 进入并推送 `unit/bugfix-525`，milestone worktree/branch 清理。
