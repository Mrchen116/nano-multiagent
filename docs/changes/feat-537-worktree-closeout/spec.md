# feat-537: change unit worktree 收尾闭环

## Relations

- Related: feat-487
- Related: refactor-488
- Related: feat-514
- Related: feat-515

## 原始需求

> simple是最近开的，orchestrator也是最近简化的。这两个改动都是有目的的，你看看找到不，然后你帮我看看怎么改

> “标准编排则是把重复流程和通用说明从 skill 中拿掉、回归权威流程文档。”更准确说，是模型能力更强了，不需要把skill写的过于冗长，而是言简意赅

> 好，开始改

> 这个补个spec吧，把你上面的对过往unit执行的分析补进去

> 和skill的变动一同提交

> and push

## 澄清记录

- Q1: `change-orchestrator-simple` 和精简后的 `change-orchestrator` 是否应以恢复固定实施流程的方式解决遗留 worktree？
  A(原话): simple是最近开的，orchestrator也是最近简化的。这两个改动都是有目的的，你看看找到不，然后你帮我看看怎么改
  Agent 解读: 先追溯两次改动的原意，再选择不抵消其目标的最小修复。
- Q2: 标准编排精简的核心边界是什么？
  A(原话): “标准编排则是把重复流程和通用说明从 skill 中拿掉、回归权威流程文档。”更准确说，是模型能力更强了，不需要把skill写的过于冗长，而是言简意赅
  Agent 解读: 不用把删掉的说明换成强制预读；只保留模型无法可靠猜出的必要交付边界。
- Q3: 本次是否实施这一最小修复，并补齐可追溯首文档？
  A(原话): 好，开始改
  Agent 解读: 实施不改变两种流程的编排自由度。
- Q4: 首文档需要保留哪些取证？
  A(原话): 这个补个spec吧，把你上面的对过往unit执行的分析补进去
  Agent 解读: 文档记录历史执行事实、归因和本次边界，而非只记录最终 prompt 文本。
- Q5: 如何交付这次文档和 skill 改动？
  A(原话): 和skill的变动一同提交

  and push
  Agent 解读: 将首文档与对应 skill 改动合并为同一提交并推送。

## 过往 unit 执行分析

### 已观察事实

对已归档、已合入 `main` 的 unit 回看其 Codex 会话与当时 worktree 后，确认并非所有目录都来自同一种流程：

| Unit | 会话中的执行事实 | 收尾结果 |
|---|---|---|
| `refactor-480` | 创建 `unit-refactor-480`；只移除了临时 baseline 目录。 | unit worktree 留在本机。 |
| `bugfix-500` | 创建 `unit-bugfix-500`。 | 会话没有正常完成后的 worktree remove 记录。 |
| `feat-514` | 创建 unit worktree 和多个 milestone worktree。 | 会话结束时没有对应的完整删除闭环。 |
| `feat-515` | 主会话除 unit worktree 外还直接创建 reviewer / verifier worktree；用户曾要求暂留 IM / Gateway 测试现场。 | 临时保留测试现场有正当理由，但不足以解释后续遗留的所有 review、verify 与 fix worktree。 |

本次维护已在不影响未合入 unit 的前提下移除了这些已完成 unit 的历史 worktree。上述会话的共同问题是交付结束时没有把实际创建过的 worktree 全部纳入收尾，而不是把某个仍在运行或仍待合入的现场误判为垃圾。

### 归因

已有子角色契约并非完全缺失：`change-impl-worker` 在 milestone DONE 后删除自己的 worktree，`change-verifier` 在报告 push 后默认删除自己创建的只读 worktree。断点在主流程：

- 原流程只明确 worker 自建自清和正常完成时删除 unit worktree；主会话直接创建或接管的临时 worktree 没有同样清晰的 owner 及收尾核对。
- 简化流程允许主 Agent 自主决定 subagent、并行度和工作区；它虽要求清理“本 unit 创建”的临时 worktree，但没有把创建者责任和完成前的实际路径核对写成明确的交付条件。

因此问题不是简化流程不该存在，也不是要重新绑定 milestone、worker、分支和 worktree；而是自由组织仍需要一个不可猜的资源所有权边界。

## 用户场景

仓库维护者选择标准或简化流程完成一个 change unit，并拿到 CI 全绿的 PR。维护者希望主仓保持不受影响，已完成 unit 不再持续堆积本地 worktree；同时，简化流程仍允许主 Agent 根据任务自行决定直接实现、委派、并行和工作区组织。

当维护者明确要求保留一个测试现场继续验证时，系统不应擅自删除它；维护者应能在交付信息中看到其确切路径、保留理由和后续清理触发，而不是事后面对无主目录猜测能否删除。

## 验收标准

### Requirement: 已完成 unit 的工作区可追溯地收尾

#### Scenario: 主流程直接创建临时工作区
- **WHEN** 标准或简化流程为一个 unit 直接创建或接管临时 worktree，并且 PR required CI 已全绿
- **THEN** 维护者看到该 worktree 已由主流程清理
- **AND** 不会因按目录名称通配而删除其他 unit 的工作区

#### Scenario: 子角色创建自己的工作区
- **WHEN** worker 或 verifier 按其自身职责创建 worktree 并正常完成
- **THEN** 维护者看到该角色按其既有契约完成收尾
- **AND** 主流程在交付前确认本 unit 不遗留该工作区

### Requirement: 用户要求保留的测试现场保持显式

#### Scenario: 用户正在继续测试
- **WHEN** 用户明确要求保留某个 unit 的运行时或 worktree 现场
- **THEN** 交付信息列出现场路径、保留理由和后续清理触发
- **AND** 该现场不会被描述为已经完成清理的普通交付状态

### Requirement: 收尾修复不增加实施编排税

#### Scenario: 使用简化流程完成多个 milestone
- **WHEN** 主 Agent 判断直接实现、委派、串行、并行或额外工作区中的任一种组织更合适
- **THEN** 维护者仍可使用该组织方式完成 unit
- **AND** 流程不会重新强制一 milestone 一 worker、固定 worktree 拓扑、过程台账或额外独立门禁

#### Scenario: 使用标准流程完成 unit
- **WHEN** 标准 orchestrator 运行一个已确认设计的 unit
- **THEN** 维护者仍获得精炼、可直接执行的实施 contract
- **AND** skill 不以要求预读完整生命周期文档或 child skill 的方式补回已删除的冗长说明

## 范围与非目标

- 在范围：
  - 为 `change-orchestrator` 和 `change-orchestrator-simple` 明确 worktree 创建者的收尾责任。
  - 将普通交付的 worktree 清理和用户明确保留测试现场的披露纳入完成条件。
  - 在简化流程中要求基于本次实际路径核对 worktree 遗留。
  - 记录本次结论所依据的过往 unit 执行事实和归因。
- 非目标：
  - 恢复一 milestone 一 worker、固定 subagent 数量、固定并行度或固定 worktree 拓扑。
  - 扩写标准 orchestrator 的通用说明、shell 小抄或固定轮询。
  - 修改 `change-impl-worker`、`change-verifier` 已有的自清契约。
  - 按名称批量删除其他 active、paused 或未合入 unit 的 worktree。
  - 改变产品行为、选定门禁组合、PR/CI 交付标准或 worktree 的隔离要求。
