# Codex 执行说明

这份说明记录 `change-orchestrator` 在 Codex 下运行时需要替换的运行时机制。除本文明确说明的差异外，原 skill 的调度流程、门禁、fix loop、reviewer/verifier 分工、worktree 规则和 PR/CI 流程都保持不变。

## 工具映射

| Claude Code 机制 | Codex 机制 |
|---|---|
| `Agent` 工具 + `run_in_background: true` | `multi_agent_v1.spawn_agent`。Codex subagent 创建后就是后台运行；不要派发后立刻长时间 `wait_agent`，除非下一步必须等它结果。 |
| 按稳定 `name` 调 `SendMessage` | `multi_agent_v1.send_input(target=<agent_id>)`。Codex 不能自定义稳定 agent name；orchestrator 需要在内存里维护 `milestone_id -> agent_id`、`reviewer_agent_id`、`verifier_agent_id`。 |
| `subagent_type: general-purpose` | `agent_type: default`。实现 / fix worker 用 `agent_type: worker`；窄范围只读探索用 `agent_type: explorer`。 |
| `model: sonnet` | 需要显式强模型覆盖时用 `model: gpt-5.5`。否则省略 `model`，让 subagent 继承当前模型。 |
| Agent `isolation=worktree` 参数 | Codex 没有这个参数，不设置。正好符合原 skill “不要设置 `isolation=worktree`” 的要求。 |
| 用稳定 agent `name` 复用热上下文 | 用 `spawn_agent` 返回的 `agent_id` 复用。fix loop 需要唤醒原 worker 时，调用 `send_input(target=<agent_id>)`。 |
| 等后台 agent 结果 | `multi_agent_v1.wait_agent(targets=[...])`。只在 orchestrator 需要结果才能继续路由时等待。 |
| 关闭已完成 agent | 结果整合完成且后续不再需要时，调用 `multi_agent_v1.close_agent(target=<agent_id>)`。 |

## Code Review

保持原 skill 行为：`change-code-review` 由主会话调度。Codex 主会话可以直接用 `multi_agent_v1.spawn_agent` 派 finder / verifier subagents，沿用同一套 review contract，并把 findings 交回正常 failure loop 路由。

## 运行态记录

因为 Codex 不能自定义稳定 agent name，orchestrator 运行时需要维护一张小的本地状态表：

| Key | Value |
|---|---|
| `<milestone_id>.agent_id` | `spawn_agent` 返回的 worker agent id。 |
| `<milestone_id>.status` | `READY`、`DISPATCHED`、`RUNNING`、`DONE`、`BLOCKED` 或 `FAILED`。 |
| `reviewer_agent_id` | `spawn_agent` 返回的 reviewer agent id。 |
| `verifier_agent_id` | `spawn_agent` 返回的 verifier agent id。 |
| `code_review_finder_agent_ids` | 主会话为 `change-code-review` 派出的 finder agent ids。 |

这张表只替代 Claude Code 稳定 name 的寻址能力，不改变任何 unit / milestone branch、worktree、证据或验收规则。
