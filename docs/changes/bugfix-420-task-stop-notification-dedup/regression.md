# bugfix-420 — 回归验证

> 对齐: incident.md v1
> Review round: 1 — 2026-06-22

## Verdict

**pass**

## 验收标准覆盖

### Requirement: 停后台 bash 不再多发冗余通知

#### Scenario: 停一个仍在跑的后台 bash

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md 验收标准 |
| 验证方式 | 真实旅程：IM Web + Gateway（worktree 服务），parent agent 派后台 bash（sleep 60），再 task_stop，观察 IM 消息流 + proxy log 消息序列 |
| 证据 | proxy log session `2026-06-22_15-11-24_228_sess_e560529207c21af3`，req `15-15-54_290`（msgs=27）包含 task_stop tool_result at [26]（`Task stopped... task_type: bash status: killed`），无 task-notification；req `15-16-06_056`（msgs=29）检索全文，`bb6df7b2ac18da9c0` 相关 task-notification 不存在 |
| 结果 | **pass** |
| 备注 | bash task_stop 后 LLM 消息序列只有 [tool_result]，抑制通知生效 |

### Requirement: 停后台 subagent 的通知携带半成品产出

#### Scenario: 子 agent 已产出文字后被停

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md 验收标准 |
| 验证方式 | 真实旅程：parent agent 派后台 subagent（分析 src 下所有 Python 文件，耗时任务），等 ~5s 后 task_stop，观察 proxy log |
| 证据 | proxy log req `15-16-06_056`：task_id=`ab60221bbdf30ac6a`，task_stop tool_result at [26]（`Task stopped... task_type: subagent status: killed`），assistant 回复 at [27]，之后 at [28] 注入 `<task-notification>` 含 `<status>killed</status>` 和 `<result>I'll analyze all Python files under the \`src\` directory step by step. Let me start by recursively finding all \`.py\` files.</result>` 以及 `<error>stopped by user</error>`；对该 task_id 搜索整个 req，只有 1 条 task-notification（非重复） |
| 结果 | **pass** |
| 备注 | `<result>` 携带了子 agent 被杀前的实际 assistant 文字（第一个 text block），非空壳。通知出现在下一轮 LLM 调用，不与同一轮 tool_result 重复 |

#### Scenario: 子 agent 尚无任何产出就被停

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md 验收标准 |
| 验证方式 | 旅程中尝试：parent agent 派后台 subagent 后"立即"task_stop（人工操作，中间仅有 1~2s）；补充：单测 `test_runtime_runner_aborted_run_with_no_output_omits_result` |
| 证据 | 真实旅程中 LLM 启动几乎总已产出第一个 text block，难以制造"真正零产出"场景（proxy log req 含 `<result>...</result>` 均非空）。单测 `test_runtime_runner_aborted_run_with_no_output_omits_result` PASSED（1 passed），验证 `on_kill(result_text=None)` 路径下 `<result>` tag 不出现 |
| 结果 | **pass** |
| 备注 | 该 Scenario 为接缝级行为，在实际旅程中难以触发（LLM 启动即输出），以单测作为辅助证据。设计中此路径已通过 `result_text=None` → notifications.py 自动省略 `<result>` 保证 |

#### Scenario: 停止动作本身仍生效（不变量回归）

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md 验收标准 |
| 验证方式 | 真实旅程：对三个 task 均调用 task_stop，观察是否实际被 killed；续跑测试 |
| 证据 | proxy log 中所有被停任务 status 均为 `killed`；IM agent 回复明确说明 status: killed；进一步在 Scenario 4 (resume) 测试中，ab60221 被 killed 后成功 resume 并产出 5 个文件名 |
| 结果 | **pass** |
| 备注 | task_stop 后 subagent 仍可通过 agent 工具 follow-up 续跑，killed 终态不阻断 resume |

## 用户旅程执行记录

**Journey 1: 停后台 bash（覆盖 Scenario: 停一个仍在跑的后台 bash）**

1. parent agent 在 IM 会话中派 `bash(sleep 60, run_in_background=True)` → task_id=`bb6df7b2ac18da9c0`
2. 立即发 task_stop 停掉
3. IM 消息流：4 条，agent 回复"已停止 status=killed"；等待 5s 无额外消息
4. proxy log 核查：tool_result [26] 存在，无 task-notification，PASS

**Journey 2: 停后台 subagent（有产出）（覆盖 Scenario: 子 agent 已产出后被停 + 停止不变量回归）**

1. parent agent 派后台 subagent（分析 src 所有 py 文件）→ task_id=`ab60221bbdf30ac6a`
2. 等 ~5s 让 subagent 产出文字
3. 发 task_stop
4. proxy log 核查：tool_result [26]，之后 task-notification [28] 带 `<result>`，PASS

**Journey 3: 续跑测试（覆盖 Scenario: 停止动作本身仍生效 + resume 能力）**

1. 对已 killed 的 `ab60221bbdf30ac6a` 发 follow-up（要求续跑，列 5 个文件名）
2. IM 消息显示 subagent 成功恢复并列出 5 个路径：`IM/__init__.py` 等
3. Resume 能力验证 PASS

**Journey 4: 立即停 subagent（无产出验证辅助）**

1. 派后台 subagent（分析项目架构）→ task_id=`ab615fbe60f211eff`
2. 收到 task_id 后立即 task_stop
3. proxy log 中 task-notification 存在 `<result>` 文字（LLM 已开始生成）
4. 单测 `test_runtime_runner_aborted_run_with_no_output_omits_result` PASS 弥补真实旅程无法覆盖的零产出边界

## 复现验证

修前：proxy log `2026-06-22_11-10-19_599_sess_a6bc5b8677ab20ec` 消息 [16]（tool_result）+ [17]（task-notification 空壳）两条重复信号。

修后（本轮验收）：停 bash 后 LLM 只见 tool_result，无 task-notification；停 subagent 后 task-notification 带 `<result>`，非空壳，且与 tool_result 不在同一轮（后续 turn 注入），不重复。

## 回归测试

- 相关单测：`pytest -q tests/unit -k "background_task or task_stop or registry"` → **140 passed**（含全部 R1 红测转绿 + 既有回归）
- 全测试树：`pytest -q -m "not e2e"` → **2722 passed / 1 skipped / 0 failed**（progress.md R2 记录）
- 相邻功能：前台任务 tool_result 双通道问题（bugfix-417）不受影响；resume 能力（_resume_subagent 对 killed-in-memory 任务）验证正常

## 自动化测试增量

| 测试 | 文件 | 覆盖 Scenario |
|---|---|---|
| `test_stop_running_bash_task_kills_synchronously_and_suppresses_notification` | `tests/unit/agent/background_tasks/` | 停 bash 抑制通知（notified=True） |
| `test_runtime_runner_aborted_run_invokes_on_kill_with_result` | 同上 | 停 subagent 通知带 result_text |
| `test_runtime_runner_aborted_run_with_no_output_omits_result` | 同上 | 无产出时 result_text=None，省略 `<result>` |
| `test_runtime_runner_natural_completion_not_misflagged_as_kill` | 同上 | 自然完成不被误标 killed |
| `test_kill_is_idempotent_after_terminal` | 同上 | kill 幂等，首个终态赢不变量 |
| 整合测试 `test_task_stop_kills_running_bash_task` | `tests/integration/background_tasks/` | bash task_stop 后 runs.injections==[]（通知被抑制） |
| 整合测试 `test_task_stop_kills_running_agent_task` | 同上 | subagent task_stop 后 record.status==KILLED，注入消息含 `<result>subagent done</result>` |

## Issues

无 blocking / major 问题。

## Side Findings

无额外发现。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**——本 unit 改动在 agent 内核内部，跨包架构不变
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：**需要更新**——delta-spec 已在 `docs/changes/bugfix-420-task-stop-notification-dedup/specs/kernel/spec.md` 准备好，新增「Requirement: 经 task_stop 停止后台任务，model-facing 通知不与 tool_result 重复」及 4 个 Scenario。由 orchestrator §7.0 收尾归并写入 canonical
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**——无新开发约定或运维变化
- [x] `docs/SPEC_GUIDE.md`：**无需更新**——本 unit 未改文档体系

## Highest Required Action

**pass**（无需 fix-implementation / revise-design）
