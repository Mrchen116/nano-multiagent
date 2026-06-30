# bugfix-450 — 回归验证

> 对齐: incident.md v1, design.md Runbook for Reviewer
> Round: 1
> Date: 2026-06-30

## Verdict

- Verdict: pass
- Highest Required Action: pass
- Reviewer mode: full

本轮从用户可观察语义验收：running subagent follow-up 不再只让主 agent 看到虚假的 queued；queued 成功必须对应同一 running subagent 后续可消费的 follow-up；无法确认 live delivery 时不返回已成功排队；terminal subagent continuation、后台 output file、task_stop 等相邻体验不退化。

design.md 的 reviewer runbook 标明本 unit 无常驻服务，验收入口是端到端真栈测试与真实 `agent` tool 路径代驱动，因此本轮未启动或重启 IM/Gateway。

## User Journeys Exercised

1. Running follow-up 主路径：启动 running background subagent，主 agent 使用同一个 `agent_id` 发送 follow-up，验证结果进入 live runtime controller，并在同一 subagent 后续执行中被消费。
2. 不可投递失败路径：目标 subagent record 仍为 running，但 live delivery 不可用时，验证主 agent 不再看到 `message_queued` 成功反馈。
3. 既有体验回归路径：terminal subagent continuation、JSONL rehydrate continuation、background notification、auto-background、`output_file`、`task_stop` 继续可用。

## 验收标准覆盖

### Requirement: running subagent follow-up 真实投递

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户要求正在运行的 subagent 汇报进度 | `incident.md` 验收标准；`design.md` 决策 1 | 运行集成路径，验证 running follow-up 进入 live runtime controller，而不是只停在 registry queued | `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py`，其中 `test_running_agent_follow_up_enters_live_runtime_controller` passed；整组 32 passed | pass | 该用例覆盖同一 running subagent 后续消费 follow-up 的可观察结果 |
| follow-up 在安全点处理 | `incident.md` 验收标准；`design.md` 决策 1 | 同一组测试驱动 running subagent 当前轮次后继续处理 follow-up；相邻 `task_stop`/background 回归验证当前执行未被破坏 | 同上 32 passed；另 `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` 为 12 passed | pass | 未观察到中途破坏当前执行或另起无关 worker 的用户面异常 |

### Requirement: 不再返回假 queued 状态

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 目标 subagent 无法接收 running follow-up | `incident.md` 验收标准；`design.md` 决策 2 | 验证 live delivery 不可用时 continuation 失败，而不是返回 `message_queued` 或静默新建第二个 subagent | `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py`，其中 `test_continuation_to_running_agent_without_live_delivery_fails` passed；整组 32 passed | pass | 主 agent 不会把无法确认送达的 follow-up 当作已成功排队处理 |

### Requirement: 既有后台任务体验不退化

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已完成 subagent 继续会话 | `incident.md` 验收标准 | 验证 terminal continuation 与 JSONL rehydrate continuation 仍可用 | `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py`，其中 `test_continuation_to_terminal_agent_resumes`、`test_jsonl_rehydrate_continues_agent_after_registry_loss` passed；整组 32 passed | pass | 用户仍能以同一个 subagent 后续工作继续，而不是丢失已有输出上下文 |
| 用户读取后台输出 | `incident.md` 验收标准 | 跑完整 background_tasks 集成回归，覆盖后台输出文件创建/写入、通知、auto-background 与 task_stop | `pytest -xvs tests/integration/background_tasks`，19 passed，其中 `test_background_bash_output_file_is_created_and_written` passed | pass | output file 读取/了解后台过程和结果的基础体验未退化 |

## 复现验证

修前问题是 running continuation 只返回 `message_queued`，但目标 subagent 后续 JSONL/LLM request/output 中看不到 follow-up。修后本轮跑同一类用户路径：

- running follow-up 通过 live runtime controller 被同一 subagent 消费：`test_running_agent_follow_up_enters_live_runtime_controller` passed。
- foreground auto-background 的 running follow-up 也使用 live controller：`test_foreground_auto_background_running_follow_up_uses_live_controller` passed。
- live delivery 不可用时不返回假成功：`test_continuation_to_running_agent_without_live_delivery_fails` passed。

结论：原始“queued 但没有被 subagent 收到”的用户可见假成功，本轮未复现。

## 回归测试

- `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` → 32 passed。
- `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` → 12 passed。
- `pytest -xvs tests/integration/background_tasks` → 19 passed。

## 自动化测试增量

本轮未读实现代码，只按用户旅程验证可观察行为。根据任务文档与测试输出，已覆盖的关键回归防线包括：

- running follow-up 进入 live runtime controller，而不是只检查 registry pending string。
- live delivery 不可用时显式失败。
- foreground auto-background running follow-up 使用 live controller。
- terminal subagent continuation 与 JSONL rehydrate continuation 不退化。
- background output file、completion notification、auto-background、task_stop 不退化。

## Issues

No blocking, major, or minor in-unit issues found.

## Side Findings

None.

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本修复不改变四包职责或顶层依赖方向。
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：需要由 orchestrator 收尾归并本 unit 的 kernel 行为 delta。`docs/changes/bugfix-450-running-subagent-resume/specs/kernel/spec.md` 已作为本 unit delta 文档存在。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。本修复不改变开发/运行约定。
- [x] `docs/SPEC_GUIDE.md`：无需更新。本修复不改变文档体系规范。

---

# Round 2 — 2026-06-30

## Verdict

- Verdict: pass
- Highest Required Action: pass
- Reviewer mode: full, Fast-lane复验

本轮复用 Round 1 上下文，重点复验 fast-lane 修复后的用户可观察语义：stopped/aborted running subagent follow-up 不再看到假 `message_queued`，running follow-up 仍真实进入同一 subagent 的后续输出，terminal resume、`output_file`、`task_stop` 等相邻后台任务体验不退化。

design.md 的 reviewer runbook 标明本 unit 无常驻服务，验收入口是端到端真栈测试与真实 `agent` tool 路径代驱动，因此本轮未启动或重启 IM/Gateway。系统 `python3` 无 `pytest`，本轮使用主仓现成虚拟环境解释器，并在 unit worktree 下显式设置 `PYTHONPATH=src` 执行测试，未安装依赖、未修改环境。

## User Journeys Exercised

1. Running follow-up 主路径：启动 running background subagent，主 agent 使用同一个 `agent_id` 发送 follow-up，验证 follow-up 进入 live runtime controller，并在同一 subagent 后续 LLM request / 输出中被消费。
2. Stopped/aborted follow-up 失败路径：explicit background 与 auto-background subagent 被 stop/abort 后，主 agent 再发送 follow-up，验证不返回假 `message_queued`。
3. Terminal 与后台任务回归路径：terminal/JSONL resume、background notification、auto-background、`output_file`、bash/agent `task_stop` 继续可用。

## 验收标准覆盖

### Requirement: running subagent follow-up 真实投递

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户要求正在运行的 subagent 汇报进度 | `incident.md` 验收标准；`design.md` 决策 1；Round 1 覆盖表 | 复跑真实 runtime controller 消费链路，确认 follow-up 不是只停在 queued 状态，而是进入同一 subagent 后续处理 | `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` → 35 passed；其中 `test_running_agent_follow_up_enters_live_runtime_controller` passed | pass | running follow-up 主路径仍真实投递到同一 subagent |
| follow-up 在安全点处理 | `incident.md` 验收标准；`design.md` 决策 1；Round 1 覆盖表 | 复跑 running follow-up、auto-background follow-up 与 task_stop/background 回归，确认当前执行不被中途破坏，follow-up 在后续安全点消费 | 同上 35 passed；另 `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` → 12 passed | pass | 未观察到另起无关 worker 或破坏当前执行的用户面异常 |

### Requirement: 不再返回假 queued 状态

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 目标 subagent 无法接收 running follow-up | `incident.md` 验收标准；`design.md` 决策 2；fast-lane 修复记录 | 复跑 live delivery 不可用、explicit background stopped、auto-background stopped 三类路径，确认主 agent 不会看到表示已成功排队的结果 | 35 passed；其中 `test_continuation_to_running_agent_without_live_delivery_fails`、`test_explicit_background_stopped_agent_rejects_follow_up_without_false_queued`、`test_auto_background_stopped_agent_rejects_follow_up_without_false_queued` passed | pass | stopped/aborted running subagent follow-up 不再以假 `message_queued` 呈现 |

### Requirement: 既有后台任务体验不退化

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已完成 subagent 继续会话 | `incident.md` 验收标准；Round 1 覆盖表 | 复跑 terminal continuation 与 JSONL rehydrate continuation | 35 passed；其中 `test_continuation_to_terminal_agent_resumes`、`test_jsonl_rehydrate_continues_agent_after_registry_loss` passed | pass | 用户仍能以同一个 subagent 后续工作继续 |
| 用户读取后台输出 | `incident.md` 验收标准；Round 1 覆盖表 | 复跑完整 background_tasks 集成回归，覆盖 output file、completion notification、auto-background、agent/bash task_stop | `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/integration/background_tasks` → 19 passed；其中 `test_background_bash_output_file_is_created_and_written`、`test_task_stop_kills_running_agent_task` passed | pass | `output_file` 与 `task_stop` 体验未退化 |

## 复现验证

- stopped/aborted running subagent follow-up 不再看到假 queued：`test_explicit_background_stopped_agent_rejects_follow_up_without_false_queued` 与 `test_auto_background_stopped_agent_rejects_follow_up_without_false_queued` passed。
- running follow-up 仍真实进入同一 subagent 后续输出：`test_running_agent_follow_up_enters_live_runtime_controller` passed。
- terminal resume / JSONL rehydrate 不退化：`test_continuation_to_terminal_agent_resumes`、`test_jsonl_rehydrate_continues_agent_after_registry_loss` passed。
- `output_file` / completion notification / `task_stop` 不退化：完整 `tests/integration/background_tasks` 19 passed，`test_task_stop_tool.py` 相关 6 passed。

## 回归测试

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` → 35 passed。
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` → 12 passed。
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/integration/background_tasks` → 19 passed。

## Issues

No blocking, major, or minor in-unit issues found.

## Side Findings

None.

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本修复不改变四包职责或顶层依赖方向。
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：仍需要由 orchestrator 收尾归并本 unit 的 kernel 行为 delta；本轮未发现新的契约增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。本修复不改变开发/运行约定。
- [x] `docs/SPEC_GUIDE.md`：无需更新。本修复不改变文档体系规范。
