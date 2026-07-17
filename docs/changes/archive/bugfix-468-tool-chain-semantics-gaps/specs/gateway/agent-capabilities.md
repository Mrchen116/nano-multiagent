# Delta: gateway - Agent Capabilities (bugfix-468)

> 对齐: bugfix-468
> 上级: [gateway (personal_assistant) Specification](../../../../../specs/gateway/spec.md)

## MODIFIED

### Requirement: agent 的显式工具名单在会话执行层强制

agent 配置了显式 `tool_allowlist`(含空)时,其所有会话(直聊/群聊/heartbeat/cron)在执行层只放行
名单内工具:名单外工具调用(包括模型未按声明自由发挥的调用)被拒且不产生副作用,用户可在会话中
看到工具不可用的明确反馈。空名单的 agent 会话拒绝一切工具调用。

#### Scenario: 空名单 agent 会话拒绝工具调用
- **GIVEN** agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与其会话,模型尝试调用工具
- **THEN** 工具不执行,用户在会话中看到明确的工具不可用反馈

#### Scenario: 名单内工具正常工作
- **GIVEN** agent 的 `tool_allowlist` 含 read
- **WHEN** 模型调用 read
- **THEN** read 正常执行,与既有行为一致
