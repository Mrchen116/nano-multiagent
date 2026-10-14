# Workflow Delta

## ADDED Requirements

### Requirement: 本仓 Workflow 使用简短运行引用与模型结果

#### Scenario: 新运行查询、控制与恢复
- **WHEN** Agent 启动新的本仓 Workflow 并按返回标识查询、控制或恢复
- **THEN** 使用持久稳定的短运行标识，权限、结果、重放和预算语义保持不变。
- **AND** 历史运行的原 UUID 仍可用于定位，不改 DSH 内置 schedule/subagent ID。

#### Scenario: 读取模型可见运行信息
- **WHEN** Workflow 工具返回运行详情或控制结果
- **THEN** 不向模型重复暴露父 session、input、budget、重放 hash 和子执行 attempt 的内部标识。
- **AND** 保留运行状态、结果、诊断和耗用信息，内部持久记录不因模型投影而丢失。
