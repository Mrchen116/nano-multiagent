# Delta: 全局 Agent 简短续问的回复范围

Canonical target: `docs/specs/gateway/global-agent.md`

## ADDED

### Requirement: 全局 Agent 按当前问题交付简短续问

#### Scenario: 已有上下文足以回答
- **WHEN** 用户只要求已有上下文足以回答的简短续问
- **THEN** 系统指导 Agent 直接交付答案并结束当前轮，不追加用户未请求的排障、验证请求或后续工作。
- **AND** 先前助手计划、假设与压缩检查点的 next step 作为背景，不自动成为新的用户指令或已证实事实。

#### Scenario: 明确继续验证
- **WHEN** 用户要求继续开发或验证，或有具体信息缺口阻碍正确回答
- **THEN** Agent 可以继续必要的调查和执行，保留已有的进度沟通、权限与交付要求。
