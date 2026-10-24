# Reviewer model compatibility delta

## ADDED Requirements

### Requirement: 审核请求 SHALL 使用原审核模型声明的推理能力

#### Scenario: 原模型不支持 low
- **WHEN** 所选审核模型声明可调推理能力
- **THEN** 支持 low 时使用 low，否则使用该模型声明的默认档位或首个支持档位；未声明可调能力时不强设 low。
- **AND** 保留同一审核 provider/model、完整适用证据、判定规则及失败分流，不通过换模型或删证据放行。
