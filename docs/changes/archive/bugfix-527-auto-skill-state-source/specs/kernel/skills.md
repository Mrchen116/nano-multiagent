# kernel skills Specification (delta for bugfix-527)

## MODIFIED Requirements

### Requirement: Skill 生命周期状态影响可见集合与自动优化

Skill 使用统计中的生命周期状态影响候选集合；创建动作确定 Skill 来源，读取动作不得把当前会话的创建来源误套到既有 Skill；自动创建的 Skill 在使用越线后可触发 per-skill batch review。

#### Scenario: stale skill 仍可发现和读取
- **GIVEN** skill A 的 usage state 为 stale
- **WHEN** 内核生成 `<available_skills>` 或处理 `/skill:` 候选
- **THEN** skill A 仍在候选中，并可通过 `skill_view(name="A")` 读取；读取成功后恢复为 active

#### Scenario: archived skill 退出日常候选
- **GIVEN** skill A 的 usage state 为 archived，且目录已移动到 `.archive/`
- **WHEN** 内核生成 `<available_skills>` 或处理 `/skill:` 候选
- **THEN** skill A 默认不出现在候选中，`skill_view(name="A")` 按找不到处理

#### Scenario: 自动 Skill Review 创建记录自动来源
- **GIVEN** 消费者启用了 Skill 自动 Review
- **WHEN** 后台 Review 通过 `skill_manage(create)` 成功创建 Skill
- **THEN** 新 Skill 的使用记录来源为自动创建 `F3`
- **AND** 仅 memory Review、普通 fork 或普通用户创建不虚构该自动来源

#### Scenario: 查看无记录的既有 Skill 不推断为自动创建
- **GIVEN** 一个既有手工或遗留 Skill 尚无使用记录
- **WHEN** 自动 Skill Review 通过 `skill_view` 成功读取它
- **THEN** 首次使用记录沿用非自动来源 `F1`，不因当前 Review 可创建自动 Skill 而记为 `F3`

#### Scenario: 查看已有自动来源的 Skill 保留来源
- **GIVEN** Skill A 的使用记录来源已经是 `F3` 或 `F4`
- **WHEN** 任意会话通过 `skill_view` 成功读取 Skill A
- **THEN** 读取只更新使用统计，不覆盖已有来源

#### Scenario: 自动 skill 使用计数越线后触发 batch
- **GIVEN** 自动创建的 skill A 在一次成功 `skill_view` 后达到自动优化阈值
- **WHEN** 该 `skill_view` 调用完成
- **THEN** 内核 enqueue skill A 的 per-skill batch review，不等待周期性 curator 扫描

#### Scenario: 手工 skill 越线不自动 batch
- **GIVEN** skill A 来源为用户创建、历史会话蒸馏、manual 或 unknown
- **WHEN** 一次成功 `skill_view` 让它达到同一使用阈值
- **THEN** 内核不 enqueue 自动 batch review
