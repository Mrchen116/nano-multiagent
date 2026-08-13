# bugfix-536-M2: Recovery closure and exact reset repair — Tasks

> 对齐: ../design.md v1

## 目标

修复 recovery successor 无可接管尾随消息时遗留 active owner 的终态收口，并恢复精确
`/new` 的真实 Kernel 上下文隔离；非精确命令、普通 steering、控制和 shutdown 围栏保持不变。

## 退出标准

- [ ] adopted successor 非 completed 且没有未消费 follower suffix 时，root 与 follower 恰好各终态一次，active/busy 清空，下一条普通消息可提交并回复。
- [ ] successor 仍有 suffix 时继续 recovery handoff；`/stop`、`/new`、shutdown 的既有围栏与无重复投递不变。
- [ ] 精确 `/new` 后普通消息由新 Kernel transcript 执行，不含前一会话用户/助手上下文；非精确 `/new ...` 仍作为普通输入。
- [ ] 相关 unit、真实 Kernel integration、M1 aggregate 与隔离 Web IM 真栈路径通过。

## 测试策略

- 被测行为（来自退出标准）：recovery owner 的失败收口；精确 `/new` 的 bind-to-fresh-transcript；命令精确匹配与控制围栏。
- 已有测试在：`tests/unit/personal_assistant/test_recovery_handoff_coordinator.py`（扩展）和 `tests/integration/test_session_run_coordinator_real_kernel.py`（扩展）；无新测试文件，两个文件均为所属行为测试面且仍小于 400 行。
- 落层/目录/marker：`tests/unit/`、`tests/integration/`，marker：无；真 Web IM 作为一次性 live acceptance，不固化依赖本机 LLM 的断言。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离真栈 session binding/transcript 与 IM 可见消息检查，命令和结果记录于 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| recovery successor 的 terminal handoff | `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py::test_correlated_successor_delivers_once_and_terminalizes_all_followers` | keep | 原已覆盖完成 successor；新增无 suffix 非完成分支保护收口。 | focused pytest |
| exact `/new` control publication | `tests/unit/personal_assistant/test_session_run_coordinator_admission.py::test_new_suppresses_a_running_old_final_before_confirming_fresh_session` | keep | 原覆盖活跃 run 抑制；新增真实 Kernel transcript 隔离覆盖无活跃 reset。 | focused pytest |

## Roadpoints

### R1 — 建立两条可复现的失败边界

- 步骤: 追踪 coordinator/Kernel reset 路径，补 root/follower recovery failure 和真 Kernel reset transcript 的红测。
- 验证: 两条新测试在 `dc3173750` 失败，现有 M1 aggregate 保持绿。

### R2 — 收口失败的 adopted successor

- 步骤: 在 recovery owner 层确保无 suffix 的失败 successor 关闭其 active marker，再由既有失败路径终态化 root/followers。
- 验证: recovery focused tests 通过，suffix re-handoff、控制和 shutdown 用例保留。

### R3 — 修复精确 `/new` 的实际 reset path

- 步骤: 修正 Gateway/Kernel 状态复用点，使 reset 后 bind 的 session 不携带旧 transcript；补真实 Kernel 回归。
- 验证: reset integration、命令边界、M1 aggregate 与隔离 Web IM 路径通过。
