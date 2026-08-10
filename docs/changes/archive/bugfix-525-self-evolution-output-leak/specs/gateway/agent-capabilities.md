# Gateway Agent Capabilities Specification (delta for bugfix-525)

## ADDED Requirements

### Requirement: self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和

Gateway 对 self-evolution review 成功产生的 `skill_created` 业务事件保持 session 级消费，不依赖已经结束的前台 run context。事件无论在前台 terminal 前后到达或经可恢复 stream 重连重放，都按现有 mode-aware config-sync 规则收敛，不重复改变配置。

#### Scenario: fast review 与 slow review 使用同一调和结果

- **GIVEN** Agent 的 self-evolution review 成功创建 agent-scope 或 global-scope Skill
- **WHEN** 创建事件发生在前台回答 terminal 之前或之后
- **THEN** default-discovery Agent 保持 default 并自然发现新 Skill
- **AND** explicit-allowlist Agent 保持 explicit 并按现有规则加入新 name，包括原 allowlist 为空的情形

#### Scenario: 后续前台轮次与 stream 重连不重复调和

- **GIVEN** 同一 session 的持久后台事件消费已建立，随后又完成前台轮次或发生可恢复 stream 重连
- **WHEN** self-evolution 创建事件被实时接收或重放
- **THEN** 同一创建结果不会被前台与后台两条路径重复处理
- **AND** 新 Skill 在相关 Agent 的后续 session 中保持可用
