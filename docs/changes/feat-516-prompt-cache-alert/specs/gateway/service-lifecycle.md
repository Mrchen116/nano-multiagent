# gateway (personal_assistant) - Service Lifecycle Specification (delta for feat-516)

## ADDED Requirements

### Requirement: Gateway 为高成本低 prompt 缓存命中模型调用记录可排查告警

Gateway 对每次模型调用独立判断；仅在 provider 明确报告缓存命中数据、该次总输入 token 超过 30,000 且缓存命中率低于 80% 时，在既有 `gateway.log` 记录 warning。该规则固定生效，无需新增 Gateway 配置；warning 只含模型、agent_id、session_id、输入 token、缓存命中 token 与命中率，不含 prompt 正文或用户内容。

#### Scenario: 长输入调用缓存命中低
- **GIVEN** Gateway 为一个 Agent 调用模型，provider 明确返回该次总输入 token 与缓存命中 token
- **WHEN** 总输入 token 超过 30,000 且缓存命中率低于 80%
- **THEN** 运维者在 `gateway.log` 看到一条带模型、agent_id、session_id、输入 token、缓存命中 token 与命中率的 warning
- **AND** 运维者可用 agent_id 和 session_id 定位对应 Agent workspace 的 session JSONL，warning 不包含 prompt 或用户内容

#### Scenario: 正常、边界或数据缺失的调用不误报
- **GIVEN** Gateway 调用模型后获得 usage，或 provider 未返回缓存命中数据
- **WHEN** 总输入 token 不超过 30,000、缓存命中率不低于 80%，或缓存命中数据缺失
- **THEN** Gateway 不为该次调用输出此类低缓存命中 warning
