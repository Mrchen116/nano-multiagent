# bugfix-656: As-built Design

> 本文在实现后形成，记录实际结构及本轮验证结果。

## 实现范围

- Base: `b80e6d74d72ed6f169142008a16c7c0811646754`。
- Branch: `codex/task-short-run-limit`。
- 产品修改：`packages/dsh-integration/src/task-execution.ts`。
- 永久回归：`packages/dsh-integration/tests/task-execution-limits.test.ts`。

## 最终结构

`TaskExecutionDriver` 保留 session 级运行状态，并以绑定的产品 `agentId` 保存短跑计数；同一个 Agent 的多个绑定会话共享计数。只监听精确绑定 session，子 Agent 不计入。

原生 `turn/start` 初始化本轮信息，`step/start` 累加实际执行步，`user/message` 识别已进入执行的自动输入和独立输入，`turn/end` 结算自动短跑。计数不使用候选 pre-step，也不把 provider 请求重试视为额外步骤。

达到上限后，`poke()` 在读取前和异步读取后拦截新续推，pre-step 还会拦截已经排队但尚未进入执行的自动输入。已经运行的工作不被取消，外部输入仍沿既有执行路径进入。

## 清零规则

| 当前状态 | 事件 | 结果 |
|---|---|---|
| 未触顶 | 本轮达到 3 个实际执行步 | 计数清零 |
| 未触顶 | 独立输入只执行一两步 | 计数保持 |
| 已触顶 | 独立输入实际进入执行 | 清零并解除自动续推限制 |
| 已触顶 | 责任/配置刷新、停止上下文、投递重校验 | 不解除限制 |

独立输入使用已消费的可信 source：真人输入、Schedule，以及除 `task-execution`、`task-change`、`task-human-control`、`revalidation`、`personal-state` 外的宿主输入（包括 Inbox、Heartbeat、渠道消息）。入队或请求唤醒本身不清零；PA 来源和权限策略同步同样属于内部上下文。

## 状态、失败与回滚边界

- 本次计数为运行进程内状态；native 会话释放不清除产品 Agent 计数，整个执行进程重启会重新计数。没有新增数据库、配置项或迁移。
- 触顶仅在节点日志记录一次原因，不新增聊天消息，避免触顶通知反过来触发唤醒。无新增 UI 状态。
- Task 的 doing/waiting/paused 等状态不变；解除本限制不清除原有故障、审批拒绝或用户停止控制。
- 这里限制一段连续宿主短跑，不限制 Heartbeat/Schedule 后续再次唤醒产生的新一段执行，不是总费用上限或业务进展判定器。
- 回滚本次源码即可恢复既有自动续推行为；无持久数据需要回滚。

## 测试策略与证据

- 保护最低有效 seam：真实锁定 DSH + fixture provider，通过 runtime RPC 与原生事件观察自动执行、步骤、静止和再次唤醒。
- 新增 `task-execution-limits.test.ts`：连续短跑预算是独立回归风险，已有 `task-execution.test.ts` 保护责任新鲜度、停止、故障恢复和拒绝屏障，保留原覆盖。
- 基线 Red：未修改实现时期望自动续推 256，实际观测 260。
- 2026-10-25 最终验证：`pnpm --filter @nano/dsh-integration build` 通过；`pnpm exec vitest run packages/dsh-integration/tests/task-execution-limits.test.ts packages/dsh-integration/tests/task-execution.test.ts` 14/14 通过（47.63 秒）；`pytest tests/contract/test_runtime_dependency_contract.py -q` 13/13 通过。
- 文档与 diff：`PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` 通过（268 maintained Markdown sources、67 required routes）；`git diff --check` 通过。
- 新回归实际经历 128 轮中的长跑清零、随后 256 次短跑触顶、触顶前短外部输入不清零、触顶后内部上下文执行不解锁、产品 Agent 跨会话共享及其他 Agent 隔离、真人短输入恢复后的再次 256 次触顶、原生 Schedule 恢复。
- 环境：Node 25.8.2、pnpm 11.7.0；包管理器报告该 Node 不在仓库声明的 24.22.1/26.12.1 范围内。以上仅为该本地环境验证，未替代受支持 Node 版本上的 CI；未运行全仓 CI、真实 LLM 或生产验收。
- 用户产品验收：待完成；“对的”确认的是设计，不记为运行验收。
- 独立 full code review 确认一个 personal-state 分类问题，修复于 `f18f7ced9` 后经独立 closure 关闭，剩余 findings 为 `[]`；见 [code-review](code-review.md)。

## Canonical 文档影响

仅修改 Gateway Task 恢复契约的多轮限制并新增短跑场景。当前保留 [delta-spec](specs/gateway/task-graphs.md)，待验收和独立审查后归并，未改 current spec。
