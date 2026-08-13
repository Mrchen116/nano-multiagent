# bugfix-536-M1: recovery delivery — Tasks

> 对齐: ../design.md v1

## 目标

让正常自动压缩保持父 run 存活；当非用户中断发生在已接受插话尚未消费时，由 Kernel 提供可结算的恢复身份与 batch 描述，Gateway 将原聊天的可见交付责任恰好一次交给关联 successor。

## 退出标准

- [ ] 自动压缩 await 周期发出 `run_heartbeat(source=compaction)`，且 sidechain 内容仍保持静默。
- [ ] successful steer 返回 opaque `pending_id`；异常终态的 continuation queued status 与 exactly-once settlement 完整关联 batch。
- [ ] Gateway ledger 区分已消费前缀与未消费后缀，验证 successor/settlement，覆盖失败收口与 `/stop`、`/new`、shutdown 竞态。
- [ ] `recovery_adopted` 只 seed successor delivery context，不重复 external ACK/relay sent receipt；最终文本只从 batch anchor 投递一次，所有 follower 各自恰好一次 terminal lifecycle。
- [ ] 最窄相关 pytest、Ruff、docs check、`git diff --check` 全绿，并留下真实 Gateway 入口验证证据。

## 测试策略

- 保护的回归风险与可观察 seam: parent compaction 的 SDK stream liveness；`RunInfo.pending_id` 与 `Kernel.stream()` 的 continuation/settlement 协议；Gateway common coordinator 对 Web IM/外部 channel 的 lifecycle、可见 final output 与会话释放。
- 已有保护与处置: 扩展 `tests/unit/test_loop_compact.py`、`tests/unit/agent/runs/test_run_control_pending_origin.py`、`tests/contract/test_kernel_sdk_behavior_contract.py`、`tests/unit/personal_assistant/test_session_run_coordinator_{admission,terminal}.py`、`tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`、`tests/integration/test_session_run_coordinator_real_kernel.py`；同一失败原因只在最低 owner 断言，integration 仅保护真实 Kernel→Gateway 接线和最终投递。
- 落层/目录/marker: `tests/unit/`、`tests/contract/`、`tests/integration/`，marker: 无。无需真浏览器或外部服务依赖；真实入口为 common Gateway `dispatch()` 对真实 Kernel 的进程内产品入口。
- 文件归属: 扩展上述既有 owner；coordinator ledger 若现有超长测试文件不宜继续堆积，则新建语义 owner `tests/unit/personal_assistant/test_recovery_handoff.py`，避免以 milestone 命名。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 无；可复查的入口证据由 integration regression 固化并在 progress 记录。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| compaction 与 sidechain 静默 | `tests/unit/test_loop_compact.py` | keep | 同一 loop call-site 的最低 owner，扩展 heartbeat 断言 | focused pytest |
| pending FIFO/origin | `tests/unit/agent/runs/test_run_control_pending_origin.py` | rewrite-merge | pending identity 成为同一 stable queue contract，合并进既有断言 | focused pytest |
| SDK steer/continuation | `tests/contract/test_kernel_sdk_behavior_contract.py` | keep | SDK public seam owner，扩展 identity/descriptor/settlement | focused pytest |
| same-run steer、consumed prefix | `tests/unit/personal_assistant/test_session_run_coordinator_admission.py` | keep | 正常路径必须不退化；既有 consumed prefix 用例继续保护 | focused pytest |
| stall、terminal、shutdown | `tests/unit/personal_assistant/test_session_run_coordinator_terminal.py` | rewrite-merge | 旧测试把全部 follower 失败锁成事故行为；改为 recovery suffix 与 shutdown 明确收口 | focused pytest |
| delivery context ACK/receipt | `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` | keep | lifecycle adapter 是 no-ACK adoption 的最低 owner | focused pytest |
| real Kernel/coordinator chain | `tests/integration/test_session_run_coordinator_real_kernel.py` | keep | 仅此层能证明 SDK event 和 common Gateway delivery 接线 | focused pytest |

前端 UI: N/A。无原型/reference、浏览器或样式变化。

## Roadpoints

### R1 — 父 run liveness 与 Kernel recovery protocol

- 状态: DONE
- 步骤: 红测 compaction heartbeat、opaque pending id、multi-origin batch descriptor、old-terminal-first 与 exactly-once settlement；最小实现 run-control/registry/SDK contract。
- 验证: focused unit + contract tests；`agent.sdk` surface contract。

### R2 — Gateway recovery ledger 与 delivery adoption

- 状态: DOING
- 步骤: 红测 prefix/suffix、valid/corrupt/duplicate/late recovery、logical active marker、typed adoption、ACK/receipt/final delivery count 与 control/shutdown 收口；实现 ledger 并接入 coordinator/runtime delivery。
- 验证: focused coordinator/lifecycle unit tests。

### R3 — 跨层入口回归与交付门禁

- 状态: TODO
- 步骤: 以真实 Kernel + common Gateway dispatch 固化 old terminal→successor→settlement→visible completion 路径，并验证恢复后下一条消息、正常 same-run steer、`/stop`、`/new` 不变。
- 验证: focused integration、相关 pytest 全集、Ruff、docs check、`git diff --check`。
