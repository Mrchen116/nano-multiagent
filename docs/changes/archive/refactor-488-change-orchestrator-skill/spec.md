# refactor-488: 精简 change-orchestrator skill

## 原始需求

> 我发现现在的.claude/skills/change-orchestrator/SKILL.md有900多行，严重超500行。我要流程大体不变的情况下，精简他的描述，我预计有大量无用内容。或者重复内容。需要重构下他。

> 我们应该基于当前agent的能力更强去思考，哪些东西已经没必要写在SKILL中。

## 澄清记录

- 用户要求保留 unit 专属 worktree、独立检查和最终 PR/CI 等不可省的交付边界。
- 用户拒绝通过强制读取 `change-workflow.md`、`docs/changes/README.md` 或 child skill 把主 prompt 的上下文负担转移出去。
- 用户要求 parent orchestrator 不读取 child skill；但 parent 自己决定的 gate handoff、snapshot、worktree 与 diff-range 接口必须留在主 skill。
- 用户要求 Codex 下 code-review finder 使用 Luna、verifier 使用 Terra。

## 用户场景

维护者在 design 已确认后要求 agent 启动一个 change unit。agent 应获得一份足够短、能直接执行的 orchestrator contract：它能建立隔离的 unit worktree、调度实现和独立检查、根据证据路由 findings、归档并交付 required CI 全绿的 PR，而不需要先加载与当前阶段无关的文档或 child skill。

## 验收标准

### Requirement: 主 orchestrator contract 既简洁又保留交付边界

#### Scenario: 启动 Full 或 lite unit
- **WHEN** 维护者请求 orchestrator 推进一个 unit
- **THEN** skill 能判定准入、保护主仓 checkout，并在专属 unit worktree 内推进
- **AND** 读取范围不要求预读完整 delta-spec、prototype、references、生命周期总览或 child skill。

#### Scenario: 实施后的独立验证与收尾
- **WHEN** unit 完成实现或经历 fix loop
- **THEN** skill 仍能为 reviewer、verifier 与 code review 提供必要的 snapshot、worktree、mode 和 diff range
- **AND** 只有有效门禁、canonical 归并、归档、PR 与 required CI 都完成后才报告交付完成。

### Requirement: Codex code-review 角色使用指定模型

#### Scenario: 派发 code-review 子 agent
- **WHEN** 主会话进入 `change-code-review` 的 finder 与 verifier 阶段
- **THEN** 执行说明指定 finder 使用 `gpt-5.6-luna`、verifier 使用 `gpt-5.6-terra`
- **AND** 两者保持 `high` reasoning effort。

## 范围与非目标

- 在范围：`change-orchestrator` 主 skill、其 Codex 执行说明、对应的 workflow contract tests，以及本次快速开发的事后 unit 记录。
- 非目标：改变产品行为、修改其他角色 skill、改变 Full/Bugfix lite 的门禁组合，或为不存在的实施阶段补造记录。
