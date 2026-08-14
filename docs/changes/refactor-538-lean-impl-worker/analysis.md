# change-impl-worker 历史流程取证与精简依据

## 结论摘要

历史上真正调用 `change-impl-worker` 的样本显示，慢的主要来源不是实现，而是所有变更一律走完整 milestone 的固定流程：过程文档、重复 Git 状态/提交/推送、无新信息的测试复跑，以及不适用于该风险的 worktree/真实入口步骤。

因此本次不再让所有变更自动进入 worker，也不以分类表或行数替代判断。调度者结合当前任务判断独立 worker 是否会带来足够的 ownership、隔离或实现/验证收益；不能时直接闭环。真实验收和独立关闭仍按实际风险保留。

## 方法和样本

分析只计入 session 中确实调用过 `change-impl-worker` 的 subagent；不把仅阅读 skill、普通主会话修改或无 worker 调用的 session 混入。时间采用有活动上限的估算：相邻事件间隔最多计 5 分钟，避免把等待用户或外部 CI 的空闲时间归因给 skill。

| 来源 | 已识别调用 | 中位活动时长 | 说明 |
| --- | ---: | ---: | --- |
| Codex session | 42 | 23.8 分钟 | 基于工具/消息活动的估算 |
| Claude session | 18 | 40.2 分钟 | 同一口径；两个跨度异常大的 session 含 504/699 分钟空闲间隔 |

在 Codex 历史样本中，单个 worker 的命令文本密度中位数为：`tasks.md`/`progress.md` 10 次操作、`git status` 9.5 次、提交 5 次、推送 3 次、测试 11 次。另一个跨历史的配对统计发现 318 组 `tasks.md`/`progress.md`，共 43,906 行，单组中位数 131 行（平均 138.1 行）。这些数字不是所有内容都无效，而是说明固定工件在小闭环上可能主导工作量。

## 可复核案例

### M18：3 行尾随空格修正

`refactor-489` 的 M18 只删除 6 个尾随空格、涉及 3 行，却产出约 40 行 tasks 和 52 行 progress、2 个 milestone 提交和 1 个合并，并消耗约 27 次 worker/worktree 工具调用。这里有价值的是差异检查、文档检查与独立关闭；完整 milestone 生命周期没有增加对应风险的信息。

**改造映射：** 这是独立 worker 不增加价值的直接闭环例子：由 unit worktree 完成，运行针对性 diff/docs 检查并独立关闭。

### M17：测试格式与 PATH harness 修复

`refactor-489` 的 M17 修改约 20 个测试文件的格式和一个 PATH 测试 harness。3 个 roadpoint、约 120 行过程文档和完整 milestone 对这个风险不成比例；但 Ruff、resilience E2E、CI 与独立关闭仍有价值。

**改造映射：** 当范围和所需验证足够清楚、独立 worker 不增加价值时，主调度者直接修改，保留这些验证和独立关闭，不创建 worker 工件。

### M9 R4：11 行 helper，但仍不可按行数降级

另一实例只改约 11 行 helper，却有多个下游 worker 依赖和上下文协调。这类工作虽然小，仍需要实施判断和跨 owner 协调。

**改造映射：** 不设行数阈值；这里独立 worker 的协调和上下文收益足够，应该派发。

### feat-446：同一 tree 的重复回归

在一次修复中，基线 37 项测试、实现后 64 项、rebase（没有相关变更）后 64 项、合并后又 64 项。后两次在没有代码或环境变化时没有新增信息。

**改造映射：** 只有代码、命令、环境或风险发生变化时才复跑，否则保留有效验证结论。

### 真实入口和跨进程验收不可删

`refactor-470` M4 的参考清理还包含真实 Feishu smoke；类似 UI、外部通道和跨进程链路的验证是证明用户真实可用的必要成本，不能以“流程慢”为由删除。

**改造映射：** 当真实入口验证或独立实现 owner 能提高交付可靠性时，派 worker，并执行适用的真实入口和独立关闭。

## 冗余操作与最终改造

| 观察到的流程税 | 为什么在小闭环中无意义 | 本次改造 | 保留的边界 |
| --- | --- | --- | --- |
| 固定 `tasks.md` / `progress.md` | 没有新的协作、交接或审计信息 | 只在完整 milestone 的复杂交付、交接或证据需要时记录 | 实质性 worker 仍按需要保留 |
| 每一步 status、提交、推送 | 小闭环没有并行 handoff 价值 | 直接闭环可单次提交到 unit 分支 | 独立 worker 仍在集成前交付可验证提交 |
| 固定基线与多轮同 tree 测试 | 代码、命令、环境未变时不产生新证据 | 只有实际变化时才复跑 | 变化后重跑受影响范围 |
| 无根因时也走调试流程 | 已知定向修复会把实施变成仪式 | 仅根因未知或证据冲突时调用系统化调试 | 未知根因仍先定位再修复 |
| 每个闭环都建立 worker worktree | 增加分支、清理和交接成本 | 独立 worker 不增加价值时直接在 unit worktree 完成 | 需要独立 worker 时仍创建并拥有自己的 worktree |

历史三次提交策略已在早期提交 `9980d2792` 中移除；它是历史来源的一部分，但不是本次要重复声称解决的当前问题。

## 被否决的方案：把 milestone worktree 所有权移给 orchestrator

初步分析曾考虑把 worktree 创建与整合完全移给 orchestrator。对照仍在实施的 `feat-537-worktree-closeout` 契约后，发现这会与“worker 创建、拥有、清理其 milestone worktree”的既定收敛方向冲突。

最终保留 creator-owner 合约：worker 创建/恢复和清理自己的 milestone worktree；多个 worker 通过位于 Git common dir 的 unit 共享锁串行整合到 unit 分支。锁冲突后先检查 unit 分支是否推进；若推进，释放锁、rebase/重新评估、再获取锁，避免用陈旧基线继续集成。

## 前向验证

改造后用三个具体任务做了独立流程演练：

| 场景 | 预期路由 | 结果 |
| --- | --- | --- |
| M18 同类的文档尾随空格 | 直接闭环 | 通过；不派 worker、不建 milestone 文档/树 |
| M17 同类的测试格式/PATH 定向修复 | 直接闭环 | 通过；保留针对性测试，不建过程文档 |
| 一行生产认证/协议改动 | 独立 worker 有收益 | 通过；派 worker，保留必要验证、锁集成与独立关闭 |

前向演练确认直接闭环和派 worker 都能按上述原则工作；锁/rebase 竞态闭合，且流程文档和契约测试一致。

## 原始证据定位

- 本次取证主 session：`/Users/czj/.codex/sessions/2026/08/13/rollout-2026-08-13T17-21-33-019ffa6d-47e8-7340-a4e4-bcd6b736bcd3.jsonl`
- M18 worker：`/Users/czj/.codex/sessions/2026/08/03/rollout-2026-08-03T13-00-56-019fc5ff-158e-7172-82aa-1e3e01a34966.jsonl`
- bugfix-441 M1：`/Users/czj/.codex/sessions/2026/06/26/rollout-2026-06-26T16-46-40-019f031c-1591-7a33-a13e-c8ec5ec7aaa5.jsonl`
- feat-451 M2：`/Users/czj/.codex/sessions/2026/07/01/rollout-2026-07-01T22-33-16-019f1e19-3426-7130-992b-dd5f8886a23d.jsonl`
- feat-447 M11：`/Users/czj/.codex/sessions/2026/07/02/rollout-2026-07-02T20-13-33-019f22bf-a6ff-7550-be1f-5c9a14f3685f.jsonl`
- feat-446 修复：`/Users/czj/.codex/sessions/2026/07/03/rollout-2026-07-03T11-22-34-019f25ff-e174-7c52-b716-446796e56e76.jsonl`
- Claude project transcript 根目录：`/Users/czj/.claude/projects/-Users-czj-Repos-nano-multiagent`

活动时长是基于日志事件估算，不等同于用户端总等待时间；案例结论均按上述可回放日志复核。
