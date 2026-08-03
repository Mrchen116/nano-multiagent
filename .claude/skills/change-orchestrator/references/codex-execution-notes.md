# Codex 执行说明

这份说明记录 `change-orchestrator` 在 Codex 下运行时需要替换的运行时机制。除本文明确说明的差异外，原 skill 的调度流程、门禁、fix loop、reviewer/verifier 分工、worktree 规则和 PR/CI 流程都保持不变。

默认按 Codex MultiAgentV2 执行；只有当前 Codex 没暴露 V2 collaboration tools、或正在续跑一个锁定在旧版 multi-agent runtime 的老线程时，才使用文末 V1 兼容说明。

`reasoning_effort=ultra` 不是新的后端推理档位本身。Codex 会把请求发成 `max`，同时在 V2 下给 root agent 注入 proactive multi-agent 指令。`change-orchestrator` 不依赖这个自动性：本 skill 已经定义了明确的调度计划，仍按 milestone / reviewer / verifier 显式派发 subagent。

## 工具映射

| Claude Code 机制 | Codex 机制 |
|---|---|
| `Agent` 工具 + `run_in_background: true` | `collaboration.spawn_agent` / `spawn_agent`。Codex subagent 创建后就是后台运行；不要派发后立刻长时间 `wait_agent`，除非下一步必须等它结果。 |
| 稳定 `name` | `task_name`。使用小写字母、数字和下划线，例如 `feat_104_m1`、`feat_104_reviewer`、`feat_104_verifier`。不要直接拿 `feat-104-M1` 当 V2 `task_name`。 |
| 按稳定 `name` 调 `SendMessage` | 对已有 subagent 调 `followup_task(target=<task_name>, message=...)` 触发续跑；只排队不触发新 turn 时才用 `send_message`。 |
| `model: sonnet` | `spawn_agent` 派发时必须按下方策略表显式传 `model`，不要省略。 |
| 推理强度 | `spawn_agent` 派发时必须按下方策略表显式传 `reasoning_effort`，不要省略。 |
| Agent `isolation=worktree` 参数 | Codex 没有这个参数，不设置。正好符合原 skill “不要设置 `isolation=worktree`” 的要求。 |
| 用稳定 agent `name` 复用热上下文 | 用 V2 `task_name` / agent path 复用。fix loop 需要唤醒原 worker 时，调用 `followup_task(target=<task_name>)`，不要新开 worker。 |
| 等后台 agent 结果 | `wait_agent(timeout_ms=...)`。V2 的 `wait_agent` 只等 mailbox 更新 / 完成通知，不直接返回完整结果；收到通知后读父上下文里的 agent message 再路由。 |
| 查看运行中 agent | `list_agents`，按 task-path prefix 查当前 root thread tree。 |
| 打断 agent | `interrupt_agent(target=<task_name>)`。只在错误派发、强制停工、用户中断或轮次上限时使用。 |

V2 `spawn_agent` 的 `fork_turns` 默认是 `all`。当派发时显式传 `model` 或 `reasoning_effort`，必须设置 `fork_turns: "none"` 或一个正整数；否则 full-history fork 会拒绝这些覆盖。常规 milestone / reviewer / verifier 派发使用 `fork_turns: "none"`，把必要上下文放进派发包，不靠继承 root 历史。

## 模型与推理强度策略

`change-orchestrator` 派发任何 Codex subagent 时，必须按下表显式传 `model` 与 `reasoning_effort`，不要依赖继承或默认配置。主会话模型配置可能与本流程的角色要求不一致，省略参数会造成 worker / reviewer / verifier 强度漂移。

| Subagent | `model` | `reasoning_effort` |
|---|---|---|
| impl / fix worker | `gpt-5.6-sol` | `xhigh` |
| product reviewer (`change-reviewer`) | `gpt-5.6-sol` | `medium` |
| implementation verifier (`change-verifier`) | `gpt-5.6-sol` | `medium` |
| code-review finder (`change-code-review`) | `gpt-5.6-luna` | `high` |
| code-review verifier (`change-code-review`) | `gpt-5.6-terra` | `high` |

预算分配原则：impl / fix worker 有最高自主性，需要在实现路径、边界处理、测试策略和失败修复上做技术判断，固定传 `xhigh`；product reviewer / implementation verifier 的职责是按既定 contract 严格验收，不做方案发散，固定传 `medium`；code-review finder 用 Luna，verifier 用 Terra。

## Code Review

保持原 skill 行为：`change-code-review` 由主会话调度。Codex 主会话用 V2 `spawn_agent` 派 finder / verifier subagents：finder 传 `model: gpt-5.6-luna`，verifier 传 `model: gpt-5.6-terra`；两者都传 `reasoning_effort: high`、`fork_turns: "none"`，沿用同一套 review contract，把 findings 交回正常 failure loop 路由。

## 运行态记录

orchestrator 运行时需要维护一张小的本地状态表：

| Key | Value |
|---|---|
| `<milestone_id>.task_name` | V2 `spawn_agent` 使用的稳定 task name，例如 `feat_104_m1`。 |
| `<milestone_id>.agent_path` | V2 agent path，例如 `/root/feat_104_m1`；有歧义时用 canonical path 寻址。 |
| `<milestone_id>.thread_id` | 若工具回包 / `list_agents` 提供 thread id，则记录；V2 常规续跑优先用 task name。 |
| `<milestone_id>.status` | `READY`、`DISPATCHED`、`RUNNING`、`DONE`、`BLOCKED` 或 `FAILED`。 |
| `reviewer_task_name` | reviewer 的稳定 task name。 |
| `verifier_task_name` | verifier 的稳定 task name。 |
| `code_review_finder_task_names` | 主会话为 `change-code-review` 派出的 finder task names。 |

这张表只替代 Claude Code 稳定 name 的寻址能力，不改变任何 unit / milestone branch、worktree、证据或验收规则。

## V1 兼容说明

如果当前 Codex 只暴露 `multi_agent_v1` 工具，按以下替换执行：

| V2 默认机制 | V1 兼容机制 |
|---|---|
| `spawn_agent(task_name=...)` | `multi_agent_v1.spawn_agent`，记录返回的 `agent_id`。 |
| `followup_task(target=<task_name>)` | `multi_agent_v1.send_input(target=<agent_id>)`。 |
| `wait_agent(timeout_ms=...)` | `multi_agent_v1.wait_agent(targets=[...])`。 |
| `list_agents` | 用 orchestrator 本地状态表代替。 |
| `interrupt_agent` | 无等价稳定接口；必要时停止等待并走 escalate / teardown。 |
| 不需要手动 close | 结果整合完成且后续不再需要时，调用 `multi_agent_v1.close_agent(target=<agent_id>)`。 |

V1 下仍必须显式传 `model` 与 `reasoning_effort`，并维护 `milestone_id -> agent_id`、`reviewer_agent_id`、`verifier_agent_id`。
