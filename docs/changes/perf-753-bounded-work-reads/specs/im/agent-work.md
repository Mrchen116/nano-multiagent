# Delta · Work 分页

## ADDED Requirements

### Requirement: 大量执行可逐步检查

#### Scenario: 逐页浏览历史关联执行
- **WHEN** 用户在支持分页的客户端打开历史很多的 Work
- **THEN** 主执行和关联执行可分别逐页检查；从已知的委派或执行入口可以直接进入相应的旧执行。

#### Scenario: 正在回看时出现新事实
- **WHEN** 用户停在已加载的历史页，Agent 产生新的工作事实
- **THEN** 可以继续看到实时进展，旧页和选择位置保持可用。
