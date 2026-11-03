# Agent Capabilities delta

## ADDED

### Requirement: 携程问道 Skill 随安装版本仅向 PA 默认提供

#### Scenario: 默认配置的 PA 使用旅行查询指导
- **WHEN** PA 使用默认 Skill 发现配置
- **THEN** 可发现并按需加载随包携程问道 Skill，无需另行安装，能力配置默认标记为开启
- **AND** 显式 Skill 选择及实际工具权限继续生效

#### Scenario: 其他 Agent 不默认启用
- **WHEN** Agent 没有 PA 身份，包括其他 Global Agent
- **THEN** 不默认装配本次随包携程 Skill，用户已有自建 Skill 配置保持

#### Scenario: 沿用原版凭证配置
- **WHEN** 用户按携程问道 Skill 发起查询
- **THEN** 凭证配置和缺少凭证时的提示遵循随包原版说明，不提供共享的内置凭证或新增授权界面
