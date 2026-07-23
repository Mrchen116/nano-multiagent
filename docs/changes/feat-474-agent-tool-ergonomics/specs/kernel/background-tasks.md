# kernel / background-tasks — delta (feat-474)

> 目标 canonical: `docs/specs/kernel/background-tasks.md`

## ADDED Requirements

（无。）

## MODIFIED Requirements

### Requirement: 派生子 agent 的前台执行与内核 run 隔离

经 `agent` 工具派发的前台子 agent，复用内核同一事件循环执行，不在独立的瞬时事件循环上运行共享内核
组件；因此前台子 agent 能正常完成并返回结果。任意工具调用（含子 agent）的失败被收敛在该工具的 tool
result 边界内，不破坏内核的 run、不影响同一内核上的其它 run，也不中断该消费者进程的其它常驻活动。

#### Scenario: 前台子 agent 正常返回结果
- **WHEN** 消费者经 `agent` 工具派发一个前台子 agent（提供 description 与 prompt；可选 `subagent_type`）
- **THEN** 该工具调用返回子 agent 的执行结果（status=completed 含结果文本），而非因跨事件循环绑定而失败

#### Scenario: 单次工具 / 子 agent 失败被隔离，不拖垮内核与常驻进程
- **GIVEN** 某消费者进程常驻运行内核（持续有心跳 / 中继等常驻活动）
- **WHEN** 一次 `agent` 工具派发的子 agent 调用失败
- **THEN** 该失败仅作为该工具调用的失败结果（status=failed + error）返回
- **AND** 内核的其它 run 与该消费者进程的常驻活动不受影响、继续正常运行（进程不失联、不需重启）

### Requirement: 前台子 agent 超预算自动转后台（模型不可调超时）

（若 canonical 中该能力挂在其他 Requirement 下，归并时对齐下列 Scenario 语义；本 delta 强调参数面。）

#### Scenario: 超过系统默认前台预算仍转后台且不可用参数改超时
- **WHEN** 消费者前台派发子 agent，且运行超过系统默认前台预算
- **THEN** 该调用转为后台继续跑，消费者仍能拿到可继续跟进的标识/输出路径
- **AND** 消费者无法通过 `agent` 工具参数自定义这笔超时

## REMOVED Requirements

（无整 Requirement 删除。归并时删除「传齐 description + subagent_type / category」这类过时措辞。）
