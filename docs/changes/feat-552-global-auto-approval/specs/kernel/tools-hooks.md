# Tools and Hooks — feat-552 delta

目标：`docs/specs/kernel/tools-hooks.md`。依据 design D3/D5/D6。

## ADDED Requirements

### Requirement: 工具未执行结果携带可区分的审批来源

#### Scenario: 有效自动拒绝
- **WHEN** Auto 明确拒绝动作
- **THEN** SDK 工具结果保留既有 denied 终态，并携带 classifier_block 来源和可解释原因。

#### Scenario: 用户拒绝与服务故障
- **WHEN** 原因分别为用户否决、必须人工、模型不可用、解析失败或上下文不足
- **THEN** 消费者及主模型可以区分各原因，不能统一归因为用户未授权。

### Requirement: 审批 transcript 不把执行成功当成授权背书

#### Scenario: 读取既往动作结果
- **WHEN** 审批读取历史 tool outcome
- **THEN** 能区分执行、自动拒绝、人工拒绝和无结论；执行成功不等于以后同类动作安全，后台启动成功不代表完成。

既有 permission_decision 用户决定标识维度保持独立；本单元不把自动决定伪装成人工批准。
